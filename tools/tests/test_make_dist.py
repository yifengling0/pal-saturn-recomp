"""Synthetic packaging safety regressions. Never read a user's disc/save/output.

The EXE/DLL and guest statements are invented and never executed. The real
read-only option-manifest verifier is exercised; only the unrelated runtime
support pin catalog is replaced by an empty synthetic variant. This fixture is
not build provenance and must never be used to produce a release.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
import pal_options
import pal_data_cd_speed
import pal_keyboard_profile
import pal_paired_frame_queue

spec = importlib.util.spec_from_file_location('make_dist_under_test', HERE.parent / 'make_dist.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def snapshot(root):
    result = {}
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[name] = ('symlink', os.readlink(path))
        elif path.is_file():
            result[name] = ('file', path.read_bytes())
        elif path.is_dir():
            result[name] = ('directory',)
        else:
            result[name] = ('special',)
    return result


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='PAL distribution synthetic 空格 ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.build = self.root / 'build/windows-pal-options/recomp-build'
        self.recomp = self.build.parent / 'recomp'
        self.runtime = self.build.parent / 'runtime'
        self.out = self.root / 'dist/new package'
        for path in (self.build, self.recomp, self.runtime, self.root / 'src/pal_game', self.out.parent):
            path.mkdir(parents=True, exist_ok=True)
        self.exe = self.build / 'saturn.exe'
        self.dll = self.build / 'SDL3.dll'
        self.proof = self.build / 'pal-options-build.json'
        self.manifest = self.recomp / pal_options.MANIFEST
        self.exe.write_bytes(b'NOT A PE: synthetic executable, never execute\n')
        self.dll.write_bytes(b'NOT A DLL: synthetic library, never load\n')
        self.cache = self.build / 'CMakeCache.txt'
        self.cache.write_text('SATURN_VDP1_GPL:BOOL=OFF\n', encoding='utf-8')
        header_names = (*pal_options.HEADERS, 'pal_host_edge.h', 'pal_paired_frame_queue.cpp',
                        'pal_paired_frame_queue.h', 'pal_keyboard_profile.h', 'pal_field_input.h',
                        'pal_release_gate.h', 'pal_release_runtime.h')
        self.headers = {}
        for name in header_names:
            target = self.root / 'src/pal_game' / name
            shutil.copy2(REPO / 'src/pal_game' / name, target)
            self.headers[name] = m.sha256(target)
        for name in (*pal_options.HEADERS, 'pal_paired_frame_queue.cpp', 'pal_field_input.h',
                     'pal_release_gate.h', 'pal_release_runtime.h'):
            shutil.copy2(self.root / 'src/pal_game' / name, self.recomp / name)
        names = {*pal_paired_frame_queue.RUNTIME_FILES, 'src/host/host_null.cpp',
                 'src/machine/smpc.cpp', 'src/machine/machine.cpp', 'src/host/settings.cpp',
                 'src/host/settings.h', 'src/host/launcher.cpp', 'src/host/pal_host_edge.h',
                 'include/pal_paired_frame_queue.h', 'include/saturn/pal_keyboard_profile.h'}
        for name in names:
            target = self.runtime / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('// Synthetic runtime statement; not a usable implementation.\n', encoding='utf-8')
        (self.runtime / 'src/host/host.cpp').write_text(
            '#include "pal_field_input_ledger.h"\n// synthetic pal_keyboard:: marker\n', encoding='utf-8')
        for target, name in (('src/host/pal_host_edge.h', 'pal_host_edge.h'),
                             ('include/pal_paired_frame_queue.h', 'pal_paired_frame_queue.h'),
                             ('include/saturn/pal_keyboard_profile.h', 'pal_keyboard_profile.h')):
            shutil.copy2(self.root / 'src/pal_game' / name, self.runtime / target)
        (self.runtime / 'runtime.cmake').write_text('# synthetic\n', encoding='utf-8')
        (self.recomp / 'CMakeLists.txt').write_text('# synthetic\n', encoding='utf-8')
        self.generated = self.recomp / 'p_prog_001.cpp'
        self.generated.write_text('// Synthetic hook inventory, no original guest code.\n' +
                                  '\n'.join(marker for group in m.GUEST_MARKERS.values() for marker in group),
                                  encoding='utf-8')
        # Use the reviewed open runtime CD transform in the private fixture, not
        # an invented production hash. It contains no extracted game code/data.
        cd = self.runtime / pal_data_cd_speed._SOURCE
        shutil.copy2(REPO / 'third_party/saturn-recomp-pal/runtime' / pal_data_cd_speed._SOURCE, cd)
        pal_data_cd_speed.apply_data_cd_speed(self.runtime)
        self.instrumentation = {
            'version': pal_options.VERSION, 'runtime': '../runtime',
            'headers_sha256': self.headers,
            'defaults': {'PAL_RESPONSIVE_INPUT': '0', 'PAL_RESPONSIVE_ALIGN': '0',
                         'PAL_RESPONSIVE_WAKE': '0', 'PAL_SHORT_EFFECT_PREP': '1',
                         'PAL_EFFECT_ANIMATION_SPEED': '1.5', 'PAL_PAIRED_FRAME_QUEUE': '0'},
            'inputs_sha256': {'recomp': {'CMakeLists.txt': m.sha256(self.recomp / 'CMakeLists.txt')},
                              'runtime': {'runtime.cmake': m.sha256(self.runtime / 'runtime.cmake')}},
            'outputs_sha256': {
                'recomp': {p.name: m.sha256(p) for p in self.recomp.iterdir()},
                'runtime': {name: m.sha256(self.runtime / name) for name in names}},
        }
        self.write_instrumentation()
        self.build_proof = {'schema': 1, 'version': pal_options.VERSION,
                            'features': sorted(m.REQUIRED_FEATURES), 'exe_sha256': m.sha256(self.exe),
                            'instrumentation_manifest_sha256': m.sha256(self.manifest)}
        self.write_proof()
        self.saved = self.root / 'private.bup'
        payload = b'SYNTHETIC PRIVATE PROGRESS'
        self.saved.write_bytes(b'FIXTURE\0'.ljust(12, b'\0') + bytes(12) + struct.pack('<II', 0, len(payload)) + payload)
        for mocker in (patch.object(m, 'ROOT', self.root), patch.object(m, 'BUILD', self.build),
                       patch.object(m, 'OUT', self.out),
                       patch.object(pal_keyboard_profile, 'runtime_support_inputs', return_value={})):
            mocker.start()
            self.addCleanup(mocker.stop)
        self.objdump = patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess(
            ['objdump'], 0, '\tDLL Name: SDL3.dll\n', ''))
        self.run = self.objdump.start()
        self.addCleanup(self.objdump.stop)

    def write_proof(self, data=None):
        self.proof.write_text(json.dumps(self.build_proof if data is None else data), encoding='utf-8')

    def write_instrumentation(self):
        self.manifest.write_text(json.dumps(self.instrumentation), encoding='utf-8')
        if hasattr(self, 'build_proof'):
            self.build_proof['instrumentation_manifest_sha256'] = m.sha256(self.manifest)
            self.write_proof()

    def assert_refuses(self, pattern='.', args=()):
        before = snapshot(self.root)
        with self.assertRaisesRegex(SystemExit, pattern):
            m.main(list(args))
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(list(self.out.parent.glob('.*.staging-*')))

    def symlink(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except OSError as exc:
            self.skipTest(f'Symlink unavailable: {exc}')

    def test_required_exe_hash_missing_empty_null_malformed_mismatch(self):
        for value in (None, '', [], 123, 'a' * 63, 'x' * 64, '0' * 64):
            with self.subTest(value=value):
                self.write_proof({**self.build_proof, 'exe_sha256': value})
                self.assert_refuses('exe_sha256')
        data = dict(self.build_proof)
        del data['exe_sha256']
        self.write_proof(data)
        self.assert_refuses('exe_sha256')
        self.run.assert_not_called()

    def test_manifest_must_be_object_valid_json_and_unique(self):
        for value in ('[]', 'null', '"text"', '42', '{broken', '{"schema":1,"schema":1}'):
            with self.subTest(value=value):
                self.proof.write_text(value, encoding='utf-8')
                self.assert_refuses()
        self.run.assert_not_called()

    def test_missing_build_manifest(self):
        self.proof.unlink()
        self.assert_refuses('pal-options-build.json')

    def test_schema_and_version_are_required_and_exact(self):
        for key, values in (('schema', (None, True, '1', 2)), ('version', (None, '', 'old'))):
            for value in values:
                with self.subTest(key=key, value=value):
                    self.write_proof({**self.build_proof, key: value})
                    self.assert_refuses('schema/version')

    def test_feature_inventory_cannot_be_missing_partial_or_invented(self):
        for features in (None, [], {}, ['keyboard_profile_v1'],
                         sorted(m.REQUIRED_FEATURES) + ['invented'],
                         sorted(m.REQUIRED_FEATURES) + ['field_input_v1'],
                         [None, *sorted(m.REQUIRED_FEATURES)]):
            with self.subTest(features=features):
                self.write_proof({**self.build_proof, 'features': features})
                self.assert_refuses('features')

    def test_instrumentation_hash_missing_empty_malformed_mismatch(self):
        for value in (None, '', '0' * 64, 'invalid'):
            with self.subTest(value=value):
                self.write_proof({**self.build_proof, 'instrumentation_manifest_sha256': value})
                self.assert_refuses('instrumentation_manifest_sha256')

    def test_missing_instrumentation_file(self):
        self.manifest.unlink()
        self.assert_refuses('pal-options-manifest.json')

    def test_wrong_instrumentation_version_and_runtime(self):
        for key, value in (('version', 'old'), ('runtime', '../../elsewhere')):
            previous = self.instrumentation[key]
            self.instrumentation[key] = value
            self.write_instrumentation()
            self.assert_refuses('instrumentation version/runtime')
            self.instrumentation[key] = previous

    def test_empty_instrumentation_maps_fail_even_with_matching_sidecar(self):
        for key in ('inputs_sha256', 'outputs_sha256'):
            previous = self.instrumentation[key]
            for value in ({}, {'recomp': {}, 'runtime': {}}):
                self.instrumentation[key] = value
                self.write_instrumentation()
                self.assert_refuses('instrumentation')
            self.instrumentation[key] = previous

    def test_missing_required_output_rejected_even_when_rehashed(self):
        del self.instrumentation['outputs_sha256']['recomp']['pal_field_input.h']
        self.write_instrumentation()
        self.assert_refuses('不完整')

    def test_missing_release_helper_output_rejected_even_when_rehashed(self):
        for name in ('pal_release_gate.h', 'pal_release_runtime.h'):
            with self.subTest(helper=name):
                original = self.instrumentation['outputs_sha256']['recomp'].pop(name)
                previous_out = self.out
                self.out = self.root / 'dist' / ('missing-' + name)
                self.write_instrumentation()
                try:
                    with patch.object(m, 'OUT', self.out):
                        self.assert_refuses('不完整|Incomplete field')
                finally:
                    self.out = previous_out
                    self.instrumentation['outputs_sha256']['recomp'][name] = original
                    self.write_instrumentation()

    def test_rehashed_release_helper_cannot_replace_reviewed_source(self):
        for name in ('pal_release_gate.h', 'pal_release_runtime.h'):
            with self.subTest(helper=name):
                target = self.recomp / name
                original = target.read_bytes()
                previous_out = self.out
                self.out = self.root / 'dist' / ('replaced-' + name)
                target.write_bytes(b'// Unreviewed synthetic replacement\n')
                self.instrumentation['outputs_sha256']['recomp'][name] = m.sha256(target)
                self.write_instrumentation()
                try:
                    with patch.object(m, 'OUT', self.out):
                        self.assert_refuses('helper 与来源不符')
                finally:
                    self.out = previous_out
                    target.write_bytes(original)
                    self.instrumentation['outputs_sha256']['recomp'][name] = m.sha256(target)
                    self.write_instrumentation()

    def test_manifest_traversal_rejected_without_reading_target(self):
        self.instrumentation['outputs_sha256']['runtime']['../../private.bup'] = m.sha256(self.saved)
        self.write_instrumentation()
        self.assert_refuses('不安全')

    def test_changed_generated_bytes_are_rejected(self):
        self.generated.write_text(self.generated.read_text() + '\n// changed\n', encoding='utf-8')
        self.assert_refuses('Previously injected')

    def test_feature_claim_without_hooks_fails_even_with_matching_hashes(self):
        self.generated.write_text('// no instrumentation at all\n', encoding='utf-8')
        self.instrumentation['outputs_sha256']['recomp'][self.generated.name] = m.sha256(self.generated)
        self.write_instrumentation()
        self.assert_refuses('实际重编译源码缺少')

    def test_changed_source_header_rejected(self):
        path = self.root / 'src/pal_game/pal_input_intent.h'
        path.write_bytes(path.read_bytes() + b'// changed\n')
        self.assert_refuses('Option/header version changed')

    def test_data_cd_claim_without_patched_runtime_rejected(self):
        (self.runtime / pal_data_cd_speed._SOURCE).write_bytes(b'no CD patch\n')
        self.assert_refuses('data_cd_speed')

    def test_gpl_configuration_missing_or_enabled_is_refused(self):
        for content in ('# absent\n', 'SATURN_VDP1_GPL:BOOL=ON\n'):
            self.cache.write_text(content, encoding='utf-8')
            self.assert_refuses('SATURN_VDP1_GPL')

    def test_existing_user_tree_and_legacy_stash_unchanged(self):
        for name, content in {'disc/user.BIN': b'FAKE DISC', 'disc/user.cue': b'FAKE CUE',
                              'settings.ini': b'private settings', 'saves/one.bup': b'private save',
                              'other.txt': b'private content'}.items():
            path = self.out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        stash = self.out.with_name(self.out.name + '.saves')
        stash.mkdir()
        (stash / 'older.bup').write_bytes(b'older private progress')
        self.assert_refuses('输出已存在')
        self.run.assert_not_called()

    def test_existing_file_or_empty_directory_not_overwritten(self):
        self.out.write_bytes(b'private file')
        self.assert_refuses('输出已存在')
        self.out.unlink()
        self.out.mkdir()
        self.assert_refuses('输出已存在')

    def test_output_symlink_and_dangling_symlink_refused(self):
        for target in (self.root / 'private destination', self.root / 'does not exist'):
            self.symlink(self.out, target)
            self.assert_refuses('符号链接|重定向')
            self.out.unlink()

    def test_output_parent_symlink_and_traversal_refused(self):
        link = self.root / 'linked parent'
        self.symlink(link, self.out.parent)
        self.assert_refuses('符号链接|重定向', ['--output', str(link / 'fresh')])
        self.assert_refuses('不支持', ['--output', str(self.out.parent / '../fresh')])
        self.assert_refuses('构建输入', ['--output', str(self.build / 'package')])

    def test_input_symlink_and_directory_refused(self):
        self.exe.unlink()
        self.symlink(self.exe, self.saved)
        self.assert_refuses('符号链接|重定向')
        self.exe.unlink()
        self.exe.mkdir()
        self.assert_refuses('普通文件')

    def test_objdump_failure_cannot_masquerade_as_sdl(self):
        for code, text in ((1, 'DLL Name: SDL3.dll\n'), (0, 'DLL Name: SDL30dll\n'), (0, '')):
            self.run.return_value = subprocess.CompletedProcess([], code, text, '')
            self.assert_refuses('objdump')

    def test_missing_objdump_preserves_everything(self):
        self.run.side_effect = FileNotFoundError('objdump unavailable')
        self.assert_refuses('objdump unavailable')

    def test_save_missing_wrong_extension_disc_disguise_and_truncation(self):
        self.assert_refuses('普通文件', ['--with-save', str(self.root / 'missing.bup')])
        for name, content in (('disc.bin', b'FAKE DISC'), ('disc.bup', b'FAKE RAW DISC'),
                              ('large.bup', bytes(32769)), ('truncated.bup', self.saved.read_bytes()[:-1])):
            path = self.root / name
            path.write_bytes(content)
            self.assert_refuses('bup|BUP', ['--with-save', str(path)])

    def test_save_symlink_refused(self):
        link = self.root / 'linked.bup'
        self.symlink(link, self.saved)
        self.assert_refuses('符号链接|重定向', ['--with-save', str(link)])

    def test_readonly_disc_validator_preserves_every_byte(self):
        target = self.root / 'user installation'
        target.mkdir()
        (target / 'user.BIN').write_bytes(b'FAKE DISC')
        (target / 'settings.ini').write_bytes(b'private settings')
        before = snapshot(self.root)
        with self.assertRaisesRegex(ValueError, '光盘'):
            m.refuse_disc_data(target, 'synthetic test')
        self.assertEqual(snapshot(self.root), before)

    def test_copy_failure_cleans_only_private_staging(self):
        with patch.object(m.shutil, 'copy2', side_effect=OSError('copy failed')):
            self.assert_refuses('copy failed')

    def test_corrupted_copy_is_rejected(self):
        def bad_copy(source, target):
            Path(target).write_bytes(b'corrupt')
        with patch.object(m.shutil, 'copy2', side_effect=bad_copy):
            self.assert_refuses('复制校验失败')

    def test_scan_failure_cleans_only_private_staging(self):
        with patch.object(m, 'scan', side_effect=OSError('scan failed')):
            self.assert_refuses('scan failed')

    def test_staged_disc_injection_is_refused_and_cleaned(self):
        original = m.refuse_disc_data
        def injected(root, stage):
            (root / 'unexpected.iso').write_bytes(b'FAKE DISC')
            return original(root, stage)
        with patch.object(m, 'refuse_disc_data', side_effect=injected):
            self.assert_refuses('光盘')

    def test_checksums_write_failure_leaves_no_partial_output(self):
        original = Path.write_text
        def fail(path, *args, **kwargs):
            if path.name == 'SHA256SUMS.txt':
                raise OSError('checksum write failed')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'write_text', fail):
            self.assert_refuses('checksum write failed')

    def test_publish_failure_cleans_staging_preserves_inputs(self):
        with patch.object(m, 'publish_new', side_effect=OSError('publish failed')):
            self.assert_refuses('publish failed')

    def test_success_fresh_output_checksums_and_private_save(self):
        before = snapshot(self.root)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(['--with-save', str(self.saved)]), 0)
        after_inputs = {k: v for k, v in snapshot(self.root).items() if not k.startswith('dist/new package')}
        self.assertEqual(after_inputs, before)
        self.assertEqual((self.out / 'saves/pal-saturn.bup').read_bytes(), self.saved.read_bytes())
        self.assertEqual((self.out / 'pal-options-build.json').read_bytes(), self.proof.read_bytes())
        sums = (self.out / 'SHA256SUMS.txt').read_text(encoding='utf-8')
        for line in sums.splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(m.sha256(self.out / name), digest)
        self.assertEqual(set(p.relative_to(self.out).as_posix() for p in m.scan(self.out)),
                         {line.split('  ', 1)[1] for line in sums.splitlines()} | {'SHA256SUMS.txt'})
        self.assertEqual({p.name for p in (self.out / 'disc').iterdir()}, {'README.txt'})
        self.assertIn(b'\r\n', (self.out / 'run.bat').read_bytes())
        self.assertNotIn(b'\r', (self.out / 'SHA256SUMS.txt').read_bytes())
        self.assertFalse(list(self.out.parent.glob('.*.staging-*')))

    def test_fresh_alternative_leaves_old_installation_unchanged(self):
        self.out.mkdir()
        (self.out / 'settings.ini').write_bytes(b'private custom settings')
        before = snapshot(self.root)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(['--output', 'dist/alternative']), 0)
        after = {k: v for k, v in snapshot(self.root).items() if not k.startswith('dist/alternative')}
        self.assertEqual(after, before)
        self.assertTrue((self.root / 'dist/alternative/saves/README.txt').is_file())

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Real Linux no-replace syscall regression')
    def test_atomic_publish_refuses_destination_created_after_preflight(self):
        stage = self.out.parent / '.isolated test staging'
        stage.mkdir()
        (stage / 'only ours.txt').write_bytes(b'owned fixture')
        original = m.fresh_output
        def racing(path):
            value = original(path)
            path.mkdir()  # Even an empty directory must not be replaced.
            return value
        before_stage = snapshot(stage)
        with patch.object(m, 'fresh_output', side_effect=racing):
            with self.assertRaises(FileExistsError):
                m.publish_new(stage, self.out)
        self.assertTrue(self.out.is_dir())
        self.assertEqual(list(self.out.iterdir()), [])
        self.assertEqual(snapshot(stage), before_stage)

    def test_missing_or_changed_instrumentation_defaults(self):
        self.instrumentation.pop('defaults')
        self.write_instrumentation()
        self.assert_refuses('defaults')

    def test_unlisted_generated_file_is_rejected(self):
        (self.recomp / 'p_true_999.cpp').write_text('// synthetic untracked source\n', encoding='utf-8')
        self.assert_refuses('重编译源码不在')

    def test_instrumentation_source_symlink_refused(self):
        original = self.generated.read_bytes()
        self.generated.unlink()
        target = self.root / 'user_source.cpp'
        target.write_bytes(original)
        self.symlink(self.generated, target)
        self.assert_refuses('符号链接|重定向')

    def test_unexpected_asset_rejected_by_fixed_file_allowlist(self):
        original = m.refuse_disc_data
        def injected(root, stage):
            (root / 'unexpected.png').write_bytes(b'FAKE IMAGE')
            return original(root, stage)
        with patch.object(m, 'refuse_disc_data', side_effect=injected):
            self.assert_refuses('白名单')

    def test_staged_symlink_refused_without_touching_target(self):
        original = m.refuse_disc_data
        def injected(root, stage):
            self.symlink(root / 'private.bup', self.saved)
            return original(root, stage)
        with patch.object(m, 'refuse_disc_data', side_effect=injected):
            self.assert_refuses('符号链接|重定向')

    def test_checksum_content_corruption_is_rejected(self):
        original = Path.write_text
        def corrupt(path, content, *args, **kwargs):
            return original(path, 'corrupt checksum\n' if path.name == 'SHA256SUMS.txt' else content,
                            *args, **kwargs)
        with patch.object(Path, 'write_text', corrupt):
            self.assert_refuses('SHA256SUMS')

    def test_second_provenance_verification_failure_cleans_staging(self):
        original = m.verify_build
        calls = 0
        def changed():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError('synthetic late provenance failure')
            return original()
        with patch.object(m, 'verify_build', side_effect=changed):
            self.assert_refuses('late provenance')
        self.assertEqual(calls, 2)

    def test_files_added_by_other_process_at_publish_are_preserved(self):
        original = m.publish_new
        before_inputs = snapshot(self.root)
        def racing(stage, output):
            output.mkdir()
            (output / 'settings.ini').write_bytes(b'other process settings')
            (output / 'user.bin').write_bytes(b'other process FAKE disc')
            return original(stage, output)
        with patch.object(m, 'publish_new', side_effect=racing):
            with self.assertRaisesRegex(SystemExit, '输出已存在'):
                m.main([])
        self.assertEqual((self.out / 'settings.ini').read_bytes(), b'other process settings')
        self.assertEqual((self.out / 'user.bin').read_bytes(), b'other process FAKE disc')
        after_inputs = {k: v for k, v in snapshot(self.root).items() if not k.startswith('dist/new package')}
        self.assertEqual(after_inputs, before_inputs)
        self.assertFalse(list(self.out.parent.glob('.*.staging-*')))

    def test_rehashed_helper_cannot_claim_unchanged_source_identity(self):
        name = 'include/saturn/pal_keyboard_profile.h'
        target = self.runtime / name
        target.write_bytes(b'// wrong helper with self-consistent output hash\n')
        self.instrumentation['outputs_sha256']['runtime'][name] = m.sha256(target)
        self.write_instrumentation()
        self.assert_refuses('helper 与来源不符')

    def test_source_helper_symlink_refused(self):
        source = self.root / 'src/pal_game/pal_keyboard_profile.h'
        target = self.root / 'user_helper.h'
        target.write_bytes(source.read_bytes())
        source.unlink()
        self.symlink(source, target)
        self.assert_refuses('符号链接|重定向')

    def test_empty_save_is_not_packaged_as_playable_progress(self):
        self.saved.write_bytes(b'')
        self.assert_refuses('BUP 进度为空', ['--with-save', str(self.saved)])

    def test_notice_distinguishes_original_logic_rights(self):
        self.assertIn('静态重编译生成的游戏逻辑', m.NOTICE)
        self.assertIn('不声称已获大宇（Softstar）', m.NOTICE)
        self.assertIn('MIT 许可适用于其所覆盖的运行时代码', m.NOTICE)
        self.assertNotIn('整个程序按', m.NOTICE)
        self.assertNotIn('本包不含任何原版游戏内容', m.NOTICE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
