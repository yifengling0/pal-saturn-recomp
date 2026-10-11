"""Pure PC98 mapping planner v1. No file I/O, no edge queue, no timing options.

Call at the LAST in-memory planning stage (after optional precise/paired changes),
then commit its returned changes in the caller's one transaction/manifest.
Ordinary builds call the same function on the verified five-patch runtime.
The caller owns path resolution, source reads, race guards, backup/rollback,
manifest idempotence, and CMake runtime selection. Repeated raw planning fails.
"""
from pathlib import Path
import hashlib,re
VERSION='pal-keyboard-profile-v1-mapping-2'
def sha(s):return hashlib.sha256(s.encode() if isinstance(s,str) else s).hexdigest()
RUNTIME_HASHES = {'host.cpp': ['6b82aaa5f9720e3ad9a53db35e6dda8ef08198d4dbcacf7f3f0f6b25f2a9518d', '9af5f2ac245114cb7cdf858c69a90ecb0c217a29f423c9168c353558bf0222a4'], 'settings.cpp': ['4da2c93a0eec58ca861c972076961eaf4d64d4ecb471b4d29d94af73f1705b66'], 'launcher.cpp': ['23d65e3b6f854823fd33a1f3b1373584d22e98b9edf247125458648fad863e32']}
FUNCTION_HASHES = {'06020040': ['49fc15d214cc14ad85134d3301ce577f699d38aec8301287d632dd5b545bad7c'], '06026D84': ['9e83b5975b9f141c3d0e22f15907be2ada11b74aab7237444cde410ae4fefaaa', 'f04a09eb1154c18fcdb61a95fd4f3f945106da5daccf7eec6131edf88800e8a8'], '06021F14': ['1a72d209543cdd95d863b4e62b28c7639a24c2098c855279d2a97075203722e0'], '06026F90': ['33b311616b04e42b7e6cb85366ff11f58e1ecc4a1573fd5b9d7b8527cb2fcb75', '677f5eb849f6f0f3731cf35a0292d91dacef58e127de7d427fb659101b56e056'], '0604A5B8': ['38a41b3879208ad03418cbe48ed1efeb1888129062f385fc362955afd8e0ce50'], '060516B4': ['8d243239da6d34c6b188603ca3108a13b9984f855348edf66a04759c5a93b60d'], '06020058': ['9548908855627449ef75ff2a63a87d8083fc953294231d447073e05bec6beca7']}
HEADER_SHA256 = '3cb6b4a9019d341b3a38eecd14c3c3eae3a613b32e7fd07afe1ec48efca5d9e3'
LAUNCHER_HUNKS = [('        std::string name;\n        if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {\n            if (e.key.scancode == SDL_SCANCODE_ESCAPE) { binding_.clear(); return true; }\n            if (binding_section_ == "keyboard") name = SDL_GetScancodeName(e.key.scancode);\n        } else if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN && binding_section_ == "gamepad") {\n            name = SDL_GetGamepadStringForButton((SDL_GamepadButton)e.gbutton.button);\n        } else if (e.type == SDL_EVENT_GAMEPAD_AXIS_MOTION && binding_section_ == "gamepad" &&\n', '        std::string name;\n        if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {\n            if (e.key.scancode == SDL_SCANCODE_ESCAPE) { binding_.clear(); return true; }\n            if (binding_section_.rfind("keyboard", 0) == 0) name = SDL_GetScancodeName(e.key.scancode);\n        } else if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN && binding_section_ == "gamepad") {\n            name = SDL_GetGamepadStringForButton((SDL_GamepadButton)e.gbutton.button);\n        } else if (e.type == SDL_EVENT_GAMEPAD_AXIS_MOTION && binding_section_ == "gamepad" &&\n'), ('\n    void controls() {\n        ImGui::SeparatorText("Controls");\n        if (!binding_.empty())\n            ImGui::TextColored(ImVec4(1, 0.9f, 0.4f, 1), "Press the %s for %s (Esc cancels)",\n                               binding_section_ == "keyboard" ? "key" : "gamepad button", label(binding_));\n        else\n            ImGui::TextWrapped("Choose a binding, then press its new key or button. Every gamepad uses these.");\n        if (ImGui::BeginTable("controls", 3, ImGuiTableFlags_SizingStretchSame)) {\n            ImGui::TableSetupColumn("Saturn");\n            ImGui::TableSetupColumn("Keyboard");\n', '\n    void controls() {\n        ImGui::SeparatorText("Controls");\n        const bool pc = set_.get("controls", "keyboard_profile") == "pc98";\n        if (ImGui::RadioButton("PC98 keyboard", pc)) {\n            binding_.clear(); set_.set("controls", "keyboard_profile", "pc98"); save();\n        }\n        ImGui::SameLine();\n        if (ImGui::RadioButton("Saturn keyboard", !pc)) {\n            binding_.clear(); set_.set("controls", "keyboard_profile", "saturn"); save();\n        }\n        ImGui::TextWrapped("PC98 F10: host menu. PC98: Enter confirms/interacts; Esc opens the game menu or cancels. Gamepad bindings are independent.");\n        const char* keyboard_section = pc ? "keyboard pc98" : "keyboard";\n        if (pc) {\n            for (const char* key : {"confirm", "menu_cancel"}) {\n                ImGui::TextUnformatted(key == std::string("confirm") ? "Confirm / interact" : "Game menu / cancel");\n                ImGui::SameLine();\n                std::string id = set_.get(keyboard_section, key) + "##semantic" + key;\n                if (ImGui::Button(id.c_str()) && binding_.empty()) { binding_ = key; binding_section_ = keyboard_section; }\n            }\n        }\n        if (!binding_.empty())\n            ImGui::TextColored(ImVec4(1, 0.9f, 0.4f, 1), "Press the %s for %s (Esc cancels)",\n                               binding_section_.rfind("keyboard", 0) == 0 ? "key" : "gamepad button", label(binding_));\n        else\n            ImGui::TextWrapped("Choose a binding, then press its new key or button. PC98 reserves F10. Saturn keeps custom F10 bindings. Esc cancels binding capture.");\n        if (ImGui::BeginTable("controls", 3, ImGuiTableFlags_SizingStretchSame)) {\n            ImGui::TableSetupColumn("Saturn");\n            ImGui::TableSetupColumn("Keyboard");\n'), ('                ImGui::TableNextRow();\n                ImGui::TableNextColumn();\n                ImGui::TextUnformatted(b.label);\n                for (const char* section : {"keyboard", "gamepad"}) {\n                    ImGui::TableNextColumn();\n                    std::string id = set_.get(section, b.key) + "##" + section + b.key;\n                    bool waiting = binding_ == b.key && binding_section_ == section;\n', '                ImGui::TableNextRow();\n                ImGui::TableNextColumn();\n                ImGui::TextUnformatted(b.label);\n                for (const char* section : {keyboard_section, "gamepad"}) {\n                    ImGui::TableNextColumn();\n                    std::string id = set_.get(section, b.key) + "##" + section + b.key;\n                    bool waiting = binding_ == b.key && binding_section_ == section;\n'), ('        }\n        if (ImGui::Button("Default controls")) {\n            Settings defaults;\n            for (const char* section : {"keyboard", "gamepad"})\n                for (auto& key : defaults.keys(section)) set_.set(section, key, defaults.get(section, key));\n            save();\n        }\n', '        }\n        if (ImGui::Button("Default controls")) {\n            Settings defaults;\n            for (const char* section : {keyboard_section, "gamepad"})\n                for (auto& key : defaults.keys(section)) set_.set(section, key, defaults.get(section, key));\n            save();\n        }\n')]


