"""Synthetic injection/portability tests: no ROM, compiler or game execution."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
spec = importlib.util.spec_from_file_location('pal_options', HERE.parent / 'pal_options.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def func(pc, lines=''):
    return f'void f_{pc}(SH2Context& c) {{\n' + lines + '}\n'


class InjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='PAL Windows options 空格 ')
        self.root = Path(self.tmp.name)
        self.recomp = self.root / 'build/test options/recomp'
        self.runtime = self.root / 'build/test options/runtime'
        for p in (self.recomp, self.runtime / 'src/host', self.runtime / 'src/machine', self.root / 'src/pal_game'):
            p.mkdir(parents=True, exist_ok=True)
        for name in (*m.HEADERS, 'pal_host_edge.h', 'pal_paired_frame_queue.cpp', 'pal_paired_frame_queue.h', 'pal_keyboard_profile.h'):
            shutil.copy2(REPO / 'src/pal_game' / name, self.root / 'src/pal_game' / name)
        self.source = self.recomp / 'p_prog_099.cpp'  # No dependence on generator chunk number.
        points = [('06026E1C', 'f_06035410(c)'), ('06026E58', 'exts.w r0,r1'),
                  ('06026E6C', 'mov.b r2,@r1'), ('06026E76', 'if (x == 0x0603440Cu) f_0603440C(c)'),
                  ('06026E84', 'f_06023C64(c)'), ('06026E90', 'f_0604C45C(c)'),
                  ('06026EB8', 'f_060235B8(c)'), ('06026F44', 'f_0604C5AC(c)'),
                  ('06026F52', 'f_0604C5AC(c)')]
        sync = ('    st16(c.r[1], c.r[0]); // 0605D6A2 mov\n'
                '    c.r[0] = ld32(c.gbr + 972); // 0605D6B0 mov\n'
                '    c.r[2] = 0x0602008Cu; // 0605D6BC mov\n'
                '    if (c.t) {} // 0605D6BA bt\n'
                '    st8(c.gbr + 19, c.r[0]); // 0605D770 mov\n')
        text = func('06026D84', ''.join(f'    {code}; // {pc} instruction\n' for pc, code in points))
        text += func('06026F90') + func('0606016E') + func('0605D68A', sync)
        text += func('0605D67E', sync)  # Same instruction labels in another generated entry.
        text += func('06022458', '    f_06021FD8(c); // 060224E0 jsr\n')
        text += func('06021FD8', '    if (!c.t) { goto L_06022032; } // 0602202C bf\n')
        text += func('0605D670', '    st16(c.r[1], c.r[0]); // 0605D6A2 mov\n')
        text += func('060649D0', '    c.pc = x; return; // 06064AD6 rts\n')
        text += func('0603BDE8') + func('0603108C')
        text += func('060223C0', '    f_0603E818(c); // 06022426 jsr\n')
        self.source.write_text(text, encoding='utf-8')
        (self.recomp / 'CMakeLists.txt').write_text('if(NOT SATURN_RUNTIME)\n  set(SATURN_RUNTIME "C:/old repo/runtime")\nendif()\ninclude(${SATURN_RUNTIME}/runtime.cmake)\ntarget_link_libraries(saturn runtime)\n')
        (self.runtime / 'runtime.cmake').write_text('# fixture\n')
        self.host = self.runtime / 'src/host/host.cpp'
        self.host.write_text('static bool g_menu_open, g_quitting;\nstatic uint16_t touch_read();\n'
            '    for (int s = 0; s < kHostSlots; ++s) {\n}\nstatic void menu_open() {\n}\n'
            'static void menu_close() {\n}\nstatic void on_event(const SDL_Event& e) {\n}\n')
        (self.runtime / 'src/host/host_null.cpp').write_text('#include <cstdint>\n')
        (self.runtime / 'src/machine/smpc.cpp').write_text('// original INTBACK unchanged\n')
        from pal_paired_frame_queue import RUNTIME_FILES
        (self.runtime / 'include/saturn').mkdir(parents=True)
        for name in ('settings.cpp','launcher.cpp','settings.h'):
            (self.runtime / 'src/host' / name).write_text('// synthetic keyboard fixture\n')
        # This suite isolates the options transaction. The keyboard planner has
        # its own portable synthetic suite and full-ROM integration runs.
        self.keyboard = patch('pal_keyboard_profile.plan_keyboard', side_effect=lambda recomp,runtime,texts,rt,header: {runtime/'include/saturn/pal_keyboard_profile.h':header})
        self.keyboard.start()
        for name in (*RUNTIME_FILES, 'src/machine/machine.cpp'):
            dest = self.runtime / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / 'third_party/saturn-recomp-pal/runtime' / name, dest)


    def tearDown(self):
        self.keyboard.stop()
        self.tmp.cleanup()

    def run_inject(self):
        return m.prepare_options(self.recomp, self.runtime, self.root)

    def test_both_independent_features_and_relative_paths(self):
        manifest = self.run_inject()
        text = self.source.read_text()
        self.assertEqual(text.count('#include "pal_responsive_input.h"'), 1)
        self.assertEqual(text.count('#include "pal_effect_wait_runtime.h"'), 1)
        self.assertEqual(text.count('pal_input_script_before();'), 2)
        self.assertEqual(text.count('pal_input_sync_enter(c);'), 1)
        self.assertEqual(text.count('// 0605D6B0 '), 2)
        self.assertEqual(text.count('pal_effect_wait::Scope pal_effect_scope(c);'), 1)
        self.assertEqual(text.count('pal_effect_wait::ready(c)'), 1)
        self.assertNotIn(str(self.root), text)
        self.assertEqual(manifest['runtime'], '../runtime')
        self.assertIn('${CMAKE_CURRENT_LIST_DIR}/../runtime', (self.recomp / 'CMakeLists.txt').read_text())
        self.assertEqual(manifest['defaults']['PAL_EFFECT_ANIMATION_SPEED'], '1.5')
        self.assertEqual(manifest['defaults']['PAL_SHORT_EFFECT_PREP'], '1')
        self.assertEqual({v for k, v in manifest['defaults'].items()
                          if k not in ('PAL_EFFECT_ANIMATION_SPEED', 'PAL_SHORT_EFFECT_PREP')}, {'0'})
        self.assertEqual(text.count('pal_effect_cadence::prepare_sync(c);'), 1)
        self.assertNotIn('pal_effect_cadence::shorten_sync', text)
        self.assertNotIn('pal_effect_cadence::finish_sync', text)
        sync_body=text.split('void f_0605D68A(SH2Context& c) {',1)[1].split('\nvoid ',1)[0]
        self.assertLess(sync_body.index('pal_input_sync_enter(c);'), sync_body.index('pal_effect_cadence::prepare_sync(c);'))
        self.assertLess(sync_body.index('pal_effect_cadence::prepare_sync(c);'), sync_body.index('c.r[0] = ld32(c.gbr + 972)'))
        for name in m.HEADERS:
            self.assertEqual((self.recomp / name).read_bytes(), (REPO / 'src/pal_game' / name).read_bytes())
        self.assertNotIn('pal_battle_probe', text)
        self.assertNotIn('completed_frame', text)

    def test_identical_rerun_is_noop(self):
        self.run_inject()
        before = hashes(self.root)
        times = {p: p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
        self.run_inject()
        self.assertEqual(hashes(self.root), before)
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in times})

    def test_missing_instruction_has_zero_partial_writes(self):
        self.source.write_text(self.source.read_text().replace('// 06026E84 ', '// 16026E84 '))
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, '06026E84'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_duplicated_function_rejected_before_writes(self):
        self.source.write_text(self.source.read_text() + func('06026F90'))
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, '06026F90'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_changed_host_anchor_has_zero_partial_writes(self):
        self.host.write_text(self.host.read_text().replace('static bool g_menu_open, g_quitting;', 'changed;'))
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'SDL host'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_changed_injected_output_rejected(self):
        self.run_inject()
        self.host.write_text(self.host.read_text() + '// changed\n')
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'Previously injected runtime'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_changed_source_header_rejected(self):
        self.run_inject()
        helper = self.root / 'src/pal_game/pal_input_intent.h'
        helper.write_text(helper.read_text() + '// changed\n')
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'Option/header version changed'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_prior_instrumentation_rejected(self):
        self.source.write_text('#include "pal_battle_probe.h"\n' + self.source.read_text())
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'already instrumented'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_cannot_modify_source_runtime(self):
        third_party = self.root / 'third_party/runtime'
        third_party.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'Only detached'):
            m.prepare_options(self.recomp, third_party, self.root)

    def test_unexpected_existing_header_rejected_before_write(self):
        (self.recomp / m.HEADERS[0]).write_text('user edit\n')
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'preexisting option header'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_effect_branch_shape_checked(self):
        self.source.write_text(self.source.read_text().replace('if (!c.t)', 'if (c.t)'))
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, '0602202C'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_duplicate_instruction_within_target_rejected(self):
        text = self.source.read_text()
        text = text.replace('// 0602202C bf\n', '// 0602202C bf\n    if (!c.t) {} // 0602202C bf\n')
        self.source.write_text(text)
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, '0602202C'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)


    def test_queue_runtime_drift_fails_before_any_writes(self):
        path = self.runtime / 'src/video/vdp1.cpp'
        path.write_text(path.read_text() + '// changed runtime version\n')
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'Runtime source/version changed'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_queue_pc_drift_fails_before_any_writes(self):
        self.source.write_text(self.source.read_text().replace('// 06064AD6 ', '// 16064AD6 '))
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, '06064AD6'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_cadence_anchor_failure_is_atomic(self):
        self.source.write_text(self.source.read_text().replace('// 06022426 ', '// 16022426 '))
        before = hashes(self.root)
        with self.assertRaisesRegex(ValueError, '06022426'):
            self.run_inject()
        self.assertEqual(hashes(self.root), before)

    def test_windows_crlf_sources_and_runtime(self):
        for base in (self.recomp, self.runtime):
            for path in base.rglob('*'):
                if path.is_file():
                    path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        manifest = self.run_inject()
        text = self.source.read_text()
        self.assertEqual(text.count('pal_input_sync_enter(c);'), 1)
        self.assertEqual(text.count('pal_effect_wait::ready(c)'), 1)
        self.assertEqual(manifest['runtime'], '../runtime')
        before = hashes(self.root)
        self.run_inject()
        self.assertEqual(hashes(self.root), before)

if __name__ == '__main__':
    unittest.main(verbosity=2)
