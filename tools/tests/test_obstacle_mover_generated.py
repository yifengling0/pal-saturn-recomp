"""Opt-in execution of the locally generated original mover (no ROM shipped).

PAL_OBSTACLE_RECOMP=/path/to/build/recomp python -m unittest discover \
    -s tools/tests -p test_obstacle_mover_generated.py -v
Requires C++20 and the pinned runtime headers. Collision and animation callees
are controlled stubs; mover, facing conversion and boundary clamp are original
locally generated code. This is not a real map/entity or controller integration test.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OriginalMoverScenarios(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('PAL_OBSTACLE_RECOMP'),
                         'Private generated PROG functions not supplied')
    def test_original_mover_scenarios(self):
        source = (Path(os.environ['PAL_OBSTACLE_RECOMP']) / 'p_prog_004.cpp').read_text()
        functions = []
        for address in ('06033538', '0603358C', '06033654'):
            start = source.index('void f_' + address + '(')
            end = source.index('\nvoid f_', start + 1)
            functions.append(source[start:end])
        mover = functions[-1]
        self.assertEqual(mover.count('sh2_hook(c, 0x06033752u)'), 1)
        # Recover the switch table from generated targets, not a redistributed ROM.
        switch = re.search(r'switch \(x\) \{ (case .*?)default:', mover)
        self.assertIsNotNone(switch)
        targets = re.findall(r'case (0x[0-9A-F]+)u:', switch.group(1))
        self.assertEqual(len(targets), 4)
        table = '\n'.join(f'st16(0x0603376Cu + {i * 2}, {target}u - 0x0603376Cu);'
                          for i, target in enumerate(targets))
        with tempfile.TemporaryDirectory(prefix='pal-original-mover-') as directory:
            directory = Path(directory)
            (directory / 'mover-functions.inc').write_text('\n'.join(functions))
            (directory / 'mover-switch.inc').write_text(table)
            exe = directory / ('test.exe' if os.name == 'nt' else 'test')
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++20', '-O1',
                            '-Wall', '-Wextra', '-DPAL_OBSTACLE_HOOK_VERIFIED=1',
                            '-I' + str(directory), '-I' + str(ROOT / 'src/pal_game'),
                            '-I' + str(ROOT / 'third_party/saturn-recomp-pal/runtime/include'),
                            str(ROOT / 'tools/tests/obstacle_mover_generated_test.cpp'),
                            str(ROOT / 'src/pal_game/pal_obstacle_stop.cpp'),
                            '-o', str(exe)], check=True)
            for mode in ('0', '1'):
                env = dict(os.environ, PAL_OBSTACLE_STOP=mode)
                subprocess.run([str(exe)], env=env, check=True)
