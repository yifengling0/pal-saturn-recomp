#!/usr/bin/env python3
"""Summarize PAL_BATTLE logs. Durations are inclusive; do not sum nested buckets."""
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path

def percentile(values,p):
    if not values:return None
    values=sorted(values);idx=(len(values)-1)*p;a=int(idx);b=min(a+1,len(values)-1)
    return values[a]+(values[b]-values[a])*(idx-a)

def summarize(path):
    opened={};groups=defaultdict(list);markers=[];unwinds=[];anomalies=[];limited=False
    for lineno,line in enumerate(path.read_text(errors='replace').splitlines(),1):
        if not line.startswith('PAL_BATTLE '):continue
        row=dict(item.split('=',1) for item in line.split()[1:] if '=' in item)
        event=row.get('event')
        if event=='LIMIT':limited=True;continue
        if event=='M':markers.append(row);continue
        if event=='B':
            ident=row['id']
            if ident in opened:anomalies.append(f'duplicate begin {ident} at line{lineno}')
            opened[ident]=row;continue
        if event!='E':continue
        begin=opened.pop(row['id'],None)
        if begin is None:anomalies.append(f'unmatched end {row["id"]} at line{lineno}');continue
        if begin['pc']!=row['pc']:anomalies.append(f'PC mismatch {row["id"]}');continue
        if row.get('unwind')=='1':unwinds.append({'begin':begin,'end':row});continue
        key=row['pc']
        if key=='06020094':key+=':'+begin.get('name','?')+':caller='+begin['pr']
        groups[key].append((begin,row))
    result={'source_log':str(path),'inclusive_durations':True,
            'warning':'Nested function durations overlap. Guest frame_present is not proof of SDL presentation.',
            'limited':limited,'unmatched_begins':list(opened.values()),'unwinds':unwinds,'anomalies':anomalies,
            'markers':markers,'groups':{}}
    for name,pairs in groups.items():
        bucket={'calls':len(pairs)}
        for field,scale in [('dvb',1),('dguest_ns',1e-6),('dwall_ns',1e-6)]:
            vals=[int(end[field])*scale for _,end in pairs]
            outfield={'dvb':'vblanks','dguest_ns':'guest_ms','dwall_ns':'host_ms'}[field]
            bucket[outfield]={'sum':sum(vals),'min':min(vals),'median':statistics.median(vals),
                              'p95':percentile(vals,.95),'max':max(vals)}
        if name.startswith('06020094:'):
            bucket['requested_bytes_nonzero']=sum(int(start['bytes_req']) for start,_ in pairs)
            bucket['whole_file_requests']=sum(start.get('whole_file')=='1' for start,_ in pairs)
            bucket['request_examples']=[{k:start[k] for k in ['name','sector','bytes_req','dest','vb','pr']} for start,_ in pairs[:6]]
        if name=='0602F590':bucket['uploaded_bytes']=sum(int(end.get('upload_bytes',0)) for _,end in pairs)
        result['groups'][name]=bucket
    result['incomplete']=bool(limited or opened or unwinds or anomalies)
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('log',type=Path);a=ap.parse_args()
    print(json.dumps(summarize(a.log),indent=2))
