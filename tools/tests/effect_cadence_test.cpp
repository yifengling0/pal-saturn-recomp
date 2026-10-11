#include "pal_effect_cadence_runtime.h"
#include <cassert>
#include <stdexcept>
#include <vector>
uint8_t g_wram_h[1<<20]{},g_wram_l[1<<20]{},g_vdp2_regs[0x200]{};
uint32_t g_sh2_watch_lo=0,g_sh2_watch_len=0;
void sh2_watch_store(uint32_t,uint32_t,int){}
bool runtime_supported=true;unsigned support_checks=0,io_reads=0,io_writes=0;
uint16_t tvstat=0,fbcr=3;uint64_t clock_vb=100;
bool pal_effect_cadence_scope_supported() noexcept {++support_checks;return runtime_supported;}
uint64_t sat_vblanks(){return clock_vb;}
uint32_t sh2_io_read(uint32_t a,int size){++io_reads;assert(size==2);if(a==0x25F80004u)return tvstat;assert(a==0x25D00002u);return fbcr;}
void sh2_io_write(uint32_t a,uint32_t v,int size){assert(a==0x25D00002u&&size==2&&v==2);++io_writes;fbcr=uint16_t(v);}
using namespace pal_effect_cadence;
void set8(uint32_t a,uint8_t v){g_wram_h[a&0xFFFFF]=v;}
void set16(uint32_t a,uint16_t v){set8(a,v>>8);set8(a+1,v);}
void set32(uint32_t a,uint32_t v){set16(a,v>>16);set16(a+2,v);}
void setup(SH2Context& c){
 std::memset(g_wram_h,0,sizeof g_wram_h);std::memset(g_wram_l,0,sizeof g_wram_l);
 c={};c.cpu=0;c.gbr=0x060FFC00;c.r[14]=0x060FF000;
 set16(0x060768EC,0xFFFF);set8(c.gbr+18,2);set8(c.gbr+19,1);
 set8(c.gbr+168,1);set8(c.gbr+188,4);set8(0x060FFCEC,7);g_vdp2_regs[0x2C]=7;
 set16(0x060769DA,20);tvstat=0;fbcr=3;clock_vb=100;io_reads=io_writes=0;
}
template<class F> void in_sync(F f){
 SH2Context c{};setup(c);Cast a(c);assert(cast==&a);
 c.pr=0x0603BEE0;c.r[4]=33;{Prepare p(c);}assert(a.armed);
 c.pr=0x0603C26A;{Frame fr(c);assert(frame==&fr);fr.fields=2;
  c.r[4]=2;c.r[5]=0;Wait w(c);c.pr=0x06022354;set32(c.r[14]+4,0x0603E8E8);
  Sync sy(c);assert(sync==&sy);f(c,sy);++clock_vb;
 }
}
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

 assert(parse_speed(nullptr)==Speed::original&&parse_speed("invalid")==Speed::original);
 for(auto v:{Speed::original,Speed::five_fourths,Speed::three_halves,Speed::twice})for(unsigned n:{7,14,20,26}){
  unsigned total=0;for(unsigned i=0;i<n;++i){auto f=frame_fields(v,i);assert(f>=2&&f<=4);assert(sync_fields(f,0)>=1&&sync_fields(f,1)>=1);total+=f;}assert(total==cumulative(v,n));
 }
 if(speed()==Speed::original){
  SH2Context c{};auto before=std::vector<uint8_t>(g_wram_h,g_wram_h+sizeof g_wram_h);
  {Cast a(c);Prepare p(c);Frame f(c);Wait w(c);Sync s(c);prepare_sync(c);}
  assert(io_reads==0&&io_writes==0&&support_checks==0);assert(std::equal(before.begin(),before.end(),g_wram_h));return 0;
 }
 {SH2Context c{};setup(c);runtime_supported=false;Cast a(c);assert(!cast);prepare_sync(c);assert(io_reads==0&&io_writes==0);runtime_supported=true;}
 // Each rejected condition performs no guest store or hardware transaction.
 for(int which=0;which<12;++which)in_sync([&](SH2Context& c,Sync& s){
  if(which==0)set8(c.gbr+176,0x10);
  if(which==1)set8(c.gbr+176,0x80);
  if(which==2)set8(c.gbr+27,2);
  if(which==3)set8(c.gbr+168,0);
  if(which==4)set8(c.gbr+188,0);
  if(which==5)tvstat=8;
  if(which==6)fbcr=0;
  if(which==7)fbcr=1;
  if(which==8)++clock_vb;
  if(which==9)set8(c.gbr+19,0);
  if(which==10)set8(c.gbr+18,1);
  if(which==11)c.gbr=0x060F0000;
  auto before=std::vector<uint8_t>(g_wram_h,g_wram_h+sizeof g_wram_h);auto old_fbcr=fbcr;
  prepare_sync(c);assert(!s.switched&&io_writes==0&&fbcr==old_fbcr);assert(std::equal(before.begin(),before.end(),g_wram_h));
 });
 in_sync([](SH2Context& c,Sync& s){Cast nested(c);prepare_sync(c);assert(!s.switched&&io_writes==0);});
 in_sync([](SH2Context& c,Sync& s){
  prepare_sync(c);assert(s.switched&&io_writes==1&&fbcr==2&&raw8(c.gbr+19)==0&&raw8(c.gbr+18)==2);
  prepare_sync(c);assert(io_writes==1); // Never enqueue erase twice.
  ++clock_vb;set8(c.gbr+19,0xFF);c.r[0]=uint32_t(int32_t(int8_t(raw8(c.gbr+19))))+raw8(c.gbr+18);st8(c.gbr+19,c.r[0]);assert(raw8(c.gbr+19)==1);
 });
 try{in_sync([](SH2Context&,Sync&){throw std::runtime_error("before commit");});assert(false);}catch(const std::runtime_error&){}
 assert(io_writes==0&&!cast&&!frame&&!wait&&!sync);
 // After the hardware request there is deliberately no pretend rollback.
 // RunStop/ProgramStart can occur only at a later SH2 safe point, not between
 // the FBCR and countdown stores. Unsupported resumable fiber/state modes fail
 // closed above. Unwinding must only release scopes, even with IRQ-altered GBR.
 try{in_sync([](SH2Context& c,Sync&){prepare_sync(c);c.gbr=0x060F0000;throw std::runtime_error("after commit");});assert(false);}catch(const std::runtime_error&){}
 assert(io_writes==1&&g_wram_h[0xFFC12]==2&&g_wram_h[0xFFC13]==0&&!cast&&!frame&&!wait&&!sync);
}
