"""Portable synthetic keyboard planner tests; no game assets, SDL, or build tree.

Production defaults: tools/pal_keyboard_profile.py and src/pal_game/*.h.
For a private prototype set PAL_KEYBOARD_PLANNER and PAL_KEYBOARD_HEADER.
"""
import copy
from pathlib import Path
from types import MappingProxyType
import unittest
from unittest.mock import patch

from keyboard_test_fixtures import Fixture, HEADER, digest, function, load_planner, wrap

m = load_planner()

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.patches = self.f.hashes(m)
        self.patches.__enter__()
        self.addCleanup(self.patches.__exit__, None, None, None)

    def plan(self):
        return self.f.plan(m)

    def unchanged_on_error(self, pattern='.'):
        before = copy.deepcopy((self.f.texts, self.f.rt, self.f.header))
        with self.assertRaisesRegex((ValueError, TypeError), pattern):
            self.plan()
        self.assertEqual((self.f.texts, self.f.rt, self.f.header), before)

    def guest(self, output, pc):
        return output[self.f.paths[pc]].decode()

    def test_success_returns_bytes_without_mutating_readonly_inputs(self):
        before = copy.deepcopy((self.f.texts, self.f.rt, self.f.header))
        self.f.texts = MappingProxyType(self.f.texts)
        self.f.rt = MappingProxyType(self.f.rt)
        out = self.plan()
        self.assertEqual((self.f.texts, self.f.rt, self.f.header), before)
        self.assertEqual(set(out), set(self.f.texts) | set(self.f.rt) |
                         {self.f.runtime / 'include/saturn/pal_keyboard_profile.h'})
        self.assertTrue(all(isinstance(p, Path) and isinstance(b, bytes) for p, b in out.items()))
        self.assertEqual(out[self.f.runtime / 'include/saturn/pal_keyboard_profile.h'], self.f.header)

    def test_plan_performs_no_file_io_or_path_resolution(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('Pure planner attempted filesystem access')
        with patch('builtins.open', forbidden), patch.object(Path, 'open', forbidden), \
             patch.object(Path, 'read_text', forbidden), patch.object(Path, 'read_bytes', forbidden), \
             patch.object(Path, 'write_text', forbidden), patch.object(Path, 'write_bytes', forbidden), \
             patch.object(Path, 'resolve', forbidden), patch.object(Path, 'stat', forbidden):
            self.plan()

    def test_new_key_after_boundary_is_not_discarded_by_later_pad_read(self):
        host = self.plan()[self.f.runtime / 'src/host/host.cpp'].decode()
        event = host.split('static void on_event(const SDL_Event& e) {', 1)[1]
        self.assertLess(event.index('sync_pc_boundary();'), event.index('g_pc_press.down('))
        self.assertIn('static void read_pads() {\n    sync_pc_boundary();', host)
        self.assertIn('g_pc_boundary = pal_keyboard::boundary; g_pc_press.block();', host)

    def test_battle_scope_is_only_in_main_command_menu(self):
        out = self.plan()
        hook = b'pal_keyboard::BattleCommandsScope pal_battle_commands(ld16(0x060768ECu) == 0xFFFFu);'
        self.assertEqual(sum(value.count(hook) for value in out.values()), 1)
        self.assertIn(hook, out[self.f.paths['0604A0BC']])
        self.assertNotIn(hook, out[self.f.paths['0604A5B8']])

    def test_battle_shortcuts_respect_existing_binding_priorities(self):
        out = self.plan()[self.f.runtime / 'src/host/host.cpp'].decode()
        self.assertIn('!native_bound && !semantic_key(key)', out)
        self.assertIn('add_battle_keys("strongest", g_strongest_keys);', out)
        self.assertIn('add_battle_keys("repeat", g_repeat_keys);', out)
        self.assertIn('repeat_command ? pal_keyboard::Repeat : pal_keyboard::Strongest', out)
        self.assertIn('g_battle_press.up(e.key.scancode)', out)
        self.assertEqual(out.count('g_pc_press.block(); g_battle_press.block();'), 2)

    def test_real_helper_digest_is_pinned(self):
        self.assertEqual(digest(HEADER.read_bytes().replace(b'\r\n', b'\n')), m.HEADER_SHA256)

    def test_header_mutation_rejected(self):
        self.f.header += b'\n// unreviewed helper\n'
        self.unchanged_on_error('helper|[Hh]eader')

    def test_bad_each_runtime_hash_is_rejected_without_input_mutation(self):
        for path in self.f.rt:
            with self.subTest(source=path.name):
                old = self.f.rt[path]
                self.f.rt[path] += '\n// unreviewed source\n'
                self.unchanged_on_error('Runtime source/version')
                self.f.rt[path] = old

    def test_bad_each_guest_hash_is_rejected_without_input_mutation(self):
        for pc, path in self.f.paths.items():
            with self.subTest(pc=pc):
                old = self.f.texts[path]
                self.f.texts[path] = old.replace('SH2Context& c) {\n', 'SH2Context& c) {\n    changed();\n')
                self.unchanged_on_error('Guest function changed')
                self.f.texts[path] = old

    def test_missing_each_runtime_input_rejected(self):
        for path in list(self.f.rt):
            with self.subTest(source=path.name):
                old = self.f.rt.pop(path)
                self.unchanged_on_error('Missing runtime input')
                self.f.rt[path] = old

    def test_missing_each_guest_function_rejected(self):
        for pc, path in self.f.paths.items():
            with self.subTest(pc=pc):
                old = self.f.texts.pop(path)
                self.unchanged_on_error(pc)
                self.f.texts[path] = old

    def test_raw_repeat_is_rejected(self):
        out = self.plan()
        for path in self.f.texts:
            self.f.texts[path] = out[path].decode()
        for path in self.f.rt:
            self.f.rt[path] = out[path].decode()
        self.unchanged_on_error('Already injected')

    def test_markers_reject_already_injected_or_partial_guest(self):
        path = self.f.paths['06020040']
        old = self.f.texts[path]
        for marker in ('pal_keyboard::field();', '#include <saturn/pal_keyboard_profile.h>'):
            with self.subTest(marker=marker):
                self.f.texts[path] = marker + '\n' + old
                self.unchanged_on_error('Already injected')
        self.f.texts[path] = old

    def test_all_checks_precede_result_even_late_anchor_failure(self):
        # Bless the synthetic changed function so this exercises final anchoring,
        # after earlier guest/runtime transformations would already have occurred.
        pc = '0604A5B8'
        self.f.replace_function(pc, self.f.functions[pc].replace('// 0604A8C0 ', '// DEADBEEF '))
        with self.f.hashes(m):
            self.unchanged_on_error('0604A8C0')

    def test_duplicate_instruction_inside_target_rejected(self):
        pc = '0604A5B8'
        self.f.replace_function(pc, function(pc, '    synthetic(); // 0604A8C0 synthetic\n' * 2))
        with self.f.hashes(m):
            self.unchanged_on_error('0604A8C0')

    def test_duplicate_instruction_in_unrelated_function_is_untouched(self):
        path = self.f.recomp / 'p_prog_777.cpp'
        self.f.texts[path] = wrap('p_prog', function('06000001', '    ignored(); // 0604A8C0 synthetic\n'))
        out = self.plan()
        self.assertNotIn(path, out)
        self.assertEqual(sum(data.count(b'pal_keyboard::ui(ld16(c.r[14]+30)==13);') for data in out.values()), 1)

    def test_duplicate_function_in_target_module_rejected(self):
        self.f.texts[self.f.recomp / 'p_prog_999.cpp'] = wrap('p_prog', self.f.functions['06026D84'])
        self.unchanged_on_error('06026D84')

    def test_duplicate_function_in_one_source_rejected(self):
        pc = '06026D84'
        self.f.texts[self.f.paths[pc]] = wrap('p_prog', self.f.functions[pc] * 2)
        self.unchanged_on_error(pc)

    def test_prog_address_collision_in_true_is_ignored(self):
        path = self.f.recomp / 'p_true_999.cpp'
        self.f.texts[path] = wrap('p_true', self.f.functions['06026D84'])
        out = self.plan()
        self.assertNotIn(path, out)
        self.assertIn(b'pal_keyboard::field();', out[self.f.paths['06026D84']])

    def test_true_address_collision_in_prog_is_ignored(self):
        path = self.f.recomp / 'p_prog_999.cpp'
        self.f.texts[path] = wrap('p_prog', self.f.functions['06020058'])
        out = self.plan()
        self.assertNotIn(path, out)
        self.assertIn(b'pal_keyboard::boot();', out[self.f.paths['06020058']])

    def test_true_hook_cannot_be_satisfied_by_prog_module(self):
        source = self.f.texts.pop(self.f.paths['06020058'])
        self.f.texts[self.f.recomp / 'p_prog_999.cpp'] = source.replace('p_true', 'p_prog')
        self.unchanged_on_error('06020058|TRUE|true')

    def test_prog_hook_cannot_be_satisfied_by_true_module(self):
        source = self.f.texts.pop(self.f.paths['06026D84'])
        self.f.texts[self.f.recomp / 'p_true_999.cpp'] = source.replace('p_prog', 'p_true')
        self.unchanged_on_error('06026D84|PROG|prog')

    def test_precise_hook_preserved_and_guest_poll_count_unchanged(self):
        out = self.plan()
        self.assertEqual(self.guest(out, '06026F90').count('pal_input_clear();'), 1)
        for pc, path in self.f.paths.items():
            self.assertEqual(out[path].count(b'SH2_POLL'), self.f.texts[path].count('SH2_POLL'))
            self.assertEqual(out[path].count(b'#include <saturn/pal_keyboard_profile.h>'), 1)
        self.assertLess(self.guest(out, '06026F90').index('pal_keyboard::clear();'),
                        self.guest(out, '06026F90').index('pal_input_clear();'))

    def test_multiple_target_functions_in_one_module_source(self):
        prog = self.f.recomp / 'p_prog_000.cpp'
        true = self.f.paths['06020058']
        self.f.texts = {prog: wrap('p_prog', '\n'.join(text for pc, text in self.f.functions.items() if pc != '06020058')),
                        true: self.f.texts[true]}
        out = self.plan()
        self.assertEqual(out[prog].count(b'#include <saturn/pal_keyboard_profile.h>'), 1)
        self.assertIn(b'pal_keyboard::ui((uint16_t)c.r[4] == 1);', out[prog])

    def test_expected_context_hooks_and_order(self):
        out = self.plan()
        for pc in ('06020040', '06020058'):
            self.assertIn('pal_keyboard::boot();', self.guest(out, pc))
        self.assertIn('pal_keyboard::ui(true);', self.guest(out, '06021F14'))
        self.assertIn('pal_keyboard::ui((uint16_t)c.r[4] == 1);', self.guest(out, '060516B4'))
        field = self.guest(out, '06026D84')
        self.assertEqual(field.count('pal_keyboard::field();'), 7)
        self.assertEqual(field.count('pal_keyboard::ui();'), 6)
        for pc in ('06026E1C', '06026E84', '06026E90', '06026EB8', '06026F44', '06026F52'):
            self.assertIn(f'pal_keyboard::ui();\n    synthetic_guest_step(c); // {pc} synthetic instruction\n    pal_keyboard::field();', field)

    def test_lf_and_crlf_inputs_are_equivalent(self):
        baseline = self.plan()
        self.f.texts = {p: s.replace('\n', '\r\n') for p, s in self.f.texts.items()}
        self.f.rt = {p: s.replace('\n', '\r\n') for p, s in self.f.rt.items()}
        out = self.plan()
        self.assertEqual(out, baseline)

    def test_crlf_header_is_accepted_and_preserved_as_supplied(self):
        self.f.header = self.f.header.replace(b'\n', b'\r\n')
        out = self.plan()
        self.assertEqual(out[self.f.runtime / 'include/saturn/pal_keyboard_profile.h'], self.f.header)

    def test_separate_absolute_nonoverlapping_paths_required(self):
        rec, rt = self.f.recomp, self.f.runtime
        for a, b in [(Path('relative'), rt), (rec, Path('relative')), (rec, rec), (rec, rec / 'nested'), (rt / 'nested', rt)]:
            with self.subTest(recomp=a, runtime=b):
                self.f.recomp, self.f.runtime = a, b
                self.unchanged_on_error('Separate absolute|overlap')
        self.f.recomp, self.f.runtime = rec, rt

    def test_empty_sources_rejected(self):
        self.f.texts = {}
        self.unchanged_on_error('Generated sources|PROG')

    def test_outside_source_rejected(self):
        self.f.texts[self.f.recomp.parent / 'outside.cpp'] = 'ignored'
        self.unchanged_on_error('inside recomp')

    def test_prefix_sibling_is_not_inside(self):
        self.f.texts[self.f.recomp.with_name(self.f.recomp.name + '-other') / 'p_prog_777.cpp'] = 'ignored'
        self.unchanged_on_error('inside recomp')

    def test_relative_source_rejected(self):
        self.f.texts[Path('p_prog_777.cpp')] = 'ignored'
        self.unchanged_on_error('inside recomp')

    def test_dotdot_source_rejected_before_returning_escaped_destination(self):
        pc = '06020040'
        self.f.texts[self.f.recomp / '../outside.cpp'] = self.f.texts.pop(self.f.paths[pc])
        self.unchanged_on_error('inside|path|canonical|normalized|traversal')

    def test_settings_marker_defaults_and_migration_in_output(self):
        out = self.plan()[self.f.runtime / 'src/host/settings.cpp'].decode()
        self.assertEqual(out.count('PAL_KEYBOARD_PROFILE_V1'), 1)
        for expected in ('keyboard_profile = pc98', '[keyboard pc98]', 'confirm = Return, Keypad Enter, Space',
                         'menu_cancel = Escape', 'strongest = F', 'repeat = R', 'start = Tab', 'has_profile ? "pc98" : "saturn"',
                         '{"keyboard_profile", {"pc98", "saturn"}}'):
            self.assertIn(expected, out)
        self.assertIn('[keyboard]\na = Z', out)
        self.assertIn('[gamepad]\na = a', out)

    def test_host_semantic_priorities_boundaries_and_focus_guards_present(self):
        out = self.plan()[self.f.runtime / 'src/host/host.cpp'].decode()
        for expected in ('cancel ? pal_keyboard::context.cancel : pal_keyboard::context.confirm',
                         '!semantic_key(key)', '!(pc_keyboard() && key == SDL_SCANCODE_F10)',
                         'pc_keyboard() || !f10_bound || g_menu_open',
                         'g_pc_boundary != pal_keyboard::boundary',
                         'SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID == wid) { g_pc_press.reset(); g_battle_press.block(); }',
                         'g_menu_open || (e.key.mod & SDL_KMOD_ALT)',
                         'e.key.windowID != wid || SDL_GetKeyboardFocus() != g_win',
                         'existing_close_hook();', 'existing_open_hook();'):
            self.assertIn(expected, out)

    def test_unreadable_settings_guard_is_present_in_all_runtime_outputs(self):
        out = self.plan()
        host = out[self.f.runtime / 'src/host/host.cpp'].decode()
        settings = out[self.f.runtime / 'src/host/settings.cpp'].decode()
        header = out[self.f.runtime / 'src/host/settings.h'].decode()
        self.assertIn('g_settings = Settings{};', host)
        self.assertIn('g_settings_read_failed = true;', host)
        self.assertIn('if (g_settings_read_failed)', host)
        self.assertIn('settings_load_checked(path, status)', host)
        self.assertIn('if (!f.eof()) return {};', settings)
        self.assertIn('SettingsLoadStatus::Error', settings)
        self.assertIn('enum class SettingsLoadStatus { Missing, Loaded, Error };', header)

    def test_launcher_lists_profiles_semantic_capture_and_current_section_reset(self):
        out = self.plan()[self.f.runtime / 'src/host/launcher.cpp'].decode()
        for expected in ('PC98 keyboard', 'Saturn keyboard', 'keyboard_profile', 'confirm', 'menu_cancel',
                         'binding_section_.rfind("keyboard", 0) == 0',
                         'for (const char* section : {keyboard_section, "gamepad"})'):
            self.assertIn(expected, out)
        self.assertEqual(out.count('for (const char* section : {keyboard_section, "gamepad"})'), 2)

if __name__ == '__main__':
    unittest.main(verbosity=2)
