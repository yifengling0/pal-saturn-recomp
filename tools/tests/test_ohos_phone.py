"""Phone preflight service/policy and native handoff regression tests."""
import os
import json
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
        result = subprocess.run([node, str(Path(__file__).with_name(script)), str(MAIN / 'ets/services' / service)],
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_storage_service(self):
        self.run_node('ohos_storage_test.cjs', 'PalStorage.ets')

    def test_phone_window_policy(self):
        self.run_node('ohos_orientation_test.cjs', 'PhoneOrientation.ets')

    def test_fold_screen_orientation(self):
        self.run_node('ohos_fold_orientation_test.cjs', 'FoldLayout.ets')

    def test_orientation_observes_sdl_lifecycle_without_replacing_it(self):
        ability = (MAIN / 'ets/entryability/EntryAbility.ets').read_text(encoding='utf-8')
        self.assertLess(ability.index('PhoneOrientation.install(this)'), ability.index('sdl.provideArkTSObjects('))
        self.assertNotRegex(ability, r'(?m)^\s*onWindowStageCreate\(')
        page = (MAIN / 'ets/pages/Index.ets').read_text(encoding='utf-8')
        self.assertIn('PhoneOrientation.getCurrent()', page)
        self.assertIn('setReporter(undefined)', page)
        self.assertNotIn('orientation?.stop()', page)

    def test_phone_tablet_launch_resources_match_runtime_policy(self):
        self.assertIn('"orientation": "$string:pal_start_orientation"', (MAIN / 'module.json5').read_text())
        for qualifier, expected in [('phone', 'auto_rotation_landscape'), ('tablet', 'auto_rotation_landscape'),
                                    ('base', 'auto_rotation_restricted')]:
            strings = json.loads((MAIN / 'resources' / qualifier / 'element/string.json').read_text())['string']
            values = [item['value'] for item in strings if item['name'] == 'pal_start_orientation']
            self.assertEqual(values, [expected])

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
        self.assertEqual((MAIN / 'resources/rawfile/pal-selftest.txt').read_text(encoding='utf-8').strip(),
                         (MAIN / 'cpp/selftest.txt').read_text(encoding='utf-8').strip())
        self.assertIn('getApplicationContext().filesDir', (MAIN / 'ets/services/PalStorage.ets').read_text(encoding='utf-8'))
        self.assertIn('OH_AbilityRuntime_ApplicationContextGetFilesDir', (MAIN / 'cpp/pal_ohos_entry.cpp').read_text(encoding='utf-8'))

    def test_surface_holds_focus_so_hardware_keys_arrive(self):
        # SDL's OpenHarmony backend only hears a key press through the XComponent's own
        # key-event callback, which ArkUI fires for the focused component. A page that
        # mounts the surface without focus looks like a dead keyboard on a real device.
        page = (MAIN / 'ets/pages/Index.ets').read_text(encoding='utf-8')
        lines = page.splitlines()
        mounted = [i for i, line in enumerate(lines) if 'XComponent(' in line and 'SDL_XComponent' in line]
        self.assertEqual(len(mounted), 1, 'the page must mount exactly one SDL surface')
        chain = ' '.join(lines[mounted[0]:mounted[0] + 3])
        self.assertIn('focusable(true)', chain, 'the SDL surface must be able to take focus')
        self.assertIn('defaultFocus(true)', chain, 'the SDL surface must take focus when it appears')


if __name__ == '__main__':
    unittest.main()
