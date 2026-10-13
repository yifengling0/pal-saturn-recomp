"""Pure, fail-closed mode-10 prompt edge planner, after PC keyboard translation.

The ordinary timer and its guest poll remain intact. Only the exact call from
message cleanup can substitute its local accept result using a fresh host edge.
"""
from pathlib import Path
import hashlib

VERSION = 'pal-prompt-confirm-v1'
WAIT_SHA256 = 'c0d356c074df40533ee46ef4b955d0cc0e453877bbb871d12c3ee6500dac38b7'

def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Prompt anchor missing or duplicated: ' + old[:90])
    return s.replace(old, new, 1)

def guest(text):
    marker = 'void f_060220D0(SH2Context& c) {\n'
    if text.count(marker) != 1: raise ValueError('Prompt wait function missing or duplicated')
    a = text.index(marker)
    z = text.find('\nvoid f_', a + len(marker))
    if z < 0: raise ValueError('Prompt wait end missing')
    f = text[a:z]
    if hashlib.sha256(f.encode()).hexdigest() != WAIT_SHA256:
        raise ValueError('Prompt original wait function identity mismatch')
    f = once(f, marker, marker + '    pal_prompt::Scope pal_prompt_wait(c.pr==0x0602315Eu && c.r[4]==180u && ld16(0x06076902u)==10u && ld16(0x060768FCu)!=0u);\n')
    anchor = '    c.r[1] = c.r[14];  // 0602213C mov r14,r1\n'
    f = once(f, anchor, '    if (pal_prompt_wait.enabled) st16(c.r[14]+4, pal_prompt_wait.accept() ? 1 : 0);\n' + anchor)
    out = text[:a] + f + text[z:]
    if '#include <saturn/pal_keyboard_profile.h>' not in out:
        out = '#include <saturn/pal_keyboard_profile.h>\n' + out
    return out

