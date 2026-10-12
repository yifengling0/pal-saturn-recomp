"""Phone preflight service/policy and native handoff regression tests."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / 'harmony/pal-saturn-openharmony/entry/src/main'

class PhonePreflightTests(unittest.TestCase):
    def run_node(self, script, service):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node 22.13+ required to execute ArkTS service adapter tests')
        supported = subprocess.run([node, '-e', 'process.exit(typeof require("node:module").stripTypeScriptTypes === "function" ? 0 : 1)'])
        if supported.returncode:
            self.skipTest('Node with stripTypeScriptTypes required; real ArkTS compilation is separate')
        result = subprocess.run([node, str(Path(__file__).with_name(script)), str(MAIN / 'ets/services' / service)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_storage_service(self):
        self.run_node('ohos_storage_test.cjs', 'PalStorage.ets')

    def test_phone_window_policy(self):
        self.run_node('ohos_orientation_test.cjs', 'PhoneOrientation.ets')

    def test_native_handoff_parser(self):
        cxx = shutil.which('c++') or shutil.which('g++')
        if not cxx:
            self.skipTest('host C++ compiler unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            source = work / 'test.cpp'
            source.write_text('''#include "pal_ohos_launch.h"
#include <cassert>
int main(int argc, char** argv) {
  pal_ohos::LaunchPaths result;
  assert(argc == 3);
  bool valid = pal_ohos::read_launch_paths(argv[1], result);
  return valid == (std::string(argv[2]) == "yes") ? 0 : 1;
}
''')
            binary = work / 'parse'
            subprocess.run([cxx, '-std=c++17', '-I', str(MAIN / 'cpp'), str(source), '-o', str(binary)], check=True, capture_output=True)
            cases = [('PAL1\n/data/files\n/data/files/disc/game.cue\n/data/files\n', True),
                     ('PAL1\n/data/files\n/data/files/imports/disc-a/game.cue\n/data/files\n', True),
                     ('PAL1\n/data/files\n/data/files2/game.cue\n/data/files\n', False),
                     ('PAL1\n/data/files\n/data/files/../game.cue\n/data/files\n', False),
                     ('PAL1\n/data/files\n/data/files/game.cue\n', False),
                     ('PAL1\n/data/files\n/data/files/game.cue\n/data/files\nextra\n', False),
                     ('PAL1\nrelative\nrelative/game.cue\n/data/files\n', False),
                     ('PAL0\n/data/files\n/data/files/game.cue\n/data/files\n', False)]
            for contents, valid in cases:
                with self.subTest(contents=contents):
                    state = work / 'state'
                    state.write_text(contents)
                    subprocess.run([str(binary), str(state), 'yes' if valid else 'no'], check=True)

    def test_selftest_page_and_native_switch_agree(self):
        self.assertEqual((MAIN / 'resources/rawfile/pal-selftest.txt').read_text().strip(),
                         (MAIN / 'cpp/selftest.txt').read_text().strip())
        self.assertIn('getApplicationContext().filesDir', (MAIN / 'ets/services/PalStorage.ets').read_text())
        self.assertIn('OH_AbilityRuntime_ApplicationContextGetFilesDir', (MAIN / 'cpp/pal_ohos_entry.cpp').read_text())

if __name__ == '__main__':
    unittest.main()
