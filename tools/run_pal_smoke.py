"""Repeatable PAL diagnostic run. Exit status is never interpreted as playability."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cue',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--vblanks',type=int,default=6500)
    p.add_argument('--timeout',type=int,default=300)
    p.add_argument('--input',default='1500:START,1512:,2500:START,2512:,2600:A,2612:')
    p.add_argument('--shots',default='600,1500,2500,2600,2700,3000,3900,4500,5000,6100,6500')
    p.add_argument('--window',action='store_true')
    p.add_argument('--input-file',type=Path,help='Replay a saved input script instead of --input text')
    saves=p.add_mutually_exclusive_group()
    saves.add_argument('--save-copy',type=Path,help='Copy an existing test save into the fresh run directory')
    saves.add_argument('--save-new',action='store_true',help='Create fresh persistent test backup memory in the run directory')
    p.add_argument('--exe',type=Path,default=ROOT/'build/linux-game-sdl/recomp-build/saturn')
    a=p.parse_args()
    if a.vblanks<=0 or a.timeout<=0: p.error('positive vblank/timeout limits required')
    cue=a.cue.resolve(strict=True);out=a.out.resolve();exe=a.exe.resolve(strict=True)
    out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT/'validation'))
    from pal_validate.core import cue_references
    inputs=[cue,*cue_references(cue)];before={str(q):sha(q) for q in inputs}
    script=a.input_file.read_text() if a.input_file else a.input+'\n'
    (out/'input.txt').write_text(script)
    save='-'
    save_source=a.save_copy.resolve(strict=True) if a.save_copy else None
    save_source_hash=sha(save_source) if save_source else None
    if a.save_new or save_source:
        save=str(out/'test-backup.bup')
        if save_source:shutil.copy2(save_source,save)
    frames=','.join(x for x in a.shots.split(',') if 0<int(x)<=a.vblanks)
    cmd=[str(exe),'--cue',str(cue),'--out',str(out),'--save',save,
         '--clock','1998-11-01T12:00:00','--vblanks',str(a.vblanks),
         '--input','@'+str(out/'input.txt'),'--shot',frames,'--dump',frames,
         '--peek','060768DC:6,06076928:2,06076968:2','--wav',str(out/'sound.wav')]
    if not a.window:cmd.append('--headless')
    report={'command':cmd,'input_sha256_before':before,'game_normal_operation':False,
            'note':'No game completion claim follows from reaching a frame limit',
            'executable_sha256':sha(exe),'input_script_sha256':sha(out/'input.txt'),
            'save_source':str(save_source) if save_source else None,
            'save_source_sha256_before':save_source_hash}
    started=time.monotonic()
    with (out/'run.log').open('wb') as log:
        try:report['returncode']=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=a.timeout,cwd=ROOT).returncode
        except subprocess.TimeoutExpired:report['returncode']=124;report['timed_out']=True
    report['elapsed_seconds']=time.monotonic()-started
    report['input_sha256_after']={str(q):sha(q) for q in inputs}
    report['inputs_unchanged']=before==report['input_sha256_after']
    if save_source:
        report['save_source_sha256_after']=sha(save_source)
        report['inputs_unchanged'] &= report['save_source_sha256_after']==save_source_hash
    if save!='-' and Path(save).exists():report['save_result_sha256']=sha(Path(save))
    report['pngs']={q.name:sha(q) for q in sorted(out.glob('shot-*.png'))}
    from inspect_video_dump import inspect
    report['dumps']={q.name:inspect(q.read_bytes()) for q in sorted(out.glob('dump-*.bin'))}
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['returncode','elapsed_seconds','inputs_unchanged','pngs']},indent=2))
    return report['returncode'] if report['inputs_unchanged'] else 3
if __name__=='__main__':sys.exit(main())
