#!/usr/bin/env python3
"""Structural verification only; not a hardware/runtime test."""
import hashlib,json,pathlib,struct,sys
p=pathlib.Path(sys.argv[1]);b=p.read_bytes()
assert b[16:20]==b'NRO0','Not NRO0'
version,size,flags=struct.unpack_from('<III',b,20)
assert size<=len(b) and size>=128
segments={}
last=0
for n,o in [('text',32),('rodata',40),('data',48)]:
 offset,length=struct.unpack_from('<II',b,o)
 assert offset>=last and offset+length<=size,(n,offset,length,size)
 assert offset%4096==0 and length%4096==0
 segments[n]={'offset':offset,'length':length};last=offset+length
assert b[size:size+4]==b'ASET','Missing NACP/icon asset header'
asset_version=struct.unpack_from('<I',b,size+4)[0]
assets={}
for n,o in [('icon',8),('nacp',24),('romfs',40)]:
 offset,length=struct.unpack_from('<QQ',b,size+o)
 if length:assert size+offset+length<=len(b)
 assets[n]={'offset':offset,'length':length}
assert assets['nacp']['length']==0x4000
assert assets['romfs']['length']==0,'Game resource ROMFS must not be embedded'
print(json.dumps({'file':p.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'nro_version':version,'segments':segments,'assets':assets,'validation':'structural only; no Switch hardware test'},indent=2))
