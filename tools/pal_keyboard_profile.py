"""Pure PC98 mapping planner v1. No file I/O, no edge queue, no timing options.

Call at the LAST in-memory planning stage (after optional precise/paired changes),
then commit its returned changes in the caller's one transaction/manifest.
Ordinary builds call the same function on the verified five-patch runtime.
The caller owns path resolution, source reads, race guards, backup/rollback,
manifest idempotence, and CMake runtime selection. Repeated raw planning fails.
"""
from pathlib import Path
import hashlib,re
VERSION='pal-keyboard-profile-v1-mapping-10-menu-vblank'
def sha(s):return hashlib.sha256(s.encode() if isinstance(s,str) else s).hexdigest()
RUNTIME_HASHES = {'host.cpp': ['6b82aaa5f9720e3ad9a53db35e6dda8ef08198d4dbcacf7f3f0f6b25f2a9518d', '9af5f2ac245114cb7cdf858c69a90ecb0c217a29f423c9168c353558bf0222a4', '16fd0b06648fb3f3c1dda96b3200aa7bf8baaff1f2aca9d0b4e0ffa720055937', 'f4c957d90193478ac77588f6592b1061226686b062bbd3e7561ba7a236da94a1'], 'settings.cpp': ['4da2c93a0eec58ca861c972076961eaf4d64d4ecb471b4d29d94af73f1705b66', '6dd16bf8b13057ddd35aa50a474aaf958df2515e94e877a533b99f5430df9cfb'], 'launcher.cpp': ['23d65e3b6f854823fd33a1f3b1373584d22e98b9edf247125458648fad863e32']}
RUNTIME_HASHES['host.cpp'].append('4b2c32d213a9a28823c214cbfe3f62ac166e238beb127105441e1baee1eef7ed')
RUNTIME_HASHES['host.cpp'].append('f3c49e658ea2e687bcf5734e935d698f0e012654882141f108ba9c87aa4af49b')
RUNTIME_HASHES['host.cpp'].append('d388ef17f964c9ef1f46278d1155dbf0fed4e349fcfdc4850bc106019c206ac7')
RUNTIME_HASHES['host.cpp'].append('40ad654e2f837a291a0d27e254cab4f853f243eb4c50457c32e7b078c619b4bc')
RUNTIME_HASHES['host.cpp'].append('c8f6c1c6cd450d58e5c38d3238475a979c38c4a39be36239f42638f2078e9a42')
RUNTIME_HASHES['settings.cpp'].append('fe5b419476049441a717a99928066e619eb9546f2763f6dc1e784cf318eed80d')
RUNTIME_HASHES['host.cpp'].append('44f882f679696aa1b9f0dbf1db742c19e0f1a68e7de75d4ad00fe5641ec56d90')
RUNTIME_HASHES['host.cpp'].append('811878f044cdaeb55f442d31d3524e2b4ae8aaee20f4652df76b967c74340dfb')
RUNTIME_HASHES['settings.cpp'].append('909ea2d8fdf41755ceae9ef8eaf8730ad6a12d9269d91f95b607185bd7de556b')
RUNTIME_HASHES['host.cpp'].append('476a8cd5b88eb926d3cdd581bbd31c94d2c4ac6114a9983906a74e7bb85f2ffd')
RUNTIME_HASHES['launcher.cpp'].append('6fab3c98d05f4f9eb69c2c14672b205f487964fc6c02f9815289699525b4fc57')
# 0013's tap hold, as a mapping-only build reads it straight from the patched runtime.
RUNTIME_HASHES['host.cpp'].append('bc6134fcf2b9509fe339aca897586efe5e0412ce9f89074db2dc7edfccf6ea56')
# 0013 again as the options build hands it to this planner: after that build's own input stages.
RUNTIME_HASHES['host.cpp'].append('c681e48800584a4384ccb85daf1502541ae300f21a0c2d4d3477f2283bf2e8f7')
# Full fixed-upstream UI13 + 0014 + restored 0015; see input build identity audit.
RUNTIME_HASHES['host.cpp'].append('17236f5e8e8d8316482040b00ba72dbdda7d19daadaf9e101ed31eae7f20168e')
# The same complete chain after existing precise-input and paired-queue stages.
RUNTIME_HASHES['host.cpp'].append('1486417a81f3546751aa1d7b0293b2f4c98e8316034576f3bac14c838bbf2fa0')
# Verified complete patch 0016 host; see field input source manifest.
RUNTIME_HASHES['host.cpp'].append('a381f4bd6d80f1b0cf19eaecd37fc0875f82747dc91f37382f59f8ad07703f5d')
# Exact reviewed runtime after 0018 scene-held continuity.
RUNTIME_HASHES['host.cpp'].append('109c29033e8159c462a9516e85fbaceb57611112269bbc8f838a92383dd6233a')
RUNTIME_HASHES['host.cpp'].append('6f0c959abaa3d6f4f8324182d65c56af2f79acd374f65ba2e7f5765527c78ef5')

