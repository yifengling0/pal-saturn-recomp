"""Stress the actual runtime handoff, including wakeups arriving before waits."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def test_directed_guest_cpu_handoffs():
    raw=(ROOT/'third_party/saturn-recomp/runtime/src/machine/machine.cpp').read_text(encoding='utf8')
    with tempfile.TemporaryDirectory(prefix='pal-handoff-') as folder:
        tmp=Path(folder)
        src=tmp/'runtime/src/machine/machine.cpp'
        src.parent.mkdir(parents=True);src.write_text(raw,encoding='utf8')
        patch=ROOT/'patches/0025-directed-cpu-handoff.patch'
        subprocess.run(['git','apply','--check',str(patch)],cwd=tmp,check=True,capture_output=True)
        subprocess.run(['git','apply',str(patch)],cwd=tmp,check=True,capture_output=True)
        for directed,text in [(False,raw),(True,src.read_text(encoding='utf8'))]:
            begin=text.index('static std::mutex g_mu;')
            end=text.index('static void to_slave()',begin)
            snippet=tmp/'handoff.inc';snippet.write_text(text[begin:end],encoding='utf8')
            exe=tmp/('handoff.exe' if os.name=='nt' else 'handoff')
            flags=['-DPAL_DIRECTED_CV=1'] if directed else []
            subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O2','-pthread',
                            '-DPAL_CPU_HANDOFF="'+snippet.as_posix()+'"',*flags,
                            str(ROOT/'tools/tests/cpu_handoff_test.cpp'),'-o',str(exe)],check=True,capture_output=True)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=20)
            print(('directed' if directed else 'baseline'),result.stdout.strip())
