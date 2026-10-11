"""Optional observation-only instrumentation of generated folded literal loads."""
from pathlib import Path

def install():
    from saturnrecomp.recomp import emit, __main__ as generator
    original_generate=generator.Module.generate
    def traced_generate(module,*args,**kwargs):
        original_mov=emit._mov
        def traced_mov(ins,form,size,literal):
            original=original_mov(ins,form,size,literal)
            if form=='@T,Rn' and literal is not None:
                return (f'pal_literal_probe(c, "{module.name}", 0x{ins.pc:08X}u, '
                        f'0x{ins.target:08X}u, {size}, 0x{literal&0xffffffff:08X}u); '+original)
            return original
        emit._mov=traced_mov
        try:return original_generate(module,*args,**kwargs)
        finally:emit._mov=original_mov
    generator.Module.generate=traced_generate

def add_headers(out,root):
    for p in Path(out).glob('p_*_funcs.h'):
        text=p.read_text().replace('#include "saturn/sh2.h"',
            '#include "saturn/sh2.h"\n#include "'+str(Path(root)/'src/pal_game/pal_literal_probe.h')+'"')
        p.write_text(text)
