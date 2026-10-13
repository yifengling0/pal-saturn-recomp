"""Compile portable policies without ROM, SDL device or proprietary generated code."""
import os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CXX=shutil.which('g++') or shutil.which('clang++')
@unittest.skipUnless(CXX,'A C++17 compiler is required')
class Helpers(unittest.TestCase):
 def run_cpp(self,name,includes=(),env=None):
  with tempfile.TemporaryDirectory(prefix='pal-continuity-') as d:
   d=Path(d);stub=d/'saturn';stub.mkdir()
   (stub/'sh2.h').write_text('#pragma once\n#include <cstdint>\nstruct SH2Context { uint32_t r[16]{}, pr=0; };\nuint32_t ld8(uint32_t); uint32_t ld16(uint32_t); uint32_t ld32(uint32_t);\n')
   exe=d/('test.exe' if os.name=='nt' else 'test')
   args=[CXX,'-std=c++17','-Wall','-Wextra','-Werror',str(ROOT/'tools/tests'/name),'-I'+str(d),'-I'+str(ROOT/'src/pal_game')]+['-I'+str(x)for x in includes]+['-o',str(exe)]
   if name.startswith('field_release_') and name != 'field_release_policy_test.cpp':
    (d/'pal_field_input_api.h').write_text('#pragma once\nnamespace pal_field_host { bool available(); }\n')
    args.append(str(ROOT/'tools/tests/field_host_availability_stub.cpp'))
   subprocess.run(args,check=True,capture_output=True,text=True)
   outputs=[]
   for changes in (env if isinstance(env,list) else [env or {}]):
    child={k:v for k,v in os.environ.items() if k not in ('PAL_FIELD_INPUT','PAL_FIELD_CONTINUITY')}
    child.update({k:v for k,v in changes.items() if v is not None})
    outputs.append(subprocess.run([str(exe)],check=True,capture_output=True,text=True,env=child).stdout)
   return ''.join(outputs)
 def test_field1_only_dynamic_capability(self):
  cases=[{'PAL_FIELD_INPUT':f,'PAL_FIELD_CONTINUITY':c} for f in [None,'0','1','','true','2','01'] for c in [None,'0','1','','true','2','00','false']]
  self.assertEqual(self.run_cpp('field_release_enabled_test.cpp',env=cases).count('PASS'),56)
 def test_field0_wrapper_disabled(self):
  for name in ['runtime','fade','reveal','debt']:
   with self.subTest(helper=name):self.assertIn('PASS',self.run_cpp('field_release_'+name+'_test.cpp',env={'PAL_FIELD_INPUT':'0','PAL_FIELD_CONTINUITY':'1'}))
 def test_provenance_policy(self):self.assertIn('PASS',self.run_cpp('field_release_policy_test.cpp'))
 def test_runtime_enabled(self):self.assertIn('PASS',self.run_cpp('field_release_runtime_test.cpp',env={'PAL_FIELD_CONTINUITY':'1'}))
 def test_runtime_disabled(self):self.assertIn('PASS',self.run_cpp('field_release_runtime_test.cpp',env={'PAL_FIELD_CONTINUITY':'0'}))
 def test_fade_enabled(self):self.assertIn('PASS',self.run_cpp('field_release_fade_test.cpp',env={'PAL_FIELD_CONTINUITY':'1'}))
 def test_fade_disabled(self):self.assertIn('PASS',self.run_cpp('field_release_fade_test.cpp',env={'PAL_FIELD_CONTINUITY':'0'}))
 def test_field_scene_integration(self):
  rt=ROOT/'third_party/saturn-recomp-pal/runtime'
  if not (rt/'src/host/pal_field_input_ledger.h').is_file():self.skipTest('Prepare pinned patched runtime first')
  for on in ['0','1']:
   with self.subTest(continuity=on):self.assertIn('PASS',self.run_cpp('field_scene_integration_test.cpp',[rt/'include',rt/'src/host'],env={'PAL_FIELD_CONTINUITY':on}))
 def test_walk_cadence_opt_out_and_unknown_values(self):
  rt=ROOT/'third_party/saturn-recomp-pal/runtime'
  if not (rt/'src/host/pal_field_input_ledger.h').is_file():self.skipTest('Prepare pinned patched runtime first')
  cases=[{'PAL_FIELD_WALK_CADENCE':value} for value in ['original','0','1','','fast','Gentle','gentle ']]
  self.assertEqual(self.run_cpp('field_scene_integration_test.cpp',[rt/'include',rt/'src/host'],env=cases).count('PASS'),len(cases))
 def test_reveal_enabled(self):self.assertIn('PASS',self.run_cpp('field_release_reveal_test.cpp',env={'PAL_FIELD_CONTINUITY':'1'}))
 def test_reveal_disabled(self):self.assertIn('PASS',self.run_cpp('field_release_reveal_test.cpp',env={'PAL_FIELD_CONTINUITY':'0'}))
 def test_debt_enabled(self):self.assertIn('PASS',self.run_cpp('field_release_debt_test.cpp',env={'PAL_FIELD_CONTINUITY':'1'}))
 def test_debt_disabled(self):self.assertIn('PASS',self.run_cpp('field_release_debt_test.cpp',env={'PAL_FIELD_CONTINUITY':'0'}))
 def test_scene_ledger(self):
  rt=ROOT/'third_party/saturn-recomp-pal/runtime'
  if not (rt/'src/host/pal_field_input_ledger.h').is_file():self.skipTest('Prepare pinned patched runtime first')
  self.assertIn('PASS',self.run_cpp('scene_continuity_ledger_test.cpp',[rt/'include',rt/'src/host']))
if __name__=='__main__':unittest.main()
