#pragma once
#include <cstdint>
#include "pal_field_input_api.h"
#include "pal_release_runtime.h"
#include <saturn/sh2.h>

uint64_t sat_vblanks();

// PAL field-only policy at the existing input decision slot. This helper never
// calls the guest mover, advances the machine, or writes position. The optional
// gentle cadence changes only the proved live-field render wait interval.
namespace pal_field_input {
inline constexpr uint32_t Scene = 0x060768EEu, SceneChange = 0x060768DCu;
inline constexpr uint32_t ReleaseGate = 0x06076A09u;
inline constexpr uint32_t DeltaX = 0x060768E8u, DeltaY = 0x060768EAu;
inline constexpr uint32_t Facing = 0x06076970u;
inline constexpr uint32_t PlayerX = 0x06076928u, PlayerY = 0x0607692Au;

enum class ReadState : uint8_t { Empty, Ready, Applied };
struct Outcome {
    pal_field_host::Read read{};
    uint64_t intent_vblank = 0, outcome_vblank = 0;
    uint16_t before_x = 0, before_y = 0, after_x = 0, after_y = 0;
    bool accepted = false, observed = false, displaced = false;
};
// Only live, successfully displaced continuous field holds use this cadence.
// Five repeat intervals total 18 VBlanks: 16.7% slower than the original 15.
// No sleep, host clock change, extra mover call or smaller collision-grid step.
struct WalkCadence {
    uint64_t source = 0, press = 0;
    uint16_t direction = 0;
    unsigned phase = 0;
    bool restoring = false;
    static bool enabled() {
        const char* value = std::getenv("PAL_FIELD_WALK_CADENCE");
        return !value || !std::strcmp(value, "gentle");
    }
    void reset() { source = press = direction = phase = 0; }
    unsigned next(const pal_field_host::Read& read, bool displaced) {
        if (!enabled() || !displaced || !read.active || read.blocked ||
            !read.direction || !(read.held & read.direction) || read.scene_held) {
            reset(); return 3;
        }
        if (read.pending || source != read.source || press != read.press_seq ||
            direction != read.direction) {
            source = read.source; press = read.press_seq;
            direction = read.direction; phase = 0;
            return 3; // Fresh press/turn always retains original first interval.
        }
        // Ceiling cumulative 18/5 produces 4,4,3,4,3 with <=1 VB jitter.
        const unsigned before = (phase * 18 + 4) / 5;
        const unsigned after = ((phase + 1) * 18 + 4) / 5;
        phase = (phase + 1) % 5;
        return after - before;
    }
};
struct State {
    pal_field_host::Read read{};
    ReadState read_state = ReadState::Empty;
    bool field = false, scene_known = false;
    uint16_t scene = 0;
    unsigned script_depth = 0, ui_depth = 0;
    bool script_waited = false;
    uint16_t script_scene = 0;
    uint64_t accepted = 0, blocked = 0, rejected = 0;
    Outcome outcome{};
    WalkCadence cadence;
};
inline State state;

// This is a session-level ownership test, intentionally true also in guest UI
// while the enabled live host owns this policy. Planners use it to suppress old
// apply/tick/align. Keep old wait/script/sync bookkeeping for frame-queue users.
inline bool owns_input() { return pal_field_host::available(); }
inline bool movement_action(uint16_t action) {
    return action == 0 || (action >= 3 && action <= 6);
}
inline bool single_direction(uint16_t direction) {
    return direction == 0x1000 || direction == 0x2000 ||
           direction == 0x4000 || direction == 0x8000;
}
inline void invalidate_read() {
    state.read = {};
    state.read_state = ReadState::Empty;
    state.outcome = {};
}
// Scope bookkeeping runs for FIELD0 and FIELD1. Only host capture and field
// replacement are conditional on owns_input(). No scope hook changes guest RAM.
inline void clear() {
    pal_release_runtime::hard_boundary();
    state.cadence.reset();
    invalidate_read();
    state.field = false;
    state.scene = ld16(Scene);
    state.scene_known = true;
    if (owns_input()) pal_field_host::context(false, true);
}
struct FadeScope {
    explicit FadeScope(uint32_t caller) {
        if (pal_release_runtime::fade_before(caller)) {
            invalidate_read();
            state.field = false;
            if (owns_input()) pal_field_host::scene_suspend();
        }
    }
    ~FadeScope() { pal_release_runtime::fade_after(); }
    FadeScope(const FadeScope&) = delete;
    FadeScope& operator=(const FadeScope&) = delete;
};
struct RevealScope {
    explicit RevealScope(uint32_t caller) {
        if (pal_release_runtime::reveal_before(caller)) {
            invalidate_read();
            state.field = false;
            if (owns_input()) pal_field_host::scene_suspend(
                pal_release_runtime::reveal_requires_scene_held());
        }
    }
    ~RevealScope() { pal_release_runtime::reveal_after(); }
    RevealScope(const RevealScope&) = delete;
    RevealScope& operator=(const RevealScope&) = delete;
};
inline void scene_clear() {
    if (!pal_release_runtime::scene_transition_start()) { clear(); return; }
    invalidate_read();
    state.field = false;
    state.scene = ld16(Scene);
    state.scene_known = true;
    if (owns_input()) pal_field_host::scene_suspend();
}
inline void resume_field() {
    if (state.script_depth || state.ui_depth) return;
    const uint16_t scene = ld16(Scene);
    if (!state.scene_known || scene != state.scene) {
        if (pal_release_runtime::scene_soft()) scene_clear();
        else clear();
    }
    state.scene = scene;
    state.scene_known = true;
    state.field = ld16(SceneChange) == 0;
    if (owns_input()) pal_field_host::context(state.field, false);
    // The host drains loading-time events while still suspended. Only after
    // that reconciliation may the guest transition token be retired.
    if (state.field) pal_release_runtime::scene_transition_end();
}
inline void enter() {
    pal_release_runtime::field_enter();
    state.script_depth = state.ui_depth = 0;
    state.script_waited = false;
    clear();
    // Initial field entry always loads a scene first. Do not arm capture or
    // infer scene continuity before the first natural field decision. The
    // disabled comparison retains the original immediate activation.
    if (!pal_release_runtime::enabled()) resume_field();
}

// Hook immediately BEFORE the original 06026E54 converter call. Only the host
// implementation may service SDL, using its input-only safe-thread entry.
inline void begin() {
    invalidate_read();
    if (state.script_depth || state.ui_depth) { clear(); return; }
    if (ld16(SceneChange)) { scene_clear(); return; }
    resume_field();
    if (!owns_input()) return;
    state.read = pal_field_host::begin();
    state.read_state = ReadState::Ready;
}

// After the original field interval branch, before its unchanged mover call.
// Deny only this displacement attempt; do not synthesize a pad release or
// change the action, chosen interval, timer, acknowledgement or guest registers.
inline void filter_scene_debt(const SH2Context& c) {
    if (pal_release_runtime::should_defer_displacement(c, sat_vblanks())) {
        st16(DeltaX, 0);
        st16(DeltaY, 0);
    }
}

inline void suppress(SH2Context& c, bool clear_action) {
    st16(DeltaX, 0);
    st16(DeltaY, 0);
    if (clear_action) st16(c.r[14], 0);
    c.r[0] = c.r[1] = 0;
}

// Hook AFTER the original 06026E58 exts.w instruction. The original converter
// retains nonmovement priority. The host-blocked exception discards the entire
// current input action so host-menu/focus events cannot leak into guest UI.
inline void apply(SH2Context& c) {
    if (!owns_input()) {
        if (!movement_action(ld16(c.r[14]))) clear();
        return;
    }
    if (state.read_state == ReadState::Applied) return;
    const bool has_read = state.read_state == ReadState::Ready;
    state.read_state = ReadState::Applied;
    const auto read = state.read;
    const uint16_t action = ld16(c.r[14]);

    if (has_read && read.blocked) {
        ++state.blocked;
        suppress(c, true);
        clear();
        state.read_state = ReadState::Applied;
        return;
    }
    // Original converter safe points can present/pump SDL after begin. Validate
    // the host context without consuming a direction before preserving a UI
    // action. Do not discard a newer epoch's pending input on stale rejection.
    if (has_read && !pal_field_host::current(read)) {
        ++state.rejected;
        suppress(c, true);
        return;
    }
    if (!movement_action(action)) {
        // Preserve all converter outputs, including its nonmovement action.
        clear();
        state.read_state = ReadState::Applied;
        return;
    }
    if (!has_read || !state.field || !read.active || state.script_depth ||
        state.ui_depth || !state.scene_known || ld16(Scene) != state.scene ||
        ld16(SceneChange)) {
        ++state.rejected;
        suppress(c, true);
        clear();
        state.read_state = ReadState::Applied;
        return;
    }
    if (ld8(ReleaseGate) == 0xFF) {
        // Only a proven scene/resource FF origin may admit a CURRENT held
        // direction. A released pending tap alone never qualifies. Preserve
        // all real non-direction buttons when consulting the source gate.
        const uint16_t buttons = uint16_t(read.held |
            (uint16_t(~ld16(pal_release_runtime::Pad)) & 0x0FF8u));
        const bool held_current = pal_field_host::current(read) &&
            read.direction && (read.held & read.direction);
        if (!pal_release_runtime::permits_field(c, read.direction, buttons,
                held_current, read.scene_held && !read.pending)) {
            suppress(c, true);
            return;
        }
    }
    const uint16_t direction = read.direction;
    if (direction && (!single_direction(direction) ||
        (!read.pending && !(read.held & direction)))) {
        ++state.rejected;
        suppress(c, true);
        return;
    }
    // Validation/acceptance is atomic in the host ledger. The converter may
    // have polled in between begin and apply; stale focus/epoch/press/held
    // snapshots must not be applied. A rejection never clears a NEWER tap.
    if (!pal_field_host::acknowledge(read)) {
        ++state.rejected;
        suppress(c, true);
        return;
    }
    if (!direction) {
        suppress(c, true);
        return;
    }

    int dx = 0, dy = 0;
    uint8_t facing = 0;
    uint16_t next_action = 0;
    switch (direction) {
    case 0x1000: dx = 1; dy = -1; facing = 2; next_action = 3; break;
    case 0x2000: dx = -1; dy = 1; facing = 0; next_action = 4; break;
    case 0x4000: dx = -1; dy = -1; facing = 1; next_action = 5; break;
    case 0x8000: dx = 1; dy = 1; facing = 3; next_action = 6; break;
    }
    state.outcome.read = read;
    state.outcome.intent_vblank = sat_vblanks();
    state.outcome.before_x = ld16(PlayerX);
    state.outcome.before_y = ld16(PlayerY);
    state.outcome.accepted = true;
    // The accepted attempt is already acknowledged above, before guest writes.
    // Collision may block the one original mover without leaving a tap owed.
    ++state.accepted;
    st16(DeltaX, static_cast<uint16_t>(dx));
    st16(DeltaY, static_cast<uint16_t>(dy));
    st8(Facing, facing);
    st16(c.r[14], next_action);
    c.r[0] = c.r[1] = 1;
}

// Hook at 06026E74, after the ONE original f06033654 call. Observe collision
// outcome before selecting the next continuous manual-field wait interval.
inline void outcome() {
    if (!owns_input() || !state.outcome.accepted || state.outcome.observed) return;
    auto& result = state.outcome;
    result.outcome_vblank = sat_vblanks();
    result.after_x = ld16(PlayerX);
    result.after_y = ld16(PlayerY);
    result.displaced = result.before_x != result.after_x || result.before_y != result.after_y;
    result.observed = true;
    // E74 is after the original collision/mover and before its field render
    // wait. Never touch scene debt, a scripted delta, neutral/blocked motion or
    // an unknown interval. Resource/scene release provenance remains unchanged.
    const bool ordinary = state.field && !state.script_depth && !state.ui_depth &&
        !ld16(SceneChange) && ld16(Scene) == state.scene &&
        !pal_release_runtime::state.carry_required && ld8(0x060FFC12u) == 3;
    const unsigned interval = state.cadence.next(result.read, ordinary && result.displaced);
    if (ordinary && interval == 4) {
        st8(0x060FFC12u, 4);
        state.cadence.restoring = true;
    }
}
// Paired immediately after E76's field render/wait. The longer NEXT field
// countdown is owned by the original sync; do not leak interval4 into scripts,
// menus, palette reveals or battles invoked later in this iteration.
inline void wait_after() {
    if (!state.cadence.restoring) return;
    state.cadence.restoring = false;
    if (ld8(0x060FFC12u) == 4) st8(0x060FFC12u, 3);
}

inline void script_before() {
    pal_release_runtime::script_before();
    if (!state.script_depth++) {
        invalidate_read();
        state.script_waited = false;
        state.script_scene = ld16(Scene);
        // Ordinary NPC computation can cross a raster boundary and pump SDL.
        // Keep capturing until the guest actually enters a frame-sync wait.
    }
}
// Hook at the original f0605D68A frame-sync entry. Its seal/RNG/wait runs
// unchanged. Resource/render sync is not a genuine script-wait boundary.
inline void note_wait() {
    const bool hard_wait = pal_release_runtime::note_wait();
    if (pal_release_runtime::enabled()) {
        if (!hard_wait) return;
    } else if (!owns_input() || !state.script_depth || state.script_waited) return;
    state.script_waited = true;
    clear();
}
inline void script_after() {
    // A tentative fade without a confirmed scene, or a revoked nested scope,
    // must flush the host even when this helper has no outer script depth.
    if (pal_release_runtime::script_after()) { state.script_waited = true; clear(); }
    if (!state.script_depth) return;
    if (--state.script_depth) return;
    if (state.script_waited) clear();
    else if (ld16(Scene) != state.script_scene || ld16(SceneChange)) scene_clear();
    state.script_waited = false;
    resume_field();
}
inline void ui_before() {
    pal_release_runtime::ui_before();
    ++state.ui_depth;
    clear();
}
inline void ui_after() {
    pal_release_runtime::ui_after();
    if (!state.ui_depth) return;
    if (--state.ui_depth) return;
    // Also discard contacts that were first pressed inside the UI. A clear
    // only on entry would let a new UI-held direction escape on return.
    clear();
    resume_field();
}
} // namespace pal_field_input
