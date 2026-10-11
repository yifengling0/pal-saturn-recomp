#!/usr/bin/env python3
"""Linux host tests: actual runtime host + real shared SDL3 + mocked OH service."""
import argparse, os, shlex, subprocess
from pathlib import Path

here = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime', required=True, type=Path, help='Patched runtime, raw or PC98-transformed')
parser.add_argument('--sdl-prefix', required=True, type=Path, help='SDL3 prefix containing include/SDL3 and lib/libSDL3.so')
parser.add_argument('--sdk-headers', type=Path, default=here/'fixtures/upstream-gamecontroller', help='Parent directory containing GameControllerKit/*.h; fixture is public headers only, not an SDK')
parser.add_argument('--bridge-dir', type=Path, default=here.parents[1]/'harmony/pal-saturn-openharmony/entry/src/main/cpp')
parser.add_argument('--output', type=Path, default=here/'out')
parser.add_argument('--cxx', default=os.environ.get('CXX','c++'))
parser.add_argument('--sanitizers', action='store_true', help='Enable AddressSanitizer and UndefinedBehaviorSanitizer')
parser.add_argument('--no-leak-check', action='store_true', help='Disable LeakSanitizer only, for ptrace-restricted executors')
args=parser.parse_args()
rt,prefix,sdk,bridge,out=[p.resolve() for p in (args.runtime,args.sdl_prefix,args.sdk_headers,args.bridge_dir,args.output)]
for p in [rt/'src/host/host.cpp',rt/'src/host/settings.cpp',prefix/'include/SDL3/SDL.h',sdk/'GameControllerKit/game_device.h',bridge/'pal_ohos_gamepad.cpp']:
 if not p.is_file(): parser.error(f'missing required source/header: {p}')
out.mkdir(parents=True,exist_ok=True)
cxx=shlex.split(args.cxx)
flags=['-std=c++17','-pthread']
if args.sanitizers: flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
def run(command, name, env=None):
 p=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
 (out/(name+'.log')).write_text(p.stdout)
 print(p.stdout,end='')
 if p.returncode: raise SystemExit(f'{name} failed ({p.returncode}); see {out/(name+".log")}')
def compile(extra,name):run(cxx+flags+extra,name)
compile(['-Wall','-Wextra','-Werror','-fPIC','-shared','-I'+str(sdk),str(here/'mock_game_controller.cpp'),'-o',str(out/'libohgame_controller.z.so')],'compile-mock-service')
compile(['-Wall','-Wextra','-Werror','-DPAL_OHOS_GAMEPAD_BRIDGE=1','-I'+str(sdk),'-I'+str(prefix/'include'),'-c',str(bridge/'pal_ohos_gamepad.cpp'),'-o',str(out/'bridge.o')],'compile-real-api-bridge')
includes=[bridge,rt/'include',rt/'src/host',rt/'src/machine',rt/'src/video',rt/'src/sound',prefix/'include',here]
link=['-L'+str(prefix/'lib'),'-Wl,-rpath,'+str(prefix/'lib'),'-lSDL3','-ldl']
compile(['-O1','-ffunction-sections','-fdata-sections','-DPAL_OHOS_INPUT=1','-DHOST_SOURCE="'+str(rt/'src/host/host.cpp')+'"']+
 ['-I'+str(p) for p in includes]+[str(here/'actual_host_gamepad_tests.cpp'),str(rt/'src/host/settings.cpp'),str(out/'bridge.o'),'-Wl,--gc-sections']+link+
 ['-L'+str(out),'-Wl,-rpath,'+str(out),'-l:libohgame_controller.z.so','-o',str(out/'actual-host-gamepad-tests')],'compile-host-tests')
env=os.environ.copy();env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',LD_LIBRARY_PATH=str(out)+':'+str(prefix/'lib'))
if args.no_leak_check:env['ASAN_OPTIONS']=env.get('ASAN_OPTIONS','')+':detect_leaks=0'
run([str(out/'actual-host-gamepad-tests')],'host-tests',env)
(out/'unavailable.cpp').write_text('''#include "pal_ohos_gamepad.h"
#include <SDL3/SDL.h>
#include <cstdio>
int main(){if(!SDL_Init(SDL_INIT_GAMEPAD))return 2;bool ready=pal_ohos_gamepad_start();pal_ohos_gamepad_pump();pal_ohos_gamepad_stop();pal_ohos_gamepad_stop();SDL_Quit();printf("Unavailable bridge safely reported: %s\\n",ready?"FAIL":"PASS");return ready?1:0;}
''')
compile(['-I'+str(bridge),'-I'+str(prefix/'include'),str(out/'unavailable.cpp'),str(out/'bridge.o')]+link+['-o',str(out/'unavailable-api')],'compile-unavailable-tests')
env['LD_LIBRARY_PATH']=str(prefix/'lib')
run([str(out/'unavailable-api')],'missing-library',env)
missing=out/'missing-symbol';missing.mkdir(exist_ok=True);(missing/'empty.cpp').write_text('void placeholder() {}\n')
compile(['-shared','-fPIC',str(missing/'empty.cpp'),'-o',str(missing/'libohgame_controller.z.so')],'compile-missing-symbol')
env['LD_LIBRARY_PATH']=str(missing)+':'+str(prefix/'lib')
run([str(out/'unavailable-api')],'missing-symbol',env)
compile(['-Wall','-Wextra','-Werror','-DPAL_OHOS_GAMEPAD_BRIDGE=0','-I'+str(bridge),'-I'+str(prefix/'include'),str(out/'unavailable.cpp'),str(bridge/'pal_ohos_gamepad.cpp')]+link+['-o',str(out/'disabled-bridge')],'compile-disabled-bridge')
run([str(out/'disabled-bridge')],'disabled-bridge',env)
print('PASS: host tests and runtime-unavailable paths. No real OHOS SDK build or hardware test was performed by this script.')
