#pragma once
#include "pal_release_gate.h"
#include "pal_field_input_api.h"
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <saturn/sh2.h>

// Read-only SH2 adapter. All mutation below is private native policy state.
// There are deliberately no st8/st16/st32, host event pumps or guest calls.
namespace pal_release_runtime {
inline constexpr uint32_t Gate=0x06076A09u, Scene=0x060768EEu;
inline constexpr uint32_t NextScene=0x060768E0u, SceneChange=0x060768DCu;
inline constexpr uint32_t Pad=0x0607682Au;
// runtime/src/host/host.h defines all 13 Saturn buttons from bit3 through bit15.
// Low bits0..2 are unused, not confirmation/cancel/shortcut controls.
inline constexpr uint16_t ButtonMask=0xFFF8u;
inline bool enabled() {
    static const bool value=[] { const char* v=std::getenv("PAL_FIELD_CONTINUITY");
        return !v || std::strcmp(v,"0") != 0; }();
    // available() owns the exact FIELD option and live-source contract. It is
    // dynamic: headless/scripted/foreign-thread paths must never inherit this
    // exemption, while scene suspension alone does not make it unavailable.
    return value && pal_field_host::available();
}
struct State {
    pal_field_release::GateLedger gate;
    pal_field_release::Snapshot frozen{};
    uint32_t field_frame=0;
    unsigned resource_depth=0, scene_depth=0, script_depth=0, ui_depth=0;
    unsigned fade_depth=0, reveal_depth=0;
    uint16_t converter_buttons=0, scene_buttons=0, target_scene=0, fade_buttons=0;
    bool in_field=false, seen_slot=false, captured=false, converter_seen=false;
    bool script_waited=false, scene_pending=false, scene_token=false;
    bool loader_complete=false, carry_required=false;
    bool field_return_pending=false, returned_debt=false;
    bool script_hard=false, fade_started=false, fade_waited=false, fade_authorized=false;
    bool scene_reveal_pending=false, reveal_started=false, reveal_authorized=false;
    bool reveal_requires_identity=false;
    bool displacement_qualified=false, displacement_checked=false, displacement_deferred=false;
    uint16_t displacement_direction=0, displacement_buttons=0;
    bool displacement_deadline_active=false;
    uint64_t displacement_not_before=0, displacement_last_vblank=0;
};
inline State state;
inline bool resource_active() { return state.resource_depth != 0; }
inline bool protected_scope() {
    return !state.in_field || state.ui_depth || state.script_waited || state.script_hard ||
        (state.scene_depth && !state.scene_token);
}
inline void invalidate_read() {
    state.captured=state.converter_seen=state.displacement_qualified=false;
    state.displacement_checked=state.displacement_deferred=false;
    state.displacement_direction=state.displacement_buttons=0;
}
inline void reset_displacement_admission() {
    state.displacement_deadline_active=false;
    state.displacement_not_before=state.displacement_last_vblank=0;
}
inline void hard_boundary() {
    // Sticky for the complete outer script: a later scene opcode cannot undo it.
    if (state.script_depth) state.script_hard=true;
    state.gate.hard_boundary(); invalidate_read(); reset_displacement_admission();
    state.in_field=state.seen_slot=false;
    state.scene_pending=state.scene_token=state.loader_complete=false;
    state.carry_required=false; state.scene_buttons=0;
    state.field_return_pending=state.returned_debt=false;
    state.scene_reveal_pending=false;
}
inline void field_enter() {
    static bool announced=false;
    if (!announced) {
        announced=true;
        std::fprintf(stderr,"PAL field continuity v1: enabled=%d\n",int(enabled()));
    }
    state=State{}; state.in_field=true; state.gate.hard_boundary();
}
inline bool scene_soft() {
    return enabled() && state.scene_pending && state.scene_token && !protected_scope();
}
inline bool can_scene_suspend() {
    if (!enabled() || protected_scope() ||
        (state.script_depth && (state.fade_started || state.reveal_started))) return false;
    if (state.scene_pending) return state.scene_token;
    return state.seen_slot && ld16(SceneChange) != 0;
}
inline bool scene_transition_start() {
    if (!can_scene_suspend()) return false;
    if (state.scene_pending) return scene_soft();
    state.scene_reveal_pending=false; reset_displacement_admission();
    state.scene_pending=state.scene_token=true; state.loader_complete=false;
    state.target_scene=ld16(NextScene);
    const uint16_t buttons=uint16_t(~ld16(Pad)) & ButtonMask;
    const uint16_t held=(buttons & 0x0FFF) ? 0 : buttons & 0xF000;
    // FIELD0 has no host source ledger. At least retain the pre-fade complete
    // snapshot and reject a different/no-longer-held direction at this boundary.
    // FIELD1 additionally validates the source/press identity in scene_held.
    state.scene_buttons=state.fade_started ?
        ((buttons==state.fade_buttons) ? state.fade_buttons : 0) : held;
    state.carry_required=true; invalidate_read();
    return true;
}
// Call only AFTER the helper has reconciled/returned the host scene context.
// Loader exit deliberately retains scene_soft for resume_field's scene mismatch.
inline bool scene_transition_end() {
    if (!scene_soft() || !state.loader_complete || state.scene_depth ||
        ld16(SceneChange) || ld16(Scene)!=state.target_scene) return false;
    state.scene_pending=state.scene_token=state.loader_complete=false;
    state.scene_reveal_pending=true; // One ticket for the next natural E84 reveal.
    return true; // Keep carry_required until original neutral or a hard boundary.
}
inline void ui_before() { ++state.ui_depth; hard_boundary(); }
inline void ui_after() {
    if (state.ui_depth) --state.ui_depth;
    hard_boundary(); // Do not import a direction first held in the UI.
}
inline void script_before() {
    if (state.script_depth && (state.fade_started || state.reveal_started)) hard_boundary();
    if (!state.script_depth++) {
        state.script_waited=state.script_hard=false;
        state.fade_started=state.fade_waited=false; state.fade_buttons=0;
        state.reveal_started=false;
        // An unbalanced/foreign fade lifetime is never a scene witness.
        if (state.fade_depth || state.reveal_depth) hard_boundary();
    }
    invalidate_read();
}
// Scope the complete original opcode80 call at 0602B046, including its own
// SH2_POLL, with return_pc=0602B04A. This is earlier than f06023914 entry.
// The helper must
// invalidate its read and scene_suspend() immediately on true, before returning
// to the unchanged guest. This freezes only pre-fade held identities, discards
// pending taps and prevents input first pressed during the fade from escaping.
// Every call, including false, must be paired with fade_after().
inline bool fade_before(uint32_t return_pc) {
    if (++state.fade_depth != 1) { hard_boundary(); return false; }
    state.fade_authorized=enabled() && return_pc==0x0602B04Au &&
        state.script_depth==1 && !state.scene_depth && !state.reveal_depth &&
        !state.reveal_started && state.seen_slot &&
        !protected_scope();
    if (!state.fade_authorized) {
        if (state.fade_started || state.reveal_started) hard_boundary();
        return false;
    }
    if (!state.fade_started) {
        const uint16_t buttons=uint16_t(~ld16(Pad)) & ButtonMask;
        state.fade_buttons=(buttons & 0x0FFF) ? 0 : buttons & 0xF000;
    }
    state.fade_started=true;
    invalidate_read();
    return true;
}
inline void fade_after() {
    if (!state.fade_depth) { hard_boundary(); return; }
    if (!--state.fade_depth) state.fade_authorized=false;
}
// One-shot completion of the already-authorized scene load. The field helper
// wraps the entire original E84 call (return E88), including its SH2_POLL, and
// suspends held-only input before entering the unchanged palette reveal.
inline bool reveal_before(uint32_t return_pc) {
    if (++state.reveal_depth != 1) { hard_boundary(); return false; }
    const bool ticket=state.scene_reveal_pending;
    state.scene_reveal_pending=false; // Consume even a rejected/foreign attempt.
    state.reveal_authorized=ticket && enabled() && return_pc==0x06026E88u &&
        state.script_depth==1 && !state.scene_depth && !state.fade_depth &&
        !state.fade_started && state.seen_slot && !protected_scope() &&
        !ld16(SceneChange) && ld16(Scene)==state.target_scene;
    if (!state.reveal_authorized) {
        if (ticket || state.reveal_started) hard_boundary();
        return false;
    }
    state.reveal_started=true;
    state.reveal_requires_identity=state.carry_required;
    invalidate_read();
    return true;
}
// True: host suspension must intersect existing scene_held identities, never
// promote a newly armed contact first pressed after the scene resumed.
inline bool reveal_requires_scene_held() { return state.reveal_requires_identity; }
inline void reveal_after() {
    if (!state.reveal_depth) { hard_boundary(); return; }
    if (!--state.reveal_depth) state.reveal_authorized=false;
}
// true means a genuine script wait: field helper must perform its hard clear.
// Resource/render sync remains unchanged. Only the exact opcode80 fade scope
// may defer the decision; a nested script/fade cannot borrow its permission.
inline bool note_wait() {
    if (!state.script_depth || resource_active() || state.script_waited) return false;
    if (state.fade_depth==1 && state.fade_authorized && state.script_depth==1 &&
        !protected_scope()) {
        state.fade_waited=true;
        return false;
    }
    if (state.reveal_depth==1 && state.reveal_authorized && state.script_depth==1 &&
        !state.fade_depth && !protected_scope()) return false;
    state.script_waited=true; hard_boundary(); return true;
}
// true is a required host hard clear, including a fade that returned without a
// real scene request. The field helper must consume this result BEFORE its
// own depth early returns. Runtime-only nested scopes retain script_hard until
// the enclosing helper scope returns, so an inner hard cannot be re-upgraded.
inline bool script_after() {
    if (!state.script_depth) { hard_boundary(); return true; }
    if (--state.script_depth) return state.script_hard || state.script_waited;
    bool hard=state.script_hard || state.script_waited;
    if (state.reveal_started && (state.reveal_depth || ld16(SceneChange) ||
        ld16(Scene)!=state.target_scene)) hard=true;
    if (state.fade_started) {
        if (state.fade_depth || !ld16(SceneChange) || state.scene_depth || hard ||
            !scene_transition_start()) hard=true;
    } else if (!hard && !state.scene_depth && ld16(SceneChange)) {
        scene_transition_start();
    }
    state.script_waited=state.script_hard=false;
    state.fade_started=state.fade_waited=state.reveal_started=false;
    if (hard) hard_boundary();
    return hard;
}
struct ScriptScope {
    ScriptScope() { script_before(); }
    ~ScriptScope() { script_after(); }
    ScriptScope(const ScriptScope&)=delete;
    ScriptScope& operator=(const ScriptScope&)=delete;
};
struct ResourceScope {
    uint32_t caller;
    explicit ResourceScope(uint32_t return_pc):caller(return_pc) {
        ++state.resource_depth; state.gate.resource_enter();
    }
    ~ResourceScope() {
        if (state.resource_depth) --state.resource_depth;
        else hard_boundary();
        state.gate.resource_leave();
    }
    ResourceScope(const ResourceScope&)=delete;
    ResourceScope& operator=(const ResourceScope&)=delete;
};
struct SceneScope {
    uint32_t caller;
    explicit SceneScope(uint32_t return_pc):caller(return_pc) {
        if (!state.scene_depth) {
            if (caller!=0x06026DAEu || !scene_transition_start()) hard_boundary();
        } else hard_boundary(); // The current original loader loops; recursive loading is unknown.
        ++state.scene_depth;
    }
    ~SceneScope() {
        if (!state.scene_depth) { hard_boundary(); return; }
        --state.scene_depth;
        if (!state.scene_depth && state.scene_token) {
            if (protected_scope() || ld16(SceneChange) || ld16(Scene)!=state.target_scene)
                hard_boundary();
            else state.loader_complete=true;
        }
    }
    SceneScope(const SceneScope&)=delete;
    SceneScope& operator=(const SceneScope&)=delete;
};
inline void writer_pre(const SH2Context& c, uint32_t pc) {
    using namespace pal_field_release;
    Writer w;
    w.site=static_cast<WriteSite>(pc);
    w.scene=ld16(Scene);
    w.field_scope=enabled() && state.in_field;
    w.protected_scope=protected_scope();
    if (w.site==WriteSite::Resource) w.return_pc=ld32(c.r[14]+12);
    else if (w.site==WriteSite::Scene) {
        w.return_pc=ld32(c.r[14]+4); w.scene=ld16(NextScene);
        w.scene_continuation=scene_soft();
        // Scene scripts can redirect the same original loader loop to a new target.
        if (w.scene_continuation) state.target_scene=w.scene;
    }
    state.gate.write_ff(w,ld8(Gate));
}
inline void neutral_post() {
    // Do not treat a caller mistake as evidence of a real guest neutral clear.
    if (ld8(Gate)!=0) { hard_boundary(); return; }
    state.gate.neutral_cleared(); reset_displacement_admission();
    state.carry_required=false; state.scene_buttons=0;
    state.returned_debt=false;
}
inline void field_returned() { state.field_return_pending=true; }
inline void capture_field_frame(uint32_t frame) {
    invalidate_read(); state.field_frame=frame;
    if (state.ui_depth || state.script_depth || state.script_waited ||
        state.scene_depth || ld16(SceneChange)) return;
    // Re-entry to the exact natural field decision is the mode witness in FIELD0.
    state.in_field=true; state.seen_slot=true;
    if (state.field_return_pending && enabled() && !resource_active()) {
        state.field_return_pending=false;
        state.gate.field_returned(ld16(Scene));
        state.returned_debt=ld8(Gate)==0xFF;
        state.carry_required=false; state.scene_buttons=0;
        reset_displacement_admission();
    }
    state.frozen=state.gate.freeze(); state.captured=true;
}
inline uint16_t direction(int dx,int dy) {
    if(dx==1 && dy==-1) return 0x1000;
    if(dx==-1 && dy==1) return 0x2000;
    if(dx==-1 && dy==-1) return 0x4000;
    if(dx==1 && dy==1) return 0x8000;
    return 0;
}
inline pal_field_release::Decision decision(uint32_t return_pc,uint32_t dx_ptr,
        uint32_t dy_ptr,uint32_t action_ptr,uint16_t buttons,uint16_t selected,
        bool current) {
    return {return_pc,dx_ptr,dy_ptr,action_ptr,state.field_frame,
        uint16_t(ld16(action_ptr)),uint16_t(ld16(Scene)),uint16_t(ld16(SceneChange)),
        buttons,selected,uint8_t(ld8(Gate)),
        state.in_field,protected_scope(),current};
}
// Record only the permission actually established by the captured converter or
// validated FIELD1 apply path. The later E6E hook cannot manufacture a source.
inline bool record_displacement_permission(bool allowed, const pal_field_release::Decision& d) {
    state.displacement_qualified=allowed && (state.carry_required || state.returned_debt);
    if (state.displacement_qualified) {
        state.displacement_direction=d.selected_direction;
        state.displacement_buttons=d.pressed_buttons;
    }
    return allowed;
}
// At 06022FD8 before the unchanged FF branch. Return true -> original FF2 path.
inline bool permits(const SH2Context& c) {
    state.displacement_qualified=false;
    if (!state.captured) return false;
    const uint32_t return_pc=ld32(c.r[14]+24), action=ld32(c.r[14]+8);
    if (return_pc!=pal_field_release::FieldReturn ||
        ld32(c.r[14]+28)!=state.field_frame || action!=state.field_frame) return false;
    state.converter_buttons=uint16_t(~ld16(c.r[14]+22)) & ButtonMask; state.converter_seen=true;
    const uint16_t selected=direction(int16_t(ld16(c.r[14]+14)),int16_t(ld16(c.r[14]+16)));
    bool current=!state.carry_required ||
        ((state.converter_buttons & 0xF000)==state.scene_buttons && state.scene_buttons!=0);
    const auto d=decision(return_pc,ld32(c.r[14]),ld32(c.r[14]+4),action,
        state.converter_buttons,selected,current);
    return record_displacement_permission(enabled() &&
        state.gate.permits_held_direction(state.frozen,d),d);
}
// After original E58, before FIELD1 ack/writes. pressed_buttons must combine a
// complete current non-direction snapshot with read.held, NOT read.held alone.
// source_current is current(Read) plus held membership; final acknowledge(Read)
// remains mandatory after this method and before any guest writes.
inline bool permits_field(const SH2Context& c,uint16_t selected,
        uint16_t pressed_buttons,bool source_current,bool scene_held) {
    state.displacement_qualified=false;
    if (!enabled() || !state.captured || !state.converter_seen ||
        c.r[14]!=state.field_frame) return false;
    source_current=source_current && (!state.carry_required || scene_held);
    const auto d=decision(pal_field_release::FieldReturn,pal_field_release::DeltaX,
        pal_field_release::DeltaY,state.field_frame,pressed_buttons & ButtonMask,selected,source_current);
    return record_displacement_permission(state.gate.permits_held_direction(state.frozen,d),d);
}
// At L_06026E6E, after the ORIGINAL movement/neutral interval branch and before
// the ONE original E70 mover call. Native admission state only: the caller may
// zero dx/dy on true, but must preserve action, r0/r1, facing, timer and the call.
// FIELD1 has already acknowledged its read. Do not acknowledge or clear again.
inline bool should_defer_displacement(const SH2Context& c,uint64_t now) {
    if (!enabled() || !(state.carry_required || state.returned_debt) || !state.displacement_qualified ||
        !state.captured || !state.converter_seen || c.r[14]!=state.field_frame ||
        ld16(Scene)!=(state.carry_required ? state.target_scene : state.frozen.scene) ||
        ld16(SceneChange) || protected_scope()) return false;
    const uint16_t selected=direction(int16_t(ld16(pal_field_release::DeltaX)),
        int16_t(ld16(pal_field_release::DeltaY)));
    // Rejected/stale FIELD1 apply leaves zero deltas: it must neither move nor
    // reserve a deadline. Its selected host direction need not match raw pad.
    if (!selected || selected!=state.displacement_direction) return false;
    const auto d=decision(pal_field_release::FieldReturn,pal_field_release::DeltaX,
        pal_field_release::DeltaY,state.field_frame,state.displacement_buttons,selected,true);
    // Re-use the already-established source proof only in this no-POLL window;
    // fresh ledger revision and complete button/action gates are still checked.
    if (!state.gate.permits_held_direction(state.frozen,d)) return false;
    if (state.displacement_checked) return state.displacement_deferred;
    state.displacement_checked=true;
    const auto defer=[] {state.displacement_deferred=true;return true;};
    // E6C writes3 on every observed nonzero-direction path. Unknown modes do
    // not authorize faster stepping. No timer is written or phase redefined.
    const uint8_t interval=uint8_t(ld8(0x060FFC12u));
    if (interval!=3 || int8_t(ld8(0x060FFC13u))<0) return defer();
    if (state.displacement_deadline_active &&
        (now<=state.displacement_last_vblank || now<state.displacement_not_before)) return defer();
    const uint64_t max=std::numeric_limits<uint64_t>::max();
    if (now>max-interval) return defer(); // No representable safe future deadline.
    state.displacement_deadline_active=true;
    state.displacement_last_vblank=now;
    state.displacement_not_before=now+interval;
    state.displacement_deferred=false;
    return false;
}
} // namespace pal_release_runtime
