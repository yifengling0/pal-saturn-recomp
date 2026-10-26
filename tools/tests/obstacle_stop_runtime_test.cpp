#include <saturn/sh2.h>
#include "pal_obstacle_stop.h"
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <vector>
uint8_t g_wram_h[1 << 20]{}, g_wram_l[1 << 20]{};
uint32_t g_sh2_watch_lo=0, g_sh2_watch_len=0xFFFFFFFFu;
static SH2HookFn callback;
static unsigned stores, io;
void sh2_hook_add(uint32_t addr,SH2HookFn fn){assert(addr==pal_obstacle_stop::Hook);callback=fn;}
void sh2_watch_store(uint32_t,uint32_t,int){++stores;}
uint32_t sh2_io_read(uint32_t,int){++io;return 0;}
void sh2_io_write(uint32_t,uint32_t,int){++io;}
SH2Context fixture(){
 memset(g_wram_h,0xA5,sizeof g_wram_h);memset(g_wram_l,0x5A,sizeof g_wram_l);
 SH2Context c{};c.cpu=0;c.r[14]=0x060FF000;c.r[1]=0;c.r[3]=3;c.pr=0x0603371E;
 st16(c.r[14],0);st32(c.r[14]+4,pal_obstacle_stop::ManualReturn);st16(pal_obstacle_stop::Hook,0xE303);return c;
}
void check(SH2Context c,uint32_t addr,bool change){
 SH2Context expected=c;if(change)expected.r[1]=4;
 std::vector<uint8_t> before(g_wram_h,g_wram_h+sizeof g_wram_h);
 stores=io=0;callback(c,addr);assert(!memcmp(&c,&expected,sizeof c));
 assert(!memcmp(g_wram_h,before.data(),before.size()));assert(stores==0&&io==0);
}
int main(){
 const char* mode=std::getenv("PAL_OBSTACLE_STOP");
 if(mode&&!strcmp(mode,"0")){assert(!callback);return 0;}
 assert(callback);auto c=fixture();
 for(unsigned d=0;d<4;++d){c.r[1]=d;check(c,pal_obstacle_stop::Hook,true);}c=fixture();
 for(auto caller:{0x06023818u,0x060238B0u,0u,0x0603371Eu}){st32(c.r[14]+4,caller);check(c,pal_obstacle_stop::Hook,false);}
 c=fixture();c.cpu=1;check(c,pal_obstacle_stop::Hook,false);
 c=fixture();c.r[1]=4;check(c,pal_obstacle_stop::Hook,false);
 c=fixture();c.r[3]=2;check(c,pal_obstacle_stop::Hook,false);
 c=fixture();st16(c.r[14],1);check(c,pal_obstacle_stop::Hook,false);
 c=fixture();st16(pal_obstacle_stop::Hook,0);check(c,pal_obstacle_stop::Hook,false);
 c=fixture();check(c,pal_obstacle_stop::Hook+2,false);
 for(auto frame:{0u,0x05FFFFFCu,0x06100000u,0x060FFFF4u,0x060FF001u}){c=fixture();c.r[14]=frame;check(c,pal_obstacle_stop::Hook,false);}
}
