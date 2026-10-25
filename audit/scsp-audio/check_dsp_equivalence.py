#!/usr/bin/env python3
"""Production DSP vs same source with all128 steps; only loop bound differs."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True);a.out=a.out.resolve();rt=a.runtime.resolve();here=Path(__file__).resolve().parent
source=(rt/'src/sound/scsp.cpp').read_text();needle='std::min(d.last_step + 2, 128)';assert source.count(needle)==1
includes=[rt/'include',rt/'src/machine',rt/'src/sound',rt/'src/host',rt/'src/video',rt/'tests']
logs={}
for name,bound in [('optimized',needle),('full128','128'),('old-tail','std::min(d.last_step + 1, 128)')]:
    src=a.out/f'{name}.cpp';src.write_text(source.replace(needle,bound))
    cmd=['g++','-std=c++20','-O2',*[f'-I{i}' for i in includes],str(src),str(here/'dsp_equivalence.cpp'),str(here/'unit_support.cpp'),'-o',str(a.out/name)]
    subprocess.run(cmd,check=True,capture_output=True)
    run=subprocess.run([str(a.out/name)],check=True,capture_output=True,text=True)
    logs[name]=run.stdout.splitlines();(a.out/f'{name}.log').write_text(run.stdout)
assert len(logs['optimized'])==2048
assert logs['optimized']==logs['full128']
diffs=sum(x!=y for x,y in zip(logs['old-tail'],logs['full128']));assert diffs>0
result={'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'seeds':512,'comparisons':2048,'optimized_mismatches':0,'old_tail_mismatches':diffs,'scope':'same DSP implementation with only optimization bound changed; not an independent hardware oracle'}
(a.out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