# Frozen field-host r2 after unchanged precise-input and paired-queue stages.
RUNTIME_HASHES['host.cpp'].append('8ec6ce8cad954a98be6a64b086d6b150644bafa7e7bdb0cf851664fe3a0d9bbf')
FUNCTION_HASHES = {'06020040': ['49fc15d214cc14ad85134d3301ce577f699d38aec8301287d632dd5b545bad7c'], '06026D84': ['9e83b5975b9f141c3d0e22f15907be2ada11b74aab7237444cde410ae4fefaaa', 'f04a09eb1154c18fcdb61a95fd4f3f945106da5daccf7eec6131edf88800e8a8'], '06021F14': ['1a72d209543cdd95d863b4e62b28c7639a24c2098c855279d2a97075203722e0'], '06026F90': ['33b311616b04e42b7e6cb85366ff11f58e1ecc4a1573fd5b9d7b8527cb2fcb75', '677f5eb849f6f0f3731cf35a0292d91dacef58e127de7d427fb659101b56e056'], '0604A5B8': ['38a41b3879208ad03418cbe48ed1efeb1888129062f385fc362955afd8e0ce50'], '060516B4': ['8d243239da6d34c6b188603ca3108a13b9984f855348edf66a04759c5a93b60d'], '06020058': ['9548908855627449ef75ff2a63a87d8083fc953294231d447073e05bec6beca7']}
FUNCTION_HASHES['0604A0BC'] = ['ab7cfc91ca77e9b977d3bc6e986174bdc7ff89baed1a1ab21630540fe749cae1']
HEADER_SHA256 = '342eb19a2e8f705d7779f2215ae59fccb03b6e3fa8b9f6c8f837d795a68d72e3'
LAUNCHER_HUNKS = [('        std::string name;\n        if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {\n            if (e.key.scancode == SDL_SCANCODE_ESCAPE) { binding_.clear(); return true; }\n            if (binding_section_ == "keyboard") name = SDL_GetScancodeName(e.key.scancode);\n        } else if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN && binding_section_ == "gamepad") {\n            name = SDL_GetGamepadStringForButton((SDL_GamepadButton)e.gbutton.button);\n        } else if (e.type == SDL_EVENT_GAMEPAD_AXIS_MOTION && binding_section_ == "gamepad" &&\n', '        std::string name;\n        if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {\n            if (e.key.scancode == SDL_SCANCODE_ESCAPE) { binding_.clear(); return true; }\n            if (binding_section_.rfind("keyboard", 0) == 0) name = SDL_GetScancodeName(e.key.scancode);\n        } else if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN && binding_section_ == "gamepad") {\n            name = SDL_GetGamepadStringForButton((SDL_GamepadButton)e.gbutton.button);\n        } else if (e.type == SDL_EVENT_GAMEPAD_AXIS_MOTION && binding_section_ == "gamepad" &&\n'), ('\n    void controls() {\n        ImGui::SeparatorText("Controls");\n        if (!binding_.empty())\n            ImGui::TextColored(ImVec4(1, 0.9f, 0.4f, 1), "Press the %s for %s (Esc cancels)",\n                               binding_section_ == "keyboard" ? "key" : "gamepad button", label(binding_));\n        else\n            ImGui::TextWrapped("Choose a binding, then press its new key or button. Every gamepad uses these.");\n        if (ImGui::BeginTable("controls", 3, ImGuiTableFlags_SizingStretchSame)) {\n            ImGui::TableSetupColumn("Saturn");\n            ImGui::TableSetupColumn("Keyboard");\n', '\n    void controls() {\n        ImGui::SeparatorText("Controls");\n        const bool pc = set_.get("controls", "keyboard_profile") == "pc98";\n        if (ImGui::RadioButton("PC98 keyboard", pc)) {\n            binding_.clear(); set_.set("controls", "keyboard_profile", "pc98"); save();\n        }\n        ImGui::SameLine();\n        if (ImGui::RadioButton("Saturn keyboard", !pc)) {\n            binding_.clear(); set_.set("controls", "keyboard_profile", "saturn"); save();\n        }\n        ImGui::TextWrapped("PC98 F10: host menu. Enter confirms/interacts; Esc opens the game menu or cancels. E and F open the field item and spell pages; in the battle main menu F and A use native strongest attacks and R repeats previous commands for the remaining party. Gamepad bindings are independent.");\n        const char* keyboard_section = pc ? "keyboard pc98" : "keyboard";\n        if (pc) {\n            const struct { const char* key; const char* label; } kSemantic[] = {\n                {"confirm", "Confirm / interact"}, {"menu_cancel", "Game menu / cancel"},\n                {"item", "Items (field)"}, {"spell", "Spells (field) / strongest (battle)"},\n                {"status", "Status (field)"}, {"equip", "Equipment (field)"},\n                {"system", "Save / load (field)"},\n                {"strongest", "Strongest attacks (battle)"}, {"repeat", "Repeat commands (battle)"}};\n            for (auto& sem : kSemantic) {\n                ImGui::TextUnformatted(sem.label);\n                ImGui::SameLine();\n                std::string id = set_.get(keyboard_section, sem.key) + "##semantic" + sem.key;\n                if (ImGui::Button(id.c_str()) && binding_.empty()) { binding_ = sem.key; binding_section_ = keyboard_section; }\n            }\n        }\n        if (!binding_.empty())\n            ImGui::TextColored(ImVec4(1, 0.9f, 0.4f, 1), "Press the %s for %s (Esc cancels)",\n                               binding_section_.rfind("keyboard", 0) == 0 ? "key" : "gamepad button", label(binding_));\n        else\n            ImGui::TextWrapped("Choose a binding, then press its new key or button. PC98 reserves F10. Existing ordinary/confirm/cancel bindings and host hotkeys take priority over the field and battle shortcuts. Saturn keeps custom F10 bindings. Esc cancels binding capture.");\n        if (ImGui::BeginTable("controls", 3, ImGuiTableFlags_SizingStretchSame)) {\n            ImGui::TableSetupColumn("Saturn");\n            ImGui::TableSetupColumn("Keyboard");\n'), ('                ImGui::TableNextRow();\n                ImGui::TableNextColumn();\n                ImGui::TextUnformatted(b.label);\n                for (const char* section : {"keyboard", "gamepad"}) {\n                    ImGui::TableNextColumn();\n                    std::string id = set_.get(section, b.key) + "##" + section + b.key;\n                    bool waiting = binding_ == b.key && binding_section_ == section;\n', '                ImGui::TableNextRow();\n                ImGui::TableNextColumn();\n                ImGui::TextUnformatted(b.label);\n                for (const char* section : {keyboard_section, "gamepad"}) {\n                    ImGui::TableNextColumn();\n                    std::string id = set_.get(section, b.key) + "##" + section + b.key;\n                    bool waiting = binding_ == b.key && binding_section_ == section;\n'), ('        }\n        if (ImGui::Button("Default controls")) {\n            Settings defaults;\n            for (const char* section : {"keyboard", "gamepad"})\n                for (auto& key : defaults.keys(section)) set_.set(section, key, defaults.get(section, key));\n            save();\n        }\n', '        }\n        if (ImGui::Button("Default controls")) {\n            Settings defaults;\n            for (const char* section : {keyboard_section, "gamepad"})\n                for (auto& key : defaults.keys(section)) set_.set(section, key, defaults.get(section, key));\n            save();\n        }\n')]


def once(s,a,b):
 if s.count(a)!=1:raise ValueError(f'expected 1 got {s.count(a)}: {a[:100]}')
 return s.replace(a,b,1)

def settings(s):
 s=once(s,'[keyboard]\n','[controls]\n; PAL_KEYBOARD_PROFILE_V2 (context-latched mapping and PAL98 field/battle shortcuts; no edge queue)\n; pc98: Enter confirms, Escape opens the game menu or cancels. F10 is the host menu.\n; saturn: use the original [keyboard] map. Physical gamepads always retain their own map.\nkeyboard_profile = pc98\n\n[keyboard]\n')
 anchor='; Every gamepad\'s buttons'
 new='''; PC98 keyboard bindings. Confirm/menu_cancel select one context-appropriate Saturn button.
; They are latched on key-down until release; holding Escape never opens then closes a menu.
; An empty binding is deliberately unbound: the PAL98 letters below own those Saturn buttons.
[keyboard pc98]
up = Up
down = Down
left = Left
right = Right
start = Tab
a = Z
b = X
c = C
x = V
y =
z =
l =
r =
confirm = Return, Keypad Enter, Space
menu_cancel = Escape
; The PAL98 shortcut letters either press the Saturn button that does the same thing or
; drive the command menu for the player. item/spell are the field quick pages and
; strongest/repeat only the battle command menu, so one key can serve both: F is 仙術 in
; the field and 最強 in battle. status/equip/system have no Saturn button to borrow, so
; they open 狀態 / 系統 through the menu, walking to the entry the game is left on.
; Ordinary bindings, confirm/cancel and host hotkeys win conflicts; an empty value disables.
item = E
spell = F
status = S
equip = W
system = Q
strongest = F, A
repeat = R

'''
 s=once(s,anchor,new+anchor)
 s=once(s,'{"controls", {"auto", "on", "off"}},','{"keyboard_profile", {"pc98", "saturn"}}, {"controls", {"auto", "on", "off"}},')
 s=once(s,'void Settings::read(const std::string& text, std::vector<std::string>& problems) {','''void Settings::read(const std::string& text, std::vector<std::string>& problems) {
    // A pre-profile file retains every legacy binding and the legacy Escape rule.
    // Never rewrite the user's file merely because it was read.
    bool has_profile = false;
    each_line(text, [&](int, const std::string& section, const std::string& key, const std::string&) {
        if (section == "controls" && key == "keyboard_profile") has_profile = true;
    });
    values_["controls"]["keyboard_profile"] = has_profile ? "pc98" : "saturn";''')
 return s

