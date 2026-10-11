"""Synthetic detached prepare_keyboard transaction/manifest safety tests.

No compiler/game/ROM/runtime checkout needed. Test inputs are created in a
TemporaryDirectory; scoped mocks only allow hashes of hand-written fixtures.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from keyboard_test_fixtures import Fixture, HEADER, digest, function, load_planner, wrap

m = load_planner()


def snapshot(root):
    result = {}
    for p in sorted(root.rglob('*')):
        name = p.relative_to(root).as_posix()
        if p.is_symlink():
            result[name] = ('symlink', os.readlink(p))
        elif p.is_file():
            result[name] = ('file', p.read_bytes())
    return result


@unittest.skipUnless(hasattr(m, 'prepare_keyboard'), 'prepare_keyboard is not integrated yet')
class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='PAL keyboard safety 空格 ')
        self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(self.tmp.name)
        for p in (self.f.recomp, self.f.runtime / 'src/host', self.f.runtime / 'include/saturn',
                  self.f.root / 'src/pal_game'):
            p.mkdir(parents=True, exist_ok=True)
        for path, text in {**self.f.texts, **self.f.rt}.items():
            path.write_text(text, encoding='utf-8')
        self.source_header = self.f.root / 'src/pal_game/pal_keyboard_profile.h'
        self.source_header.write_bytes(self.f.header)
        self.cmake = self.f.recomp / 'CMakeLists.txt'
        self.cmake.write_text('if(NOT SATURN_RUNTIME)\n  set(SATURN_RUNTIME "C:/synthetic/runtime")\nendif()\n'
                              'include(${SATURN_RUNTIME}/runtime.cmake)\n', encoding='utf-8')
        (self.f.runtime / 'runtime.cmake').write_text('# Synthetic runtime entry\n', encoding='utf-8')
        self.manifest = self.f.recomp / m.MANIFEST
        self.helper = self.f.runtime / 'include/saturn/pal_keyboard_profile.h'
        self.patches = self.f.hashes(m)
        self.patches.__enter__()
        self.addCleanup(self.patches.__exit__, None, None, None)

    def prepare(self):
        return m.prepare_keyboard(self.f.recomp, self.f.runtime, self.f.root)

    def rejects_without_writes(self, pattern='.'):
        before = snapshot(self.f.root)
        with self.assertRaisesRegex((ValueError, OSError, KeyError, TypeError), pattern):
            self.prepare()
        self.assertEqual(snapshot(self.f.root), before)

    def symlink(self, path, target, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except OSError as exc:
            self.skipTest(f'This platform cannot create the symlink needed by this test: {exc}')

    def write_manifest(self, data):
        self.manifest.write_text(json.dumps(data), encoding='utf-8')

    def test_manifest_covers_changed_files_with_relative_paths(self):
        data = self.prepare()
        self.assertEqual(data['version'], m.VERSION)
        self.assertEqual(data['runtime'], '../runtime')
        self.assertEqual(data['header_sha256'], digest(self.f.header))
        self.assertEqual(data, json.loads(self.manifest.read_text(encoding='utf-8')))
        for group, base in [('recomp', self.f.recomp), ('runtime', self.f.runtime)]:
            for name, expected in data['outputs_sha256'][group].items():
                self.assertFalse(Path(name).is_absolute())
                self.assertNotIn('..', Path(name).parts)
                self.assertEqual(digest((base / name).read_bytes()), expected)
        self.assertIn('include/saturn/pal_keyboard_profile.h', data['outputs_sha256']['runtime'])
        self.assertIn('CMakeLists.txt', data['outputs_sha256']['recomp'])
        self.assertIn('${CMAKE_CURRENT_LIST_DIR}/../runtime', self.cmake.read_text())
        self.assertIn('FATAL_ERROR', self.cmake.read_text())
        self.assertNotIn(str(self.f.root), self.cmake.read_text())

    def test_identical_repeat_is_a_strict_no_write(self):
        first = self.prepare()
        before = snapshot(self.f.root)
        times = {p: p.stat().st_mtime_ns for p in self.f.root.rglob('*') if p.is_file()}
        with patch.object(Path, 'write_bytes', side_effect=AssertionError('repeat writes bytes')), \
             patch.object(Path, 'write_text', side_effect=AssertionError('repeat writes text')):
            self.assertEqual(self.prepare(), first)
        self.assertEqual(snapshot(self.f.root), before)
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in times})

    def test_crlf_sources_and_header_then_repeat(self):
        for path in [*self.f.texts, *self.f.rt, self.cmake, self.source_header]:
            path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        data = self.prepare()
        self.assertEqual(data['header_sha256'], digest(self.source_header.read_bytes()))
        before = snapshot(self.f.root)
        self.assertEqual(self.prepare(), data)
        self.assertEqual(snapshot(self.f.root), before)

    def test_options_transaction_is_rejected_without_changes(self):
        (self.f.recomp / 'pal-options-manifest.json').write_text('{}\n')
        self.rejects_without_writes('options transaction')

    def test_helper_source_drift_rejected_before_first_write(self):
        self.source_header.write_bytes(self.f.header + b'\n// changed\n')
        self.rejects_without_writes('helper source/version')

    def test_helper_source_drift_rejected_on_repeat(self):
        self.prepare()
        self.source_header.write_bytes(self.f.header + b'\n// changed\n')
        self.rejects_without_writes('helper source/version|source/version')

    def test_guest_source_drift_rejected_before_first_write(self):
        p = self.f.paths['060516B4']
        p.write_text(p.read_text().replace('synthetic_guest_step(c);', 'changed_guest_step(c);'))
        self.rejects_without_writes('Guest function changed')

    def test_runtime_source_drift_rejected_before_first_write(self):
        p = self.f.runtime / 'src/host/launcher.cpp'
        p.write_text(p.read_text() + '// changed\n')
        self.rejects_without_writes('Runtime source/version')

    def test_last_cmake_anchor_failure_has_zero_partial_writes(self):
        self.cmake.write_text('No recognized runtime setting\n')
        self.rejects_without_writes('CMake runtime anchor')

    def test_preexisting_helper_is_not_overwritten(self):
        self.helper.write_text('Existing user content\n')
        self.rejects_without_writes('helper|path')

    def test_dirty_injected_guest_rejected(self):
        self.prepare()
        p = self.f.paths['060516B4']
        p.write_bytes(p.read_bytes() + b'// modified after injection\n')
        self.rejects_without_writes('injected output changed')

    def test_dirty_injected_runtime_rejected(self):
        self.prepare()
        p = self.f.runtime / 'src/host/host.cpp'
        p.write_bytes(p.read_bytes() + b'// modified after injection\n')
        self.rejects_without_writes('injected output changed')

    def test_dirty_injected_helper_rejected(self):
        self.prepare()
        self.helper.write_bytes(self.helper.read_bytes() + b'// modified after injection\n')
        self.rejects_without_writes('injected output changed')

    def test_missing_injected_output_rejected(self):
        self.prepare()
        self.helper.unlink()
        self.rejects_without_writes('injected output changed')

    def test_runtime_entry_drift_on_repeat_rejected(self):
        self.prepare()
        path = self.f.runtime / 'runtime.cmake'
        path.write_text('# changed runtime entry\n')
        self.rejects_without_writes('source|output|input|runtime|manifest')

    def test_runtime_entry_missing_on_repeat_rejected(self):
        self.prepare()
        (self.f.runtime / 'runtime.cmake').unlink()
        self.rejects_without_writes('source|output|input|runtime|manifest')

    def test_runtime_change_on_repeat_rejected(self):
        self.prepare()
        other = self.f.runtime.with_name('other runtime')
        shutil.copytree(self.f.runtime, other)
        self.f.runtime = other
        self.rejects_without_writes('source/version|runtime')

    def test_outside_root_build_rejected(self):
        outside = self.f.root / 'third_party/runtime'
        outside.mkdir(parents=True)
        self.f.runtime = outside
        self.rejects_without_writes('detached')

    def test_parent_overlap_rejected(self):
        self.f.runtime = self.f.recomp.parent
        self.rejects_without_writes('detached|overlap')

    def test_source_symlink_escape_rejected(self):
        p = self.f.paths['060516B4']
        outside = self.f.root / 'source-outside.cpp'
        outside.write_bytes(p.read_bytes())
        p.unlink()
        self.symlink(p, outside)
        self.rejects_without_writes('symlink|path')

    def test_runtime_file_symlink_escape_rejected(self):
        p = self.f.runtime / 'src/host/host.cpp'
        outside = self.f.root / 'host-outside.cpp'
        outside.write_bytes(p.read_bytes())
        p.unlink()
        self.symlink(p, outside)
        self.rejects_without_writes('symlink|path')

    def test_runtime_directory_symlink_escape_rejected(self):
        outside = self.f.root / 'outside-runtime'
        self.f.runtime.rename(outside)
        self.symlink(self.f.runtime, outside, directory=True)
        self.rejects_without_writes('detached|symlink|path')

    def test_helper_parent_symlink_escape_rejected(self):
        parent = self.helper.parent
        parent.rmdir()
        outside = self.f.root / 'outside-headers'
        outside.mkdir()
        self.symlink(parent, outside, directory=True)
        self.rejects_without_writes('helper|path|symlink')

    def test_dangling_helper_symlink_cannot_create_outside_file(self):
        outside = self.f.root / 'outside-helper.h'
        self.symlink(self.helper, outside)
        self.rejects_without_writes('helper|path|symlink')
        self.assertFalse(outside.exists())

    def test_dangling_manifest_symlink_cannot_create_outside_file(self):
        outside = self.f.root / 'outside-manifest.json'
        self.symlink(self.manifest, outside)
        self.rejects_without_writes('manifest|path|symlink')
        self.assertFalse(outside.exists())

    def test_existing_manifest_symlink_rejected_even_with_identical_payload(self):
        data = self.prepare()
        outside = self.f.root / 'outside-manifest.json'
        outside.write_text(json.dumps(data))
        self.manifest.unlink()
        self.symlink(self.manifest, outside)
        self.rejects_without_writes('manifest|path|symlink')

    def test_manifest_empty_output_maps_cannot_bypass_verification(self):
        self.write_manifest({'version': m.VERSION, 'runtime': '../runtime',
                             'header_sha256': digest(self.f.header),
                             'inputs_sha256': {'recomp': {}, 'runtime': {}},
                             'outputs_sha256': {'recomp': {}, 'runtime': {}}})
        self.rejects_without_writes('[Mm]anifest|output|incomplete|invalid|inventory')

    def test_manifest_missing_host_entry_cannot_bypass_dirty_output(self):
        data = self.prepare()
        del data['outputs_sha256']['runtime']['src/host/host.cpp']
        self.write_manifest(data)
        host = self.f.runtime / 'src/host/host.cpp'
        host.write_bytes(host.read_bytes() + b'// dirty\n')
        self.rejects_without_writes('[Mm]anifest|output|incomplete|invalid|inventory')

    def test_missing_guest_hash_entry_cannot_bypass_dirty_guest(self):
        data = self.prepare()
        path = self.f.paths['060516B4']
        name = path.relative_to(self.f.recomp).as_posix()
        del data['outputs_sha256']['recomp'][name]
        del data['inputs_sha256']['recomp'][name]
        self.write_manifest(data)
        path.write_bytes(path.read_bytes() + b'// dirty unrecorded source\n')
        self.rejects_without_writes('[Mm]anifest|output|input|inventory|[Ii]ncomplete')

    def test_root_build_symlink_cannot_escape_detached_directory(self):
        original = self.f.root / 'build'
        outside = self.f.root / 'outside-build'
        original.rename(outside)
        self.symlink(original, outside, directory=True)
        self.rejects_without_writes('detached|symlink|path')

    def test_hardlinked_source_cannot_modify_external_original(self):
        path = self.f.paths['060516B4']
        outside = self.f.root / 'hardlink-original.cpp'
        original = path.read_bytes()
        outside.write_bytes(original)
        path.unlink()
        try:
            os.link(outside, path)
        except OSError as exc:
            self.skipTest(f'This platform cannot create the hardlink needed by this test: {exc}')
        before = snapshot(self.f.root)
        try:
            self.prepare()
        except (ValueError, OSError):
            self.assertEqual(snapshot(self.f.root), before)
        self.assertEqual(outside.read_bytes(), original, 'An isolated build must not rewrite a hardlinked external original')

    def test_manifest_relative_escape_rejected(self):
        data = self.prepare()
        outside = self.f.root / 'manifest-target.txt'
        outside.write_text('outside\n')
        data['outputs_sha256']['recomp']['../../../manifest-target.txt'] = digest(outside.read_bytes())
        self.write_manifest(data)
        self.rejects_without_writes('manifest|output|path')

    def test_unchanged_guest_source_is_fingerprinted_for_repeat(self):
        untouched = self.f.recomp / 'p_true_555.cpp'
        untouched.write_text(wrap('p_true', function('06000001')))
        self.prepare()
        untouched.write_text(untouched.read_text() + '// changed verified input\n')
        self.rejects_without_writes('source|output|input|manifest')

    def test_new_guest_source_invalidates_manifest(self):
        self.prepare()
        (self.f.recomp / 'p_prog_555.cpp').write_text(wrap('p_prog', function('06000001')))
        self.rejects_without_writes('source|output|input|manifest|inventory')

    def test_removed_unchanged_guest_source_invalidates_manifest(self):
        untouched = self.f.recomp / 'p_true_555.cpp'
        untouched.write_text(wrap('p_true', function('06000001')))
        self.prepare()
        untouched.unlink()
        self.rejects_without_writes('source|output|input|manifest|inventory')

    def test_source_byte_race_before_commit_has_zero_injection_writes(self):
        original_plan = m.plan_keyboard
        observed = {}
        def race(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            path = self.f.paths['060516B4']
            path.write_bytes(path.read_bytes() + b'// concurrent edit\n')
            observed['after_race'] = snapshot(self.f.root)
            return result
        with patch.object(m, 'plan_keyboard', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'changed while preparing|race'):
                self.prepare()
        self.assertEqual(snapshot(self.f.root), observed['after_race'])
        self.assertFalse(self.manifest.exists())

    def test_helper_source_race_before_commit_has_zero_injection_writes(self):
        original_plan = m.plan_keyboard
        observed = {}
        def race(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            self.source_header.write_bytes(self.f.header + b'// concurrent helper edit\n')
            observed['after_race'] = snapshot(self.f.root)
            return result
        with patch.object(m, 'plan_keyboard', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'changed while preparing|race|helper'):
                self.prepare()
        self.assertEqual(snapshot(self.f.root), observed['after_race'])

    def test_new_source_race_before_commit_has_zero_injection_writes(self):
        original_plan = m.plan_keyboard
        observed = {}
        def race(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            (self.f.recomp / 'p_prog_555.cpp').write_text(wrap('p_prog', function('06000001')))
            observed['after_race'] = snapshot(self.f.root)
            return result
        with patch.object(m, 'plan_keyboard', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'changed while preparing|race|source|inventory'):
                self.prepare()
        self.assertEqual(snapshot(self.f.root), observed['after_race'])

    def test_same_byte_source_symlink_race_has_zero_outside_or_injection_writes(self):
        original_plan = m.plan_keyboard
        outside = self.f.root / 'race-outside.cpp'
        path = self.f.paths['060516B4']
        outside.write_bytes(path.read_bytes())
        observed = {}
        def race(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            path.unlink()
            self.symlink(path, outside)
            observed['after_race'] = snapshot(self.f.root)
            return result
        with patch.object(m, 'plan_keyboard', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'changed while preparing|race|symlink|path'):
                self.prepare()
        self.assertEqual(snapshot(self.f.root), observed['after_race'])
        self.assertFalse(self.manifest.exists())

if __name__ == '__main__':
    unittest.main(verbosity=2)
