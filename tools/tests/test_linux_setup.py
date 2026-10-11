import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'prepare_linux_runtime.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pal setup test ')
        self.root = Path(self.temp.name)
        self.clean = self.root / 'clean repo'
        self.clean.mkdir()
        m.git(self.clean, 'init', '-b', 'master')
        (self.clean / 'file.txt').write_text('before\n')
        m.git(self.clean, 'add', '.')
        m.git(self.clean, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-m', 'Fixture')
        self.pin = m.git(self.clean, 'rev-parse', 'HEAD').decode().strip()
        self.patch = self.root / 'test change.patch'
        # LF: write_text would translate \n to \r\n here, and the fixture's LF blob then rejects a
        # context line that carries a trailing CR.
        self.patch.write_text('diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-before\n+after\n',
                              newline='\n')
        self.dest = self.root / 'patched repo'

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        return m.prepare(self.clean, self.dest, self.pin, [self.patch])

    def test_spaces_and_repeat_are_safe(self):
        self.assertTrue(self.prepare())
        self.assertEqual((self.dest / 'file.txt').read_text(), 'after\n')
        self.assertFalse(self.prepare())
        self.assertEqual((self.clean / 'file.txt').read_text(), 'before\n')
        self.assertEqual(m.git(self.clean, 'status', '--porcelain').strip(), b'')

    def test_bad_patch_does_not_leave_partial_destination(self):
        self.patch.write_text('this is not a patch\n')
        with self.assertRaises(subprocess.CalledProcessError): self.prepare()
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.root.glob('.pal-runtime-*')))

    def test_dirty_clean_is_rejected(self):
        (self.clean / 'file.txt').write_text('dirty\n')
        with self.assertRaisesRegex(ValueError, 'clean'): self.prepare()

    def test_wrong_pin_is_rejected(self):
        self.pin = '0' * 40
        with self.assertRaisesRegex(ValueError, 'commit'): self.prepare()

    def test_existing_patched_modification_is_not_overwritten(self):
        self.prepare()
        (self.dest / 'file.txt').write_text('user work\n')
        with self.assertRaisesRegex(ValueError, 'refusing'): self.prepare()
        self.assertEqual((self.dest / 'file.txt').read_text(), 'user work\n')

    def test_changed_patch_is_rejected(self):
        self.prepare()
        self.patch.write_text(self.patch.read_text().replace('+after', '+different'), newline='\n')
        with self.assertRaisesRegex(ValueError, 'refusing'): self.prepare()

    def test_parent_git_identity_is_not_accepted(self):
        child = self.clean / 'child'
        child.mkdir()
        with self.assertRaisesRegex(ValueError, 'independent'): m.identity(child, self.pin)

    def test_pipeline_failure_is_nonzero(self):
        script = Path(__file__).parents[1] / 'check_linux.sh'
        self.assertIn('set -euo pipefail', script.read_text())
        result = subprocess.run(['bash', '-c', 'set -euo pipefail; false | tee /dev/null; echo WRONG'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'WRONG', result.stdout)
