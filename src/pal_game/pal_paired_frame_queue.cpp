// Default-off bounded PAL host RGB queue. No guest writes, polls, or event scheduling.
#include "pal_paired_frame_queue.h"
#include "saturn.h"
#include "video.h"
#include "pal_responsive_input.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>
#include <deque>

bool pal_pfq_enabled=[] {const char* x=std::getenv("PAL_PAIRED_FRAME_QUEUE");return x&&!std::strcmp(x,"1")&&pal_responsive_enabled();}();
int pal_pfq_host_bank=-1;
uint16_t pal_pfq_host_tvmr;
namespace {
uint64_t token,epoch=1,last_shown,pending_serial;
int pending_bank=-1;
bool field,master_sealed,eligible_dma;
uint64_t last_token;
struct Ready { Frame rgb;uint64_t serial,token,epoch,completed_vb,completed_ns; };
std::deque<std::shared_ptr<Ready>> ready;
std::shared_ptr<Ready> presented,retiring;
uint16_t scene;
uint8_t* ptr(uint32_t a,size_t n) {
 a&=0x07ffffff;
 if(a>=0x06000000&&a+n<=0x06100000)return g_wram_h+(a-0x06000000);
 if(a>=0x00200000&&a+n<=0x00300000)return g_wram_l+(a-0x00200000);
 if(a>=0x05c00000&&a+n<=0x05c80000)return g_vdp1_vram+(a-0x05c00000);
 return nullptr;
}
uint32_t rd(uint32_t a,int n) {auto p=ptr(a,n);uint32_t v=0;if(!p)return 0;while(n--)v=v<<8|*p++;return v;}
bool active() {return pal_field_wait && rd(0x060768DC,2)==0 && rd(0x06076A09,1)!=255 && rd(0x060768EE,2)==scene;}
bool raster(size_t i) {return i==4||i==5||i==8||i==9||i==10||i==11;}
// All observation calls compile away, including their arguments.
#define emit(...) ((void)0)
struct Vdp2 {
 std::array<uint8_t,0x200> regs;
 std::array<uint8_t,0x80000> vram;
 std::array<uint8_t,0x1000> cram;
 uint64_t token,epoch;
 uint16_t scene;
};
std::shared_ptr<Vdp2> capture() {
 auto s=std::make_shared<Vdp2>();
 std::copy(g_vdp2_regs,g_vdp2_regs+0x200,s->regs.begin());
 // The producer's original 0x120-byte shadow will be DMA'd by the guest at its original time.
 std::copy(g_wram_h+0xffcc0,g_wram_h+0xffde0,s->regs.begin());
 std::copy(g_vdp2_vram,g_vdp2_vram+0x80000,s->vram.begin());
 std::copy(g_vdp2_cram,g_vdp2_cram+0x1000,s->cram.begin());
 s->token=token;s->epoch=epoch;s->scene=scene;return s;
}
int physical_diff(const Vdp2& s) {
 for(int i=0;i<0x200;++i)if(!raster(i)&&s.regs[i]!=g_vdp2_regs[i])return i;
 if(std::memcmp(s.vram.data(),g_vdp2_vram,0x80000))return 0x10000;
 if(std::memcmp(s.cram.data(),g_vdp2_cram,0x1000))return 0x20000;
 return -1;
}
struct Range {uint32_t addr;std::vector<uint8_t> bytes;};
struct Producer {std::shared_ptr<Vdp2> vdp2;uint32_t table;std::vector<Range> ranges;bool valid=false;} producer;
std::shared_ptr<Vdp2> master,submitted;
std::array<uint8_t,0x80000> submit_vram;
struct Bank {std::shared_ptr<Vdp2> vdp2;uint64_t serial=0;uint16_t tvmr=0;bool eligible=false,complete=false;} banks[2];
bool remember_range(uint32_t a,size_t n) {
 auto p=ptr(a,n);if(!p)return false;
 producer.ranges.push_back({a,std::vector<uint8_t>(p,p+n)});return true;
}
bool descriptors_match() {
 if(!producer.valid)return false;
 for(auto& r:producer.ranges){auto p=ptr(r.addr,r.bytes.size());if(!p||std::memcmp(p,r.bytes.data(),r.bytes.size()))return false;}
 return true;
}
}
void pal_pfq_clear(const char* why) {
 ++epoch;field=false;master_sealed=false;master.reset();producer.valid=false;submitted.reset();
 for(auto& b:banks)b.eligible=false;
 // Invalidate ownership immediately, but retire the already emitted RGB until
 // normal DISPLAY has caught up. Clearing eligibility must never display an
 // older draw. The retirement contains no live bank or VDP2 pointer.
 if(presented&&(!retiring||presented->serial>=retiring->serial))retiring=presented;
 ready.clear();presented.reset();pending_bank=-1;
 if(!std::strcmp(why,"state_load")||!std::strcmp(why,"interp_disabled")){
  retiring.reset();last_shown=last_token=0;
 }
 emit("clear",why);
}
void pal_pfq_field_begin(const SH2Context& c) {
 ++token;const auto next_scene=rd(0x060768EE,2);
 if(next_scene!=scene)pal_pfq_clear("scene_changed");
 scene=next_scene;uint32_t a=rd(c.r[14],2);
 field=pal_field_wait&&(a==0||(a>=3&&a<=6))&&rd(0x060768DC,2)==0&&rd(0x06076A09,1)!=255;
 master_sealed=false;master.reset();producer.valid=false;
 if(!field)pal_pfq_clear("field_not_eligible");
 emit("field_begin",field?"eligible":"ineligible",-1,0,token);
}
void pal_pfq_master_seal() {
 master_sealed=false;master.reset();
 if(field&&active()){master=capture();master_sealed=true;emit("master_seal","captured",-1,0,token);}
}
void pal_pfq_slave_done() {
 producer.valid=false;producer.ranges.clear();producer.vdp2.reset();
 if(!field||!master_sealed||!active()||!master||master->epoch!=epoch||master->token!=token)return;
 // No producer-side background/CRAM/shadow mutation may be silently assigned to this token.
 auto s=capture();
 if(s->regs!=master->regs||s->vram!=master->vram||s->cram!=master->cram){emit("producer_reject","vdp2_changed_during_production",-1,0,token);return;}
 producer.table=rd(0x060663D8,4);uint32_t t=producer.table;
 for(unsigned i=0;i<4096;++i,t+=12){
  if(!ptr(t,12))return;
  uint32_t n=rd(t,4),dst=rd(t+4,4),src=rd(t+8,4);if(!n)n=0x1000;
  uint32_t d=dst&0x07ffffff;
  if(n>0x100000||d<0x05c00000||uint64_t(d)+n>0x05c80000||!remember_range(src,n))return;
  if(src>>31){if(!remember_range(producer.table,(i+1)*12))return;producer.vdp2=s;producer.valid=true;emit("producer_done","complete",-1,0,token);return;}
 }
}
void pal_pfq_dma_begin(int lvl,uint32_t,uint32_t w,uint32_t,uint32_t ad,uint32_t md) {
 if(lvl!=1)return;
 eligible_dma=false;submitted.reset();
 if((md>>24&1)&&w==producer.table&&ad==0x101&&descriptors_match()&&active()&&producer.vdp2->epoch==epoch){
  submitted=producer.vdp2;eligible_dma=true;emit("submit_begin","exact_descriptors_payload",-1,0,submitted->token);
 }else emit("submit_reject","unmatched_producer",-1,0,token);
}
void pal_pfq_dma_end(int lvl) {
 if(lvl==1&&eligible_dma&&submitted){std::copy(g_vdp1_vram,g_vdp1_vram+0x80000,submit_vram.begin());emit("submit_done","original_dma",-1,0,submitted->token);}
}
void pal_pfq_draw_begin(int bank,uint64_t serial,const uint16_t* regs) {
 auto& b=banks[bank];b.serial=serial;b.complete=false;b.eligible=false;b.vdp2.reset();b.tvmr=regs[0];
 pending_bank=bank;pending_serial=serial;
 if(!g_cfg.interp&&submitted&&submitted->epoch==epoch&&active()&&!std::memcmp(submit_vram.data(),g_vdp1_vram,0x80000)){
  int d=physical_diff(*submitted);
  if(d<0){b.vdp2=submitted;b.eligible=true;emit("draw_begin","paired",bank,serial,submitted->token);}
  else emit("draw_reject","vdp2_mismatch",bank,serial,submitted->token,d);
 }else emit("draw_reject","ineligible_or_vram_changed",bank,serial,0);
}
void pal_pfq_sprite_end() {
 if(pending_bank>=0&&banks[pending_bank].serial==pending_serial){
  const int bank=pending_bank;auto& b=banks[bank];b.complete=true;
  emit("sprite_end","hardware_event_elapsed",bank,pending_serial,b.vdp2?b.vdp2->token:0);
  if(b.eligible&&b.vdp2&&b.vdp2->epoch==epoch&&active()&&!g_cfg.interp){
   // No deferred bank reference escapes: sample the valid completed VDP1 bank now,
   // through its captured TVMR, against its immutable producer VDP2 version.
   auto q=std::make_shared<Ready>();q->serial=b.serial;q->token=b.vdp2->token;q->epoch=epoch;
   q->completed_vb=sat_vblanks();q->completed_ns=sat_now();
   pal_pfq_host_bank=bank;pal_pfq_host_tvmr=b.tvmr;
   vdp2_compose_snapshot(q->rgb,b.vdp2->regs.data(),b.vdp2->vram.data(),b.vdp2->cram.data());
   pal_pfq_host_bank=-1;
   if((ready.empty()||q->serial>ready.back()->serial)&&q->serial>=last_shown&&q->token>=last_token){
    ready.push_back(q);while(ready.size()>2)ready.pop_front();
    emit("snapshot","complete_rgb_immutable_vdp2",bank,q->serial,q->token,physical_diff(*b.vdp2));
   }else emit("snapshot_reject","nonmonotonic",bank,q->serial,q->token);
  }
 }
 pending_bank=-1;
}
void pal_pfq_bank_invalidate(int bank,const char* why) {banks[bank].eligible=false;banks[bank].complete=false;emit("bank_invalidate",why,bank,banks[bank].serial,banks[bank].vdp2?banks[bank].vdp2->token:0);}
bool pal_pfq_choose(Frame& out,int draw,const uint16_t*,bool) {
 pal_pfq_host_bank=-1;const int display=draw^1;
 const char* boundary=nullptr;
 if(g_cfg.interp)boundary="interp_disabled";
 else if(!field||!active())boundary="outside_field_wait";
 // TVMD display-off is a complete, independently defined image, not a
 // background/sprite mixture. Honor it on this VI even during retirement.
 // vdp2_compose returns all-black before any sprite, VRAM, or CRAM access.
 // serial here is only the monotonic handoff watermark; this black image has
 // no VDP1 source bank or field-producer token.
 if(!g_cfg.interp && !(g_vdp2_regs[0]&0x80)){
  pal_pfq_clear("display_disabled");
  vdp2_compose(out);
  if(retiring&&banks[display].serial>=retiring->serial)retiring.reset();
  last_shown=std::max(last_shown,banks[display].serial);
  emit("compose","display_disabled_black",-1,last_shown,0);
  return true;
 }
 if(boundary)pal_pfq_clear(boundary);
 if(retiring){
  if(banks[display].serial<retiring->serial){
   out=retiring->rgb;emit("compose","retire_rgb_until_display_catches_up",-1,retiring->serial,retiring->token);
   return true;
  }
  emit("handoff","display_caught_up",display,banks[display].serial,retiring->token);
  retiring.reset();
 }
 if(boundary){emit("compose",boundary,display,banks[display].serial,0);last_shown=std::max(last_shown,banks[display].serial);return false;}
 while(!ready.empty()){
  auto q=ready.front();ready.pop_front();
  if(q->epoch==epoch&&q->serial>=last_shown&&q->token>=last_token)presented=q;
 }
 // If an unpaired newer draw has reached normal DISPLAY, stop overriding it.
 // This guarantees that a rejected producer cannot leave an indefinitely held image.
 if(presented&&banks[display].serial>presented->serial){
  emit("handoff","newer_unpaired_display",display,banks[display].serial,0);
  pal_pfq_clear("newer_unpaired_display");
 }
 if(!presented){emit("compose","baseline_no_snapshot",display,banks[display].serial,0);last_shown=std::max(last_shown,banks[display].serial);return false;}
 bool regression=presented->serial<last_shown||presented->token<last_token;
 if(regression)sat_fatal("paired-frame queue regression");
 const char* why=presented->serial==last_shown?"hold_complete_rgb":"present_complete_rgb";
 out=presented->rgb;
 emit("compose",why,-1,presented->serial,presented->token,-1,regression);
 last_shown=presented->serial;last_token=presented->token;
 return true;
}
