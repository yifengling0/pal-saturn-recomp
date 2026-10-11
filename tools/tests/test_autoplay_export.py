from pathlib import Path
import importlib.util,json,tempfile,unittest
spec=importlib.util.spec_from_file_location('autoplay_export',Path(__file__).parents[1]/'export_autoplay_inputs.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ExportTests(unittest.TestCase):
    def test_boot_order_release_and_observations(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'boot-input.txt').write_text('1500:START,1512:,\n');rows=[]
            for op,vb,b in [('pad',3400,'RIGHT'),('read',3400,''),('pad',3401,'')]:
                rows.append({'request':{'op':op,'buttons':b},'result':{'reply':'ok','vblank':vb}})
            (d/'commands.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));out=d/'replay.txt'
            self.assertEqual(m.export(d,out),2);self.assertEqual(out.read_text(),'1500:START,1512:,3400:RIGHT,3401:\n')
            with self.assertRaises(ValueError):m.export(d,out)
    def test_failed_or_out_of_order_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'boot-input.txt').write_text('')
            for values in [(5,4),(-2,)]:
                rows=[{'request':{'op':'pad','buttons':'A'},'result':{'reply':'ok','vblank':v}} for v in values]
                (d/'commands.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                with self.assertRaises(ValueError):m.export(d,d/'out')
