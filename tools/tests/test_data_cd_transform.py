import importlib.util
from pathlib import Path
import tempfile
import unittest

W=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('pal_data_cd_speed',W.parent/'pal_data_cd_speed.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
BASE=W.parents[1]/'third_party/saturn-recomp-pal/runtime/src/machine/cdblock.cpp'
class ApplyTests(unittest.TestCase):
 def test_lf_crlf_and_idempotence(self):
  for ending in [b'\n',b'\r\n']:
   with self.subTest(ending=ending),tempfile.TemporaryDirectory(dir=W) as name:
    rt=Path(name);p=rt/'src/machine/cdblock.cpp';p.parent.mkdir(parents=True);p.write_bytes(BASE.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',ending))
    self.assertTrue(module.apply_data_cd_speed(rt)['changed']);first=p.read_bytes();self.assertFalse(module.apply_data_cd_speed(rt)['changed']);self.assertEqual(first,p.read_bytes());self.assertIn(b'SATURN_DATA_CD_SPEED',first)
    p.write_bytes(first+b'// edited\n');before=p.read_bytes()
    with self.assertRaises(ValueError):module.apply_data_cd_speed(rt)
    self.assertEqual(p.read_bytes(),before)
 def test_unknown_and_mixed_inputs_refuse_without_write(self):
  for data in [BASE.read_bytes()+b'// edited\n',BASE.read_bytes().replace(b'\n',b'\r\n',1),b'unknown',BASE.read_bytes().replace(b'\n',b'\r',1)]:
   with self.subTest(),tempfile.TemporaryDirectory(dir=W) as name:
    p=Path(name)/'src/machine/cdblock.cpp';p.parent.mkdir(parents=True);p.write_bytes(data)
    with self.assertRaises(ValueError):module.apply_data_cd_speed(Path(name))
    self.assertEqual(p.read_bytes(),data)
if __name__=='__main__':unittest.main()
