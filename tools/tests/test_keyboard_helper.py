"""Self-contained C++ helper tests plus an explicitly opt-in Settings integration.

The default helper test needs only a C++17 compiler, standard library and helper.
Set PAL_KEYBOARD_UPSTREAM_RUNTIME to an existing public runtime checkout to run
Settings integration; absent setup is reported as SKIP, never claimed as PASS.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

from keyboard_test_fixtures import HEADER, digest, load_planner

HERE = Path(__file__).resolve().parent

class HelperTests(unittest.TestCase):
    def compiler(self):
        requested = shlex.split(os.environ.get('CXX', 'c++'))
        if not requested or not shutil.which(requested[0]):
            self.skipTest('A C++17 compiler is not installed; Python planner tests still run')
        return requested

    def build_run(self, source, extra_files=()):
        compiler = self.compiler()
        with tempfile.TemporaryDirectory(prefix='keyboard C++ unit 空格 ') as tmp:
            tmp = Path(tmp)
            shutil.copyfile(HEADER, tmp / 'pal_keyboard_profile.h')
            for name, data in extra_files:
                (tmp / name).write_bytes(data)
            exe = tmp / ('test.exe' if os.name == 'nt' else 'test')
            cmd = [*compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(tmp), str(source)]
            cmd += [str(tmp / name) for name, _ in extra_files if name.endswith('.cpp')]
            result = subprocess.run([*cmd, '-o', str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS:', result.stdout)

    def test_pure_context_and_latch_no_sdl(self):
        self.build_run(HERE / 'keyboard_context_test.cpp')

    def test_optional_upstream_settings_migration_no_sdl(self):
        root = os.environ.get('PAL_KEYBOARD_UPSTREAM_RUNTIME')
        if not root:
            self.skipTest('Optional upstream integration: set PAL_KEYBOARD_UPSTREAM_RUNTIME; no runtime checkout is required by default')
        runtime = Path(root)
        source, header = runtime / 'src/host/settings.cpp', runtime / 'src/host/settings.h'
        if not source.is_file() or not header.is_file():
            self.fail('PAL_KEYBOARD_UPSTREAM_RUNTIME does not contain src/host/settings.{cpp,h}')
        m = load_planner()
        text = source.read_bytes().decode('utf-8').replace('\r\n', '\n')
        self.assertIn(digest(text), m.RUNTIME_HASHES['settings.cpp'], 'Optional upstream Settings source is not the reviewed version')
        self.build_run(HERE / 'keyboard_settings_test.cpp',
                       [('settings.cpp', m.guard_settings(m.settings(text)).encode()),
                        ('settings.h', m.settings_header(header.read_text(encoding='utf-8')).encode())])

if __name__ == '__main__':
    unittest.main(verbosity=2)
