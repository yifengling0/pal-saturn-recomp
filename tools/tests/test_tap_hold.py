"""A tap quicker than a poll must still reach the game (pal_tap_hold.h).

The measured reason this exists: through the pads the SMPC reads, a button held for one VBlank is
dropped by the game and held for two the recorded title-to-village path runs byte for byte, while the
host polled a quick tap for one frame at best and often for none. So the stretching is tested here
against its own clock, with no window, no ROM and no SDL to pace it.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'third_party/saturn-recomp-pal/runtime/src/host/pal_tap_hold.h'
SOURCE = Path(__file__).resolve().parent / 'tap_hold_test.cpp'

# A probe built by one MinGW must not load another's libstdc++ off PATH, which is what
# tools/check_windows.sh -static avoids for the runtime tests.
STATIC = ['-static'] if os.name == 'nt' else []


class TapHoldTests(unittest.TestCase):
    def compile(self, tmp):
        exe = Path(tmp) / ('tap.exe' if os.name == 'nt' else 'tap')
        result = subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-Wall', '-Wextra', '-Werror',
                                 '-I' + str(HEADER.parent), str(SOURCE), *STATIC, '-o', str(exe)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return exe

    def test_a_press_holds_for_several_vblanks(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = self.compile(tmp)
            result = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
            self.assertIn('PASS:', result.stdout)

    def test_the_original_timing_is_one_opt_out_away(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = self.compile(tmp)
            result = subprocess.run([str(exe), '0'], env=dict(os.environ, PAL_TAP_HOLD='0'),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('publishes the polled state', result.stdout)


if __name__ == '__main__':
    unittest.main()
