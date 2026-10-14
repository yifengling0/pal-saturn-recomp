#pragma once
#include <cstdint>
#include <limits>

// Candidate policy only. No guest memory, SDL, clock, RNG, mover or input writes.
// The installer must pin the complete original functions and supply identities
// at the documented original instruction boundaries. Unknown input fails closed.
namespace pal_field_release {
inline constexpr uint32_t FieldReturn = 0x06026E58u;
inline constexpr uint32_t DeltaX = 0x060768E8u, DeltaY = 0x060768EAu;
enum class WriteSite : uint32_t {
    Unknown = 0, Scene = 0x06026FACu, Resource = 0x060323B8u,
    Script = 0x0602C384u
};
enum class Origin : uint8_t { Unknown, Protected, Scene, Resource, FieldReturn };

struct Writer {
    WriteSite site = WriteSite::Unknown;
    uint32_t return_pc = 0; // Original caller saved at function entry, NOT last leaf PR.
    uint16_t scene = 0;    // Scene writer: target 060768E0; resource: current 060768EE.
    bool field_scope = false;
    bool protected_scope = true; // UI, battle, boot, genuine script wait, host block.
    bool scene_continuation = false; // A verified field-to-field transition token.
};
struct Snapshot {
    uint64_t revision = 0;
    uint16_t scene = 0;
    Origin origin = Origin::Unknown;
    bool resumable = false;
};
struct Decision {
    uint32_t return_pc = 0;
    uint32_t dx_ptr = 0, dy_ptr = 0, action_ptr = 0, field_frame = 0;
    uint16_t action = 0, scene = 0, scene_change = 0;
    uint16_t pressed_buttons = 0; // Complete positive-polarity pad snapshot.
    uint16_t selected_direction = 0; // One cardinal bit, selected by existing policy.
    uint8_t gate = 0;
    bool field_scope = false, protected_scope = true;
    bool input_current = false; // FIELD1: current(Read), plus continuity identity.
};
inline constexpr bool movement_action(uint16_t a) {
    return a == 0 || (a >= 3 && a <= 6);
}
inline constexpr bool cardinal(uint16_t d) {
    return d == 0x1000 || d == 0x2000 || d == 0x4000 || d == 0x8000;
}

class GateLedger {
    uint64_t revision_ = 1;
    uint32_t resource_depth_ = 0;
    uint16_t scene_ = 0;
    Origin origin_ = Origin::Unknown;
    bool resumable_ = false;
    void changed() { ++revision_; if (!revision_) ++revision_; }
    void protect() { origin_ = Origin::Protected; resumable_ = false; }
public:
    // These are balanced function-entry/exit observations, not extra guest calls.
    void resource_enter() {
        changed();
        if (resource_depth_ == std::numeric_limits<uint32_t>::max()) protect();
        else ++resource_depth_;
    }
    void resource_leave() {
        changed();
        if (resource_depth_) --resource_depth_;
        else protect(); // Broken instrumentation must not grant an exemption.
    }

    // Observe immediately BEFORE an unchanged original FF store. previous_gate
    // must be read before that store: a protected/unknown FF cannot be upgraded
    // by a later resource (or scene) FF write. No host/guest poll in this hook.
    void write_ff(const Writer& w, uint8_t previous_gate) {
        changed();
        const bool old_allowed = resumable_ &&
            (origin_ == Origin::Scene || origin_ == Origin::Resource || origin_ == Origin::FieldReturn);
        const bool identified = w.field_scope && !w.protected_scope &&
            ((w.site == WriteSite::Resource && w.return_pc == 0x060327D4u &&
              resource_depth_ != 0) ||
             (w.site == WriteSite::Scene && w.return_pc == 0x06026DAEu &&
              w.scene_continuation));
        const bool same_resource_scene = w.site != WriteSite::Resource ||
            previous_gate != 0xFF || scene_ == w.scene;
        if (!identified || (previous_gate == 0xFF && !old_allowed) ||
            !same_resource_scene) {
            protect();
            return;
        }
        scene_ = w.scene;
        origin_ = w.site == WriteSite::Scene ? Origin::Scene : Origin::Resource;
        resumable_ = true;
    }

    // Only after the ORIGINAL neutral-clear store (06022D1A / 06022EEA).
    // This does not fabricate neutral or clear the original guest byte.
    void neutral_cleared() {
        changed(); origin_ = Origin::Unknown; resumable_ = false;
    }
    // All actual hard boundaries invalidate frozen decisions, even if no FF
    // is currently present. A later observed 0->FF field resource may qualify.
    void hard_boundary() { changed(); protect(); }
    // Exact natural field re-entry after the live host reconciled a completed
    // guest boundary. This retires the guest release latch for CURRENT holds;
    // permits_held_direction still excludes UI buttons, released taps and debt.
    void field_returned(uint16_t scene) {
        changed(); scene_ = scene; origin_ = Origin::FieldReturn; resumable_ = true;
    }
    Snapshot freeze() const {
        return {revision_, scene_, origin_, resumable_ && resource_depth_ == 0};
    }
    bool permits_held_direction(const Snapshot& s, const Decision& d) const {
        if (s.revision != revision_ || !s.resumable || !resumable_ ||
            resource_depth_ || s.scene != scene_ || s.origin != origin_) return false;
        if (d.gate != 0xFF || d.return_pc != FieldReturn ||
            d.dx_ptr != DeltaX || d.dy_ptr != DeltaY ||
            !d.field_frame || d.action_ptr != d.field_frame ||
            !d.field_scope || d.protected_scope || !d.input_current ||
            d.scene != scene_ || d.scene_change || !movement_action(d.action)) return false;
        // Never turn a held confirmation/cancel/menu/shortcut into movement.
        // In particular, action 0 alone is not proof of a direction-only input.
        const uint16_t held = d.pressed_buttons & 0xF000;
        if (d.pressed_buttons & 0x0FFF) return false;
        if ((held & 0xC000) == 0xC000 || (held & 0x3000) == 0x3000) return false;
        return cardinal(d.selected_direction) && (held & d.selected_direction);
    }
};
} // namespace pal_field_release
