"""Build an isolated, opt-in PAL effect preparation-delay experiment.

Only the exact f0603108C bitmap-bank setup caller may shorten its wait.
The baseline and original 20-frame effect cadence remain untouched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--sdl-prefix',type=Path)
    a=parser.parse_args();out=a.out.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'build'):
        raise SystemExit('Choose a new directory under build; existing files are never overwritten')
    # The diagnostic snapshot validates baseline identity and all probe sites.
    subprocess.run([sys.executable,str(ROOT/'tools/battle_probe/prepare_probe.py'),
                    '--root',str(ROOT),'--output',str(out)],check=True)
    source=out/'recomp/p_prog_000.cpp';lines=source.read_text().splitlines(True)
    points=[i for i,line in enumerate(lines) if '// 060224E0 ' in line]
    if len(points)!=1 or 'f_06021FD8(c)' not in lines[points[0]]:
        raise SystemExit('Effect preparation wait call changed; stop and review')
    call=lines[points[0]]
    lines[points[0]]='    { pal_effect_wait::Scope pal_effect_scope(c);\n'+call+'    }\n'
    checks=[i for i,line in enumerate(lines) if '// 0602202C ' in line]
    if len(checks)!=1 or 'if (!c.t)' not in lines[checks[0]]:
        raise SystemExit('Original delay-loop condition changed; stop and review')
    lines.insert(checks[0],'    if (!c.t && pal_effect_wait::ready(c)) c.t=true;\n')
    source.write_text('#include "pal_effect_wait_runtime.h"\n'+''.join(lines))
    helpers=[ROOT/'src/pal_game/pal_effect_wait.h',ROOT/'src/pal_game/pal_effect_wait_runtime.h']
    for helper in helpers:shutil.copy2(helper,out/'recomp'/helper.name)
    (out/'effect-wait-provenance.json').write_text(json.dumps({
      'mode':'PAL_SHORT_EFFECT_PREP=1; default off',
      'scope':'224E0 caller31172, master battle, mode1/bank7/argument200/interval2; preserve original 50-loop cap; exit only after >=2 loops, >=2 guest VBlanks and actual BMPNA byte matches target',
      'helpers_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers},
      'warning':'Game-specific optional timing change; fewer battle tick/RNG/input-cancel opportunities; no claim of full gameplay equivalence'
    },indent=2)+'\n')
    cmake=ROOT/'build/venv/bin/cmake'
    command=[str(cmake),'-S',str(out/'recomp'),'-B',str(out/'compile'),'-G','Ninja']
    if a.sdl_prefix:command+=['-DSDL3_DIR='+str(a.sdl_prefix.resolve()/'lib/cmake/SDL3')]
    else:command+=['-DSATURN_NO_SDL=ON']
    env=os.environ.copy();env["PATH"]=str(ROOT/"build/venv/bin")+os.pathsep+env["PATH"]
    subprocess.run(command,env=env,check=True)
    subprocess.run([str(cmake),'--build',str(out/'compile'),'--target','saturn','-j',str(a.jobs)],env=env,check=True)
    print(out/'compile/saturn')
if __name__=='__main__':main()