def host(s):
 s='#include <saturn/pal_keyboard_profile.h>\n'+s
 s=once(s,'static std::vector<std::pair<SDL_Scancode, uint16_t>> g_keys;','''static std::vector<std::pair<SDL_Scancode, uint16_t>> g_keys;
static std::vector<SDL_Scancode> g_confirm_keys, g_cancel_keys, g_item_keys, g_spell_keys;
static std::vector<SDL_Scancode> g_status_keys, g_equip_keys, g_system_keys;
static pal_keyboard::MenuWalk g_pc98_walk;
static std::vector<SDL_Scancode> g_strongest_keys, g_repeat_keys;
static pal_keyboard::BattlePressLatch g_battle_press;
static bool battle_key(SDL_Scancode key) {
    return std::find(g_strongest_keys.begin(), g_strongest_keys.end(), key) != g_strongest_keys.end() ||
           std::find(g_repeat_keys.begin(), g_repeat_keys.end(), key) != g_repeat_keys.end();
}
// The field's quick pages share the confirm/cancel latch, so their button is picked
// once on key-down and a held key never changes its mind when a page opens.
// Letters with no Saturn button behind them (狀態 / 装备 / 系統) walk that menu instead.
static bool in_keys(const std::vector<SDL_Scancode>& keys, SDL_Scancode key) {
    return std::find(keys.begin(), keys.end(), key) != keys.end();
}
static bool field_key(SDL_Scancode key) {
    return in_keys(g_item_keys, key) || in_keys(g_spell_keys, key);
}
static bool walk_key(SDL_Scancode key) {
    return in_keys(g_status_keys, key) || in_keys(g_equip_keys, key) || in_keys(g_system_keys, key);
}
// Saturn has no equip screen: 装备 is done from the 物品 page, so W walks to that entry.
static uint16_t wanted_entry(SDL_Scancode key) {
    if (in_keys(g_system_keys, key)) return pal_keyboard::SystemEntry;
    return in_keys(g_equip_keys, key) ? pal_keyboard::ItemEntry : pal_keyboard::StatusEntry;
}
static pal_keyboard::PressLatch g_pc_press;
static bool pc_keyboard() { return g_settings.get("controls", "keyboard_profile") == "pc98"; }
static bool semantic_key(SDL_Scancode key) {
    return battle_key(key) || field_key(key) || walk_key(key) ||
           std::find(g_confirm_keys.begin(), g_confirm_keys.end(), key) != g_confirm_keys.end() ||
           std::find(g_cancel_keys.begin(), g_cancel_keys.end(), key) != g_cancel_keys.end();
}''')
 s=once(s,'    g_keys.clear();\n    for (auto& b : kSaturn)','''    g_keys.clear();
    g_confirm_keys.clear(); g_cancel_keys.clear(); g_pc_press.block();
    g_item_keys.clear(); g_spell_keys.clear();
    g_status_keys.clear(); g_equip_keys.clear(); g_system_keys.clear(); g_pc98_walk.stop();
    g_strongest_keys.clear(); g_repeat_keys.clear(); g_battle_press.block();
    const std::string section = pc_keyboard() ? "keyboard pc98" : "keyboard";
    for (auto& b : kSaturn)''')
 s=once(s,'names(g_settings, "keyboard", b.name','names(g_settings, section, b.name')
 marker='            g_keys.push_back({(SDL_Scancode)k, b.bit});\n}'
 s=once(s,marker,'''            g_keys.push_back({(SDL_Scancode)k, b.bit});
    if (pc_keyboard()) {
        auto scancode = [](const std::string& n) { auto c=SDL_GetScancodeFromName(n.c_str()); return c==SDL_SCANCODE_UNKNOWN ? -1 : (int)c; };
        for (int k : names(g_settings, section, "confirm", scancode)) g_confirm_keys.push_back((SDL_Scancode)k);
        for (int k : names(g_settings, section, "menu_cancel", scancode)) g_cancel_keys.push_back((SDL_Scancode)k);
        // Preserve all preexisting bindings when adding defaults to an old PC profile.
        // An explicitly duplicated shortcut is also non-destructive: ordinary keys,
        // confirm/cancel and host hotkeys win; item precedes spell, strongest precedes repeat.
        // One key may serve the field page and the battle command menu at once, because the
        // two contexts never hold together and each latch zeroes the press outside its own.
        auto claimable = [&](const SDL_Scancode key) {
            const bool native_bound = std::any_of(g_keys.begin(), g_keys.end(),
                [key](const auto& v) { return v.first == key; });
            const bool host_key = key == SDL_SCANCODE_F10 || key == SDL_SCANCODE_F11 ||
                key == SDL_SCANCODE_F12 || key == SDL_SCANCODE_AC_BACK;
            const bool ordinary = std::find(g_confirm_keys.begin(), g_confirm_keys.end(), key) != g_confirm_keys.end() ||
                                  std::find(g_cancel_keys.begin(), g_cancel_keys.end(), key) != g_cancel_keys.end();
            return !host_key && !native_bound && !ordinary;
        };
        auto add_keys = [&](const char* name, std::vector<SDL_Scancode>& out, bool (*taken)(SDL_Scancode)) {
            for (int k : names(g_settings, section, name, scancode)) {
                const auto key = (SDL_Scancode)k;
                if (claimable(key) && !taken(key)) out.push_back(key);
            }
        };
        add_keys("item", g_item_keys, field_key);
        add_keys("spell", g_spell_keys, field_key);
        add_keys("status", g_status_keys, walk_key);
        add_keys("equip", g_equip_keys, walk_key);
        add_keys("system", g_system_keys, walk_key);
        add_keys("strongest", g_strongest_keys, battle_key);
        add_keys("repeat", g_repeat_keys, battle_key);
    }
}''')
 s=once(s,'        if (k[key] && !(alt && key == SDL_SCANCODE_RETURN)) b[0] |= bit;','''        if (!semantic_key(key) && key != SDL_SCANCODE_F10 && k[key] &&
            SDL_GetKeyboardFocus() == g_win && !(alt && key == SDL_SCANCODE_RETURN)) b[0] |= bit;
    if (SDL_GetKeyboardFocus() == g_win) {
        for (auto key : g_confirm_keys) b[0] |= g_pc_press.read(key);
        for (auto key : g_cancel_keys) b[0] |= g_pc_press.read(key);
        for (auto key : g_item_keys) b[0] |= g_pc_press.read(key);
        for (auto key : g_spell_keys) b[0] |= g_pc_press.read(key);
        for (auto key : g_strongest_keys) b[0] |= g_battle_press.read(key);
        for (auto key : g_repeat_keys) b[0] |= g_battle_press.read(key);
        // A walk paces itself and waits for the guest's own menu counter, so a menu the player
        // left open, or an arrow they stepped in the meantime, cannot send the confirm elsewhere.
        const auto walk = g_pc98_walk.tick(pal_keyboard::field_menu.epoch, sat_vblanks());
        b[0] |= walk.bits;
        if (walk.ask) pal_keyboard::menu_intent = uint16_t(g_pc98_walk.target + 1);
    }''')
 s=once(s,'static void menu_close() {','static void menu_close() {\n    g_pc_press.block(); g_battle_press.block(); g_pc98_walk.stop();')
 s=once(s,'static void menu_open() {','static void menu_open() {\n    g_pc_press.block(); g_battle_press.block(); g_pc98_walk.stop();')
 s=once(s,'static bool escape_is_a_button() {','static bool escape_is_a_button() {\n    if (semantic_key(SDL_SCANCODE_ESCAPE)) return true;')
 s=once(s,'static void on_event(const SDL_Event& e) {','''static void on_event(const SDL_Event& e) {
    const auto wid = SDL_GetWindowID(g_win);
    if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID == wid) g_pc_press.block();
    if (e.type == SDL_EVENT_KEY_UP && e.key.windowID == wid) { g_pc_press.up(e.key.scancode); g_battle_press.up(e.key.scancode); }
    if (e.type == SDL_EVENT_KEY_DOWN && e.key.windowID == wid && semantic_key(e.key.scancode)) {
        sync_pc_boundary();  // Retire only old presses before accepting a new edge.
        const bool item = std::find(g_item_keys.begin(), g_item_keys.end(), e.key.scancode) != g_item_keys.end();
        const bool spell = std::find(g_spell_keys.begin(), g_spell_keys.end(), e.key.scancode) != g_spell_keys.end();
        if (battle_key(e.key.scancode)) {
            const bool repeat_command = std::find(g_repeat_keys.begin(), g_repeat_keys.end(), e.key.scancode) != g_repeat_keys.end();
            g_battle_press.down(e.key.scancode, repeat_command ? pal_keyboard::Repeat : pal_keyboard::Strongest,
                               e.key.repeat, SDL_GetKeyboardFocus() == g_win,
                               g_menu_open || (e.key.mod & SDL_KMOD_ALT));
        }
        if (walk_key(e.key.scancode)) {
            // Only the field loop owns these letters: inside the menu, a dialogue or a battle
            // the same key has to stay inert, because the walk ends in an A press.
            const bool field_now = pal_keyboard::context.cancel == pal_keyboard::Menu;
            if (!e.key.repeat && field_now && !pal_keyboard::battle_commands && !g_menu_open &&
                SDL_GetKeyboardFocus() == g_win && !(e.key.mod & SDL_KMOD_ALT))
                g_pc98_walk.ask(wanted_entry(e.key.scancode));
        } else if (item || spell) {
            g_pc_press.down(e.key.scancode, item ? pal_keyboard::context.item : pal_keyboard::context.spell,
                            e.key.repeat, SDL_GetKeyboardFocus() == g_win,
                            g_menu_open || (e.key.mod & SDL_KMOD_ALT));
        } else if (!battle_key(e.key.scancode)) {
            const bool cancel = std::find(g_cancel_keys.begin(), g_cancel_keys.end(), e.key.scancode) != g_cancel_keys.end();
            g_pc_press.down(e.key.scancode, cancel ? pal_keyboard::context.cancel : pal_keyboard::context.confirm,
                            e.key.repeat, SDL_GetKeyboardFocus() == g_win,
                            g_menu_open || (e.key.mod & SDL_KMOD_ALT));
        }
    }''')
 s=once(s,'        bool back = k == SDL_SCANCODE_AC_BACK || (k == SDL_SCANCODE_ESCAPE && !escape_is_a_button());','''        if (e.key.windowID != wid || SDL_GetKeyboardFocus() != g_win) break;
        bool back = k == SDL_SCANCODE_F10 || k == SDL_SCANCODE_AC_BACK ||
                    (k == SDL_SCANCODE_ESCAPE && (g_menu_open || !escape_is_a_button()));''')
 s=s.replace('Android\'s Back, Escape, a','Android\'s Back, F10 (or unbound Escape), a')
 s=once(s,'static pal_keyboard::PressLatch g_pc_press;','static pal_keyboard::PressLatch g_pc_press;\nstatic uint64_t g_pc_boundary = 0;\nstatic void sync_pc_boundary() {\n    if (g_pc_boundary != pal_keyboard::boundary) {\n        g_pc_boundary = pal_keyboard::boundary; g_pc_press.block(); g_pc98_walk.stop();\n    }\n}')
 s=once(s,'static void read_pads() {','static void read_pads() {\n    sync_pc_boundary();')
 s=s.replace('e.window.windowID == wid) g_pc_press.block();','e.window.windowID == wid) { g_pc_press.reset(); g_battle_press.block(); g_pc98_walk.stop(); }')
 s=s.replace('!semantic_key(key) && key != SDL_SCANCODE_F10 && k[key]', '!semantic_key(key) && !(pc_keyboard() && key == SDL_SCANCODE_F10) && k[key]')
 s=once(s,'        bool back = k == SDL_SCANCODE_F10 || k == SDL_SCANCODE_AC_BACK ||', '        const bool f10_bound = std::any_of(g_keys.begin(), g_keys.end(), [](const auto& v) { return v.first == SDL_SCANCODE_F10; });\n        bool back = (k == SDL_SCANCODE_F10 && (pc_keyboard() || !f10_bound || g_menu_open)) || k == SDL_SCANCODE_AC_BACK ||')
 return s


