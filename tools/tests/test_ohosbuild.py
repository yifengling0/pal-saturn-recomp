"""Launcher regression tests. Every subprocess call is mocked; no hvigor/hdc runs."""
from __future__ import annotations

import contextlib
import ctypes
import importlib.util
import io
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


AUDIT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OHOSBUILD_UNDER_TEST', AUDIT / 'ohosbuild.py'))
spec = importlib.util.spec_from_file_location('ohosbuild_under_test', SOURCE)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='test-', dir=AUDIT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        runtime = self.root / 'build/pal-keyboard-runtime/src/host'
        runtime.mkdir(parents=True)
        current_host = b'#include "host_menu_text.h"\n// reviewed fixture host v12\n'
        (runtime / 'host.cpp').write_bytes(current_host)
        (runtime / 'host_menu_text.h').write_bytes(b'// fixture labels\n')
        mocker = patch.object(driver, 'OHOS_HOST_UI_SHA256', frozenset({hashlib.sha256(current_host).hexdigest()}))
        mocker.start()
        self.addCleanup(mocker.stop)
        generated = self.root / 'build/recomp'
        generated.mkdir(parents=True)
        (generated / 'p_true_000.cpp').write_text('sh2_hook(c, 0x06021C1Eu);')
        self.project = self.root / 'harmony/pal-saturn-openharmony'
        self.output = self.project / 'entry/build/default/outputs/default'
        self.output.mkdir(parents=True)
        (self.project / 'entry/src/main/cpp').mkdir(parents=True)
        self.home = self.root / 'deveco'
        (self.home / 'tools/hvigor/bin').mkdir(parents=True)
        (self.home / 'tools/hvigor/bin/hvigorw.bat').touch()
        (self.home / 'sdk').mkdir()
        self.hdc = '/mock/bin/hdc'
        self.calls = []
        self.events = []
        self.fresh = {'entry-default-signed.hap': b'fresh-signed'}
        self.hvigor_returncode = 0
        self.device_returncode = 0
        self.device_output = 'tablet USB Connected device\n'
        self.logs_returncode = 0
        self.logs = 'PAL/OHOS stopped after N VBlanks\nPAL/OHOS audio stream: 0 times empty\nother-app unrelated\n'
        self.log_exception = None
        self.git_sha = 'a' * 40
        self.git_status = ''
        self.git_exception = None
        for name, value in [('ROOT', self.root), ('PROJECT', self.project), ('HAP_OUT', self.output)]:
            mocker = patch.object(driver, name, value)
            mocker.start()
            self.addCleanup(mocker.stop)
        for mocker in [patch.object(driver.subprocess, 'run', side_effect=self.fake_run),
                       patch.object(driver.shutil, 'which', return_value=self.hdc),
                       patch.object(driver.time, 'sleep')]:
            mocker.start()
            self.addCleanup(mocker.stop)
        self.real_verify = getattr(driver, 'verify_existing_runtime', None)
        mocker = patch.object(driver, 'verify_existing_runtime',
                              side_effect=lambda root: self.events.append('verify'), create=True)
        self.verify = mocker.start()
        self.addCleanup(mocker.stop)

    def fake_run(self, cmd, **kwargs):
        cmd = [str(x) for x in cmd]
        self.calls.append((cmd, kwargs))
        if 'learn' in cmd:
            self.events.append('learn')
        if 'assembleHap' in cmd:
            self.events.append('hvigor')
            if self.hvigor_returncode == 0:
                for name, data in self.fresh.items():
                    (self.output / name).write_bytes(data)
            return subprocess.CompletedProcess(cmd, self.hvigor_returncode, '', '')
        if cmd[0] == 'git':
            if self.git_exception:
                raise self.git_exception
            return subprocess.CompletedProcess(cmd, 0, self.git_sha if 'rev-parse' in cmd else self.git_status, '')
        if cmd[1:4] == ['list', 'targets', '-v']:
            return subprocess.CompletedProcess(cmd, self.device_returncode, self.device_output, '')
        if 'hilog' in cmd:
            if self.log_exception:
                raise self.log_exception
            return subprocess.CompletedProcess(cmd, self.logs_returncode, self.logs, '')
        return subprocess.CompletedProcess(cmd, 0, '', '')

    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = driver.main(['--deveco', str(self.home), *args])
        return result, output.getvalue()

    def commands(self):
        return [cmd for cmd, kwargs in self.calls]

    def test_missing_movie_hook_blocks_hvigor(self):
        (self.root / 'build/recomp/p_true_000.cpp').write_text('// old source without call')
        with self.assertRaises(SystemExit):
            self.invoke('--skip-learn')
        self.assertFalse(any('assembleHap' in c for c in self.commands()))

    def test_movie_hook_guard_after_learn(self):
        (self.root / 'build/recomp/p_true_000.cpp').write_text('')
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertIn('learn', self.events)
        self.assertFalse(any('assembleHap' in c for c in self.commands()))

    def test_default_release(self):
        result, text = self.invoke()
        self.assertEqual(result, 0)
        build = next(cmd for cmd in self.commands() if 'assembleHap' in cmd)
        self.assertIn('buildMode=release', build)
        self.assertIn('实际 native 编译旗标', text)
        self.assertFalse(any(cmd[0] == self.hdc for cmd in self.commands()))

    def test_explicit_debug_and_skip_learn(self):
        self.invoke('--build-mode', 'debug', '--skip-learn')
        self.assertIn('buildMode=debug', next(cmd for cmd in self.commands() if 'assembleHap' in cmd))
        self.assertFalse(any('learn' in cmd for cmd in self.commands()))

    def test_learn_still_precedes_build(self):
        self.invoke()
        learn = next(i for i, cmd in enumerate(self.commands()) if 'learn' in cmd)
        build = next(i for i, cmd in enumerate(self.commands()) if 'assembleHap' in cmd)
        self.assertLess(learn, build)

    def test_verify_runs_after_learn_and_before_hvigor(self):
        self.invoke()
        self.verify.assert_called_once_with(self.root)
        self.assertEqual(self.events, ['learn', 'verify', 'hvigor'])

    def test_skip_learn_still_verifies_before_hvigor(self):
        self.invoke('--skip-learn')
        self.verify.assert_called_once_with(self.root)
        self.assertEqual(self.events, ['verify', 'hvigor'])

    def test_logs_does_not_verify_or_import_runtime(self):
        self.invoke('--logs')
        self.verify.assert_not_called()
        self.assertEqual(self.events, [])

    def fake_profile(self, error=None):
        return types.SimpleNamespace(__file__=str(self.root / 'tools/pal_keyboard_profile.py'),
                                     prepare_keyboard=Mock(side_effect=error))

    def put_manifest(self):
        path = self.root / 'build/recomp/pal-keyboard-manifest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"version":"fixture"}\n')
        return path

    def test_missing_manifest_never_calls_prepare_or_writes(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        profile = self.fake_profile()
        with patch.dict(sys.modules, {'pal_keyboard_profile': profile}):
            with self.assertRaisesRegex(SystemExit, '先重新生成'):
                self.real_verify(self.root)
        profile.prepare_keyboard.assert_not_called()
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_existing_manifest_calls_local_profile_read_only(self):
        manifest = self.put_manifest()
        before = manifest.read_bytes()
        profile = self.fake_profile()
        previous = sys.dont_write_bytecode
        with patch.dict(sys.modules, {'pal_keyboard_profile': profile}), contextlib.redirect_stdout(io.StringIO()):
            self.real_verify(self.root)
        profile.prepare_keyboard.assert_called_once_with(self.root / 'build/recomp',
                                                          self.root / 'build/pal-keyboard-runtime', self.root,
                                                          verify_only=True)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertEqual(sys.dont_write_bytecode, previous)

    def test_self_consistent_old_ui_blocks_hvigor_after_general_verification(self):
        self.put_manifest()
        host = self.root / 'build/pal-keyboard-runtime/src/host/host.cpp'
        host.write_bytes(b'#include "host_menu_text.h"\n// old layout with a current manifest\n')
        self.verify.side_effect = self.real_verify
        for skip in (False, True):
            self.calls.clear()
            profile = self.fake_profile()
            with patch.dict(sys.modules, {'pal_keyboard_profile': profile}):
                with self.assertRaisesRegex(SystemExit, '身份不符'):
                    self.invoke(*(['--skip-learn'] if skip else []))
            profile.prepare_keyboard.assert_called_once()
            self.assertFalse(any('assembleHap' in cmd or 'install' in cmd for cmd in self.commands()))

    def test_profile_from_another_checkout_is_rejected(self):
        self.put_manifest()
        profile = self.fake_profile()
        profile.__file__ = str(self.root / 'other/tools/pal_keyboard_profile.py')
        with patch.dict(sys.modules, {'pal_keyboard_profile': profile}):
            with self.assertRaisesRegex(SystemExit, '其他目录'):
                self.real_verify(self.root)
        profile.prepare_keyboard.assert_not_called()

    def test_missing_stale_or_tampered_runtime_aborts_before_hvigor(self):
        for skip in [False, True]:
            for kind in ['missing', 'stale', 'tampered']:
                with self.subTest(skip_learn=skip, kind=kind):
                    self.calls.clear()
                    self.events.clear()
                    manifest = self.root / 'build/recomp/pal-keyboard-manifest.json'
                    if manifest.exists():
                        manifest.unlink()
                    if kind != 'missing':
                        self.put_manifest()
                    profile = self.fake_profile(ValueError(kind + ' fixture'))
                    self.verify.side_effect = self.real_verify
                    with patch.dict(sys.modules, {'pal_keyboard_profile': profile}):
                        with self.assertRaises(SystemExit):
                            self.invoke(*(['--skip-learn'] if skip else []))
                    self.assertFalse(any('assembleHap' in cmd or 'install' in cmd for cmd in self.commands()))
                    if kind == 'missing':
                        profile.prepare_keyboard.assert_not_called()
                        self.assertFalse(manifest.exists())
                    else:
                        profile.prepare_keyboard.assert_called_once()
                        self.assertEqual(manifest.read_text(), '{"version":"fixture"}\n')

    def test_rejects_unchanged_old_hap(self):
        (self.output / 'entry-default-signed.hap').write_bytes(b'old-signed')
        self.fresh = {}
        with self.assertRaisesRegex(SystemExit, '拒绝拾取旧产物'):
            self.invoke('--install')
        self.assertFalse(any('install' in cmd for cmd in self.commands()))

    def test_ignores_old_signed_when_unsigned_new(self):
        (self.output / 'entry-default-signed.hap').write_bytes(b'old-signed')
        self.fresh = {'entry-default-unsigned.hap': b'new-unsigned'}
        with self.assertRaisesRegex(SystemExit, 'signed HAP'):
            self.invoke('--install')
        self.assertFalse(any('install' in cmd for cmd in self.commands()))

    def test_empty_hap_is_not_installable(self):
        self.fresh = {'entry-default-signed.hap': b''}
        with self.assertRaisesRegex(SystemExit, '非空 HAP'):
            self.invoke('--install')

    def test_multiple_fresh_signed_haps_refused(self):
        self.fresh = {'a-signed.hap': b'a', 'b-signed.hap': b'b'}
        with self.assertRaisesRegex(SystemExit, '恰有一个'):
            self.invoke('--install')
        self.assertFalse(any('install' in cmd for cmd in self.commands()))

    def test_unsigned_build_only_still_succeeds(self):
        self.fresh = {'entry-default-unsigned.hap': b'unsigned'}
        result, output = self.invoke()
        self.assertEqual(result, 0)
        self.assertIn('未签名', output)

    def test_fresh_install_honors_device_without_launch(self):
        self.device_output += 'phone USB Connected device\n'
        self.invoke('--install', '--device', 'phone')
        install = next(cmd for cmd in self.commands() if 'install' in cmd)
        self.assertEqual(install[:5], [self.hdc, '-t', 'phone', 'install', '-r'])
        self.assertFalse(any('aa' in cmd for cmd in self.commands()))

    def test_unknown_device_does_not_install(self):
        with self.assertRaisesRegex(SystemExit, '不在线'):
            self.invoke('--install', '--device', 'missing')
        self.assertFalse(any('install' in cmd for cmd in self.commands()))

    def test_hvigor_failure_never_installs(self):
        self.hvigor_returncode = 17
        with self.assertRaisesRegex(SystemExit, '17'):
            self.invoke('--install')
        self.assertFalse(any('install' in cmd for cmd in self.commands()))

    def test_launch_and_later_logs_never_clear(self):
        result, output = self.invoke('--launch', '--device', 'tablet')
        self.assertEqual(result, 0)
        self.assertTrue(any('install' in cmd for cmd in self.commands()))
        self.assertTrue(any('aa' in cmd and 'start' in cmd for cmd in self.commands()))
        self.assertTrue(any('hilog' in cmd and '-x' in cmd for cmd in self.commands()))
        self.assertFalse(any('hilog' in cmd and '-r' in cmd for cmd in self.commands()))
        self.assertIn('Quit 后单独运行 --logs', output)

    def test_logs_standalone_no_build_install_launch_or_reset(self):
        self.device_output += 'phone USB Connected device\n'
        result, output = self.invoke('--logs', '--device', 'phone', '--log-timeout', '7')
        self.assertEqual(result, 0)
        self.assertIn('audio stream: 0 times empty', output)
        self.assertIn('可能含多次运行', output)
        self.assertNotIn('other-app unrelated', output)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[-1][0], [self.hdc, '-t', 'phone', 'shell', 'hilog', '-x'])
        self.assertEqual(self.calls[-1][1]['timeout'], 7)

    def test_logs_works_with_path_hdc_without_deveco(self):
        (self.home / 'tools/hvigor/bin/hvigorw.bat').unlink()
        with patch.object(driver, 'deveco_home', side_effect=AssertionError('must not resolve DevEco')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(driver.main(['--logs']), 0)

    def test_logs_uses_explicit_deveco_hdc_without_hvigor(self):
        (self.home / 'tools/hvigor/bin/hvigorw.bat').unlink()
        hdc = self.home / 'sdk/default/openharmony/toolchains/hdc.exe'
        hdc.parent.mkdir(parents=True)
        hdc.touch()
        with patch.object(driver.shutil, 'which', return_value=None):
            result, output = self.invoke('--logs', '--device', 'tablet')
        self.assertEqual(result, 0)
        self.assertEqual(self.calls[-1][0][0], str(hdc))

    def test_missing_hdc_reported_before_any_process(self):
        with patch.object(driver.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(SystemExit, '找不到 hdc'):
                self.invoke('--logs')
        self.assertEqual(self.calls, [])

    def test_logs_conflicting_launch_or_install_rejected(self):
        for flag in ['--launch', '--install', '--skip-learn']:
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.invoke('--logs', flag)
        self.assertEqual(self.calls, [])

    def test_empty_matching_logs_still_reports_snapshot_limit(self):
        self.logs = 'unrelated app\n'
        result, output = self.invoke('--logs')
        self.assertEqual(result, 0)
        self.assertIn('没有匹配', output)
        self.assertIn('覆盖', output)

    def test_logs_conflicting_selftest_does_not_write(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke('--logs', '--selftest', 'on')
        self.assertFalse((self.project / 'entry/src/main/cpp/selftest.txt').exists())
        self.assertEqual(self.calls, [])

    def test_logs_invalid_timeout_rejected(self):
        for value in ['0', '121', '-1']:
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.invoke('--logs', '--log-timeout', value)
        self.assertEqual(self.calls, [])

    def test_logs_timeout_is_reported_without_reinstall(self):
        self.log_exception = subprocess.TimeoutExpired('hdc', 30)
        with self.assertRaisesRegex(SystemExit, '快照失败或超时'):
            self.invoke('--logs')
        self.assertFalse(any('install' in cmd for cmd in self.commands()))

    def test_logs_command_failure_is_not_success(self):
        self.logs_returncode = 3
        with self.assertRaisesRegex(SystemExit, '退出码 3'):
            self.invoke('--logs')

    def test_device_query_failure_is_not_empty_logs_success(self):
        self.device_returncode = 2
        with self.assertRaisesRegex(SystemExit, '设备查询失败'):
            self.invoke('--logs')
        self.assertFalse(any('hilog' in cmd for cmd in self.commands()))

    def test_device_selection_zero_one_many_missing(self):
        cases = [
            ('', None, None, '没有在线设备'),
            ('tablet USB Offline device\n', None, None, '没有在线设备'),
            ('tablet USB Connected device\n', None, 'tablet', None),
            ('tablet USB Connected device\nphone USB Connected device\n', None, None, '多台在线设备'),
            ('tablet USB Connected device\nphone USB Connected device\n', 'phone', 'phone', None),
            ('tablet USB Connected device\nphone USB Offline device\n', 'phone', None, '不在线'),
            ('tablet USB Connected device\n', 'missing', None, '不在线'),
            ('tablet USB Connected device\n', '', None, '不在线'),
            ('tablet USB Connected device\ntablet USB Connected device\n', None, 'tablet', None),
        ]
        for listing, wanted, expected, error in cases:
            with self.subTest(listing=listing, wanted=wanted):
                self.device_output = listing
                if error:
                    with self.assertRaisesRegex(SystemExit, error):
                        driver.hdc_target(self.hdc, wanted)
                else:
                    self.assertEqual(driver.hdc_target(self.hdc, wanted), expected)

    def test_logs_install_launch_reject_zero_multiple_or_missing_device(self):
        cases = [
            ('', [], '没有在线设备'),
            ('tablet USB Connected device\nphone USB Connected device\n', [], '多台在线设备'),
            ('tablet USB Connected device\n', ['--device', 'missing'], '不在线'),
        ]
        for mode in ['--logs', '--install', '--launch']:
            for listing, choice, error in cases:
                with self.subTest(mode=mode, choice=choice, error=error):
                    self.calls.clear()
                    self.device_output = listing
                    with self.assertRaisesRegex(SystemExit, error):
                        self.invoke(mode, *choice)
                    self.assertFalse(any('install' in cmd or 'aa' in cmd or 'hilog' in cmd
                                         for cmd in self.commands()))

    def test_logs_install_launch_allow_one_or_explicit_online_device(self):
        cases = [
            ('tablet USB Connected device\n', [], 'tablet'),
            ('tablet USB Connected device\nphone USB Connected device\n', ['--device', 'phone'], 'phone'),
        ]
        for mode in ['--logs', '--install', '--launch']:
            for listing, choice, expected in cases:
                with self.subTest(mode=mode, choice=choice):
                    self.calls.clear()
                    self.device_output = listing
                    result, output = self.invoke(mode, *choice)
                    self.assertEqual(result, 0)
                    actions = [cmd for cmd in self.commands()
                               if 'install' in cmd or 'aa' in cmd or 'hilog' in cmd]
                    self.assertTrue(actions)
                    for cmd in actions:
                        self.assertEqual(cmd[:3], [self.hdc, '-t', expected])

    def test_selftest_switch_compatible(self):
        self.invoke('--selftest', 'on')
        self.assertEqual((self.project / 'entry/src/main/cpp/selftest.txt').read_text(), 'on\n')

    def test_sdl_revision_is_sanitized_and_local_only(self):
        (self.root / 'third_party/sdl3-src/.git').mkdir(parents=True)
        self.git_status = ' M PRIVATE_FILENAME_DO_NOT_PRINT\n'
        _, output = self.invoke()
        self.assertIn(self.git_sha, output)
        self.assertIn('worktree=modified', output)
        self.assertNotIn('PRIVATE_FILENAME_DO_NOT_PRINT', output)
        git = [cmd for cmd in self.commands() if cmd[0] == 'git']
        self.assertEqual(len(git), 2)
        self.assertFalse(any('remote' in cmd or 'config' in cmd for cmd in git))

    def test_invalid_git_output_never_printed(self):
        (self.root / 'third_party/sdl3-src/.git').mkdir(parents=True)
        self.git_sha = 'credential-like-do-not-print'
        _, output = self.invoke()
        self.assertNotIn(self.git_sha, output)
        self.assertIn('SDL source revision: unavailable', output)

    def test_no_sdl_git_marker_does_not_report_parent_git(self):
        (self.root / 'third_party/sdl3-src').mkdir(parents=True)
        self.invoke()
        self.assertFalse(any(cmd[0] == 'git' for cmd in self.commands()))

    def test_git_timeout_nonfatal(self):
        (self.root / 'third_party/sdl3-src/.git').mkdir(parents=True)
        self.git_exception = subprocess.TimeoutExpired('git', 5)
        result, output = self.invoke()
        self.assertEqual(result, 0)
        self.assertIn('SDL source revision: unavailable', output)

    def test_same_mtime_size_content_change_detected(self):
        path = self.output / 'entry-default-signed.hap'
        path.write_bytes(b'old')
        before = driver.hap_snapshot()
        old_stat = path.stat()
        path.write_bytes(b'new')
        os.utime(path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
        self.assertNotEqual(before[path], driver.hap_snapshot()[path])


class RequiredUiTests(unittest.TestCase):
    """Source identity tests; the general planner still owns full helper hashes."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ui-identity-', dir=AUDIT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.runtime = self.root / 'build/pal-keyboard-runtime'
        self.host = self.runtime / 'src/host/host.cpp'
        self.labels = self.host.with_name('host_menu_text.h')
        self.host.parent.mkdir(parents=True)
        self.current = (b'#include "host_menu_text.h"\n'
                        b'extern "C" int pal_host_ui_feature_version() { return 12; }\n'
                        b'// current reviewed layout implementation\n')
        self.host.write_bytes(self.current)
        self.labels.write_bytes(b'// reviewed labels; hashes owned by full verifier\n')
        mocker = patch.object(driver, 'OHOS_HOST_UI_SHA256',
                              frozenset({hashlib.sha256(self.current).hexdigest()}))
        mocker.start()
        self.addCleanup(mocker.stop)

    def verify(self):
        with contextlib.redirect_stdout(io.StringIO()):
            driver.verify_required_ohos_ui(self.root)

    def test_new_0012_host_is_accepted(self):
        self.verify()

    def test_crlf_equivalent_approved_source_is_accepted(self):
        self.host.write_bytes(self.current.replace(b'\n', b'\r\n'))
        self.verify()

    def test_complete_old_0010_without_labels_is_rejected(self):
        self.host.write_bytes(b'// complete old host implementation\n')
        self.labels.unlink()
        with self.assertRaisesRegex(SystemExit, '重新生成'):
            self.verify()

    def test_old_0011_host_with_new_label_marker_still_rejected(self):
        self.host.write_bytes(b'#include "host_menu_text.h"\n// old 0011 layout\n')
        with self.assertRaisesRegex(SystemExit, '身份不符'):
            self.verify()

    def test_old_host_with_version_12_pasted_on_is_rejected(self):
        self.host.write_bytes(self.current.replace(b'current reviewed', b'old 0011'))
        with self.assertRaisesRegex(SystemExit, '身份不符'):
            self.verify()

    def test_empty_approved_hash_set_fails_closed(self):
        with patch.object(driver, 'OHOS_HOST_UI_SHA256', frozenset()):
            with self.assertRaisesRegex(SystemExit, '身份不符'):
                self.verify()

    def test_missing_host_or_labels_is_rejected_without_writes(self):
        for path in (self.host, self.labels):
            data = path.read_bytes()
            path.unlink()
            before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(SystemExit, '缺件或路径不安全'):
                self.verify()
            self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
            path.write_bytes(data)

    def test_host_symlink_is_rejected(self):
        other = self.root / 'other.cpp'
        other.write_bytes(self.current)
        self.host.unlink()
        try:
            self.host.symlink_to(other)
        except OSError as error:
            self.skipTest(f'symlinks unavailable: {error}')
        with self.assertRaisesRegex(SystemExit, '路径不安全'):
            self.verify()

    def test_runtime_symlink_is_rejected(self):
        moved = self.root / 'elsewhere'
        self.runtime.rename(moved)
        try:
            self.runtime.symlink_to(moved, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'symlinks unavailable: {error}')
        with self.assertRaisesRegex(SystemExit, '路径不安全'):
            self.verify()


class NativeIdentityContractTests(unittest.TestCase):
    """Real local compiler fixtures, not an OHOS SDK or device acceptance test."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='native-identity-', dir=AUDIT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.cpp = AUDIT.parent / 'harmony/pal-saturn-openharmony/entry/src/main/cpp'
        self.cmake = os.environ.get('PAL_CMAKE') or shutil.which('cmake')
        self.cxx = os.environ.get('CXX') or shutil.which('c++')
        self.host = self.root / 'build/pal-keyboard-runtime/src/host/host.cpp'
        self.host.parent.mkdir(parents=True)
        self.host.write_text('int fixture_host() { return 0; }\n')

    def configure(self, selected_runtime=None, selected_host=None, extra_host=None):
        if not self.cmake:
            self.skipTest('cmake unavailable; set PAL_CMAKE to the existing executable')
        source = (self.cpp / 'CMakeLists.txt').read_text()
        def block(name):
            return source.split('# PAL_OHOS_' + name + '_BEGIN\n', 1)[1].split(
                '# PAL_OHOS_' + name + '_END', 1)[0]
        runtime = selected_runtime or self.root / 'build/pal-keyboard-runtime'
        host = selected_host or self.host
        cmake = ('cmake_minimum_required(VERSION 3.16)\nproject(identity_fixture CXX)\n'
                 f'set(PAL_ROOT "{self.root.as_posix()}")\n'
                 f'set(SATURN_RUNTIME "{runtime.as_posix()}")\n' + block('RUNTIME_IDENTITY') +
                 f'add_library(saturn_host OBJECT "{host.as_posix()}")\n')
        if extra_host:
            cmake += f'target_sources(saturn_host PRIVATE "{extra_host.as_posix()}")\n'
        cmake += block('HOST_IDENTITY')
        (self.root / 'CMakeLists.txt').write_text(cmake)
        return subprocess.run([self.cmake, '-S', str(self.root), '-B', str(self.root / 'cmake-build')],
                              capture_output=True, text=True, timeout=60)

    def test_actual_source_path_and_hash_are_reported(self):
        result = self.configure()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(hashlib.sha256(self.host.read_bytes()).hexdigest(), result.stdout)

    def test_cmake_source_bytes_hash_preserves_crlf(self):
        self.host.write_bytes(b'int fixture_host() { return 0; }\r\n')
        result = self.configure()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('source_bytes_sha256=' + hashlib.sha256(self.host.read_bytes()).hexdigest(), result.stdout)

    def test_selected_runtime_from_another_directory_is_rejected(self):
        other = self.root / 'other-runtime'
        other.mkdir()
        result = self.configure(selected_runtime=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('OHOS must compile', result.stdout + result.stderr)

    def test_target_using_another_host_is_rejected(self):
        other = self.root / 'other/host.cpp'
        other.parent.mkdir()
        other.write_text('int old_host() { return 0; }\n')
        result = self.configure(selected_host=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('saturn_host must own', result.stdout + result.stderr)

    def test_target_with_two_host_sources_is_rejected(self):
        other = self.root / 'other/host.cpp'
        other.parent.mkdir()
        other.write_text('int second_host() { return 0; }\n')
        result = self.configure(extra_host=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('saturn_host must own', result.stdout + result.stderr)

    def link(self, source):
        if not self.cxx:
            self.skipTest('C++ compiler unavailable')
        entry = (self.cpp / 'pal_ohos_entry.cpp').read_text()
        cmake = (self.cpp / 'CMakeLists.txt').read_text()
        self.assertIn('set_property(TARGET main APPEND_STRING PROPERTY LINK_FLAGS " -Wl,--no-undefined")', cmake)
        declarations = []
        for symbol, type_name in [('pal_host_ui_feature_version', 'int'),
                                  ('pal_host_ui_source_hash', 'const char*')]:
            declaration = f'extern "C" {type_name} {symbol}();'
            self.assertIn(declaration, entry)
            self.assertGreaterEqual(entry.count(symbol + '()'), 2)
            declarations.append(declaration)
        client = self.root / 'client.cpp'
        client.write_text('#include <cstdio>\n' + '\n'.join(declarations) +
                          '\nint main() { std::printf("%d %s\\n", pal_host_ui_feature_version(), '
                          'pal_host_ui_source_hash()); return pal_host_ui_feature_version() != 12; }\n')
        self.host.write_text(source)
        digest = hashlib.sha256(self.host.read_bytes()).hexdigest()
        binary = self.root / ('identity.dll' if os.name == 'nt' else 'libidentity.so')
        result = subprocess.run([self.cxx, '-shared', '-fPIC', '-Wl,--no-undefined', str(client), str(self.host),
                                 f'-DPAL_HOST_UI_SOURCE_SHA256="{digest}"', '-o', str(binary)],
                                capture_output=True, text=True, timeout=60)
        return result, binary, digest

    def test_old_host_object_missing_strong_symbols_fails_link(self):
        result, _, _ = self.link('int old_host() { return 0; }\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pal_host_ui_feature_version', result.stderr)

    def test_version_only_marker_missing_source_symbol_fails_link(self):
        result, _, _ = self.link('extern "C" int pal_host_ui_feature_version() { return 12; }\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pal_host_ui_source_hash', result.stderr)

    def test_new_host_object_links_and_reports_actual_source_hash(self):
        result, binary, digest = self.link(
            'extern "C" int pal_host_ui_feature_version() { return 12; }\n'
            'extern "C" const char* pal_host_ui_source_hash() { return PAL_HOST_UI_SOURCE_SHA256; }\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        library = ctypes.CDLL(str(binary))
        library.pal_host_ui_feature_version.restype = ctypes.c_int
        library.pal_host_ui_source_hash.restype = ctypes.c_char_p
        self.assertEqual(library.pal_host_ui_feature_version(), 12)
        self.assertEqual(library.pal_host_ui_source_hash().decode(), digest)


if __name__ == '__main__':
    unittest.main(verbosity=2)
