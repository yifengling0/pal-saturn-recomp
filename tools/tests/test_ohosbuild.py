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


class LauncherFixture:
    """Fake DevEco/hdc tree shared by the launcher and generation tests."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='test-', dir=AUDIT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        runtime = self.root / 'build/pal-keyboard-runtime/src/host'
        runtime.mkdir(parents=True)
        current_host = b'#include "host_menu_text.h"\n// reviewed fixture host v13\n'
        (runtime / 'host.cpp').write_bytes(current_host)
        (runtime / 'host_menu_text.h').write_bytes(b'// fixture labels\n')
        mocker = patch.object(driver, 'OHOS_HOST_UI_SHA256', frozenset({hashlib.sha256(current_host).hexdigest()}))
        mocker.start()
        self.addCleanup(mocker.stop)
        generated = self.root / 'build/recomp'
        generated.mkdir(parents=True)
        (generated / 'p_true_000.cpp').write_text('sh2_hook(c, 0x06021C1Eu);')
        # Packaging defaults to the accelerated generation, so the fixture carries that tree too:
        # its movie hook plus the learner winbuild.py learn needs before it can generate.
        options = self.root / 'build/windows-pal-options'
        (options / 'recomp').mkdir(parents=True)
        (options / 'recomp/p_true_000.cpp').write_text('sh2_hook(c, 0x06021C1Eu);')
        (options / 'recomp-build').mkdir()
        (options / 'recomp-build' / ('saturn.exe' if os.name == 'nt' else 'saturn')).touch()
        self.recomp = options / 'recomp'
        self.project = self.root / 'harmony/pal-saturn-openharmony'
        self.output = self.project / 'entry/build/default/outputs/default'
        self.output.mkdir(parents=True)
        (self.project / 'entry/src/main/cpp').mkdir(parents=True)
        self.home = self.root / 'deveco'
        (self.home / 'tools/hvigor/bin').mkdir(parents=True)
        self.hvigor = self.home / 'tools/hvigor/bin' / ('hvigorw.bat' if os.name == 'nt' else 'hvigorw')
        self.hvigor.touch()
        node_dir = self.home / 'tools/node' / ('' if os.name == 'nt' else 'bin')
        node_dir.mkdir(parents=True)
        (node_dir / ('node.exe' if os.name == 'nt' else 'node')).touch()
        (self.home / 'tools/ohpm/bin').mkdir(parents=True)
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
                              side_effect=lambda root, generation=driver.MAPPING: self.events.append('verify'),
                              create=True)
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

class LauncherTests(LauncherFixture, unittest.TestCase):
    def test_missing_movie_hook_blocks_hvigor(self):
        (self.recomp / 'p_true_000.cpp').write_text('// old source without call')
        with self.assertRaises(SystemExit):
            self.invoke('--skip-learn')
        self.assertFalse(any('assembleHap' in c for c in self.commands()))

    def test_movie_hook_guard_after_learn(self):
        (self.recomp / 'p_true_000.cpp').write_text('')
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
        self.verify.assert_called_once_with(self.root, driver.ACCELERATED)
        self.assertEqual(self.events, ['learn', 'verify', 'hvigor'])

    def test_skip_learn_still_verifies_before_hvigor(self):
        self.invoke('--skip-learn')
        self.verify.assert_called_once_with(self.root, driver.ACCELERATED)
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
                    self.invoke(*(['--speed', 'mapping'] + (['--skip-learn'] if skip else [])))
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
                            self.invoke(*(['--speed', 'mapping'] + (['--skip-learn'] if skip else [])))
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
        self.hvigor.unlink()
        with patch.object(driver, 'deveco_home', side_effect=AssertionError('must not resolve DevEco')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(driver.main(['--logs']), 0)

    def test_logs_uses_explicit_deveco_hdc_without_hvigor(self):
        self.hvigor.unlink()
        hdc = self.home / 'sdk/default/openharmony/toolchains' / ('hdc.exe' if os.name == 'nt' else 'hdc')
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

    def test_logs_include_phone_orientation_diagnostics(self):
        self.logs = 'PAL/ORIENTATION getMainWindow failed code=1300005 sdk=26\nother-app unrelated\n'
        result, output = self.invoke('--logs')
        self.assertEqual(result, 0)
        self.assertIn('PAL/ORIENTATION getMainWindow failed code=1300005 sdk=26', output)
        self.assertNotIn('other-app unrelated', output)

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



class GenerationSelectionTests(LauncherFixture, unittest.TestCase):
    """Which generation a HAP is packaged from, and what that costs the native cache."""

    def pointer(self):
        return self.root / 'build/pal-ohos-generation.cmake'

    def test_accelerated_is_the_default_and_its_pointer_is_published(self):
        code, out = self.invoke()
        self.assertEqual(code, 0, out)
        self.assertTrue(any('--pal-options' in cmd for cmd in self.commands()),
                        'learn must run the accelerated generation by default')
        text = self.pointer().read_text()
        self.assertIn('set(PAL_OHOS_RECOMP "', text)
        self.assertIn('windows-pal-options/recomp', text)
        self.assertIn('windows-pal-options/runtime', text)

    def test_mapping_generation_leaves_no_pointer_behind(self):
        self.invoke('--speed', 'mapping')
        self.assertFalse(self.pointer().exists())
        self.assertFalse(any('--pal-options' in cmd for cmd in self.commands()))
        # Switching back and forth must not leave the previous pointer in place.
        self.invoke()
        self.assertTrue(self.pointer().is_file())

    def test_only_a_disagreeing_native_cache_is_dropped(self):
        keep = self.project / 'entry/.cxx/keep/CMakeCache.txt'
        drop = self.project / 'entry/.cxx/drop/CMakeCache.txt'
        runtime = (self.root / 'build/windows-pal-options/runtime').as_posix()
        for path, value in ((keep, runtime), (drop, (self.root / 'build/pal-keyboard-runtime').as_posix())):
            path.parent.mkdir(parents=True)
            path.write_text('SATURN_RUNTIME:PATH=' + value + '\n', encoding='utf-8')
        self.assertEqual(driver.drop_stale_native_caches(self.root / 'build/windows-pal-options/runtime'), 1)
        self.assertTrue(keep.is_file())
        self.assertFalse(drop.exists())
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
                        b'extern "C" int pal_host_ui_feature_version() { return 13; }\n'
                        b'// current reviewed layout implementation\n')
        self.host.write_bytes(self.current)
        self.labels.write_bytes(b'// reviewed labels; hashes owned by full verifier\n')
        mocker = patch.object(driver, 'OHOS_HOST_UI_SHA256',
                              frozenset({hashlib.sha256(self.current).hexdigest()}))
        mocker.start()
        self.addCleanup(mocker.stop)

    def verify(self):
        with contextlib.redirect_stdout(io.StringIO()):
            driver.verify_required_ohos_ui(self.root, self.runtime)

    def test_new_0013_host_is_accepted(self):
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

    def test_self_consistent_0012_host_with_identity_symbols_is_rejected(self):
        self.host.write_bytes(self.current.replace(b'return 13;', b'return 12;'))
        with self.assertRaisesRegex(SystemExit, '身份不符'):
            self.verify()

    def test_old_host_with_version_13_pasted_on_is_rejected(self):
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
        # Directories a previous run could not delete (see _release) are unlocked by now, so reclaim
        # them here rather than letting tools/ fill up between runs.
        for stale in AUDIT.glob('native-identity-*'):
            shutil.rmtree(stale, ignore_errors=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='native-identity-', dir=AUDIT)
        # Windows keeps a freshly linked identity.dll locked for a moment after the loader is done
        # with it, so the assertions pass and only the teardown fails; that left a directory in
        # tools/ on every run here.
        self.addCleanup(self._release)
        self.root = Path(self.tmp.name).resolve()
        self.cpp = AUDIT.parent / 'harmony/pal-saturn-openharmony/entry/src/main/cpp'
        self.cmake = os.environ.get('PAL_CMAKE') or shutil.which('cmake')
        self.cxx = os.environ.get('CXX') or shutil.which('c++')
        self.host = self.root / 'build/pal-keyboard-runtime/src/host/host.cpp'
        self.host.parent.mkdir(parents=True)
        self.host.write_text('int fixture_host() { return 0; }\n')

    def _release(self):
        """Drop the temp dir, tolerating the window where Windows still holds the linked DLL."""
        name = self.tmp.name
        try:
            self.tmp.cleanup()
        except OSError:
            # This process loaded identity.dll with ctypes and ctypes cannot free a library, so the
            # handle only goes when pytest exits. The next run sweeps what is left; git ignores it.
            pass

    def configure(self, selected_runtime=None, selected_host=None, extra_host=None):
        if not self.cmake:
            self.skipTest('cmake unavailable; set PAL_CMAKE to the existing executable')
        source = (self.cpp / 'CMakeLists.txt').read_text(encoding='utf-8')
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
        entry = (self.cpp / 'pal_ohos_entry.cpp').read_text(encoding='utf-8')
        required = driver.OHOS_HOST_UI_VERSION
        self.assertIn(f'if (host_ui_version != {required})', entry)
        cmake = (self.cpp / 'CMakeLists.txt').read_text(encoding='utf-8')
        self.assertIn('set_property(TARGET main APPEND_STRING PROPERTY LINK_FLAGS " -Wl,--no-undefined")', cmake)
        declarations = []
        for symbol, type_name in [('pal_host_ui_feature_version', 'int'),
                                  ('pal_host_ui_source_hash', 'const char*')]:
            declaration = f'extern "C" {type_name} {symbol}();'
            self.assertIn(declaration, entry)
            self.assertGreaterEqual(entry.count(symbol + '()'), 2)
            declarations.append(declaration)
        client = self.root / 'client.cpp'
        client.write_text('\n'.join(declarations) +
                          '\nint main() { return pal_host_ui_feature_version() != ' + str(required) +
                          ' || !pal_host_ui_source_hash(); }\n')
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
        result, _, _ = self.link('extern "C" int pal_host_ui_feature_version() { return 13; }\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pal_host_ui_source_hash', result.stderr)

    def test_new_host_object_links_and_reports_actual_source_hash(self):
        result, binary, digest = self.link(
            'extern "C" int pal_host_ui_feature_version() { return 13; }\n'
            'extern "C" const char* pal_host_ui_source_hash() { return PAL_HOST_UI_SOURCE_SHA256; }\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        library = ctypes.CDLL(str(binary))
        library.pal_host_ui_feature_version.restype = ctypes.c_int
        library.pal_host_ui_source_hash.restype = ctypes.c_char_p
        self.assertEqual(library.pal_host_ui_feature_version(), 13)
        self.assertEqual(library.pal_host_ui_source_hash().decode(), digest)
        library.main.restype = ctypes.c_int
        self.assertEqual(library.main(), 0)

    def test_ui12_strong_symbols_link_but_fail_ui13_version_gate(self):
        result, binary, _ = self.link(
            'extern "C" int pal_host_ui_feature_version() { return 12; }\n'
            'extern "C" const char* pal_host_ui_source_hash() { return PAL_HOST_UI_SOURCE_SHA256; }\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        library = ctypes.CDLL(str(binary))
        library.main.restype = ctypes.c_int
        self.assertEqual(library.main(), 1)


class CurrentGenerationPinsTests(unittest.TestCase):
    def test_orientation_dispatch_runtime_pins_reject_previous_hosts(self):
        import pal_keyboard_profile as keyboard
        import pal_paired_frame_queue as paired
        # Raw and post-precise/paired 0029/0030 hosts from the sequential patch
        # replay. The old variants have a visible but inert orientation row.
        self.assertTrue({
            '8c9937895723faf4ee6de5b90316cfa484ee4bfac098ba494f572076757046e8',
            'f8936d6b0a3407d7cdf2c638544e335220b5ad34ffad4c90fe8c50edc2b427e0',
            '42a042bb96b533aca432ed99ffa791c62aaa6b5e7bb4ea8b218d6752a4120734',
            '472ba48e74eafd9ede0cddbc42c598e678818962677f78338a54c9f5f53f62f3',
        }.issubset(keyboard.RUNTIME_HASHES['host.cpp']))
        self.assertFalse(set(keyboard.RUNTIME_HASHES['host.cpp']) & {
            'a99b1ac4806643f44e5b5b703f32653895a34173ad8492c129ccca8d3f53a238',
            '330f3ac807733bd0ead2c50f609a3cc7473b88b2a90560774edf082fc2e9f36d',
            '9bd3e7b899636283c28a699db5f0e2e7548c867b762320c118b7a58ec3efd521',
            'b7711256d4e8a10546076eba03398264578a34ff67e94c01fbf89637af3aa839',
        })
        self.assertEqual(paired.HOST_DISPLAY_PIN,
                         '5ad60b79602b47adaa8478eda042005cbc1e57b10a9e3a846f8f497f69026454')
        self.assertIn(paired.HOST_DISPLAY_PIN, paired.HOST_INPUT_SHA256)
        self.assertNotIn('5f8ef2f0179c52301cc2a2d2de30535ec7fedab20862a1b42cb716d52ba0919e',
                         paired.HOST_INPUT_SHA256)

    def test_current_mapping_and_accelerated_exact_pins(self):
        # Independently replayed patch chain plus precise/paired, keyboard and
        # scoped prompt transforms, with explicit logical master input ownership.
        self.assertEqual(driver.OHOS_HOST_UI_SHA256, frozenset({
            'c5671677972bfb99fff1826e4b5eb6ef47b2d6c24cd3ca021350054b378aec69',
            '0f3def87ffa2fc3491e583b8c38469cf22b02e5b8150eee37721c56d33e657a4',
        }))

    def test_previous_ui13_hosts_are_no_longer_accepted(self):
        self.assertFalse(driver.OHOS_HOST_UI_SHA256 & {
            # Before the orientation choice gained keyboard/controller/row dispatch.
            '90d28263e77914c46362695bb35f83b76234ce4daf19f3c35974b3659231436e',
            'ae0473569b0158d84ed40a6345f57a67217a3a288beb7ead66bb181e683223e5',
            '6f7c1852106b97c05fcdc249326c46e83452039a94941fbf3e1af6a92b5d8630',
            '84ad5bfa29e649407276785db68d6d8229c9d3b7b4f07a35f31fa377d479a464',
            '8f6225b5d4ea4c430992016f62254e4608c8cfac686d7a2af45edfd5fb636fa3',
            '14afb157a0018c6356b6f66f6a9bd69315adba02861005e07e801bed4e9a6c62',
            'f2ae4720395b317f8fdaf372c148021f565eafbfc02aa5278b46e2df848edabc',
            '6ddaa48666cbada98adde0527ae6f205f13e6967479e684aa29553c3b9c61b23',
            '9f167a6f7e80353d5d469ff5c0bb82fab5b760f805e770966a89b658231e51f2',
            '7c48c8ad21c9bedc51ac4390ebef9d66516966a9e574e924056bd23f8e1875a3',
            '8e1db06d45be432c08257b6be966d6fa85bddecd7dff4e3d8c2bc20d39b96f3d',
            '8937b8d3c31929d985406b33a2119cf80877ae85d11abd63c808532434bfe3d6',

            '6f43dc25fb417a481f8576c66405a28e537281b46b5d253a81def7d5244f6886',
            'cc9e663c9c1d44e140daa4288bdbafcb8b147c29e9e2513c4f293c24a953681a',
            'fc6905e7db4acdd74372706a83461e0cf463c91d27835428eee947262e0c0398',
            '808098fd058a034da91e63cda91745dfd9e58716ff537fbdc6409c79fa12a3af',
            'c69b7a176ecf926c06ad5351c2d6b7d5edcab507c9a61639e949308190c495c6',
            'bd2449a58ac52d73d08a304b84efb1781a22d0a7144ef16fe31b487407d09d79',
        })

    @unittest.skipUnless(shutil.which('cmake'), 'CMake unavailable')
    def test_cmake_mapping_fallback_and_accelerated_pointer(self):
        cmake = AUDIT.parent / 'harmony/pal-saturn-openharmony/entry/src/main/cpp/CMakeLists.txt'
        source = cmake.read_text(encoding='utf-8')
        selection = source[source.index('set(_PAL_OHOS_GENERATION '):source.index('set(SATURN_RUNTIME ')]
        for speed, recomp, runtime in [('mapping', 'recomp', 'pal-keyboard-runtime'),
                                       ('accelerated', 'windows-pal-options/recomp', 'windows-pal-options/runtime')]:
            with self.subTest(speed=speed), tempfile.TemporaryDirectory(dir=AUDIT) as d:
                root = Path(d)
                (root / 'build').mkdir()
                if speed == 'accelerated':
                    (root / 'build/pal-ohos-generation.cmake').write_text(
                        f'set(PAL_OHOS_RECOMP "{root}/build/{recomp}")\n'
                        f'set(PAL_OHOS_RUNTIME "{root}/build/{runtime}")\n')
                script = root / 'verify.cmake'
                script.write_text(f'set(PAL_ROOT "{root}")\n' + selection +
                    f'if(NOT PAL_OHOS_RECOMP STREQUAL "{root}/build/{recomp}" OR '
                    f'NOT PAL_OHOS_RUNTIME STREQUAL "{root}/build/{runtime}")\n'
                    'message(FATAL_ERROR "Wrong generation pair")\nendif()\n')
                result = subprocess.run(['cmake', '-P', str(script)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CrossPlatformToolPathsTests(unittest.TestCase):
    def setUp(self):
        host = patch.object(driver, 'os', types.SimpleNamespace(name='posix'))
        host.start()
        self.addCleanup(host.stop)


    def make(self, root, names):
        for name in names:
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        (root / 'sdk').mkdir()

    def test_official_linux_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            self.make(h, ['bin/hvigorw', 'bin/ohpm', 'tool/node/bin/node'])
            self.assertEqual(driver.deveco_cli_paths(h), (h / 'bin/hvigorw', h / 'tool/node', h / 'bin'))

    def test_studio_unix_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            self.make(h, ['tools/hvigor/bin/hvigorw', 'tools/node/bin/node', 'tools/ohpm/bin/ohpm'])
            self.assertEqual(driver.deveco_cli_paths(h)[0], h / 'tools/hvigor/bin/hvigorw')

    def test_windows_studio_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            self.make(h, ['tools/hvigor/bin/hvigorw.bat', 'tools/node/node.exe', 'tools/ohpm/bin/ohpm.bat'])
            with patch.object(driver, 'os', types.SimpleNamespace(name='nt')):
                self.assertEqual(driver.deveco_cli_paths(h)[0], h / 'tools/hvigor/bin/hvigorw.bat')

    def test_reject_incomplete_sdk(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                driver.deveco_cli_paths(Path(tmp))

    def test_linux_hdc_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            p = h / 'sdk/default/openharmony/toolchains/hdc'
            p.parent.mkdir(parents=True)
            p.touch()
            with patch.object(driver.shutil, 'which', return_value=None):
                self.assertEqual(driver.find_hdc(h), str(p))

    def test_linux_native_learner_has_no_exe_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            self.assertEqual(driver.native_learner(h, driver.ACCELERATED), h / 'build/windows-pal-options/recomp-build/saturn')

    def test_windows_native_learner_keeps_exe_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            with patch.object(driver, 'os', types.SimpleNamespace(name='nt')):
                self.assertEqual(driver.native_learner(h, driver.ACCELERATED), h / 'build/windows-pal-options/recomp-build/saturn.exe')

    def test_linux_project_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            p = h / 'build/venv/bin/python'
            p.parent.mkdir(parents=True)
            p.touch()
            self.assertEqual(driver.project_python(h), p)

    def test_windows_project_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            p = h / 'build/venv/Scripts/python.exe'
            p.parent.mkdir(parents=True)
            p.touch()
            with patch.object(driver, 'os', types.SimpleNamespace(name='nt')):
                self.assertEqual(driver.project_python(h), p)

    def test_project_python_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(driver.project_python(Path(tmp)), Path(driver.sys.executable))

if __name__ == '__main__':
    unittest.main(verbosity=2)
