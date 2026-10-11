"""Decode exact pinned-runtime dump layout. Never substitutes for real rendering."""
import argparse
import hashlib
import json
from pathlib import Path

SIZE = 0x141220
SECTIONS = {'vdp1_vram': (0,0x80000), 'vdp1_draw_fb':(0x80000,0x40000),
            'vdp1_regs':(0xC0000,0x20), 'vdp2_vram':(0xC0020,0x80000),
            'vdp2_cram':(0x140020,0x1000), 'vdp2_regs':(0x141020,0x200)}
REGS = {'TVMD':0x00,'RAMCTL':0x0E,'BGON':0x20,'CHCTLA':0x28,'CHCTLB':0x2A,'PNCN0':0x30,
        'PLSZ':0x3A,'MPOFN':0x3C,'SCRCTL':0x9A,'RPMD':0xB0,'RPTAU':0xBC,'RPTAL':0xBE,
        'WCTLA':0xD0,'WCTLB':0xD2,'WCTLC':0xD4,'WCTLD':0xD6,'SPCTL':0xE0,'LNCLEN':0xE8,'CCCTL':0xEC,'PRISA':0xF0,'PRISB':0xF2,'PRISC':0xF4,'PRISD':0xF6,'PRINA':0xF8,'PRINB':0xFA,'PRIR':0xFC}

def inspect(data):
    if len(data) != SIZE: raise ValueError(f'Expected {SIZE} bytes, got {len(data)}')
    regs = {k:int.from_bytes(data[0x141020+o:0x141022+o],'big') for k,o in REGS.items()}
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'registers':{k:f'0x{v:04X}' for k,v in regs.items()},
            'rotation_enable_mask':f'0x{regs["BGON"]&0x30:02X}',
            'display_enabled':bool(regs['TVMD']&0x8000),
            'sections':{k:{'offset':o,'bytes':n,'nonzero_bytes':sum(v!=0 for v in data[o:o+n])} for k,(o,n) in SECTIONS.items()},
            'warning':'VDP1 framebuffer in dump is draw buffer, not necessarily displayed buffer; this report is not a renderer'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dump',type=Path);a=p.parse_args()
    print(json.dumps(inspect(a.dump.read_bytes()),indent=2))
if __name__=='__main__':main()
