"""Interactive, input-only PAL test session through the runtime's documented agent socket.

One JSON command per stdin line: {"op":"step","frames":60}, {"op":"pad","buttons":"DOWN"},
{"op":"read","address":"06076928","length":4}, {"op":"frame"}, {"op":"quit"}.
No memory-write command is exposed. Output and source save must be separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import time
import zlib


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png(path,w,h,rgb):
    def chunk(kind,payload):
        return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
    rows=b''.join(b'\0'+rgb[y*w*3:(y+1)*w*3] for y in range(h))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


def validate(req):
    op=req['op']
    if op=='step':
        n=int(req['frames'])
        if not 1<=n<=10000:raise ValueError('step range 1..10000')
        return f'step {n}'
    if op=='pad':
        value=req.get('buttons','')
        if not isinstance(value,str) or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,+.' for c in value):raise ValueError('Invalid button string')
        return 'pad '+value
    if op=='read':
        addr=int(req['address'],16);length=int(req.get('length',4));p=addr&0x1fffffff
        if not 1<=length<=256 or not (0x06000000<=p and p+length<=0x06100000 or 0x00200000<=p and p+length<=0x00300000):raise ValueError('Only bounded raw Work RAM observations are allowed')
        return f'read {addr:08X} {length}'
    if op in ('frame','quit'):return op
    raise ValueError('Unsupported command; no memory-write interface')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',type=Path,required=True);p.add_argument('--cue',type=Path,required=True)
    p.add_argument('--save-copy',type=Path,required=True);p.add_argument('--input-file',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();exe=a.exe.resolve(strict=True);cue=a.cue.resolve(strict=True);source=a.save_copy.resolve(strict=True);script=a.input_file.resolve(strict=True)
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    source_hash=sha(source);shutil.copy2(source,out/'test-backup.bup');shutil.copy2(script,out/'boot-input.txt')
    parent,child=socket.socketpair();parent.settimeout(120)
    cmd=[str(exe),'--cue',str(cue),'--headless','--save',str(out/'test-backup.bup'),'--clock','1998-11-01T12:00:00','--input','@'+str(out/'boot-input.txt'),'--out',str(out),'--agent',str(child.fileno())]
    (out/'provenance.json').write_text(json.dumps({'command':cmd,'executable_sha256':sha(exe),'save_source':str(source),'save_source_sha256':source_hash,'input_sha256':sha(script),'note':'Paused input-driven test; host wall time is not gameplay speed'},indent=2)+'\n')
    with (out/'run.log').open('wb') as log,(out/'commands.jsonl').open('w') as history:
        proc=subprocess.Popen(cmd,pass_fds=(child.fileno(),),stdout=log,stderr=subprocess.STDOUT);child.close();stream=parent.makefile('rb');count=0;vb=0
        def response():
            nonlocal vb
            line=stream.readline().decode().strip()
            if not line:raise RuntimeError('Runtime socket closed')
            if line.startswith('vblank '):vb=int(line.split()[1])
            return line
        print(json.dumps({'ready':response(),'pid':proc.pid,'out':str(out)}),flush=True)
        try:
            for raw in sys.stdin:
                started=time.monotonic()
                try:
                    req=json.loads(raw);command=validate(req);parent.sendall((command+'\n').encode())
                    if command=='quit':
                        proc.wait(timeout=20);result={'exit_code':proc.returncode};done=True
                    else:
                        result={'reply':response(),'vblank':vb};done=False
                        if command=='frame':
                            parts=result['reply'].split();assert parts[0]=='frame'
                            w,h=map(int,parts[1:]);assert 0<w<=1024 and 0<h<=1024
                            rgb=stream.read(w*h*3);assert len(rgb)==w*h*3
                            count+=1;path=out/f'frame-{vb:08d}-{count:03d}.png';png(path,w,h,rgb)
                            result.update(path=str(path),sha256=sha(path))
                    record={'request':req,'result':result,'elapsed_seconds':time.monotonic()-started}
                    history.write(json.dumps(record)+'\n');history.flush();print(json.dumps(record),flush=True)
                    if done:break
                except (ValueError,KeyError,AssertionError) as err:
                    print(json.dumps({'error':str(err)}),flush=True)
        finally:
            parent.close();stream.close()
            if proc.poll() is None:
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=10)
            from export_autoplay_inputs import export
            replay_count=export(out,out/'replay-input.txt')
            unchanged=sha(source)==source_hash
            (out/'result.json').write_text(json.dumps({'returncode':proc.returncode,'save_source_unchanged':unchanged,'final_vblank':vb,'save_sha256':sha(out/'test-backup.bup'),'replay_file':'replay-input.txt','agent_pad_events':replay_count},indent=2)+'\n')
    return proc.returncode if unchanged else 3

if __name__=='__main__':sys.exit(main())
