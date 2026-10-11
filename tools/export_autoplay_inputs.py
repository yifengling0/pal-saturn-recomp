"""Export successful input-only agent commands as a deterministic pad replay."""
import argparse
import json
from pathlib import Path

def export(directory: Path, destination: Path):
    if destination.exists():raise ValueError('Refusing to overwrite replay: '+str(destination))
    boot=(directory/'boot-input.txt').read_text().strip().rstrip(',')
    events=[];last=-1
    for line in (directory/'commands.jsonl').read_text().splitlines():
        row=json.loads(line);req=row['request'];result=row['result']
        if req.get('op')!='pad':continue
        if result.get('reply')!='ok':raise ValueError('Unsuccessful pad request in history')
        vb=int(result['vblank'])
        if vb<last:raise ValueError('Out-of-order agent input')
        last=vb;buttons=req.get('buttons','')
        if not isinstance(buttons,str) or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,+.' for c in buttons):raise ValueError('Invalid pad event')
        events.append(f'{vb}:{buttons}')
    text=','.join(([boot] if boot else [])+events)+'\n'
    with destination.open('x') as f:f.write(text)
    return len(events)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('destination',type=Path);a=p.parse_args();print(export(a.directory,a.destination),'agent pad events exported')