def scope(texts,k,transform):
 marker='void f_'+k+'(SH2Context& c) {\n'; prefix='p_true_' if k=='06020058' else 'p_prog_'; found=[p for p,s in texts.items() if p.name.startswith(prefix) and p.suffix=='.cpp' and marker in s]
 if len(found)!=1 or texts[found[0]].count(marker)!=1:raise ValueError('Function anchor '+k)
 p=found[0];s=texts[p];a=s.index(marker);m=re.search(r'\nvoid f_[0-9A-F]+\(SH2Context& c\) \{',s[a+len(marker):]);z=a+len(marker)+m.start() if m else s.rfind('\n}  // namespace')
 f=s[a:z]
 if sha(f) not in FUNCTION_HASHES[k]:raise ValueError('Guest function changed: '+k)
 texts[p]=s[:a]+transform(f)+s[z:];return p

def instruction(s,pc,before='',after=''):
 lines=s.splitlines(True);hits=[i for i,l in enumerate(lines) if '// '+pc+' ' in l]
 if len(hits)!=1:raise ValueError('Instruction anchor '+pc)
 i=hits[0];lines[i]=('    '+before+'\n' if before else '')+lines[i]+('    '+after+'\n' if after else '');return ''.join(lines)

def plan_keyboard(recomp,runtime,texts,rt,header_bytes):
 """Return Path->bytes changes over staged inputs; never mutate caller mappings.
 texts: all generated PROG and TRUE Path->str sources (including staged options).
 rt: Path->str containing host.cpp, settings.cpp, launcher.cpp and settings.h.
 header_bytes: exact reviewed pal_keyboard_profile.h bytes.
 """
 recomp,runtime=Path(recomp),Path(runtime)
 if any('..' in p.parts for p in (recomp,runtime,*map(Path,texts))):raise ValueError('Parent traversal is not permitted')
 if not recomp.is_absolute() or not runtime.is_absolute() or recomp==runtime or recomp.is_relative_to(runtime) or runtime.is_relative_to(recomp):raise ValueError('Separate absolute detached paths required')
 if sha(header_bytes.replace(b'\r\n',b'\n'))!=HEADER_SHA256:raise ValueError('Keyboard helper source/version changed')
 texts={Path(p):s.replace('\r\n','\n') for p,s in texts.items()}
 if not texts or any(not p.is_relative_to(recomp) for p in texts):raise ValueError('Generated sources must be inside recomp')
 if any('pal_keyboard::' in s or 'pal_keyboard_profile.h' in s for s in texts.values()):raise ValueError('Already injected keyboard profile; use manifest or regenerate')
 changes={};changed=set()
 for n,transform in [('host.cpp',host),('settings.cpp',settings),('launcher.cpp',None),('settings.h',settings_header)]:
  p=runtime/'src/host'/n;s=rt.get(p)
  if not isinstance(s,str):raise ValueError('Missing runtime input '+n)
  s=s.replace('\r\n','\n')
  # Paths in existing precise hooks are normalized by its planner already.
  # Quote the observed digest: registering a new generation is a pin update, and
  # re-deriving it by hand means replaying every earlier injection stage.
  got=sha(s.encode())
  if got not in RUNTIME_HASHES[n]:raise ValueError('Runtime source/version changed: '+n+' observed '+got)
  if transform:s=transform(s)
  else:
   for a,b in LAUNCHER_HUNKS:s=once(s,a,b)
  if n=='host.cpp':s=guard_host(s)
  if n=='settings.cpp':s=guard_settings(s)
  changes[p]=s.encode()
 def entry(k,code):
  changed.add(scope(texts,k,lambda s:once(s,'void f_'+k+'(SH2Context& c) {\n','void f_'+k+'(SH2Context& c) {\n    '+code+'\n')))
 entry('06020040','pal_keyboard::boot();');entry('06020058','pal_keyboard::boot();')
 entry('06021F14','pal_keyboard::ui(true);');entry('06026F90','pal_keyboard::clear();')
 def field(s):
  s=once(s,'void f_06026D84(SH2Context& c) {\n','void f_06026D84(SH2Context& c) {\n    pal_keyboard::field();\n')
  for pc in ['06026E1C','06026E84','06026E90','06026EB8','06026F44','06026F52']:s=instruction(s,pc,'pal_keyboard::ui();','pal_keyboard::field();')
  return s
 changed.add(scope(texts,'06026D84',field))
 def menu(s):
  s=once(s,'void f_0604A5B8(SH2Context& c) {\n','void f_0604A5B8(SH2Context& c) {\n    if (c.r[4] == pal_keyboard::MenuCursor && pal_keyboard::menu_intent) { st16(pal_keyboard::MenuCursor, pal_keyboard::menu_intent - 1); pal_keyboard::menu_intent = 0; }\n')
  return instruction(s,'0604A8C0','pal_keyboard::ui(ld16(c.r[14]+30)==13);\n    if (ld32(c.r[14]) == pal_keyboard::MenuCursor) pal_keyboard::field_menu_at(ld16(pal_keyboard::MenuCursor));')
 changed.add(scope(texts,'0604A5B8',menu))
 entry('060516B4','pal_keyboard::ui((uint16_t)c.r[4] == 1);')
 entry('0604A0BC','pal_keyboard::BattleCommandsScope pal_battle_commands(ld16(0x060768ECu) == 0xFFFFu);')
 for p in changed:changes[p]=('#include <saturn/pal_keyboard_profile.h>\n'+texts[p]).encode()
 changes[runtime/'include/saturn/pal_keyboard_profile.h']=header_bytes
 return changes

