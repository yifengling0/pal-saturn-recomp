"""Pure synthetic planner coverage. No disc-derived code is included."""
from pathlib import Path
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import pal_scene_continuity as p
from pal_field_input import _function,sha
class Planner(unittest.TestCase):
 def setUp(self):
  self.root=Path.cwd().resolve()/'synthetic scene 空格'
  lines={
   '06023C64':['    // original verified reveal body'],
   '06023914':['    // original verified fade body'],
   '0602B020':['    f_06023914(c); // 0602B046 original fade call'],
   '0603237C':['    st8(c.r[1], c.r[2]); // 060323B8 original store'],
   '06026F90':['    st8(c.r[1], c.r[2]); // 06026FAC original store', '    f_06024FD8(c); // 0602704C original call', '    f_060274FC(c); // 060270BA original call'],
   '0602C288':['    st8(c.r[1], c.r[2]); // 0602C384 original store'],
   '06022B8C':['    st8(c.r[1], c.r[2]); // 06022D1A original store'],
   '06022D5C':['    st8(c.r[1], c.r[2]); // 06022EEA original store','    if (c.t) { goto L_06022FDE; } // 06022FD8 original branch'],
   '06026D84':['    f_06022D5C(c); // 06026E54 original call','    c.r[8] = 0x06033654u; // 06026E6E original mover pointer','    f_06023C64(c); // 06026E84 original reveal']}
  self.texts={self.root/f'p_prog_{i:03}.cpp':'namespace fixture {\n\nvoid f_'+a+'(SH2Context& c) {\n'+'\n'.join(ls)+'\n}\n\n}  // namespace fixture\n' for i,(a,ls)in enumerate(lines.items())}
  self.helpers={'pal_release_gate.h':b'// pure policy fixture\n','pal_release_runtime.h':b'// wrapper fixture\n'}
  self.pins={a:sha(_function(self.texts,a)[3])for a in p.EXTRA_FUNCTION_SHA256}
  for m in [patch.object(p,'EXTRA_FUNCTION_SHA256',self.pins),patch.object(p,'HELPER_SHA256',{n:sha(d)for n,d in self.helpers.items()})]:m.start();self.addCleanup(m.stop)
 def plan(self,texts=None,helpers=None):return p.plan_scene_continuity(self.root,self.texts if texts is None else texts,self.texts if texts is None else texts,self.helpers if helpers is None else helpers)
 def test_original_preserved(self):
  out,hs=self.plan();self.assertEqual(len(hs),2)
  for path,text in out.items():self.assertEqual(''.join(l for l in text.splitlines(keepends=True)if 'pal_release_runtime::'not in l),self.texts[path])
  self.assertIn('goto L_06022FF2', ''.join(out.values()))
 def test_changed_function(self):
  for path in {_function(self.texts,a)[0] for a in p.EXTRA_FUNCTION_SHA256}:
   with self.subTest(path=path):
    ts=dict(self.texts);ts[path]=ts[path].replace('original','changed')
    with self.assertRaisesRegex(ValueError,'function identity'):self.plan(ts)
 def test_helper_missing_empty_extra_changed(self):
  for hs in [{},{'pal_release_gate.h':self.helpers['pal_release_gate.h']},{**self.helpers,'extra.h':b'x'},{**self.helpers,'pal_release_gate.h':b'changed'}]:
   with self.subTest(hs=hs),self.assertRaises(ValueError):self.plan(helpers=hs)
 def test_anchor_duplicate(self):
  ts=dict(self.texts);path=next(p for p,s in ts.items()if '06026FAC'in s);ts[path]=ts[path].replace('    st8','    st8(c.r[1], c.r[2]); // 06026FAC duplicate\n    st8')
  with self.assertRaisesRegex(ValueError,'instruction changed'):self.plan(ts)
 def test_cannot_apply_twice(self):
  out,_=self.plan()
  with self.assertRaises(ValueError):p.plan_scene_continuity(self.root,self.texts,out,self.helpers)
if __name__=='__main__':unittest.main()
