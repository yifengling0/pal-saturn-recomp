"""Compile production-generated keyboard binding/event/pad fragments without SDL.

Only platform/settings adapters are stubs. Keyboard routing and latch code are
extracted verbatim from the real planner output, using the real helper header.
This is a host adapter regression, not ROM or real-SDL acceptance.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

from keyboard_test_fixtures import HEADER, HOST, load_planner

HERE = Path(__file__).resolve().parent


class BattleItemHostTests(unittest.TestCase):
    def test_generated_host_routes_and_conflicts(self):
        compiler = shlex.split(os.environ.get('CXX', 'c++'))
        if not compiler or not shutil.which(compiler[0]):
            self.skipTest('A C++17 compiler is not installed')
        host = load_planner().host(HOST)
        declarations = host.split('static std::vector<std::pair<SDL_Scancode, uint16_t>> g_keys;', 1)[1]
        declarations = 'static std::vector<std::pair<SDL_Scancode, uint16_t>> g_keys;' + declarations.split('static void read_pads() {', 1)[0]
        read = host.split('static void read_pads() {', 1)[1].split('    synthetic_gamepad_and_touch_publish();', 1)[0]
        projection = host.split('        const bool pal_real_pad_input = b[s] || pad;', 1)[1].split('        g_buttons[s] = pad;', 1)[0]
        projection = '        const bool pal_real_pad_input = b[s] || pad;' + projection
        event = host.split('static void on_event(const SDL_Event& e) {', 1)[1].split('    switch (e.type)', 1)[0]
        menus = host.split('static void menu_close() {', 1)[1].split('static bool escape_is_a_button()', 1)[0]
        menus = 'static void menu_close() {' + menus
        escape = '[[maybe_unused]] static bool escape_is_a_button()' + host.split('static bool escape_is_a_button()',1)[1].split('static void on_event(',1)[0]
        key_route = '#ifdef _WIN32' + host.split('static void on_event(',1)[1].split('#ifdef _WIN32',1)[1].split('#endif',1)[0] + '#endif\n'
        source = (HERE / 'battle_item_host_prefix.cpp').read_text() + declarations
        source += '\nstatic uint16_t read_bits() { uint16_t b[1]{};\n' + read + '\nconst int s=0; uint16_t pad=b[0] | real_pad_bits;\n' + projection + '\nreturn pad; }\n'
        source += menus + escape + '\nstatic bool requests_host_menu(int k) {\n' + key_route + '\nreturn back; }\n'
        source += '\nstatic void on_event(const SDL_Event& e) {\n' + event + '\n}\n'
        source += (HERE / 'battle_item_host_suffix.cpp').read_text()
        with tempfile.TemporaryDirectory(prefix='battle item host ') as td:
            td = Path(td)
            shutil.copyfile(HEADER, td / 'pal_keyboard_profile.h')
            (td / 'test.cpp').write_text(source)
            exe = td / ('test.exe' if os.name == 'nt' else 'test')
            static = ['-static'] if os.name == 'nt' else []
            result = subprocess.run([*compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                     '-I' + str(td), str(td / 'test.cpp'), *static, '-o', str(exe)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS:', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