# Existing unreadable settings must never be mistaken for a missing file.
def settings_header(s):
 return s + "\nenum class SettingsLoadStatus { Missing, Loaded, Error };\nstd::string settings_load_checked(const std::string& path, SettingsLoadStatus& status);\n"

def guard_settings(s):
 anchor='std::string settings_load(const std::string& path, bool& found) {\n'
 checked="""std::string settings_load_checked(const std::string& path, SettingsLoadStatus& status) {
    namespace fs = std::filesystem;
    status = SettingsLoadStatus::Error;
    std::error_code ec;
    const auto entry = fs::symlink_status(path, ec);
    if (entry.type() == fs::file_type::not_found &&
        (!ec || ec == std::errc::no_such_file_or_directory)) {
        status = SettingsLoadStatus::Missing;
        return {};
    }
    if (ec || !fs::is_regular_file(fs::status(path, ec)) || ec) return {};
    std::ifstream f(path, std::ios::binary);
    if (!f) return {};
    std::string text;
    char block[4096];
    while (f.read(block, sizeof block) || f.gcount()) text.append(block, static_cast<size_t>(f.gcount()));
    if (!f.eof()) return {};  // Do not parse or later overwrite a partial read.
    status = SettingsLoadStatus::Loaded;
    return text;
}

"""
 return once(s,anchor,checked+anchor)

def guard_host(s):
 s=once(s,'static std::string g_settings_path, g_settings_text;', 'static bool g_settings_read_failed = false;\nstatic std::string g_settings_path, g_settings_text;')
 s=once(s,'static void load_settings(const std::string& named) {','static void load_settings(const std::string& named) {\n    g_settings = Settings{};\n    g_settings_read_failed = false;')
 s=once(s,'        bool found = false;\n        std::string text = settings_load(path, found);\n        if (!found) {', """        SettingsLoadStatus status;
        std::string text = settings_load_checked(path, status);
        if (status == SettingsLoadStatus::Error) {
            g_settings_read_failed = true;
            sat_note("settings: cannot safely read %s; using session defaults, original file and saving disabled", path.c_str());
        } else if (status == SettingsLoadStatus::Missing) {""")
 s=once(s,'bool host_settings_save() {',"""bool host_settings_save() {
    if (g_settings_read_failed) {
        sat_note("settings: save disabled because the existing configuration could not be read safely");
        return false;
    }""")
 return s

