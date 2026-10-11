import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
spec=importlib.util.spec_from_file_location('pal_autoplay_session',Path(__file__).parents[1]/'pal_autoplay_session.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SessionTests(unittest.TestCase):
    def test_bounded_steps_and_no_memory_writes(self):
        self.assertEqual(m.validate({'op':'step','frames':60}),'step 60')
        for req in [{'op':'step','frames':0},{'op':'step','frames':10001},{'op':'write','address':'06000000','data':'00'}]:
            with self.assertRaises(ValueError):m.validate(req)
    def test_observations_are_work_ram_only(self):
        self.assertEqual(m.validate({'op':'read','address':'06076928','length':4}),'read 06076928 4')
        for a,n in [('05F80000',2),('060FFFFF',2),('06000000',257)]:
            with self.assertRaises(ValueError):m.validate({'op':'read','address':a,'length':n})
    def test_pad_cannot_inject_another_protocol_command(self):
        self.assertEqual(m.validate({'op':'pad','buttons':''}),'pad ')
        with self.assertRaises(ValueError):m.validate({'op':'pad','buttons':'A\nwrite 06000000 FF'})
    def test_png_preserves_exact_rgb_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'frame.png';rgb=bytes([255,0,0,0,255,0]);m.png(path,2,1,rgb)
            data=path.read_bytes();self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n');at=8;chunks={}
            while at<len(data):
                n=struct.unpack('>I',data[at:at+4])[0];kind=data[at+4:at+8];payload=data[at+8:at+8+n]
                self.assertEqual(struct.unpack('>I',data[at+8+n:at+12+n])[0],zlib.crc32(kind+payload)&0xffffffff)
                chunks[kind]=payload;at+=12+n
            self.assertEqual(zlib.decompress(chunks[b'IDAT']),b'\0'+rgb)