def once(s,a,b):
 if s.count(a)!=1:raise ValueError(f'expected 1 got {s.count(a)}: {a[:100]}')
 return s.replace(a,b,1)

def settings(s):
 s=once(s,'[keyboard]\n','[controls]\n; PAL_KEYBOARD_PROFILE_V1 (context-latched mapping; no edge queue)\n; pc98: Enter confirms, Escape opens the game menu or cancels. F10 is the host menu.\n; saturn: use the original [keyboard] map. Physical gamepads always retain their own map.\nkeyboard_profile = pc98\n\n[keyboard]\n')
 anchor='; Every gamepad\'s buttons'
 new='''; PC98 keyboard bindings. Confirm/menu_cancel select one context-appropriate Saturn button.
; They are latched on key-down until release; holding Escape never opens then closes a menu.
[keyboard pc98]
up = Up
down = Down
left = Left
right = Right
start = Tab
a = Z
b = X
c = C
x = A
y = S
z = D
l = Q
r = W
confirm = Return, Keypad Enter, Space
menu_cancel = Escape

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
static std::vector<SDL_Scancode> g_confirm_keys, g_cancel_keys;
static pal_keyboard::PressLatch g_pc_press;
static bool pc_keyboard() { return g_settings.get("controls", "keyboard_profile") == "pc98"; }
static bool semantic_key(SDL_Scancode key) {
    return std::find(g_confirm_keys.begin(), g_confirm_keys.end(), key) != g_confirm_keys.end() ||
           std::find(g_cancel_keys.begin(), g_cancel_keys.end(), key) != g_cancel_keys.end();
}''')
 s=once(s,'    g_keys.clear();\n    for (auto& b : kSaturn)','''    g_keys.clear();
    g_confirm_keys.clear(); g_cancel_keys.clear(); g_pc_press.block();
    const std::string section = pc_keyboard() ? "keyboard pc98" : "keyboard";
    for (auto& b : kSaturn)''')
 s=once(s,'names(g_settings, "keyboard", b.name','names(g_settings, section, b.name')
 marker='            g_keys.push_back({(SDL_Scancode)k, b.bit});\n}'
 s=once(s,marker,'''            g_keys.push_back({(SDL_Scancode)k, b.bit});
    if (pc_keyboard()) {
        auto scancode = [](const std::string& n) { auto c=SDL_GetScancodeFromName(n.c_str()); return c==SDL_SCANCODE_UNKNOWN ? -1 : (int)c; };
        for (int k : names(g_settings, section, "confirm", scancode)) g_confirm_keys.push_back((SDL_Scancode)k);
        for (int k : names(g_settings, section, "menu_cancel", scancode)) g_cancel_keys.push_back((SDL_Scancode)k);
    }
}''')
 s=once(s,'        if (k[key] && !(alt && key == SDL_SCANCODE_RETURN)) b[0] |= bit;','''        if (!semantic_key(key) && key != SDL_SCANCODE_F10 && k[key] &&
            SDL_GetKeyboardFocus() == g_win && !(alt && key == SDL_SCANCODE_RETURN)) b[0] |= bit;
    if (SDL_GetKeyboardFocus() == g_win) {
        for (auto key : g_confirm_keys) b[0] |= g_pc_press.read(key);
        for (auto key : g_cancel_keys) b[0] |= g_pc_press.read(key);
    }''')
 s=once(s,'static void menu_close() {','static void menu_close() {\n    g_pc_press.block();')
 s=once(s,'static void menu_open() {','static void menu_open() {\n    g_pc_press.block();')
 s=once(s,'static bool escape_is_a_button() {','static bool escape_is_a_button() {\n    if (semantic_key(SDL_SCANCODE_ESCAPE)) return true;')
 s=once(s,'static void on_event(const SDL_Event& e) {','''static void on_event(const SDL_Event& e) {
    const auto wid = SDL_GetWindowID(g_win);
    if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID == wid) g_pc_press.block();
    if (e.type == SDL_EVENT_KEY_UP && e.key.windowID == wid) g_pc_press.up(e.key.scancode);
    if (e.type == SDL_EVENT_KEY_DOWN && e.key.windowID == wid && semantic_key(e.key.scancode)) {
        sync_pc_boundary();  // Retire only old presses before accepting a new edge.
        const bool cancel = std::find(g_cancel_keys.begin(), g_cancel_keys.end(), e.key.scancode) != g_cancel_keys.end();
        g_pc_press.down(e.key.scancode, cancel ? pal_keyboard::context.cancel : pal_keyboard::context.confirm,
                        e.key.repeat, SDL_GetKeyboardFocus() == g_win,
                        g_menu_open || (e.key.mod & SDL_KMOD_ALT));
    }''')
 s=once(s,'        bool back = k == SDL_SCANCODE_AC_BACK || (k == SDL_SCANCODE_ESCAPE && !escape_is_a_button());','''        if (e.key.windowID != wid || SDL_GetKeyboardFocus() != g_win) break;
        bool back = k == SDL_SCANCODE_F10 || k == SDL_SCANCODE_AC_BACK ||
                    (k == SDL_SCANCODE_ESCAPE && (g_menu_open || !escape_is_a_button()));''')
 s=s.replace('Android\'s Back, Escape, a','Android\'s Back, F10 (or unbound Escape), a')
 s=once(s,'static pal_keyboard::PressLatch g_pc_press;','static pal_keyboard::PressLatch g_pc_press;\nstatic uint64_t g_pc_boundary = 0;\nstatic void sync_pc_boundary() {\n    if (g_pc_boundary != pal_keyboard::boundary) { g_pc_boundary = pal_keyboard::boundary; g_pc_press.block(); }\n}')
 s=once(s,'static void read_pads() {','static void read_pads() {\n    sync_pc_boundary();')
 s=s.replace('e.window.windowID == wid) g_pc_press.block();','e.window.windowID == wid) g_pc_press.reset();')
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
  if sha(s) not in RUNTIME_HASHES[n]:raise ValueError('Runtime source/version changed: '+n)
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
 changed.add(scope(texts,'0604A5B8',lambda s:instruction(s,'0604A8C0','pal_keyboard::ui(ld16(c.r[14]+30)==13);')))
 entry('060516B4','pal_keyboard::ui((uint16_t)c.r[4] == 1);')
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

