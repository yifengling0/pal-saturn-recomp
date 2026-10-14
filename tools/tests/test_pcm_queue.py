"""Verify PCM continuity across delivery batching and concurrent output callbacks."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

def test_pcm_delivery_continuity():
    with tempfile.TemporaryDirectory(prefix='pal-pcm-') as folder:
        exe = Path(folder) / ('pcm.exe' if os.name == 'nt' else 'pcm')
        subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++17', '-O2', '-pthread',
                        '-Wall', '-Wextra', '-Werror',
                        '-I' + str(ROOT / 'harmony/pal-saturn-openharmony/entry/src/main/cpp'),
                        str(ROOT / 'tools/tests/pcm_queue_test.cpp'), '-o', str(exe)],
                       check=True, capture_output=True)
        subprocess.run([str(exe)], check=True, capture_output=True, timeout=20)
