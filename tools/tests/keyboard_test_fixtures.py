"""Hand-written planner fixtures. No ROM, extracted file, or generated guest body.

The text contains only invented guest statements plus public planner anchors.
Fixture SHA allowlists replace production allowlists only inside mock contexts.
Runtime snippets intentionally need not compile; the separate helper tests do.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PLANNER = Path(os.environ.get('PAL_KEYBOARD_PLANNER', ROOT / 'tools/pal_keyboard_profile.py'))
HEADER = Path(os.environ.get('PAL_KEYBOARD_HEADER', ROOT / 'src/pal_game/pal_keyboard_profile.h'))

def load_planner():
    spec = importlib.util.spec_from_file_location('keyboard_planner_under_test', PLANNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def digest(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()

def function(pc, body='    synthetic_guest_step(c);\n'):
    return f'void f_{pc}(SH2Context& c) {{\n{body}}}\n'

def wrap(module, body):
    return f'// Synthetic module, not an extracted guest source.\nnamespace {module} {{\n\n{body}\n}}  // namespace {module}\n'

HOST = '''// Hand-written host anchor fixture.
static std::string g_settings_path, g_settings_text;
static void load_settings(const std::string& named) {
        bool found = false;
        std::string text = settings_load(path, found);
        if (!found) {
            synthetic_missing_defaults();
        } else {
            synthetic_parse(text);
        }
}
bool host_settings_save() {
    return synthetic_save();
}
static std::vector<std::pair<SDL_Scancode, uint16_t>> g_keys;
static void bindings() {
    g_keys.clear();
    for (auto& b : kSaturn)
        for (int k : names(g_settings, "keyboard", b.name, ignored))
            g_keys.push_back({(SDL_Scancode)k, b.bit});
}
static void read_pads() {
    for (auto [key, bit] : g_keys)
        if (k[key] && !(alt && key == SDL_SCANCODE_RETURN)) b[0] |= bit;
}
static void menu_close() {
    existing_close_hook();
}
static void menu_open() {
    existing_open_hook();
}
static bool escape_is_a_button() {
    return false;
}
static void on_event(const SDL_Event& e) {
    switch (e.type) {
    case SDL_EVENT_KEY_DOWN:
        bool back = k == SDL_SCANCODE_AC_BACK || (k == SDL_SCANCODE_ESCAPE && !escape_is_a_button());
        break;
    }
}
'''
SETTINGS = '''// Hand-written settings anchor fixture.
static const char defaults[] = R"(
[keyboard]
a = Z
; Every gamepad's buttons
[gamepad]
a = a
)";
static const auto choices = { {"controls", {"auto", "on", "off"}}, };
void Settings::read(const std::string& text, std::vector<std::string>& problems) {
    synthetic_read(text, problems);
}
std::string settings_load(const std::string& path, bool& found) {
    return synthetic_load(path, found);
}
'''
SETTINGS_HEADER = '#pragma once\n// Synthetic Settings declarations.\n'
LAUNCHER = '''// Hand-written launcher anchor fixture.
        std::string name;
        if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {
            if (e.key.scancode == SDL_SCANCODE_ESCAPE) { binding_.clear(); return true; }
            if (binding_section_ == "keyboard") name = SDL_GetScancodeName(e.key.scancode);
        } else if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN && binding_section_ == "gamepad") {
            name = SDL_GetGamepadStringForButton((SDL_GamepadButton)e.gbutton.button);
        } else if (e.type == SDL_EVENT_GAMEPAD_AXIS_MOTION && binding_section_ == "gamepad" &&
        synthetic_remainder) {}

    void controls() {
        ImGui::SeparatorText("Controls");
        if (!binding_.empty())
            ImGui::TextColored(ImVec4(1, 0.9f, 0.4f, 1), "Press the %s for %s (Esc cancels)",
                               binding_section_ == "keyboard" ? "key" : "gamepad button", label(binding_));
        else
            ImGui::TextWrapped("Choose a binding, then press its new key or button. Every gamepad uses these.");
        if (ImGui::BeginTable("controls", 3, ImGuiTableFlags_SizingStretchSame)) {
            ImGui::TableSetupColumn("Saturn");
            ImGui::TableSetupColumn("Keyboard");
                ImGui::TableNextRow();
                ImGui::TableNextColumn();
                ImGui::TextUnformatted(b.label);
                for (const char* section : {"keyboard", "gamepad"}) {
                    ImGui::TableNextColumn();
                    std::string id = set_.get(section, b.key) + "##" + section + b.key;
                    bool waiting = binding_ == b.key && binding_section_ == section;
                    synthetic_binding_button();
                }
        }
        if (ImGui::Button("Default controls")) {
            Settings defaults;
            for (const char* section : {"keyboard", "gamepad"})
                for (auto& key : defaults.keys(section)) set_.set(section, key, defaults.get(section, key));
            save();
        }
    }
'''

class Fixture:
    def __init__(self, base=None):
        base = Path(base) if base is not None else Path(tempfile.gettempdir()) / 'PAL synthetic 空格'
        self.root = base
        self.recomp = base / 'build/keyboard fixture/recomp'
        self.runtime = base / 'build/keyboard fixture/runtime'
        self.functions = {
            '06020040': function('06020040'),
            '06021F14': function('06021F14'),
            '06026F90': function('06026F90', '    pal_input_clear();\n    synthetic_guest_step(c);\n'),
            '06026D84': function('06026D84', ''.join(
                f'    synthetic_guest_step(c); // {pc} synthetic instruction\n'
                for pc in ('06026E1C', '06026E84', '06026E90', '06026EB8', '06026F44', '06026F52')) + '    SH2_POLL(c);\n'),
            '0604A5B8': function('0604A5B8', '    synthetic_guest_step(c); // 0604A8C0 synthetic instruction\n'),
            '060516B4': function('060516B4'),
            '06020058': function('06020058'),
            '0604A0BC': function('0604A0BC'),
        }
        self.paths = {pc: self.recomp / f'{"p_true" if pc == "06020058" else "p_prog"}_{i + 90:03}.cpp'
                      for i, pc in enumerate(self.functions)}
        self.texts = {self.paths[pc]: wrap('p_true' if pc == '06020058' else 'p_prog', text)
                      for pc, text in self.functions.items()}
        self.rt = {self.runtime / 'src/host' / name: text for name, text in
                   [('host.cpp', HOST), ('settings.cpp', SETTINGS), ('launcher.cpp', LAUNCHER), ('settings.h', SETTINGS_HEADER)]}
        self.header = HEADER.read_bytes()

    @contextmanager
    def hashes(self, module):
        # Only fake source inputs are blessed. The real helper digest is never patched.
        with patch.object(module, 'HARMONY_RUNTIME_HELPERS', {}, create=True), \
             patch.object(module, 'FUNCTION_HASHES', {pc: [digest(text)] for pc, text in self.functions.items()}), \
             patch.object(module, 'RUNTIME_HASHES', {p.name: [digest(text)] for p, text in self.rt.items()}):
            yield

    def plan(self, module):
        return module.plan_keyboard(self.recomp, self.runtime, self.texts, self.rt, self.header)

    def replace_function(self, pc, body):
        old = self.functions[pc]
        self.functions[pc] = body
        self.texts[self.paths[pc]] = self.texts[self.paths[pc]].replace(old, body)
