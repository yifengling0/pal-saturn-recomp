from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
@unittest.skipIf(os.name == 'nt', 'POSIX shell profiles require POSIX paths and executables')
class ProfileTests(unittest.TestCase):
    def test_explicit_profiles_and_argument_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='pal profile ') as d:
            fake=Path(d)/'fake executable'
            fake.write_text('#!/usr/bin/env python3\nimport json,os,sys\nprint(json.dumps([os.environ["PAL_RESPONSIVE_INPUT"],os.environ["PAL_RESPONSIVE_ALIGN"],os.environ["PAL_RESPONSIVE_WAKE"],sys.argv[1:]]))\n')
            fake.chmod(0o700)
            env=dict(os.environ,PAL_RESPONSIVE_EXE=str(fake))
            for profile,expected in [('original',['0','0','0']),('precise',['1','0','0']),('experimental-fast',['1','1','1'])]:
                r=subprocess.run(['bash',str(ROOT/'tools/run_pal_profile.sh'),profile,'--cue','path with spaces.cue'],env=env,text=True,capture_output=True,check=True)
                self.assertEqual(json.loads(r.stdout),expected+[['--cue','path with spaces.cue']])
            r=subprocess.run(['bash',str(ROOT/'tools/run_pal_profile.sh'),'unknown'],env=env,capture_output=True)
            self.assertEqual(r.returncode,2)
    def test_missing_executable_fails(self):
        r=subprocess.run(['bash',str(ROOT/'tools/run_pal_profile.sh'),'precise'],env=dict(os.environ,PAL_RESPONSIVE_EXE='/nonexistent/pal-exe'),capture_output=True)
        self.assertEqual(r.returncode,3)