def prepare_keyboard(recomp, runtime, root):
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
 if manifest.exists():
  old=json.loads(manifest.read_text())
  if old.get('version')!=VERSION or old.get('header_sha256')!=header_hash or old.get('runtime')!=relative:raise ValueError('Keyboard source/version changed; regenerate')
  inventory=sorted(p.name for pattern in ('p_prog_*.cpp','p_true_*.cpp') for p in recomp.glob(pattern))
  if inventory!=old.get('generated_files'):raise ValueError('Generated source inventory changed; regenerate')
  outputs=old.get('outputs_sha256',{})
  required={'src/host/host.cpp','src/host/settings.cpp','src/host/launcher.cpp','src/host/settings.h','include/saturn/pal_keyboard_profile.h'}
  if not required.issubset(outputs.get('runtime',{})) or 'CMakeLists.txt' not in outputs.get('recomp',{}) or not all(any(n.startswith(prefix) and n.endswith('.cpp') for n in outputs.get('recomp',{})) for prefix in ('p_prog_','p_true_')):raise ValueError('Incomplete keyboard manifest')
  for group,base in [('recomp',recomp),('runtime',runtime)]:
   verified={**old.get('inputs_sha256',{}).get(group,{}),**outputs[group]}
   if group=='recomp' and not set(inventory).issubset(verified):raise ValueError('Incomplete generated source hashes')
   for name,expected in verified.items():
    p=base/name
    if '..' in Path(name).parts or p.resolve()!=p or not p.resolve().is_relative_to(base) or not p.is_file() or sha(p.read_bytes())!=expected:raise ValueError('Keyboard injected output changed; regenerate')
  return old
 if not (runtime/'runtime.cmake').is_file():raise ValueError('Missing detached runtime')
 files=[*sorted(recomp.glob('p_prog_*.cpp')),*sorted(recomp.glob('p_true_*.cpp'))]
 paths=[*files,*(runtime/'src/host'/n for n in ('host.cpp','settings.cpp','launcher.cpp','settings.h')),recomp/'CMakeLists.txt',runtime/'runtime.cmake']
 if any(p.resolve()!=p or not p.resolve().is_relative_to(recomp if p.is_relative_to(recomp) else runtime) for p in paths):raise ValueError('Source symlink escapes detached tree')
 if any(p.stat().st_nlink!=1 for p in paths):raise ValueError('Hardlinked generated inputs are not writable')
 originals={p:p.read_bytes() for p in paths}
 texts={p:originals[p].decode().replace('\r\n','\n') for p in files}
 rt={p:originals[p].decode().replace('\r\n','\n') for p in paths if p.is_relative_to(runtime)}
 changes=plan_keyboard(recomp,runtime,texts,rt,header)
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
 for p,data in originals.items():
  if p.resolve()!=p or p.stat().st_nlink!=1 or p.read_bytes()!=data:raise ValueError('Source changed while preparing keyboard injection')
 data={'version':VERSION,'runtime':relative,'header_sha256':header_hash,'generated_files':sorted(p.name for p in files),'inputs_sha256':{},'outputs_sha256':{}}
 for group,base in [('recomp',recomp),('runtime',runtime)]:
  data['inputs_sha256'][group]={p.relative_to(base).as_posix():sha(v) for p,v in originals.items() if p.is_relative_to(base)}
  data['outputs_sha256'][group]={p.relative_to(base).as_posix():sha(v) for p,v in changes.items() if p.is_relative_to(base)}
 for p in [*changes,manifest]:
  if p.resolve()!=p or p.is_symlink():raise ValueError('Output path changed while preparing keyboard injection')
 for p,content in changes.items():p.write_bytes(content)
 manifest.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
 return data
