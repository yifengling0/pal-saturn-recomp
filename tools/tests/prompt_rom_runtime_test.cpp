#include "pal_keyboard_profile.h"
#include <cstdint>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <array>
struct SH2Context{uint32_t r[16]{},pr=0,pc=0,mach=0,macl=0;bool t=false;};
static std::array<uint8_t,0x100000> mem{};
static unsigned ran[1000]{};
static uint8_t ld8(uint32_t a){assert((a&0xff000000)==0x06000000);return mem[a&0xfffff];}
static uint16_t ld16(uint32_t a){return uint16_t(ld8(a)<<8|ld8(a+1));}
static uint32_t ld32(uint32_t a){return uint32_t(ld16(a))<<16|ld16(a+2);}
static void st8(uint32_t a,uint32_t v){assert((a&0xff000000)==0x06000000);mem[a&0xfffff]=v;}
static void st16(uint32_t a,uint32_t v){st8(a,v>>8);st8(a+1,v);}
static void st32(uint32_t a,uint32_t v){st16(a,v>>16);st16(a+2,v);}
static void sh2_call(SH2Context&,uint32_t){assert(false);}
#define SH2_POLL(c) ((void)0)
#define SH2_RET(c,x) ((void)0)
void f_060231E8(SH2Context&);
void f_06022B8C(SH2Context&);
void f_06022A30(SH2Context&);
void f_060227F8(SH2Context&);
#include "prompt-functions.inc"
static unsigned frames=0,mode=0;
static uint16_t previous=0;
static bool real=true;
static bool begin(){return real;}
static bool valid(){return real;}
static void consume(){}
void f_060231E8(SH2Context&){
 ++frames;
 uint16_t pad=0;
 if(mode==1 && frames==4)pad=0x0400;
 if(mode==2 && frames==4)pad=0x1400;
 if(mode==3)pad=0x0400;
 if(mode==4 && frames==4) {pal_prompt::ledger.press({1,0,40},true);pal_prompt::ledger.release({1,0,40});}
 if(mode==2 && frames==4)pal_prompt::ledger.press({1,0,40},true);
 st16(0x06076834,ld16(0x06076832));
 st16(0x0607682A,uint16_t(~pad));
 st16(0x0607682C,uint16_t(~(pad & ~previous)));
 st16(0x0607682E,uint16_t(~(previous & ~pad)));
 previous=pad;
}
static unsigned run(bool patched,unsigned scenario,bool host=true,uint32_t caller=0x0602315E,uint16_t style=10){
 mem={};frames=0;mode=scenario;previous=scenario==3?0x400:0;
 pal_prompt::ledger={};real=host;
 pal_prompt::host_begin=begin;pal_prompt::host_valid=valid;pal_prompt::host_consume=consume;
 if(scenario==3)pal_prompt::ledger.press({1,0,40},true);
 st16(0x06076902,style);st16(0x060768FC,1);st8(0x0605CFA2,1);
 st16(0x06076832,previous);st16(0x0607682A,uint16_t(~previous));
 SH2Context c;c.r[15]=0x060F0000;c.r[4]=180;c.pr=caller;
 if(patched)f_prompt_patched(c);else f_060220D0(c);
 assert(c.r[15]==0x060F0000);assert(c.pr==caller);
 return frames;
}
int main(){
 auto no=run(false,0);auto solo=run(false,1);auto combo=run(false,2);auto hold=run(false,3);
 auto patched_combo=run(true,2);auto short_tap=run(true,4);auto patched_hold=run(true,3);
 assert(no==90 && solo==4 && combo==90 && hold==90);
 assert(patched_combo==4 && short_tap==4 && patched_hold==90);
 assert(run(true,0)==90);
 assert(run(true,2,false)==90); // headless: original result
 assert(run(true,1,false)==4);
 assert(run(true,2,true,0x06023190)==90); // other timer caller
 assert(run(true,2,true,0x0602315E,1)==90); // ordinary dialogue style
 std::printf("PASS original ROM functions: no-input=%u solo=%u direction+confirm=%u opening-held=%u; patched combo=%u down/up-tap=%u held=%u\n",no,solo,combo,hold,patched_combo,short_tap,patched_hold);
}
