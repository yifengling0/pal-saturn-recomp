// Differential RGB validation against the unmodified pinned composer.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <cstdlib>

struct Frame { int w=0,h=0; std::vector<uint32_t> px; };
struct State { template<class T> void operator()(T&) {} };
void sat_note(const char*,...) {}
static uint32_t sprite_seed;
static unsigned sprite_pattern;
uint16_t vdp1_dot(int x,int y,bool dd) {
    // A reproducible mix of transparent dots, shadows, palette and RGB data.
    uint32_t n = ((uint32_t)x*977+(uint32_t)y*1237+sprite_seed) ^ ((uint32_t)x<<7);
    if(sprite_pattern==1)return (uint16_t)(n%255+1);
    if(sprite_pattern==2)return (uint16_t)(0x8000|(n&0x7FFF));
    return (n%11==0) ? 0 : (n%13==0) ? 0x07FE : (uint16_t)n;
}
namespace reference {
#include PAL_VDP2_REFERENCE
}
namespace cached {
#include PAL_VDP2_CACHED
}

static uint32_t seed=0x10a31141;
static uint32_t rnd() { seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed; }
static void reg(unsigned a,unsigned v) {
    reference::g_vdp2_regs[a]=(uint8_t)(v>>8);
    reference::g_vdp2_regs[a+1]=(uint8_t)v;
}
static void sync() {
    std::memcpy(cached::g_vdp2_regs,reference::g_vdp2_regs,sizeof cached::g_vdp2_regs);
    std::memcpy(cached::g_vdp2_vram,reference::g_vdp2_vram,sizeof cached::g_vdp2_vram);
    std::memcpy(cached::g_vdp2_cram,reference::g_vdp2_cram,sizeof cached::g_vdp2_cram);
}
static void equal(unsigned case_id) {
    Frame a,b;reference::vdp2_compose(a);cached::vdp2_compose(b);
    if(a.w!=b.w||a.h!=b.h||a.px!=b.px) {
        size_t i=0;while(i<std::min(a.px.size(),b.px.size())&&a.px[i]==b.px[i])++i;
        std::fprintf(stderr,"RGB mismatch case=%u dot=%zu\n",case_id,i);std::exit(1);
    }
}
int main() {
    for(auto& v:reference::g_vdp2_vram)v=(uint8_t)rnd();
    for(unsigned c=0;c<192;++c) {
        for(auto& v:reference::g_vdp2_regs)v=(uint8_t)rnd();
        for(auto& v:reference::g_vdp2_cram)v=(uint8_t)rnd();
        sprite_seed=rnd();
        const unsigned n0=c%5,n1=(c/5)%4;
        reg(0x00,0x8000|(c%4)|((c%3)<<4)|((c%7==0)?0xC0:0));
        reg(0x0E,(c%4)<<12);
        reg(0x20,0x000F|(rnd()&0x0F00));
        reg(0x28,(n0<<4)|(rnd()&7)|((n1<<4|((rnd()&7)))<<8));
        reg(0x2A,rnd()&0x33);
        reg(0xE0,(rnd()&0xF330)|(c%16));
        reg(0xEC,rnd()&0xB35F);
        // Only supported layer/window bits; retain randomized special modes.
        for(unsigned a=0xD0;a<=0xD6;a+=2)reg(a,rnd()&0x8787);
        sync();equal(c*3);
        // Fresh palettes and modes must be visible on the very next compose.
        reference::g_vdp2_cram[rnd()%0x1000]^=0xFF;
        reg(0x0E,((c+1)%4)<<12);
        reg(0x110,rnd());reg(0x112,rnd());reg(0xE0,c%16);
        sync();equal(c*3+1);equal(c*3+2);
    }
    // Common PAL-style sprite + bitmap case for a host-only cost comparison.
    std::memset(reference::g_vdp2_regs,0,sizeof reference::g_vdp2_regs);
    reg(0x00,0x8000);reg(0x20,1);reg(0x28,0x0012);reg(0x78,0x100);reg(0x7C,0x100);
    reg(0xF8,1);reg(0xF0,3);reg(0xE0,0x20);reg(0xEC,0x41);sync();
    auto bench=[](auto compose) {
        Frame f;auto start=std::chrono::steady_clock::now();
        for(int i=0;i<80;++i)compose(f);
        return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    };
    std::puts("576 differential RGB frames passed");
    for(sprite_pattern=0;sprite_pattern<3;++sprite_pattern) {
        const double old_ms=bench(reference::vdp2_compose),new_ms=bench(cached::vdp2_compose);
        std::printf("host benchmark pattern=%u old_ms=%.3f cached_ms=%.3f ratio=%.3f\n",sprite_pattern,old_ms,new_ms,new_ms/old_ms);
    }
}
