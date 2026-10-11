import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('resource_probe',Path(__file__).parents[1]/'resource_probe.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ResourceProbeTests(unittest.TestCase):
    def test_instrumentation_keeps_guest_statements(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            f0=root/'p_prog_000.cpp';f3=root/'p_prog_003.cpp'
            f0.write_text('void f_06020094(SH2Context& c) {\n    c.r[14] += 24;  // 06020116 add #24,r14\n}\n')
            f3.write_text('    c.r[1] = 0; // 0602F290 synthetic\n    c.r[1] = 0; // 0602F2BC synthetic\nvoid f_0602FA8C(SH2Context& c) {\n    c.r[0]=1;\n}\nvoid f_0602FB48(SH2Context& c) {\n    c.r[0]=2;\n}\n')
            m.add_headers(root,root)
            self.assertIn('pal_resource_probe(c, 0x06020094u);',f0.read_text())
            self.assertIn('pal_resource_result(c);\n    c.r[14] += 24;',f0.read_text())
            self.assertEqual(f3.read_text().count('pal_resource_probe(c,'),2)
            self.assertIn('    c.r[0]=1;',f3.read_text())
            self.assertIn('    c.r[0]=2;',f3.read_text())

    def test_missing_generated_entry_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'Missing resource probe entries'):
                m.add_headers(d,d)
