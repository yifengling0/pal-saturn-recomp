"""Optional full generated-code red/green test; game code stays private.

PAL_RENDER_GENERATED points to unmodified pinned generated sources. No game is
launched. The five real callers and three real callees are compiled against a
small deterministic memory fixture; generated code is never committed.
"""
from pathlib import Path
import os
import subprocess
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pal_render_returns as fix


def texts():
    root = os.environ.get('PAL_RENDER_GENERATED')
    if not root:
        pytest.skip('Set PAL_RENDER_GENERATED to private original generation')
    return {p: p.read_text() for p in Path(root).glob('p_*.cpp')}


def test_exact_planner_boundaries():
    original = texts()
    patched = fix.plan(original)
    assert sum(a != patched[p] for p, a in original.items()) == 3
    for p in original:
        a, b = original[p].splitlines(), patched[p].splitlines()
        assert len(a) == len(b)
        for old, new in zip(a, b):
            if old != new:
                assert old.split('  // ')[1] == new.split('  // ')[1]
                assert 'SH2_RET(c,' in new and 'SH2_POLL(c)' in new
    with pytest.raises(ValueError, match='identity changed'):
        fix.plan(patched)
    for address in fix.PINS:
        corrupted = dict(original)
        p = next(p for p, s in original.items() if 'void f_'+address+'(' in s)
        m = fix.body(corrupted[p], address)
        corrupted[p] = corrupted[p][:m.start()] + m.group().replace('ran[', 'changed_ran[', 1) + corrupted[p][m.end():]
        with pytest.raises(ValueError, match='identity changed'):
            fix.plan(corrupted)


PREFIX = r'''
#include <cstdint>
#include <map>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <stdexcept>
struct SH2Context { uint32_t r[16]{}, pr{}, pc{}, gbr{}, mach{}, macl{}; bool t{}; };
std::map<uint32_t,uint8_t> memory;
uint32_t ld8(uint32_t a) { return memory[a]; }
uint32_t ld16(uint32_t a) { return ld8(a)*256+ld8(a+1); }
uint32_t ld32(uint32_t a) { return ld16(a)*65536+ld16(a+2); }
void st8(uint32_t a,uint32_t v) { memory[a]=v; }
void st16(uint32_t a,uint32_t v) { st8(a,v>>8);st8(a+1,v); }
void st32(uint32_t a,uint32_t v) { st16(a,v>>16);st16(a+2,v); }
void pal_literal_probe(SH2Context&,const char*,uint32_t,uint32_t,int,uint32_t) {}
void sh2_call(SH2Context&,uint32_t) { throw std::runtime_error("unknown indirect call"); }
#define SH2_POLL(c) ((void)0)
#define SH2_RET(c,x) do { if(c.pc != (x)) throw std::runtime_error("strict return"); } while(0)
'''
MAIN = r'''
using Fn=void(*)(SH2Context&);
SH2Context setup(int kind, int reject, uint32_t pr) {
 memory.clear(); SH2Context c; c.pr=pr;c.gbr=0x10000;c.r[15]=0x20000;c.r[4]=0x30000;
 st16(c.gbr+136,10);st16(c.gbr+116,reject==1?10:0);
 st32(c.gbr+104,4);st8(c.gbr+172,1);st16(c.gbr+112,10);
 st32(c.r[4]+8,reject==2?2:reject==3?0x100004:8);
 st32(0x06065EE0,0x06065F2A);st32(0x0603902C,0x06039076);
 // Null primitive bypasses rendering after a successful helper return.
 st32(c.r[4]+12,0);c.r[0]=kind==0?0:reject?1:0;
 st16(c.gbr+160,0);st32(c.gbr+52,0x40000);st32(c.gbr+56,0x50000);st32(c.gbr+60,0x60000);
 return c;
}
int main() {
 const Fn oldf[]={oldcode::f_0605E398,oldcode::f_06065E26,oldcode::f_06065E8C,oldcode::f_06038F72,oldcode::f_06038FD8};
 const Fn newf[]={newcode::f_0605E398,newcode::f_06065E26,newcode::f_06065E8C,newcode::f_06038F72,newcode::f_06038FD8};
 const uint32_t local[]={0x0605E3A0,0x06065E2C,0x06065E92,0x06038F78,0x06038FDE};
 for(int kind=0;kind<5;++kind) {
   auto a=setup(kind,0,0x060343B8);oldf[kind](a);auto mem=memory;
   auto b=setup(kind,0,0x060343B8);newf[kind](b);
   assert(!std::memcmp(a.r,b.r,sizeof(a.r)) && a.pc==b.pc && a.pr==b.pr && a.gbr==b.gbr && a.mach==b.mach && a.macl==b.macl && a.t==b.t && mem==memory);
   assert(b.pc==0x060343B8 && b.r[15]==0x20000);
   for(int reject=1;reject<=(kind==0?3:1);++reject) {
     auto red=setup(kind,reject,0x060343B8);bool failed=false;
     try {oldf[kind](red);} catch(const std::runtime_error&) {failed=true;} assert(failed);
     for(uint32_t caller:{0x060343B8u,local[kind]}) {
       auto green=setup(kind,reject,caller);newf[kind](green);
       assert(green.pc==caller && green.pr==caller && green.r[15]==0x20000);
       if(kind==0) {assert(green.r[0]==0);assert(ld16(green.gbr+170)==1);}
       else assert(green.r[4]==0x30000+((kind==1||kind==3)?20:28));
     }
   }
 }
 std::puts("PASS: 5 real caller normal paths bit-identical; 7 reject paths RED/GREEN; caller/local-PC collision safe");
}
'''


