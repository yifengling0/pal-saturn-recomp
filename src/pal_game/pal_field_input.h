#pragma once
#include <cstdint>
#include "pal_field_input_api.h"
#include <saturn/sh2.h>

uint64_t sat_vblanks();

// PAL field-only policy at the existing input decision slot. This helper never
// calls the guest mover, advances the machine, changes waits, or writes position.
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
inline void clear() {
    if (!owns_input()) return;
    invalidate_read();
    state.field = false;
    state.scene = ld16(Scene);
    state.scene_known = true;
    pal_field_host::context(false, true);
}
inline void resume_field() {
    if (!owns_input() || state.script_depth || state.ui_depth) return;
    const uint16_t scene = ld16(Scene);
    if (!state.scene_known || scene != state.scene) clear();
    state.scene = scene;
    state.scene_known = true;
    state.field = ld16(SceneChange) == 0;
    pal_field_host::context(state.field, false);
}
inline void enter() {
    if (!owns_input()) return;
    state.script_depth = state.ui_depth = 0;
    clear();
    resume_field();
}

// Hook immediately BEFORE the original 06026E54 converter call. Only the host
// implementation may service SDL, using its input-only safe-thread entry.
inline void begin() {
    if (!owns_input()) return;
    invalidate_read();
    if (state.script_depth || state.ui_depth || ld16(SceneChange)) {
        clear();
        return;
    }
    resume_field();
    state.read = pal_field_host::begin();
    state.read_state = ReadState::Ready;
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
    if (!owns_input()) return;
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
        // A pending tap is retained by the host, but no movement is accepted
        // and the guest-owned release acknowledgement byte remains untouched.
        suppress(c, true);
        return;
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

// Hook at 06026E74, after the ONE original f06033654 call. Observation only.
inline void outcome() {
    if (!owns_input() || !state.outcome.accepted || state.outcome.observed) return;
    auto& result = state.outcome;
    result.outcome_vblank = sat_vblanks();
    result.after_x = ld16(PlayerX);
    result.after_y = ld16(PlayerY);
    result.displaced = result.before_x != result.after_x || result.before_y != result.after_y;
    result.observed = true;
}

inline void script_before() {
    if (!owns_input()) return;
    if (!state.script_depth++) {
        invalidate_read();
        state.script_waited = false;
        state.script_scene = ld16(Scene);
        // Ordinary NPC computation can cross a raster boundary and pump SDL.
        // Keep capturing until the guest actually enters a frame-sync wait.
    }
}
// Hook at the original f0605D68A frame-sync entry. Its seal/RNG/wait runs
// unchanged. A regular field-render sync outside a script is not a boundary.
inline void note_wait() {
    if (!owns_input() || !state.script_depth || state.script_waited) return;
    state.script_waited = true;
    clear();
}
inline void script_after() {
    if (!owns_input() || !state.script_depth) return;
    if (--state.script_depth) return;
    if (state.script_waited || ld16(Scene) != state.script_scene ||
        ld16(SceneChange)) clear();
    state.script_waited = false;
    resume_field();
}
inline void ui_before() {
    if (!owns_input()) return;
    ++state.ui_depth;
    clear();
}
inline void ui_after() {
    if (!owns_input() || !state.ui_depth) return;
    if (--state.ui_depth) return;
    // Also discard contacts that were first pressed inside the UI. A clear
    // only on entry would let a new UI-held direction escape on return.
    clear();
    resume_field();
}
} // namespace pal_field_input
