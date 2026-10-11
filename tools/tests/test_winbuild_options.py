"""Mock Windows integration audit, no real compiler/game invocation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parent
class WindowsDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='PAL Windows driver 空格 ')
        self.root=Path(self.temp.name)
        self.cwd=Path.cwd()
        self.game=SimpleNamespace(build=str(self.root/'build'),cmake=['SATURN_EXTRA=C:/old/file','SDL3_DIR=C:/old/sdl','OTHER=1'])
        self.game.saturn=str(self.root/'build/recomp-build/saturn')
        self.fakebuild=SimpleNamespace(inputs=Mock(return_value={'source':'fixture'}),_stamp=lambda game:str(Path(game.build)/'recomp/inputs.json'))
        self.modules={
            'saturnrecomp':SimpleNamespace(build=self.fakebuild,config=SimpleNamespace(load=Mock(return_value=self.game)),learn=SimpleNamespace(),prereqs=SimpleNamespace(probe=Mock(return_value=(None,'3.4.18')))),
            'saturnrecomp.analysis':SimpleNamespace(resume=SimpleNamespace()),
            'saturnrecomp.recomp.__main__':SimpleNamespace(generate=Mock()),
            'pal_options':SimpleNamespace(VERSION='pal-options-input-v4-effect-v3-1',MANIFEST='pal-options-manifest.json')}
        self.imports=patch.dict(sys.modules,self.modules);self.imports.start()
        spec=importlib.util.spec_from_file_location('winbuild_fixture',HERE.parent/'winbuild.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.ROOT=str(self.root)
        self.m.PATCHED_RUNTIME=self.root/'third_party/saturn-recomp-pal/runtime'
    def tearDown(self):
        os.chdir(self.cwd);self.imports.stop();self.temp.cleanup()
    def call(self,args):
        with patch.object(self.m,'verify_options_runtime') as verify,patch.object(self.m,'win_ensure') as ensure,patch.object(self.m.shutil,'which',return_value='/fixture/tool'),patch.dict(os.environ,os.environ.copy()):
            result=self.m.main(args)
            return result,verify,ensure
    def test_default_options_output_and_portable_cmake(self):
        result,verify,ensure=self.call(['build','--pal-options','--headless'])
        self.assertEqual(result,0);verify.assert_called_once();ensure.assert_called_once()
        out=self.root/'build/windows-pal-options'
        self.assertEqual(self.game.build,str(out))
        self.assertEqual(json.loads((out/'pal-options-root.json').read_text())['kind'],'pal-windows-options-generated-build')
        self.assertEqual(self.game.cmake,['OTHER=1','SATURN_EXTRA='+(self.root/'src/pal_game/pal_game.cmake').as_posix(),'SATURN_NO_SDL=ON','SATURN_RUNTIME='+(out/'runtime').as_posix()])
    def test_rejects_existing_unowned_directory(self):
        out=self.root/'build/frozen-experiment';out.mkdir(parents=True);(out/'saturn').write_bytes(b'preserve')
        with self.assertRaises(SystemExit):self.call(['build','--pal-options','--headless','--build-dir',str(out)])
        self.assertEqual((out/'saturn').read_bytes(),b'preserve')
        self.assertFalse((out/'pal-options-root.json').exists())
    def test_rejects_outside_build(self):
        with self.assertRaises(SystemExit):self.call(['build','--pal-options','--headless','--build-dir',str(self.root/'outside')])
    def test_check_does_not_prepare_or_generate(self):
        _,verify,ensure=self.call(['check','--pal-options','--headless'])
        verify.assert_not_called();ensure.assert_not_called()
    def test_requested_window_requires_sdl(self):
        self.m.REQUIRE_SDL=True
        self.modules['saturnrecomp'].prereqs.probe.return_value=(None,None)
        with patch.object(self.m.shutil,'which',return_value='found'):
            problems,_=self.m.prereq_verdict()
        self.assertTrue(problems)
    def test_sdl_dir_propagates_as_one_argument(self):
        sdl=self.root/'SDL path/cmake';sdl.mkdir(parents=True);(sdl/'SDL3Config.cmake').write_text('# fixture')
        self.call(['build','--pal-options','--sdl-dir',str(sdl)])
        self.assertIn('SDL3_DIR='+sdl.as_posix(),self.game.cmake)
        self.assertIn('-DSDL3_DIR='+sdl.as_posix(),self.m._cmake_args(self.game))
    def test_stale_accepts_exe_extension(self):
        exe=Path(self.game.saturn+'.exe');exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture, never execute')
        stamp=Path(self.fakebuild._stamp(self.game));stamp.parent.mkdir(parents=True);stamp.write_text(json.dumps({'source':'fixture'}))
        self.assertEqual(self.m.win_stale(self.game),[])
    def test_build_targets_saturn_only(self):
        self.m.OPTIONS=False
        with patch.object(self.m,'_run') as run, patch('pal_keyboard_profile.prepare_keyboard'), patch.object(self.m,'option_build_manifest'):
            self.m.win_build(self.game)
        args=run.call_args.args[1]
        self.assertEqual(args[args.index('--target')+1],'saturn')
        self.assertNotIn('selftest',args)
    def test_sidecar_matches_launcher_contract(self):
        self.m.OPTIONS=True
        binary=Path(self.game.saturn+'.exe');binary.parent.mkdir(parents=True);binary.write_bytes(b'fixture never execute')
        manifest=Path(self.game.build)/'recomp/pal-options-manifest.json';manifest.parent.mkdir(parents=True);manifest.write_text('{}')
        self.m.option_build_manifest(self.game)
        proof=json.loads((binary.parent/'pal-options-build.json').read_text())
        self.assertEqual(proof['exe_sha256'],hashlib.sha256(binary.read_bytes()).hexdigest())
        self.assertEqual(proof['features'],['input_v4','effect_wait_v3','data_cd_speed','effect_cadence_v4_manual_pair','paired_frame_queue_v3','keyboard_profile_v1'])
    def test_new_game_layer_cpp_is_fingerprinted(self):
        source=self.root/'src/pal_game/pal_audio_stream_init.cpp'
        source.parent.mkdir(parents=True);source.write_text('// fixture one')
        for name in ('winbuild.py','pal_options.py','pal_data_cd_speed.py','pal_paired_frame_queue.py','pal_keyboard_profile.py'):
            tool=self.root/'tools'/name;tool.parent.mkdir(exist_ok=True);tool.write_text('# fixture')
        self.call(['build','--pal-options','--headless'])
        first=dict(self.fakebuild.inputs(self.game))
        key='PAL src/pal_game/pal_audio_stream_init.cpp'
        self.assertEqual(first[key],hashlib.sha256(source.read_bytes()).hexdigest())
        source.write_text('// fixture two')
        second=dict(self.fakebuild.inputs(self.game))
        self.assertNotEqual(first[key],second[key])
        self.assertEqual({k:v for k,v in first.items() if k!=key},
                         {k:v for k,v in second.items() if k!=key})
    def test_wrong_imported_generator_is_rejected_before_prepare(self):
        self.fakebuild.__file__ = str(self.root / 'wrong-checkout/src/saturnrecomp/build.py')
        prepare = Mock()
        with patch.dict(sys.modules, {'prepare_linux_runtime': SimpleNamespace(prepare=prepare, PIN='fixture')}):
            with self.assertRaisesRegex(SystemExit, 'Wrong imported generator'):
                self.m.verify_options_runtime()
        prepare.assert_not_called()
if __name__=='__main__':unittest.main(verbosity=2)