RUNTIME_HASHES["settings.h"] = ["2f3c544cc54529a9243ac022a79ccb707bd4e86338569fb00c21ee44fc6854b7"]


MANIFEST = 'pal-keyboard-manifest.json'
HARMONY_RUNTIME_HELPERS = {'touch_ui_policy.h': '1972c4c2c38c19b151d8caff07cf165d9f5edf185529caaf9461bce175d7784e', 'touch_menu_paging.h': 'a05761a95eebe222e1c51602b44f75ea19c4a68daaa9cbdb047cfc84c78710e7', 'pal_audio_queue_policy.h': 'b873e70bc52a265c7f74626dc771a914774b86b76e36f0379a27f2bb0ae30c67', 'pal_audio_jitter_policy.h': '893d30bfdf8b9a3373881b510064e086d516989232a1946f735011fbd46c89d8', 'host_sdl.h': 'a02c549b334ae98c3713adf8480e06183b9cf4b724c2acd3fe8be5ecc11ee954'}

# Pin the unchanged UI implementation as well as its new helpers and fonts.
# The UI variant below overrides a helper pin for the same file name, so a patch that
# touches one of these (0012 rewrote touch_pad.h) has to move both entries together.
HARMONY_RUNTIME_HELPERS.update({'touch_pad.h': '3c0aa2e16c81ce00be55b826692469ac4eba85ed55449695fa97a9fe8508bdf1', 'ui.cpp': 'f01298ab0b09b17f3dad1744ecf7f544cfb9631a4798669381bd481277b9994d', 'ui.h': '092475fc1f6698f407578218a6be84dfe87a91fa9fec4d6eed42765efb8c5b10'})
HARMONY_UI_RUNTIME_FILES = {'src/host/host_menu_text.h': '71f353f340bcd725ef9a6699e436b0f173d7d989a5203af97badc762bac23fff', 'src/host/touch_mobile_layout.h': 'ca10a5dbe807d3fd9e3fe6451ad1a6c0ab0eb94e87a74a10eb8de9041ff14000', 'src/host/touch_pad.h': 'ce116e1efa1a511dfcb83f97537dfc5b973864f9a438c4dcf432ad4c20f61dd0', 'src/host/touch_positions.h': '17e93a289335fff39e353c1cafeab145bb832670163ecbaaec39f9562b1eccea', 'src/host/ui.cpp': 'ad46a6c467a7789cc0cb97cd7378915acefb60886587c8b6c3ccde5cbb748094', 'src/host/ui.h': 'a84b5e37be41e5b78c139eb8e5d30d395fae8b66531c469d182a3b05ad6852c5', 'third_party/pal-menu-cjk/LICENSE.txt': '1dd173adfb86606c086ab1c2a5c7d3e6a1c373cd6b2ef7c729955a5f8c71f44f', 'third_party/pal-menu-cjk/README.md': 'b9db583f9951e03107353d8b19d9e7b57d0588f713097cb713e0f0aca2852f92', 'third_party/pal-menu-cjk/generate.py': '7d41876b9272d80d9b58cbae16774f5e1215b1c37ab4adbb9145ee0ea77e4320', 'third_party/pal-menu-cjk/glyphs.h': 'e42e2beefd508e1443eea17c2ce971143d2ec38b8a857140f183475000a36422', 'third_party/pal-menu-cjk/manifest.json': '40f74db2b4f2543d221e5e175d4d186370f41d5594d61b11456fe8b5b7c5f79f', 'third_party/pal-menu-cjk/pal_menu_cjk_bold.h': 'e286ee6609147260e1efea30827c653bbcd8f01a392fd3328f466cbb79b3fe5f', 'third_party/pal-menu-cjk/pal_menu_cjk_regular.h': 'e86226d416450c52d258c99dc94dbe43af422a57c79dd6e5f8f441556dfa6201'}

# UI12 discovery text and its complete font subset form one reviewed variant.
HARMONY_DISCOVERY_RUNTIME_FILES = {**HARMONY_UI_RUNTIME_FILES, **{'src/host/host_menu_text.h': '12140edd671050e1c769d517a09adb5a3d94575dca9720f5fc3ec6fb81a6fa4e', 'third_party/pal-menu-cjk/glyphs.h': '9b4c9b126fade635023cd72223e1001a2c72d586458fb9fa44b99319b6b08536', 'third_party/pal-menu-cjk/manifest.json': '6c9f1f15f6d8aa811abdfc20234279a3c128bf1f14287dc829a32e2662887dd6', 'third_party/pal-menu-cjk/pal_menu_cjk_bold.h': '395bbfea07f8562866897ae48c5d2a56093a0cd5b2d05f091c05df22b6b7740d', 'third_party/pal-menu-cjk/pal_menu_cjk_regular.h': 'abe6d558461f64ac0bca21f6b3ddb19434aec8c18a810c52a1b80a18140ab518'}}

# UI13 edge menu, translated hints and font subset are one exact variant.
HARMONY_EDGE_RUNTIME_FILES = {**HARMONY_DISCOVERY_RUNTIME_FILES, **{'src/host/host_menu_text.h': '2cfa468a58ae53dee04211dc89f6fcdb7d72c81aa8de2d030b5e6dc9236bdaf5', 'src/host/touch_edge_swipe.h': '3e96b5ca8a2416833385ae42aff8d80707bd0f5e9cf3030268db672d9a225717', 'third_party/pal-menu-cjk/glyphs.h': '7af51e87823ec02022dab795251d2673f7590f305bdf3afa671bc4e827618ca8', 'third_party/pal-menu-cjk/manifest.json': '1804b4de6cfdea61062d3c027d6273c06b467ca93dd88a109d61b4ee78f91c4f', 'third_party/pal-menu-cjk/pal_menu_cjk_bold.h': '5e9e006d0fb5a416763bf447f144bf79074a16c019384c5f1906e20933c8256c', 'third_party/pal-menu-cjk/pal_menu_cjk_regular.h': '1add110f177b7c3624d1a30be80b17bef3c1609018d03665f5b9ffa9fc2703fe'}}

# 0014/0015 add one reviewed support variant without weakening older complete ones.
# The 81-line helper is restored verbatim from 3b27d10's original tap-hold patch.
TAP_HOLD_RUNTIME_FILES = {
 'src/host/touch_pad.h': 'c8da777f3f1964b26e11327d229290b60a8cc0117ed83243dcd5160e94efdfc2',
 'src/host/pal_tap_hold.h': '072788032e2f8abce11764caa48068ff43c9d0fafc24236240f63debd2288a47',
}

