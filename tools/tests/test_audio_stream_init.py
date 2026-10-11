"""Asset-free bounds/idempotence tests for the PAL cold movie sound cache fix."""
from pathlib import Path
import os
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
def test_cold_movie_sound_cache_plan():
    with tempfile.TemporaryDirectory(prefix='PAL movie cache 空格 ') as folder:
        exe=Path(folder)/('audio-cache.exe' if os.name=='nt' else 'audio-cache')
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-Wall','-Wextra','-Werror',
            '-I'+str(ROOT/'src/pal_game'),str(ROOT/'tools/tests/audio_stream_init_test.cpp'),
            '-o',str(exe)],check=True,capture_output=True)
        subprocess.run([str(exe)],check=True,capture_output=True)

def test_registered_movie_sound_cache_callback():
    with tempfile.TemporaryDirectory(prefix='PAL movie callback 空格 ') as folder:
        folder=Path(folder)
        (folder/'saturn.h').write_text('#pragma once\nvoid sat_note(const char*, ...);\n')
        exe=folder/('audio-callback.exe' if os.name=='nt' else 'audio-callback')
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-Wall','-Wextra','-Werror',
            '-I'+str(folder),'-I'+str(ROOT/'src/pal_game'),
            '-I'+str(ROOT/'third_party/saturn-recomp-pal/runtime/include'),
            str(ROOT/'tools/tests/audio_stream_init_runtime_test.cpp'),
            str(ROOT/'src/pal_game/pal_audio_stream_init.cpp'),'-o',str(exe)],
            check=True,capture_output=True)
        subprocess.run([str(exe)],check=True,capture_output=True)
