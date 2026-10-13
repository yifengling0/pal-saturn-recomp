"""Opt-in SDL event-adapter test, not full-game acceptance.

Runs the production HOST_HELPERS verbatim against SDL's real dummy window,
real event queue, and virtual gamepad. Binding/layout containers are small test
fixtures. Supply PAL_PROMPT_SDL_PREFIX and PAL_PROMPT_RUNTIME for private SDK.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import pal_prompt_confirm as prompt
ROOT=Path(__file__).resolve().parents[2]
class PromptSDL(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('PAL_PROMPT_SDL_PREFIX') and os.environ.get('PAL_PROMPT_RUNTIME'),
                         'SDL3 SDK and runtime tap helper not supplied')
    def test_real_sdl_event_adapter(self):
        sdk=Path(os.environ['PAL_PROMPT_SDL_PREFIX']);runtime=Path(os.environ['PAL_PROMPT_RUNTIME'])
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);source=td/'test.cpp'
            source.write_text((ROOT/'tools/tests/prompt_sdl_prefix.cpp').read_text()+prompt.HOST_HELPERS+
                              (ROOT/'tools/tests/prompt_sdl_suffix.cpp').read_text())
            subprocess.run(['c++','-std=c++20','-O1','-Wall','-Wextra',
                '-I'+str(ROOT/'src/pal_game'),'-I'+str(runtime/'src/host'),'-I'+str(sdk/'include'),
                str(source),'-L'+str(sdk/'lib'),'-Wl,-rpath,'+str(sdk/'lib'),'-lSDL3','-o',str(td/'test')],check=True)
            subprocess.run([str(td/'test')],check=True)