def verify_runtime_support_manifest(manifest, runtime, support_inputs):
 """Every dependency is owned; planned outputs override their raw input hashes."""
 recorded={**manifest.get('inputs_sha256',{}).get('runtime',{}),
           **manifest.get('outputs_sha256',{}).get('runtime',{})}
 for path,raw in support_inputs.items():
  name=path.relative_to(runtime).as_posix()
  if recorded.get(name)!=sha(raw):raise ValueError('Incomplete runtime support manifest: '+name)

def runtime_support_inputs(runtime):
 """Read and verify one complete reviewed runtime support variant."""
 runtime=Path(runtime)
 if not runtime.is_absolute() or runtime.resolve()!=runtime:raise ValueError('Unsafe runtime support root')
 expected={'src/host/'+name:value for name,value in HARMONY_RUNTIME_HELPERS.items()}
 ui_only=set(HARMONY_UI_RUNTIME_FILES)-set(expected)
 host=runtime/'src/host/host.cpp'
 settings=runtime/'src/host/settings.cpp'
 if any(p.resolve()!=p or p.is_symlink() or not p.is_file() for p in (host,settings)):raise ValueError('Unsafe runtime variant source path')
 uses_ui=b'#include "host_menu_text.h"' in host.read_bytes()
 settings_ui=b'layout_version = )"' in settings.read_bytes()
 if uses_ui!=settings_ui or (not uses_ui and any((runtime/name).exists() or (runtime/name).is_symlink() for name in ui_only)):
  raise ValueError('Mixed Harmony runtime UI variants; regenerate')
 uses_discovery=b'extern "C" int pal_host_ui_feature_version() { return 12; }' in host.read_bytes()
 uses_edge=b'extern "C" int pal_host_ui_feature_version() { return 13; }' in host.read_bytes()
 edge_settings=b'edge_menu = )"' in settings.read_bytes()
 edge_only=set(HARMONY_EDGE_RUNTIME_FILES)-set(HARMONY_DISCOVERY_RUNTIME_FILES)
 if ((uses_discovery or uses_edge) and not uses_ui) or uses_edge!=edge_settings or (not uses_edge and any((runtime/name).exists() or (runtime/name).is_symlink() for name in edge_only)):
  raise ValueError('Mixed Harmony runtime UI variants; regenerate')
 if uses_ui:
  expected.update(HARMONY_EDGE_RUNTIME_FILES if uses_edge else HARMONY_DISCOVERY_RUNTIME_FILES if uses_discovery else HARMONY_UI_RUNTIME_FILES)
 uses_tap=b'#include "pal_tap_hold.h"' in host.read_bytes()
 tap=runtime/'src/host/pal_tap_hold.h'
 if uses_tap:
  expected.update(TAP_HOLD_RUNTIME_FILES)
 elif tap.exists() or tap.is_symlink():
  raise ValueError('Mixed tap-hold runtime variant; regenerate')
 if b'pal_field_input_ledger.h' in host.read_bytes():
  expected.update({'src/host/pal_field_input_ledger.h': 'c910dc4141b58069899e6423d4cb08c2b120b7e7f26bbe237efaf1e17ed49609', 'include/pal_field_input_api.h': 'b6a368e24a637e40af2f3ab65ef9cc7dd9138d3cb3f287da27ea5382a47f205b',
   # 0018 requires both scene API and 0017's stub VBlank clock.
   'src/stub/services_stub.cpp': '9e19eaec08d8b24b1838351d458f17db25f0ad145a210b9bcb3ea61a52218263'})
  null=runtime/'src/host/host_null.cpp'
  if null.resolve()!=null or null.is_symlink() or not null.is_file():raise ValueError('Field no-host helper changed or missing; regenerate')
  null_edge=b'uint16_t pal_host_direction_edge() { return 0; }' in null.read_bytes()
  host_edge=b'#include "pal_host_edge.h"' in host.read_bytes()
  if null_edge!=host_edge:raise ValueError('Mixed field/precise no-host variant; regenerate')
  expected['src/host/host_null.cpp']=('c32122f6bc455c9bb19521838713cf9f8a9a44257d43963e2bd4ae9634427655' if null_edge else
                                     '05d40afa8bca0cf129173063661f357674375012733e545663bed5a911b0dace')
 elif any((runtime/name).exists() or (runtime/name).is_symlink() for name in ('src/host/pal_field_input_ledger.h','include/pal_field_input_api.h')):
  raise ValueError('Mixed field-input runtime variant; regenerate')
 inputs={}
 for name,value in expected.items():
  if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Unsafe runtime support path')
  p=runtime/name
  if p.resolve()!=p or not p.is_relative_to(runtime) or p.is_symlink() or not p.is_file():raise ValueError('Harmony runtime helper changed or missing; regenerate: '+name)
  raw=p.read_bytes()
  # One file may carry more than one accepted generation: quote the observed digest and take a set,
  # so a companion patch (0017 on 0016) is a pin update instead of a rebuild dance.
  got=sha(raw.replace(b'\r\n',b'\n'))
  allowed=value if isinstance(value,(set,frozenset,tuple)) else {value}
  if got not in allowed:raise ValueError('Harmony runtime helper changed or missing; regenerate: '+name+' observed '+got)
  inputs[p]=raw
 return inputs