HOST_HELPERS = r'''
// Fresh physical confirmation edges belong only to the exact ROM message wait.
// SDL event timestamps are nanoseconds on SDL_GetTicksNS's monotonic clock:
// queued events from before entry cannot dismiss the just-opened message.
static uint64_t g_prompt_since = 0;
static void prompt_reconcile_releases() {
    // Releases may happen while another window owns the keyboard. Reconcile
    // only absence, never manufacture DOWN from a held/polled level.
    const bool* keys=SDL_GetKeyboardState(nullptr);
    for(auto it=pal_prompt::ledger.down.begin();it!=pal_prompt::ledger.down.end();) {
        const auto source=it->first; ++it;
        const auto domain=std::get<0>(source), id=std::get<1>(source), control=std::get<2>(source);
        bool released=false;
        if(domain==1 && control<SDL_SCANCODE_COUNT) released=!keys[control];
        if(domain==2) {
            released=true;
            for(auto& pad:g_pads) if(uint64_t(pad.id)==id)
                released=!SDL_GetGamepadButton(pad.pad,SDL_GamepadButton(control));
        }
        if(domain==4) {
            released=true;
            for(auto& pad:g_pads) if(uint64_t(pad.id)==id)
                released=SDL_GetGamepadAxis(pad.pad,SDL_GamepadAxis(control))<=pad.map.trigger;
        }
        if(domain==3) released=g_fingers.find(SDL_FingerID(control))==g_fingers.end();
        if(released) pal_prompt::ledger.release(source);
    }
}
static void prompt_snapshot_held() {
    prompt_reconcile_releases();
    const bool* keys=SDL_GetKeyboardState(nullptr);
    for(auto& [key,bit]:g_keys) if(keys[key])
        pal_prompt::ledger.press({1,0,uint64_t(key)},false,bit);
    for(auto key:g_confirm_keys) if(keys[key])
        pal_prompt::ledger.press({1,0,uint64_t(key)},false,g_pc_press.read(key));
    for(auto& pad:g_pads) if(g_slots.slot_of(pad.id)==0) for(auto& in:pad.map.inputs) {
        const bool button=in.button>=0;
        const bool down=button ? SDL_GetGamepadButton(pad.pad,SDL_GamepadButton(in.button)) :
            SDL_GetGamepadAxis(pad.pad,SDL_GamepadAxis(in.axis))>pad.map.trigger;
        if(down) pal_prompt::ledger.press({button?2u:4u,uint64_t(pad.id),uint64_t(button?in.button:in.axis)},false,in.bit);
    }

}
static bool prompt_valid() {
    return SDL_IsMainThread() && g_win && !g_cfg.headless &&
        (g_cfg.input.empty() || (g_cfg.resume && !sat_resuming())) &&
        SDL_GetKeyboardFocus()==g_win && g_edge_focus && g_edge_foreground &&
        !g_menu_open && !g_layout_edit && !g_quitting;
}
static bool prompt_begin() {
    if (!prompt_valid()) return false;
    prompt_snapshot_held();
    g_prompt_since=SDL_GetTicksNS();
    g_buttons[0] &= uint16_t(~0x0600);
    g_pal_taps[0].forget(0x0600);
    return true;
}
static void prompt_consume() {
    // Use the host's existing release quarantine. A short tap may already be
    // up; forgetting its stretcher debt prevents it reappearing in the next UI.
    g_held_over[0] |= pal_prompt::ledger.held();
    g_buttons[0] &= uint16_t(~0x0600);
    g_pal_taps[0].forget(0x0600);
    for (auto& key : g_pc_press.keys) if (key.bit & 0x0600) key.bit=0;
}
struct PromptHostInstall {
    PromptHostInstall() {
        pal_prompt::host_begin=prompt_begin;
        pal_prompt::host_valid=prompt_valid;
        pal_prompt::host_consume=prompt_consume;
    }
};
static PromptHostInstall g_prompt_host_install;
static void prompt_event(const SDL_Event& e) {
    const auto wid=SDL_GetWindowID(g_win);
    using Source=pal_prompt::Source;
    if ((e.type==SDL_EVENT_WINDOW_FOCUS_GAINED && e.window.windowID==wid) || e.type==SDL_EVENT_DID_ENTER_FOREGROUND)
        prompt_reconcile_releases();
    if ((e.type==SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID==wid) ||
        e.type==SDL_EVENT_WILL_ENTER_BACKGROUND || e.type==SDL_EVENT_DID_ENTER_BACKGROUND ||
        e.type==SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED) {
        pal_prompt::ledger.cancel(); return;
    }
    const bool eligible=prompt_valid() && e.common.timestamp>g_prompt_since;
    if(e.type==SDL_EVENT_KEY_UP && e.key.windowID==wid) {
        pal_prompt::ledger.release(Source{1,0,uint64_t(e.key.scancode)});
    } else if(e.type==SDL_EVENT_KEY_DOWN && e.key.windowID==wid && !e.key.repeat) {
        uint16_t bits=0;
        if(semantic_key(e.key.scancode)) bits=g_pc_press.read(e.key.scancode);
        else for(auto& [key,bit]:g_keys) if(key==e.key.scancode) bits|=bit;
        pal_prompt::ledger.press(Source{1,0,uint64_t(e.key.scancode)},
            eligible && !(e.key.mod & SDL_KMOD_ALT) && (bits & 0x0600),bits);
    } else if(e.type==SDL_EVENT_GAMEPAD_BUTTON_DOWN || e.type==SDL_EVENT_GAMEPAD_BUTTON_UP) {
        const Source source{2,uint64_t(e.gbutton.which),uint64_t(e.gbutton.button)};
        if(e.type==SDL_EVENT_GAMEPAD_BUTTON_UP) pal_prompt::ledger.release(source);
        else {
            uint16_t bits=0;
            for(auto& pad:g_pads) if(pad.id==e.gbutton.which && g_slots.slot_of(pad.id)==0)
                for(auto& in:pad.map.inputs) if(in.button==int(e.gbutton.button)) bits|=in.bit;
            pal_prompt::ledger.press(source,eligible && (bits & 0x0600),bits);
        }
    } else if(e.type==SDL_EVENT_GAMEPAD_AXIS_MOTION) {
        // Respect each user's exact trigger threshold. Repeated above-threshold
        // samples are the same hold; only a below/above crossing is a new edge.
        const Source source{4,uint64_t(e.gaxis.which),uint64_t(e.gaxis.axis)};
        for(auto& pad:g_pads) if(pad.id==e.gaxis.which && g_slots.slot_of(pad.id)==0) {
            uint16_t bits=0;
            for(auto& in:pad.map.inputs) if(in.axis==int(e.gaxis.axis)) bits|=in.bit;
            if(e.gaxis.value<=pad.map.trigger) pal_prompt::ledger.release(source);
            else pal_prompt::ledger.press(source,eligible && (bits & 0x0600),bits);
        }
    } else if(e.type==SDL_EVENT_FINGER_DOWN || e.type==SDL_EVENT_FINGER_UP || e.type==SDL_EVENT_FINGER_CANCELED) {
        const Source source{3,uint64_t(e.tfinger.touchID),uint64_t(e.tfinger.fingerID)};
        if(e.type!=SDL_EVENT_FINGER_DOWN) {
            pal_prompt::ledger.release(source,e.type==SDL_EVENT_FINGER_CANCELED);
        } else {
            SDL_GetCurrentRenderOutputSize(g_ren,&g_out_w,&g_out_h);
            const float x=e.tfinger.x*g_out_w, y=e.tfinger.y*g_out_h;
            const auto layout=pad_layout();
            const bool blocked=(menu_button_shown() && touch_on_menu(layout,x,y)) || touch_on_dpad(layout,x,y);
            const auto bits=touch_buttons(layout,{{x,y,false}});
            pal_prompt::ledger.press(source,eligible && touch_shown() && !blocked && (bits & 0x0600),
                touch_shown() && !blocked ? bits : uint16_t(0));
        }
    } else if(e.type==SDL_EVENT_GAMEPAD_REMOVED) {
        // A detached source must never leave an owed event behind.
        pal_prompt::ledger.cancel();
    }
}
'''

