"""Asset-free callback purity, scope and original-policy switch tests."""
from pathlib import Path
import os
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]

def test_obstacle_stop_callback():
    with tempfile.TemporaryDirectory(prefix='pal-obstacle-') as d:
        exe=Path(d)/('test.exe' if os.name=='nt' else 'test')
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-Wall','-Wextra','-Werror',
            '-DPAL_OBSTACLE_HOOK_VERIFIED=1','-I'+str(ROOT/'src/pal_game'),
            '-I'+str(ROOT/'third_party/saturn-recomp-pal/runtime/include'),
            str(ROOT/'tools/tests/obstacle_stop_runtime_test.cpp'),
            str(ROOT/'src/pal_game/pal_obstacle_stop.cpp'),'-o',str(exe)],check=True)
        for mode in (None,'0','1'):
            env=os.environ.copy();env.pop('PAL_OBSTACLE_STOP',None)
            if mode is not None:env['PAL_OBSTACLE_STOP']=mode
            subprocess.run([str(exe)],env=env,check=True)

def test_obstacle_stop_build_gate():
    """The actual linked generation, not an unused source, must match."""
    line='    c.r[3] = 0x3u; sh2_hook(c, 0x06033752u);  // 06033752 mov #3,r3\n'
    cases=[(line,'',True),('', '',False),(line+line,'',False),
           (line.replace('0x3u','0x2u'),'',False),(line,line,False),('',line,False)]
    for prog,other,valid in cases:
        with tempfile.TemporaryDirectory(prefix='pal-obstacle-cmake-') as d:
            d=Path(d)
            (d/'p_prog_000.cpp').write_text(prog)
            (d/'p_true_000.cpp').write_text(other)
            (d/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\n'
                'project(obstacle_gate LANGUAGES CXX)\n'
                'add_library(recomp OBJECT p_prog_000.cpp p_true_000.cpp)\n'
                'set(PAL_GAME_TARGET recomp)\n'
                f'include("{ROOT.as_posix()}/src/pal_game/pal_obstacle_stop.cmake")\n')
            run=subprocess.run(['cmake','-S',str(d),'-B',str(d/'build')],capture_output=True,text=True)
            assert (run.returncode==0)==valid,run.stdout+run.stderr