def test_real_generated_red_green(tmp_path):
    original = texts()
    patched = fix.plan(original)
    cpp = PREFIX
    for namespace, version in [('oldcode', original), ('newcode', patched)]:
        cpp += '\nnamespace '+namespace+' {\nint ran[2000];\n'
        cpp += ''.join('void f_'+a+'(SH2Context& c);\n' for a in fix.PINS)
        cpp += '\n'.join(next(fix.body(s,a).group() for s in version.values() if 'void f_'+a+'(' in s) for a in fix.PINS)
        cpp += '\n}\n'
    cpp += MAIN
    source=tmp_path/'private-generated-test.cpp';source.write_text(cpp)
    binary=tmp_path/'test'
    result=subprocess.run(['g++','-std=c++20','-O1',str(source),'-o',str(binary)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    print(result.stdout)


def test_cmake_rejects_stale_or_altered_generation(tmp_path):
    import shutil
    cmake=shutil.which('cmake')
    if not cmake:
        pytest.skip('CMake unavailable')
    original=texts();patched=fix.plan(original)
    root=Path(__file__).resolve().parents[2]
    selected={p:s for p,s in original.items() if any('void f_'+a+'(' in s for a in fix.PINS)}
    for mode,version in [('stale',original),('fixed',patched),('altered',patched),('duplicate',patched)]:
        source=tmp_path/mode;source.mkdir()
        names=[]
        for p in selected:
            text=version[p]
            if mode=='altered' and 'void f_06060870(' in text:
                text=text.replace('c.r[0] = 0x1u;  // 06060870', 'c.r[0] = 0x2u;  // 06060870')
            if mode=='duplicate' and 'void f_06060870(' in text:
                text+='\n'+fix.body(text,'06060870').group()+'\n'
            (source/p.name).write_text(text);names.append(p.name)
        (source/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(render_return_gate CXX)\nadd_library(recomp STATIC '+ ' '.join(names)+')\ninclude("'+(root/'src/pal_game/pal_render_returns.cmake').as_posix()+'")\n')
        result=subprocess.run([cmake,'-S',str(source),'-B',str(source/'out'),'-G','Ninja'],capture_output=True,text=True)
        if mode=='fixed':
            assert result.returncode==0,result.stdout+result.stderr
        else:
            assert result.returncode!=0 and 'PAL render return' in result.stderr,result.stdout+result.stderr


def test_prepare_rejects_unverified_modules_before_writes(tmp_path):
    from types import SimpleNamespace
    with pytest.raises(ValueError, match='PROG module/base'):
        fix.prepare(tmp_path, [])
    fake=tmp_path/'not-a-rom';fake.write_bytes(b'hand-authored invalid module')
    modules=[SimpleNamespace(name=name,base=0x06020000,file=fake) for name in ('PROG','TRUE')]
    with pytest.raises(ValueError, match='PROG.BIN identity changed'):
        fix.prepare(tmp_path,modules)
    assert sorted(p.name for p in tmp_path.iterdir())==['not-a-rom']
