"""Host field intent must survive a delayed guest key-release acknowledgement."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = r'''
#include <map>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include "pal_responsive_input.h"
std::map<uint32_t,uint8_t> mem;uint16_t bits=0,edges=0;uint64_t vb=0;
uint8_t ld8(uint32_t a){return mem[a];} uint16_t ld16(uint32_t a){return (ld8(a)<<8)|ld8(a+1);} void st8(uint32_t a,uint32_t v){mem[a]=v;}void st16(uint32_t a,uint32_t v){st8(a,v>>8);st8(a+1,v);}
uint16_t pal_input_peek(){return bits;}uint16_t pal_input_edges(){auto e=edges;edges=0;return e;}uint64_t sat_vblanks(){return vb;}void sat_note(const char*,...){}
void reset(SH2Context& c){
 mem.clear();bits=edges=0;vb=0;c={};c.r[14]=0x06000010;
 st16(0x060768EE,62);pal_input_scene=62;pal_input_clear();pal_field_wait=true;
}
void tick(uint16_t b,uint64_t t){edges=b&~bits;bits=b;vb=t;pal_field_wait=true;pal_input_tick();}
void apply(SH2Context& c){st16(c.r[14],0);pal_input_apply(c);}
bool moved(){return ld16(0x060768E8)||ld16(0x060768EA);}
int main(int argc,char**){
 if(argc>1){setenv("PAL_RESPONSIVE_INPUT","0",1);SH2Context c;c.r[14]=0x06000010;bits=edges=0x2000;pal_input_tick();pal_input_apply(c);assert(mem.empty()&&edges==0x2000);puts("original disabled no-op passed");return 0;}
 setenv("PAL_RESPONSIVE_INPUT","1",1);SH2Context c;
 unsigned count=0;
 for(uint16_t dir:{uint16_t(0x1000),uint16_t(0x2000),uint16_t(0x4000),uint16_t(0x8000)})
 for(unsigned duration:{1u,2u,3u,6u,12u})for(unsigned phase=0;phase<6;++phase)for(unsigned delay=1;delay<=6;++delay){
  reset(c);st8(0x06076A09,0xFF);uint64_t start=100+phase;
  for(unsigned t=0;t<delay;++t){tick(t<duration?dir:0,start+t);apply(c);assert(!moved());assert(ld8(0x06076A09)==0xFF);}
  st8(0x06076A09,0);tick(delay<duration?dir:0,start+delay);apply(c);
  if(!moved()){puts("RED fresh field edge lost across guest release inhibit");return 1;}
  tick(0,start+delay+1);apply(c);assert(!moved());++count;
 }
 // Genuine hard boundary clears held/pending even if FF is simultaneously set.
 for(unsigned boundary=0;boundary<5;++boundary){reset(c);tick(0x2000,100);st8(0x06076A09,0xFF);
  if(boundary==0)pal_input_clear();
  if(boundary==1){st16(c.r[14],7);pal_input_apply(c);}
  if(boundary==2){st16(0x060768DC,1);apply(c);st16(0x060768DC,0);}
  if(boundary==3){st16(0x060768EE,63);tick(0x2000,101);}
  if(boundary==4){pal_input_script_before();++vb;pal_input_script_after();}
  st8(0x06076A09,0);tick(0x2000,102);apply(c);assert(!moved());
  tick(0,103);tick(0x1000,104);apply(c);assert(moved());
 }
 // Capture is allowed while FF, but optional wake must not bypass guest readiness.
 reset(c);setenv("PAL_RESPONSIVE_WAKE","1",1);pal_in_sync_wait=true;
 st8(0x060FFC12,6);st8(0x060FFC13,6);st8(0x060FFCA8,1);st8(0x060FFCBC,4);st8(0x06076A09,0xFF);
 tick(0x1000,100);assert(ld8(0x060FFC13)==6);apply(c);assert(!moved());
 st8(0x06076A09,0);pal_in_sync_wait=true;tick(0x1000,101);assert(ld8(0x060FFC13)==1);
 printf("GREEN %u direction/duration/phase/gate cases; 5 true boundaries; wake readiness\n",count);
}
'''
STUB = r'''
#pragma once
#include <cstdint>
struct SH2Context {uint32_t r[16]{};uint32_t gbr=0;};
uint8_t ld8(uint32_t);uint16_t ld16(uint32_t);void st8(uint32_t,uint32_t);void st16(uint32_t,uint32_t);
'''

class GuestReleaseGateTests(unittest.TestCase):
    def test_capture_pause_and_true_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "saturn").mkdir()
            (work / "saturn/sh2.h").write_text(STUB)
            source = work / "release_gate.cpp"
            source.write_text(PROGRAM)
            exe = work / "release_gate"
            command = ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                       "-I" + str(work), "-I" + str(ROOT / "src/pal_game")]
            if os.name == "nt":
                # The probe sets its switches with POSIX setenv, which MinGW has not: the same
                # shim tools/check_windows.sh force-includes for the runtime tests.
                command += ["-include", str(ROOT / "tools/wincompat.h")]
            subprocess.run(command + [str(source), "-o", str(exe)], check=True, capture_output=True)
            if not exe.is_file():
                exe = exe.with_suffix(".exe")   # MinGW appends it to an extension-less -o
            for args in ([], ["original"]):
                subprocess.run([str(exe), *args], check=True, capture_output=True)