def host(text):
    if 'g_prompt_host_install' in text: raise ValueError('Prompt host already injected')
    # Input host identity was validated by the enclosing keyboard planner. These
    # unique anchors additionally reject incomplete or double-applied variants.
    text = once(text, 'static void on_event(const SDL_Event& e) {', HOST_HELPERS + '\nstatic void on_event(const SDL_Event& e) {')
    text = once(text, '    pal_note_press(e);', '    prompt_event(e);\n    pal_note_press(e);')
    text = once(text, '        g_buttons[s] = pad;', '        // The scoped ledger owns confirm: never put its edge into a later SMPC packet.\n        if (s==0 && pal_prompt::ledger.active) { g_pal_taps[0].forget(0x0600); pad &= uint16_t(~0x0600); }\n        g_buttons[s] = pad;')
    for name in ('menu_open', 'menu_close'):
        anchor = 'static void '+name+'() {'
        text = once(text, anchor, anchor+'\n    pal_prompt::ledger.cancel();')
    return text

def plan(texts, host_path, changes):
    """All arguments are staged in-memory content; no files are accessed."""
    targets=[p for p,s in texts.items() if p.name.startswith('p_prog_') and 'void f_060220D0(SH2Context& c) {' in s]
    if len(targets)!=1: raise ValueError('Prompt requires exactly one original wait function')
    p=targets[0]
    staged=changes.get(p,texts[p].encode()).decode()
    return {p:guest(staged).encode(),host_path:host(changes[host_path].decode()).encode()}

def source_identity():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
