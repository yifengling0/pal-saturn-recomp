"""Compare all rendered pixels with the pinned pre-optimization VDP2 composer."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
BASE_HASH='52921c0ba3b3ba6c48d055252a8ad598bd0c7266966aff174274a453ec7c6169'

def test_vdp2_frame_decode_preserves_rgb():
    baseline=ROOT/'third_party/saturn-recomp/runtime/src/video/vdp2.cpp'
    raw=baseline.read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(raw).hexdigest()==BASE_HASH
    with tempfile.TemporaryDirectory(prefix='pal-vdp2-') as folder:
        tmp=Path(folder)
        src=tmp/'runtime/src/video/vdp2.cpp'
        src.parent.mkdir(parents=True)
        src.write_bytes(raw)
        reference=tmp/'reference.cpp'
        reference.write_bytes(raw)
        patch=ROOT/'patches/0024-vdp2-frame-decode-cache.patch'
        subprocess.run(['git','apply','--check',str(patch)],cwd=tmp,check=True,capture_output=True)
        subprocess.run(['git','apply',str(patch)],cwd=tmp,check=True,capture_output=True)
        for name in ['saturn.h','state.h','video.h']:
            (tmp/name).write_text('// Independent composition fixture\n',encoding='utf8')
        exe=tmp/('vdp2-cache.exe' if os.name=='nt' else 'vdp2-cache')
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O2','-I'+str(tmp),
                        '-DPAL_VDP2_REFERENCE="'+reference.as_posix()+'"',
                        '-DPAL_VDP2_CACHED="'+src.as_posix()+'"',
                        str(ROOT/'tools/tests/vdp2_cache_test.cpp'),'-o',str(exe)],
                       check=True,capture_output=True)
        result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=60)
        print(result.stdout.strip())
