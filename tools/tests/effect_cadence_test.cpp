#include "pal_effect_cadence_runtime.h"
#include <cassert>
#include <stdexcept>
uint8_t g_wram_h[1<<20]{},g_wram_l[1<<20]{},g_vdp2_regs[0x200]{};
bool runtime_supported=true;unsigned support_checks=0;
bool pal_effect_cadence_scope_supported() noexcept {++support_checks;return runtime_supported;}
uint64_t clock_vb=100;
uint64_t sat_vblanks(){return clock_vb;}
using namespace pal_effect_cadence;
void set8(uint32_t a,uint8_t v){g_wram_h[a&0xFFFFF]=v;}
void set16(uint32_t a,uint16_t v){set8(a,v>>8);set8(a+1,v);}
void set32(uint32_t a,uint32_t v){set16(a,v>>16);set16(a+2,v);}
int main(){
 assert(parse_speed(nullptr)==Speed::original && parse_speed("1")==Speed::original);
 for(const char* s:{"", "3", "0", "1.50", "1.25x", "-1", "nan", " 1.5"})assert(parse_speed(s)==Speed::original);
 assert(parse_speed("2")==Speed::twice);
 assert(parse_speed("1.25")==Speed::five_fourths && parse_speed("1.5")==Speed::three_halves);
 for(auto s:{Speed::original,Speed::five_fourths,Speed::three_halves,Speed::twice})for(unsigned n:{7,14,20,26}){
  unsigned total=0;
  for(unsigned f=0;f<n;++f){unsigned d=frame_fields(s,f);assert(d>=2&&d<=4);assert(sync_fields(d,0)>=1&&sync_fields(d,1)>=1);assert(sync_fields(d,0)+sync_fields(d,1)==d);total+=d;}
  assert(total==cumulative(s,n));
 }
 assert(cumulative(Speed::twice,14)==28 && cumulative(Speed::twice,20)==40 && cumulative(Speed::twice,26)==52);
 assert(cumulative(Speed::five_fourths,20)==64 && cumulative(Speed::three_halves,20)==54);
 assert(cumulative(Speed::five_fourths,26)==84 && cumulative(Speed::three_halves,26)==70);
 assert(cumulative(Speed::five_fourths,14)==45 && cumulative(Speed::three_halves,14)==38);
 assert(matches(0,0x060FFC00,0xFFFF,33,20,0,0,2,7));
 assert(matches(0,0x060FFC00,0xFFFF,1,7,0,0,2,7));
 assert(cumulative(Speed::five_fourths,7)==23 && cumulative(Speed::three_halves,7)==19 && cumulative(Speed::twice,7)==14);
 assert(!matches(1,0x060FFC00,0xFFFF,33,20,0,0,2,7));
 assert(!matches(0,0x060FFC00,0,33,20,0,0,2,7));
 assert(!matches(0,0x060FFC00,0xFFFF,33,20,1,0,2,7));
 assert(!matches(0,0x060FFC00,0xFFFF,33,20,0,0,1,7));
 assert(!matches(0,0x060FFC00,0xFFFF,33,20,0,0,2,4));
 assert(!matches(0,0x060FFC00,0xFFFF,34,20,0,0,2,7));
 SH2Context c{};c.cpu=0;c.gbr=0x060FFC00;c.r[14]=0x060FF000;set16(0x060768EC,0xFFFF);set8(c.gbr+18,2);set8(c.gbr+19,1);set8(0x060FFCEC,7);g_vdp2_regs[0x2C]=7;set16(0x060769DA,20);
 if(speed()==Speed::original){Cast a(c);assert(!cast);Frame f(c);assert(!frame);Wait w(c);assert(!wait);Sync s(c);assert(!sync);assert(support_checks==0);return 0;}
 runtime_supported=false;{Cast a(c);assert(!cast);}runtime_supported=true;
 {
  Cast a(c);assert(cast==&a);c.pr=0x0603BEE0;c.r[4]=33;{Prepare p(c);}assert(a.armed);
  c.pr=0x0603C26A;set16(0x060769C8,0);
  {Frame f(c);assert(frame==&f);f.fields=3;c.r[4]=2;c.r[5]=0;
   {Wait w(c);assert(wait==&w);c.pr=0x06022354;set32(c.r[14]+4,0x0603E8E8);
    {Sync s(c);assert(!sync);assert(w.calls==1);}
    {Cast nested(c);Sync s(c);assert(!sync);}
    {Sync s(c);assert(sync==&s);assert(w.calls==2);c.r[0]=0;c.t=true;shorten_sync(c);assert(c.t);++clock_vb;shorten_sync(c);assert(!c.t&&s.cut);set8(c.gbr+19,0);c.r[0]=2;finish_sync(c);assert(c.r[0]==1);}
    assert(!sync);
   }assert(!wait);
  }assert(a.next==1&&!frame);
  {Cast nested(c);assert(cast==&nested&&!nested.armed);}assert(cast==&a);
  try{Cast nested(c);throw std::runtime_error("unwind");}catch(...){}assert(cast==&a);
  c.pr=0x0603C26A;set16(0x060769C8,2);{Frame f(c);assert(!frame);}assert(!a.armed);
 }assert(!cast);
}
