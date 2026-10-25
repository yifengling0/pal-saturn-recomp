#!/usr/bin/env python3
"""Asset-free sound-dataflow regression using real pinned runtime source files."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--runtime',type=Path,default=ROOT/'third_party/saturn-recomp-pal/runtime')
p.add_argument('--baseline-runtime',type=Path,default=ROOT/'third_party/saturn-recomp/runtime')
p.add_argument('--out',type=Path,default=ROOT/'build/scsp-audio')
p.add_argument('--jobs',type=int,default=2)
a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env['PATH']=str(ROOT/'build/venv/bin')+os.pathsep+env['PATH']
results={}
def run(name,cmd,expect_failure=False):
    cmd=list(map(str,cmd));print('$ '+' '.join(cmd),flush=True)
    r=subprocess.run(cmd,env=env,capture_output=True,text=True)
    (a.out/f'{name}.log').write_text('$ '+' '.join(cmd)+'\n'+r.stdout+r.stderr)
    results[name]=r.returncode
    if expect_failure:
        if r.returncode!=1:raise RuntimeError(f'{name}: expected failing regression exit1, got{r.returncode}')
    elif r.returncode:raise subprocess.CalledProcessError(r.returncode,cmd)
for name,rt,legacy in [('baseline',a.baseline_runtime,True),('candidate',a.runtime,False)]:
    rt=rt.resolve();assert (rt/'src/sound/scsp.cpp').is_file()
    build=a.out/name
    run(name+'-configure',['cmake','-S',HERE,'-B',build,'-G','Ninja',f'-DRUNTIME={rt}',f'-DLEGACY_SCSP={"ON" if legacy else "OFF"}'])
    run(name+'-build',['cmake','--build',build,'--parallel',a.jobs])
    run(name+'-scsp',[build/'scsp_regressions'],expect_failure=legacy)
run('state-loader',[a.out/'candidate/state_loader',a.out/'states'])
run('pipeline',[sys.executable,HERE/'analyze_pipeline.py','--baseline',a.out/'baseline/sound_pipeline','--candidate',a.out/'candidate/sound_pipeline','--out',a.out/'pipeline'])
run('dsp-equivalence',[sys.executable,HERE/'check_dsp_equivalence.py','--runtime',a.runtime.resolve(),'--out',a.out/'dsp-equivalence'])
sources={}
for label,rt in [('baseline',a.baseline_runtime),('candidate',a.runtime)]:
    sources[label]={str(f):hashlib.sha256((rt/f).read_bytes()).hexdigest() for f in map(Path,['src/sound/scsp.cpp','src/sound/sound.cpp','src/machine/state.cpp','src/machine/mmio.cpp'])}
(a.out/'summary.json').write_text(json.dumps({'exit_codes':results,'source_sha256':sources,'scope':'synthetic, no actual game or physical host output'},indent=2)+'\n')
print('Sound core and synthetic M68K/PCM regressions passed; real game and physical audio remain unverified.')