def prepare_keyboard(recomp, runtime, root, *, verify_only=False):
 """Verify/inject mapping-only detached sources. No compiler or game execution."""
 import json, os
 root=Path(root).resolve();build=root/'build'
 if build.resolve()!=build:raise ValueError('ROOT/build must not be a symlink')
 recomp,runtime=(Path(p).resolve() for p in (recomp,runtime))
 if any(not p.is_relative_to(build) or p==build for p in (recomp,runtime)) or recomp==runtime or recomp.is_relative_to(runtime) or runtime.is_relative_to(recomp):
  raise ValueError('Separate detached directories under ROOT/build required')
 if (recomp/'pal-options-manifest.json').exists():raise ValueError('Keyboard must be planned inside the options transaction')
 header=(root/'src/pal_game/pal_keyboard_profile.h').read_bytes()
 header_hash=sha(header)
 if sha(header.replace(b'\r\n',b'\n'))!=HEADER_SHA256:raise ValueError('Keyboard helper source/version changed')
 relative=os.path.relpath(runtime,recomp).replace('\\','/')
 if any(c in relative for c in '\n\r";$'):raise ValueError('Unsupported runtime path')
 manifest=recomp/MANIFEST
 if manifest.is_symlink() or manifest.parent.resolve()!=manifest.parent:raise ValueError('Unsafe manifest path')
 support_inputs=runtime_support_inputs(runtime)
 field_enabled=b'pal_field_input_ledger.h' in (runtime/'src/host/host.cpp').read_bytes()
 field_header=(root/'src/pal_game/pal_field_input.h').read_bytes() if field_enabled else None
 field_hash=sha(field_header) if field_header is not None else None
 release_helpers={name:(root/'src/pal_game'/name).read_bytes() for name in ('pal_release_gate.h','pal_release_runtime.h')} if field_enabled else {}
 release_hashes={name:sha(data) for name,data in release_helpers.items()}
 if manifest.exists():
  old=json.loads(manifest.read_text())
  verify_runtime_support_manifest(old,runtime,support_inputs)
  if old.get('field_header_sha256')!=field_hash:raise ValueError('Field helper changed; regenerate')
  if old.get('release_helpers_sha256',{})!=release_hashes:raise ValueError('Scene continuity helpers changed; regenerate')
  if old.get('version')!=VERSION or old.get('header_sha256')!=header_hash or old.get('runtime')!=relative:raise ValueError('Keyboard source/version changed; regenerate')
  inventory=sorted(p.name for pattern in ('p_prog_*.cpp','p_true_*.cpp') for p in recomp.glob(pattern))
  if inventory!=old.get('generated_files'):raise ValueError('Generated source inventory changed; regenerate')
  outputs=old.get('outputs_sha256',{})
  required={'src/host/host.cpp','src/host/settings.cpp','src/host/launcher.cpp','src/host/settings.h','include/saturn/pal_keyboard_profile.h'}
  if field_enabled and not {'pal_field_input.h','pal_release_gate.h','pal_release_runtime.h'}.issubset(outputs.get('recomp',{})):raise ValueError('Incomplete field input output manifest')
  if not required.issubset(outputs.get('runtime',{})) or 'CMakeLists.txt' not in outputs.get('recomp',{}) or not all(any(n.startswith(prefix) and n.endswith('.cpp') for n in outputs.get('recomp',{})) for prefix in ('p_prog_','p_true_')):raise ValueError('Incomplete keyboard manifest')
  for group,base in [('recomp',recomp),('runtime',runtime)]:
   verified={**old.get('inputs_sha256',{}).get(group,{}),**outputs[group]}
   if group=='recomp' and not set(inventory).issubset(verified):raise ValueError('Incomplete generated source hashes')
   for name,expected in verified.items():
    p=base/name
    if '..' in Path(name).parts or p.resolve()!=p or not p.resolve().is_relative_to(base) or not p.is_file() or sha(p.read_bytes())!=expected:raise ValueError('Keyboard injected output changed; regenerate')
  return old
 if verify_only:raise ValueError('Missing keyboard manifest; regenerate before packaging')
 if not (runtime/'runtime.cmake').is_file():raise ValueError('Missing detached runtime')
 files=[*sorted(recomp.glob('p_prog_*.cpp')),*sorted(recomp.glob('p_true_*.cpp'))]
 paths=[*files,*(runtime/'src/host'/n for n in ('host.cpp','settings.cpp','launcher.cpp','settings.h')),recomp/'CMakeLists.txt',runtime/'runtime.cmake']
 if any(p.resolve()!=p or not p.resolve().is_relative_to(recomp if p.is_relative_to(recomp) else runtime) for p in paths):raise ValueError('Source symlink escapes detached tree')
 if any(p.stat().st_nlink!=1 for p in paths):raise ValueError('Hardlinked generated inputs are not writable')
 originals={p:p.read_bytes() for p in paths}
 originals.update(support_inputs)
 texts={p:originals[p].decode().replace('\r\n','\n') for p in files}
 rt={p:originals[p].decode().replace('\r\n','\n') for p in paths if p.is_relative_to(runtime)}
 changes=plan_keyboard(recomp,runtime,texts,rt,header)
 if field_enabled:
  field_output=recomp/'pal_field_input.h'
  if field_output.exists() or field_output.is_symlink():raise ValueError('Unexpected preexisting field helper; regenerate')
  from pal_field_input import plan_field_input
  staged={p:changes.get(p,originals[p]).decode().replace('\r\n','\n') for p in files}
  changes.update(plan_field_input(recomp,staged,field_header,release_helpers))
 helper=runtime/'include/saturn/pal_keyboard_profile.h'
 if helper.exists() or helper.is_symlink() or helper.parent.resolve()!=helper.parent or not helper.parent.resolve().is_relative_to(runtime):raise ValueError('Unexpected keyboard helper/path')
 cmake=recomp/'CMakeLists.txt';s=originals[cmake].decode().replace('\r\n','\n')
 pattern=r'  set\(SATURN_RUNTIME "[^"\n]+"\)'
 if len(re.findall(pattern,s))!=1:raise ValueError('Generated CMake runtime anchor changed')
 s=re.sub(pattern,'  set(SATURN_RUNTIME "${CMAKE_CURRENT_LIST_DIR}/'+relative+'")',s)
 guard=('get_filename_component(_pal_keyboard_rt "${SATURN_RUNTIME}" REALPATH)\n'
        'get_filename_component(_pal_keyboard_expected "${CMAKE_CURRENT_LIST_DIR}/'+relative+'" REALPATH)\n'
        'if(NOT _pal_keyboard_rt STREQUAL _pal_keyboard_expected)\n'
        '  message(FATAL_ERROR "Use the detached PAL keyboard runtime")\nendif()\n')
 changes[cmake]=once(s,'include(${SATURN_RUNTIME}/runtime.cmake)',guard+'include(${SATURN_RUNTIME}/runtime.cmake)').encode()
 if sorted(p.name for pattern in ('p_prog_*.cpp','p_true_*.cpp') for p in recomp.glob(pattern))!=sorted(p.name for p in files):raise ValueError('Generated source inventory changed while preparing injection')
 if (root/'src/pal_game/pal_keyboard_profile.h').read_bytes()!=header:raise ValueError('Keyboard helper changed while preparing injection')
 if field_enabled and (root/'src/pal_game/pal_field_input.h').read_bytes()!=field_header:raise ValueError('Field helper changed while preparing injection')
 if any((root/'src/pal_game'/name).read_bytes()!=data for name,data in release_helpers.items()):raise ValueError('Scene continuity helper changed while preparing injection')
 for p,data in originals.items():
  if p.resolve()!=p or p.stat().st_nlink!=1 or p.read_bytes()!=data:raise ValueError('Source changed while preparing keyboard injection')
 data={'version':VERSION,'runtime':relative,'header_sha256':header_hash,'field_header_sha256':field_hash,'release_helpers_sha256':release_hashes,'generated_files':sorted(p.name for p in files),'inputs_sha256':{},'outputs_sha256':{}}
 for group,base in [('recomp',recomp),('runtime',runtime)]:
  data['inputs_sha256'][group]={p.relative_to(base).as_posix():sha(v) for p,v in originals.items() if p.is_relative_to(base)}
  data['outputs_sha256'][group]={p.relative_to(base).as_posix():sha(v) for p,v in changes.items() if p.is_relative_to(base)}
 for p in [*changes,manifest]:
  if p.resolve()!=p or p.is_symlink():raise ValueError('Output path changed while preparing keyboard injection')
 for p,content in changes.items():p.write_bytes(content)
 manifest.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
 return data
