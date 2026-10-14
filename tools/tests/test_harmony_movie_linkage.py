from pathlib import Path
import importlib.util,subprocess,tempfile,unittest,sys
PROJECT=Path(__file__).resolve().parents[2]
OLD=PROJECT
RUNTIME=PROJECT/'third_party/saturn-recomp-pal/runtime'
spec=importlib.util.spec_from_file_location('candidate_ohos',PROJECT/'tools/ohosbuild.py');ohos=importlib.util.module_from_spec(spec);spec.loader.exec_module(ohos)
class MovieLinkage(unittest.TestCase):
 def test_generated_guard(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d=root/'build/recomp';d.mkdir(parents=True)
   for content,valid in [('',False),('// sh2_hook(c, 0x06021C1Eu);',False),('c.r[2]=1; sh2_hook(c, 0x06021C1Eu);',True),('/*sh2_hook(c,0x06021C1Eu)*/',False)]:
    (d/'p_true_000.cpp').write_text(content)
    if valid:ohos.verify_movie_hook(root)
    else:
     with self.assertRaises(SystemExit):ohos.verify_movie_hook(root)
   (d/'p_true_000.cpp').write_text('sh2_hook(c,0x06021C1Eu);');(d/'p_true_001.cpp').write_text('sh2_hook(c,0x06021C1Eu);')
   with self.assertRaises(SystemExit):ohos.verify_movie_hook(root)
 def test_actual_target_sources(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);layer=p/'layer';layer.mkdir()
   (layer/'pal_game.cmake').write_text((PROJECT/'src/pal_game/pal_game.cmake').read_text())
   # The desktop branch of that file attaches the application icon, so the fixture carries the
   # resource directory the way a real checkout does; otherwise configure fails on Windows.
   (layer/'app_icon').mkdir()
   for resource in (PROJECT/'src/pal_game/app_icon').iterdir():
    (layer/'app_icon'/resource.name).write_bytes(resource.read_bytes())
   # This fixture checks target attachment only; the real asset/generation gate
   # is exercised separately by test_medicine_chest_identity.py.
   (layer/'pal_disc_identity.cmake').write_text('# target-attachment fixture only\n')
   # Full normal/probe/old/altered render gates have separate CMake regressions.
   (layer/'pal_render_returns.cmake').write_text('# target-attachment fixture only\n')
   for f in ['pal_diag.cpp','pal_audio_stream_init.cpp','pal_medicine_chest.cpp']:(layer/f).write_text('')
   (p/'dummy.cpp').write_text('int main(){return 0;}')
   (p/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(test CXX)\nadd_library(saturn_machine STATIC dummy.cpp)\nadd_executable(saturn dummy.cpp)\ninclude(layer/pal_game.cmake)\nadd_library(main SHARED dummy.cpp)\nset(PAL_GAME_TARGET main)\ninclude(layer/pal_game.cmake)\nunset(PAL_GAME_TARGET)\nforeach(t saturn main)\nget_target_property(s ${t} SOURCES)\nfile(WRITE "${CMAKE_BINARY_DIR}/${t}.txt" "${s}")\nendforeach()\n')
   subprocess.run(['cmake','-S',str(p),'-B',str(p/'out')],check=True,capture_output=True)
   for t in ['saturn','main']:
    self.assertIn('pal_audio_stream_init.cpp',(p/'out'/f'{t}.txt').read_text())
    self.assertIn('pal_medicine_chest.cpp',(p/'out'/f'{t}.txt').read_text())
 def test_real_callback_and_feature_link(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'saturn.h').write_text('void sat_note(const char*, ...);\n')
   source=(OLD/'tools/tests/audio_stream_init_runtime_test.cpp').read_text()
   source=source.replace('int main() {','extern "C" const char* pal_movie_cache_feature();\nint main() {\n assert(std::strstr(pal_movie_cache_feature(), "registered=1"));')
   self.assertIn('pal_movie_cache_feature()',source)
   (p/'test.cpp').write_text(source)
   args=['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(p),'-I'+str(PROJECT/'src/pal_game'),'-I'+str(RUNTIME/'include'),str(p/'test.cpp')]
   bad=subprocess.run(args+['-o',str(p/'red')],capture_output=True,text=True)
   self.assertNotEqual(bad.returncode,0);self.assertIn('pal_movie_cache_feature',bad.stderr)
   subprocess.run(args+[str(PROJECT/'src/pal_game/pal_audio_stream_init.cpp'),'-o',str(p/'green')],check=True,capture_output=True)
   subprocess.run([str(p/'green')],check=True)
if __name__=='__main__':unittest.main()
