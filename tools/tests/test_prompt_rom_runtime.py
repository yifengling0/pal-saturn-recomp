"""Opt-in execution of private original generated functions; ships no ROM code.

PAL_PROMPT_RECOMP points to the user's verified p_prog_000.cpp directory.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import pal_prompt_confirm as prompt
ROOT=Path(__file__).resolve().parents[2]
class PromptOriginalRuntime(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('PAL_PROMPT_RECOMP'), 'Private original generated PROG functions not supplied')
    def test_original_poll_and_scoped_acceptance(self):
        src=(Path(os.environ['PAL_PROMPT_RECOMP'])/'p_prog_000.cpp').read_text()
        functions=[]
        for name in ('060220D0','06022B8C','06022A30','060227F8'):
            a=src.index('void f_'+name+'(');z=src.index('\nvoid f_',a+1)
            f=src[a:z].replace('    pal_release_runtime::neutral_post();\n','')
            if name=='060220D0':
                transformed=prompt.guest(f+'\nvoid f_06022190(SH2Context& c) {}\n')
                transformed=transformed[transformed.index('void f_060220D0'):transformed.index('\nvoid f_06022190')]
                functions.append(transformed.replace('f_060220D0','f_prompt_patched'))
            functions.append(f)
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);(td/'prompt-functions.inc').write_text('\n'.join(functions))
            subprocess.run(['c++','-std=c++17','-O1','-Wall','-Wextra','-I'+str(ROOT/'src/pal_game'),'-I'+str(td),
                str(ROOT/'tools/tests/prompt_rom_runtime_test.cpp'),'-o',str(td/'test')],check=True)
            subprocess.run([str(td/'test')],check=True)
