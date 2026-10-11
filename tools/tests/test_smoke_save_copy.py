import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('run_pal_smoke',Path(__file__).parents[1]/'run_pal_smoke.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SmokeSaveTests(unittest.TestCase):
    def test_save_copy_and_input_script_preserve_originals(self):
        with tempfile.TemporaryDirectory(prefix='pal smoke ') as d:
            root=Path(d);cue=root/'disc.cue';track=root/'disc.bin';exe=root/'saturn';saved=root/'existing.bup';script=root/'keys.txt';out=root/'new run'
            cue.write_text('FILE "disc.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n')
            track.write_bytes(bytes(2352));exe.write_bytes(b'not executed');saved.write_bytes(b'original backup');script.write_text('1:A,2:\n')
            def fake_run(cmd,**kw):
                target=Path(cmd[cmd.index('--save')+1]);self.assertEqual(target.read_bytes(),b'original backup');target.write_bytes(b'new progress')
                return SimpleNamespace(returncode=0)
            argv=['run_pal_smoke.py','--cue',str(cue),'--out',str(out),'--exe',str(exe),'--save-copy',str(saved),'--input-file',str(script),'--shots','1','--vblanks','2']
            with patch.object(sys,'argv',argv),patch.object(m.subprocess,'run',side_effect=fake_run),patch.dict(sys.modules,{'inspect_video_dump':SimpleNamespace(inspect=lambda b:{})}):
                self.assertEqual(m.main(),0)
            self.assertEqual(saved.read_bytes(),b'original backup')
            self.assertEqual((out/'test-backup.bup').read_bytes(),b'new progress')
            self.assertEqual((out/'input.txt').read_text(),script.read_text())
            import json
            report=json.loads((out/'summary.json').read_text())
            self.assertTrue(report['inputs_unchanged'])
            self.assertEqual(report['save_source_sha256_before'],report['save_source_sha256_after'])
            self.assertNotEqual(report['save_result_sha256'],report['save_source_sha256_before'])

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cue=root/'disc.cue';exe=root/'saturn';cue.touch();exe.touch()
            with patch.object(sys,'argv',['run_pal_smoke.py','--cue',str(cue),'--exe',str(exe),'--out',str(root)]),patch.object(m.subprocess,'run') as run:
                with self.assertRaises(FileExistsError):m.main()
                run.assert_not_called()
