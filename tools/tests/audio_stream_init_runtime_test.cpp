#include <saturn/sh2.h>
#include <cassert>
#include <cstdarg>
#include <cstring>
#include <vector>
uint8_t g_wram_h[1<<20]{}, g_wram_l[1<<20]{};
uint32_t g_sh2_watch_lo=0x06040C44, g_sh2_watch_len=8;
static unsigned writes=0;
void sh2_watch_store(uint32_t a,uint32_t,int size) { assert((a==0x06040C44 || a==0x06040C48) && size==4); ++writes; }
static SH2HookFn callback=nullptr;
static unsigned registrations=0, reads=0, logs=0;
static uint32_t header=0x700;
void sh2_hook_add(uint32_t a, SH2HookFn f) { assert(a==0x06021C1E); callback=f; ++registrations; }
uint32_t sh2_io_read(uint32_t a,int size) { assert(a==0x25A00404 && size==4); ++reads;return header; }
void sh2_io_write(uint32_t,uint32_t,int) { assert(false); }
void sat_note(const char*,...) { ++logs; }
static void reset() {
    std::memset(g_wram_h,0xA5,sizeof g_wram_h);
    std::memset(g_wram_l,0x5A,sizeof g_wram_l);
    st32(0x06040C44,0x25A00000);st32(0x06040C48,0x25A000A0);
    header=0x700;reads=logs=writes=0;
}
int main() {
    assert(registrations==1 && callback);
    for(unsigned mode=0;mode<7;++mode) {
        reset();SH2Context c{};c.cpu=0;c.pr=0x06021C1E;c.r[2]=0x25A004A1;
        uint32_t pc=0x06021C1E;
        if(mode==0)c.cpu=1;
        if(mode==1)c.pr=0x06021C1A;
        if(mode==2)pc=0x06021C20;
        if(mode==3)header=0;
        if(mode==4)header=0x701;
        if(mode==5)header=0xFFFFFFFF;
        if(mode==6)st32(0x06040C48,0x25A000A4);
        std::vector<uint8_t> before(g_wram_h,g_wram_h+sizeof g_wram_h);
        SH2Context original;std::memcpy(&original,&c,sizeof c);
        writes=0;callback(c,pc);
        assert(std::memcmp(&c,&original,sizeof c)==0);
        assert(std::memcmp(before.data(),g_wram_h,sizeof g_wram_h)==0);
        assert(logs==0 && writes==0 && reads==(mode<3?0u:1u));
    }
    reset();SH2Context c{};c.cpu=0;c.pr=0x06021C1E;c.r[2]=0x25A004A1;
    SH2Context original;std::memcpy(&original,&c,sizeof c);
    st32(0x06040C44,0x25A00700);st32(0x06040C48,0x25A007A0);
    std::vector<uint8_t> expected(g_wram_h,g_wram_h+sizeof g_wram_h);
    st32(0x06040C44,0x25A00000);st32(0x06040C48,0x25A000A0);
    writes=0;callback(c,0x06021C1E);
    assert(logs==1 && reads==1 && writes==2);
    assert(std::memcmp(expected.data(),g_wram_h,sizeof g_wram_h)==0);
    assert(std::memcmp(&c,&original,sizeof c)==0);
    callback(c,0x06021C1E); // Already correct: no second write/log.
    assert(logs==1 && reads==2 && writes==2);
    assert(std::memcmp(expected.data(),g_wram_h,sizeof g_wram_h)==0);
    for(auto b:g_wram_l) assert(b==0x5A);
}
