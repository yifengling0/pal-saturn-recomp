"""Prompt policy and fail-closed planner tests, no ROM distribution."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import pal_prompt_confirm as prompt

ROOT=Path(__file__).resolve().parents[2]
class PromptTests(unittest.TestCase):
    def test_policy(self):
        with tempfile.TemporaryDirectory() as td:
            exe=Path(td)/'test'
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',
                '-I'+str(ROOT/'src/pal_game'),str(ROOT/'tools/tests/prompt_confirm_test.cpp'),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    def test_guest_pin_and_unique_local_hook(self):
        f='void f_060220D0(SH2Context& c) {\n    c.r[1] = c.r[14];  // 0602213C mov r14,r1\n}\n'
        text=f+'\nvoid f_06022190(SH2Context& c) {}\n'
        # The boundary excludes the separator newline immediately before void.
        with patch.object(prompt,'WAIT_SHA256',hashlib.sha256(f.encode()).hexdigest()):
            out=prompt.guest(text)
            self.assertIn('c.pr==0x0602315Eu && c.r[4]==180u',out)
            self.assertIn('ld16(0x06076902u)==10u && ld16(0x060768FCu)!=0u',out)
            self.assertEqual(out.count('st16(c.r[14]+4, pal_prompt_wait.accept() ? 1 : 0)'),1)
            with self.assertRaises(ValueError):prompt.guest(out)
            with self.assertRaises(ValueError):prompt.guest(text.replace('mov r14,r1','modified'))
        with self.assertRaises(ValueError):prompt.guest(text)
    def test_host_unique_hooks(self):
        f='static void on_event(const SDL_Event& e) {\n    pal_note_press(e);\n}\nstatic void menu_open() {}\nstatic void menu_close() {}\n        g_buttons[s] = pad;\n'
        out=prompt.host(f)
        self.assertIn('prompt_event(e);\n    pal_note_press(e);',out)
        self.assertIn('e.common.timestamp>g_prompt_since',out)
        self.assertIn('g_pal_taps[0].forget(0x0600)',out)
        self.assertIn('g_held_over[0] |= pal_prompt::ledger.held()',out)
        for event in ('KEY_DOWN','KEY_UP','FINGER_DOWN','FINGER_UP','FINGER_CANCELED','GAMEPAD_BUTTON_DOWN','GAMEPAD_BUTTON_UP','GAMEPAD_AXIS_MOTION','WINDOW_FOCUS_LOST','DID_ENTER_BACKGROUND'):
            self.assertIn('SDL_EVENT_'+event,out)
        with self.assertRaises(ValueError):prompt.host(out)
    def test_missing_guest_never_silently_disables(self):
        with self.assertRaises(ValueError):prompt.plan({},Path('/runtime/host.cpp'),{})
