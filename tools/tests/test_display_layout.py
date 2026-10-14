"""Exercise the actual patched geometry, settings parser and desktop PCM batcher."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def test_display_geometry_and_desktop_pcm():
    runtime=ROOT/'third_party/saturn-recomp-pal/runtime'
    with tempfile.TemporaryDirectory(prefix='pal-display-') as folder:
        exe=Path(folder)/('display.exe' if os.name=='nt' else 'display')
        result=subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O2',
            '-I'+str(runtime/'src/host'),'-I'+str(runtime/'include'),
            '-I'+str(runtime/'src/video'),'-I'+str(runtime/'src/machine'),
            str(ROOT/'tools/tests/display_layout_test.cpp'),str(runtime/'src/host/settings.cpp'),
            '-o',str(exe)],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15)
        assert result.returncode==0,result.stdout+result.stderr
