"""Compare actual threaded/fiber slave execution through nested guest tasks."""
import os
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import pal_keyboard_profile as keyboard

def test_serial_slave_preserves_schedule_and_nested_host_calls():
    with tempfile.TemporaryDirectory(prefix='pal-slave-fiber-') as folder:
        tmp=Path(folder)
        runtime=ROOT/'third_party/saturn-recomp/runtime'
        # Isolated baseline plus only the new patch, never the generated result.
        for name in ['machine.cpp','tasks.cpp']:
            dest=tmp/'runtime/src/machine'/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((runtime/'src/machine'/name).read_bytes())
        subprocess.run(['git','apply',str(ROOT/'patches/0025-directed-cpu-handoff.patch')],cwd=tmp,check=True,capture_output=True)
        original=(tmp/'runtime/src/machine/machine.cpp').read_text(encoding='utf8')
        patch=ROOT/'patches/0026-ohos-serial-cpu-coroutine.patch'
        subprocess.run(['git','apply','--check',str(patch)],cwd=tmp,check=True,capture_output=True)
        subprocess.run(['git','apply',str(patch)],cwd=tmp,check=True,capture_output=True)
        updated=(tmp/'runtime/src/machine/machine.cpp').read_text(encoding='utf8')
        for name in ['saturn.h','state.h']:
            (tmp/name).write_text('// Test-provided runtime interfaces\n')
        results=[]
        for fiber,text in [(False,original),(True,updated)]:
            handoff=text[text.index('// ---- the slave:'):text.index('// ---- the stall report')]
            control=text[text.index('bool state_slave_busy()'):text.index('// The clock and the multitap')]
            (tmp/'machine.inc').write_text(handoff+control,encoding='utf8')
            exe=tmp/('coroutine.exe' if os.name=='nt' else 'coroutine')
            flags=['-DPAL_SERIAL_SLAVE_COROUTINE=1'] if fiber else []
            compiled=subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O2','-pthread',
                            '-I'+str(tmp),'-I'+str(runtime/'third_party/minicoro'),*flags,
                            '-DPAL_TASKS_SOURCE="'+(tmp/'runtime/src/machine/tasks.cpp').as_posix()+'"',
                            str(ROOT/'tools/tests/cpu_coroutine_test.cpp'),'-o',str(exe)],
                           capture_output=True,text=True)
            assert compiled.returncode==0,compiled.stderr
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=30)
            print(('fiber' if fiber else 'thread'),result.stdout.strip())
            results.append(result.stdout.split(' time_ms=')[0])
        assert results[0]==results[1]

def test_master_input_gate_preserves_thread_and_logical_cpu_ownership():
    text=keyboard.guard_master_input('return SDL_IsMainThread();\nif (!SDL_IsMainThread()) return;')
    assert text.count('SDL_IsMainThread() && g_cpu == &g_master')==2
    # Execute the emitted guard, including negative gates used by field input.
    with tempfile.TemporaryDirectory(prefix='pal-input-owner-') as folder:
        tmp=Path(folder);source=tmp/'owner.cpp'
        gates=keyboard.guard_master_input('bool positive(){return SDL_IsMainThread();}\n'
          'bool negative(){if(!SDL_IsMainThread())return false;return true;}\n')
        source.write_text('bool on_main; int g_master,g_slave; int* g_cpu;\n'
          'bool SDL_IsMainThread(){return on_main;}\n'+gates+
          'int main(){for(int t=0;t<2;++t)for(int c=0;c<2;++c){on_main=t;'
          'g_cpu=c?&g_slave:&g_master;bool want=t&&!c;'
          'if(positive()!=want||negative()!=want)return 1;}return 0;}\n')
        exe=tmp/('owner.exe' if os.name=='nt' else 'owner')
        subprocess.run([os.environ.get('CXX','g++'),str(source),'-o',str(exe)],check=True,capture_output=True)
        subprocess.run([str(exe)],check=True,timeout=5)
