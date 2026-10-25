#!/usr/bin/env python3
"""Run real production sound sources with synthetic M68K commands; verify WAV/sink."""
import argparse,array,csv,hashlib,json,math,subprocess,sys,wave
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);results=[];payloads={}
    for version,exe in [('baseline',a.baseline),('candidate',a.candidate)]:
        for mode in ['normal','sdir-tl255']:
            for batch in [1,37,1000]:
                dest=a.out/f'{version}-{mode}-batch{batch}';dest.mkdir(exist_ok=True)
                proc=subprocess.run([str(exe.resolve()),str(dest.resolve()),str(batch),mode],capture_output=True,text=True)
                (dest/'run.log').write_text(proc.stdout+proc.stderr);proc.check_returncode()
                with wave.open(str(dest/'pipeline.wav')) as w:
                    assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(2,2,44100,48510)
                    pcm=w.readframes(w.getnframes())
                assert pcm==(dest/'host-sink.s16le').read_bytes(),'WAV and host sink must match byte for byte'
                payloads[version,mode,batch]=pcm
                samples=array.array('h',pcm)
                if sys.byteorder!='little':samples.byteswap()
                assert samples[0::2]==samples[1::2],'fixture sends equal stereo'
                commands=list(csv.DictReader((dest/'commands.csv').open()))
                assert len(commands)==4 and all(c['ack']=='0' for c in commands)
                trace=(dest/'trace.log').read_text();assert trace.count('SCSP key on')==4
                events=[]
                for c in commands:
                    start,end=int(c['pcm_start']),int(c['pcm_end']);s=samples[2*start:2*end:2]
                    nz=[i for i,v in enumerate(s) if v];active=s[nz[0]:nz[-1]+1] if nz else array.array('h')
                    crossings=sum((x<0)!=(y<0) for x,y in zip(active,active[1:]))
                    events.append(dict(sa=c['sa'],nonzero=len(nz),active_frames=len(active),peak=max(map(abs,s),default=0),rms=round(math.sqrt(sum(v*v for v in s)/len(s)),3),zero_crossings=crossings,active_sha256=hashlib.sha256(active.tobytes()).hexdigest()))
                if version=='baseline' and mode=='sdir-tl255':assert not any(samples),'baseline reproducer must remain silent'
                else:
                    assert all(e['nonzero']>4000 for e in events)
                    assert len({e['active_sha256'] for e in events[:3]})==3,'different sources must not collapse'
                    assert events[0]['active_sha256']==events[3]['active_sha256'],'explicit off/on retriggers same PCM'
                    assert 75<events[0]['zero_crossings']<90 and 155<events[1]['zero_crossings']<175
                results.append(dict(version=version,mode=mode,batch=batch,frames=len(samples)//2,sha256=hashlib.sha256(pcm).hexdigest(),events=events))
    reference=payloads['baseline','normal',1]
    for key,pcm in payloads.items():
        version,mode,_=key
        assert pcm==(bytes(len(pcm)) if version=='baseline' and mode=='sdir-tl255' else reference),key
    report={'scope':'synthetic commands and sample banks through actual mmio/sound.cpp, Musashi and SCSP; recording host seam, not game audio or physical device','runs':results,'checks':'12 WAV/sink matches, command ACKs and SCSP key-ons; 3 distinct sources; repeat same PCM; all batch sizes identical; normal baseline/candidate unchanged; SDIR TL255 silence fixed'}
    (a.out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['checks'])
if __name__=='__main__':main()
