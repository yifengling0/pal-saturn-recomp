import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('dump',Path(__file__).parents[1]/'inspect_video_dump.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DumpTests(unittest.TestCase):
    def test_exact_layout_and_big_endian(self):
        b=bytearray(m.SIZE);b[0x141020:0x141022]=b'\x80\x00';b[0x141040:0x141042]=b'\x43\x00';b[0x141048:0x14104a]=b'\x12\x12'
        d=m.inspect(b)
        self.assertEqual(d['registers']['BGON'],'0x4300');self.assertEqual(d['rotation_enable_mask'],'0x00');self.assertTrue(d['display_enabled'])
        self.assertEqual(d['registers']['CHCTLA'],'0x1212')
    def test_wrong_length_rejected(self):
        with self.assertRaises(ValueError):m.inspect(bytes(m.SIZE-1))
    def test_rotation_bits(self):
        b=bytearray(m.SIZE);b[0x141040:0x141042]=b'\x00\x13'
        self.assertEqual(m.inspect(b)['rotation_enable_mask'],'0x10')
