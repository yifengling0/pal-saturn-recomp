"""Driver tests with mocked runtime imports: no external runtime code executes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('linuxbuild', Path(__file__).parents[1] / 'linuxbuild.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pal driver ')
        self.root = Path(self.temp.name)
        self.old_cwd = Path.cwd()
        self.game = SimpleNamespace(build='original', cmake=['WINDOWS=path'],
            modules=[], tasks=None, hooks={}, learned_seeds=lambda: {})
        self.generate = Mock()
        self.modules = {
            'saturnrecomp': SimpleNamespace(
                config=SimpleNamespace(load=Mock(return_value=self.game)),
                build=SimpleNamespace(stale=Mock(return_value=False)),
                prereqs=SimpleNamespace(probe=Mock(return_value=(None, False)))),
            'saturnrecomp.analysis': SimpleNamespace(resume=SimpleNamespace(for_game=Mock(return_value=[]))),
            'saturnrecomp.recomp.__main__': SimpleNamespace(generate=self.generate),
        }

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.temp.cleanup()

    def invoke(self, action, runner=None):
        with patch.object(m, 'ROOT', self.root), patch.dict(sys.modules, self.modules), \
             patch.object(sys, 'argv', ['linuxbuild.py', action]), \
             patch.object(m.shutil, 'which', return_value='/usr/bin/tool'), \
             patch.dict(os.environ, {}, clear=False), patch.object(m.subprocess, 'run', runner or Mock()):
            m.main()

    def test_missing_modules_fail_before_generation_or_build(self):
        self.game.modules = [SimpleNamespace(file=str(self.root / 'missing.bin'))]
        runner = Mock()
        with self.assertRaisesRegex(SystemExit, 'blocked-input'):
            self.invoke('build', runner)
        runner.assert_not_called()
        self.generate.assert_not_called()

    def test_check_does_not_generate_or_build(self):
        runner = Mock()
        self.invoke('check', runner)
        runner.assert_not_called()
        self.generate.assert_not_called()

    def test_paths_with_spaces_stay_separate_arguments(self):
        runner = Mock()
        self.invoke('build', runner)
        args = runner.call_args_list[0].args[0]
        self.assertIn(str(self.root / 'build/linux-game/recomp'), args)
        self.assertIn('-DSATURN_EXTRA=' + str(self.root / 'src/pal_game/pal_game.cmake'), args)
        self.assertNotIn('WINDOWS=path', args)
        self.assertIn('--fresh', args)
        self.assertEqual(runner.call_count, 2)

    def test_cmake_failure_propagates(self):
        runner = Mock(side_effect=subprocess.CalledProcessError(7, ['cmake']))
        with self.assertRaises(subprocess.CalledProcessError) as c:
            self.invoke('build', runner)
        self.assertEqual(c.exception.returncode, 7)
        self.assertEqual(runner.call_count, 1)
