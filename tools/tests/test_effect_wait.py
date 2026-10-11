from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
def test_effect_wait_exact_scope():
    code = r'''
#include "pal_effect_wait.h"
#include <cassert>
int main() {
  assert(pal_effect_scope_matches(true,0,0x06031172,1,7,200,2,0xFFFF));
  assert(!pal_effect_scope_matches(false,0,0x06031172,1,7,200,2,0xFFFF));
  assert(!pal_effect_scope_matches(true,1,0x06031172,1,7,200,2,0xFFFF));
  assert(!pal_effect_scope_matches(true,0,0x06031164,1,4,200,2,0xFFFF));
  assert(!pal_effect_scope_matches(true,0,0x06031172,0,7,200,2,0xFFFF));
  assert(!pal_effect_scope_matches(true,0,0x06031172,1,7,8,2,0xFFFF));
  assert(!pal_effect_scope_matches(true,0,0x06031172,1,7,200,3,0xFFFF));
  assert(!pal_effect_scope_matches(true,0,0x06031172,1,7,200,2,0));
  for(unsigned loops : {0u,1u,2u,3u,49u,50u,51u})
    for(unsigned vb : {0u,1u,2u,3u,100u})
      for(unsigned actual : {3u,7u,0x17u}) {
        bool expected=loops>=2 && loops<50 && vb>=2 && actual==7;
        assert(pal_effect_wait_complete(true,50,loops,vb,actual,7)==expected);
        assert(!pal_effect_wait_complete(false,50,loops,vb,actual,7));
        assert(!pal_effect_wait_complete(true,49,loops,vb,actual,7));
      }
  assert(!pal_effect_wait_complete(true,50,2,2,4,4));
  assert(pal_effect_wait_complete(true,50,2,2,0x37,0x37));
  assert(!pal_effect_wait_complete(true,50,2,2,7,0x37));
}

'''
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/'test.cpp';exe=Path(d)/'test'
        src.write_text('#include <initializer_list>\n'+code)
        subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src/pal_game'),str(src),'-o',str(exe)],check=True,capture_output=True)
        subprocess.run([str(exe)],check=True,capture_output=True)

def test_runtime_scope_isolated_and_commit_gated():
    code=r'''
#include "pal_effect_wait_runtime.h"
#include <cassert>
#include <stdexcept>
#include <cstring>
uint8_t g_wram_h[0x100000]{};
uint8_t g_vdp2_regs[0x200]{};
uint64_t clock_vb=100;
uint64_t sat_vblanks(){return clock_vb;}
void w32(uint32_t a,uint32_t v){for(int i=0;i<4;++i)g_wram_h[(a+i)&0xFFFFF]=v>>(24-i*8);}
int main(int argc,char**) {
  SH2Context c{};c.cpu=0;c.gbr=0x060FFC00;c.r[14]=0x06001000;
  c.r[8]=1;c.r[9]=7;c.r[4]=200;w32(c.r[14]+4,0x06031172);
  g_wram_h[0xFFC12]=2;g_wram_h[0x768EC]=255;g_wram_h[0x768ED]=255;
  g_wram_h[0xFFCEC]=7;
  if(argc==2){pal_effect_wait::Scope s(c);assert(pal_effect_wait::current==nullptr);return 0;}
  SH2Context before=c;
  {
    pal_effect_wait::Scope s(c);assert(pal_effect_wait::current==&s);
    assert(std::memcmp(&before,&c,sizeof(c))==0);
    SH2Context other=c;other.r[9]=4;
    {pal_effect_wait::Scope nested(other);assert(pal_effect_wait::current==nullptr);}
    assert(pal_effect_wait::current==&s);
    c.r[14]=0x06000F00;w32(c.r[14]+8,0x060224E4);c.r[1]=2;c.r[2]=50;
    clock_vb=101;g_vdp2_regs[0x2C]=7;assert(!pal_effect_wait::ready(c));
    clock_vb=102;g_vdp2_regs[0x2C]=3;assert(!pal_effect_wait::ready(c));
    g_vdp2_regs[0x2C]=7;w32(c.r[14]+8,0);assert(!pal_effect_wait::ready(c));
    w32(c.r[14]+8,0x060224E4);c.r[1]=1;assert(!pal_effect_wait::ready(c));
    c.r[1]=2;before=c;assert(pal_effect_wait::ready(c));
    assert(std::memcmp(&before,&c,sizeof(c))==0);
    assert(!pal_effect_wait::ready(c));
  }
  assert(pal_effect_wait::current==nullptr);
  c.r[14]=0x06001000;c.r[8]=1;c.r[9]=7;c.r[4]=200;
  try {pal_effect_wait::Scope s(c);assert(pal_effect_wait::current==&s);throw std::runtime_error("fixture");}
  catch(const std::runtime_error&){}
  assert(pal_effect_wait::current==nullptr);
  assert(pal_effect_wait::raw8(0x05F8002C)==0);
}
'''
    import os
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/'scope.cpp';exe=Path(d)/'scope';src.write_text(code)
        subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',
                        '-I'+str(ROOT/'src/pal_game'),
                        '-I'+str(ROOT/'third_party/saturn-recomp-pal/runtime/include'),
                        str(src),'-o',str(exe)],check=True,capture_output=True)
        subprocess.run([str(exe),'disabled'],env=dict(os.environ,PAL_SHORT_EFFECT_PREP='0'),check=True,capture_output=True)
        subprocess.run([str(exe)],env=dict(os.environ,PAL_SHORT_EFFECT_PREP='1'),check=True,capture_output=True)
