#pragma once
#include "pal_effect_wait.h"
#include <saturn/sh2.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
extern uint64_t sat_vblanks();
extern uint8_t g_vdp2_regs[0x200];
namespace pal_effect_wait {
inline bool enabled() {
    static const bool on=[] {const char* p=std::getenv("PAL_SHORT_EFFECT_PREP");return p && !std::strcmp(p,"1");}();
    return on;
}
inline uint8_t raw8(uint32_t a) {
    const uint32_t p=a&0x1FFFFFFFu;
    return p>=0x06000000 && p<0x06100000 ? g_wram_h[p&0xFFFFF] : 0;
}
inline uint16_t raw16(uint32_t a) {return uint16_t(raw8(a))<<8|raw8(a+1);}
inline uint32_t raw32(uint32_t a) {return uint32_t(raw16(a))<<16|raw16(a+2);}
struct Scope;
inline thread_local Scope* current=nullptr;
struct Scope {
    Scope* previous;
    SH2Context* context=nullptr;
    uint64_t start=0;
    uint8_t desired=0;
    bool cut=false;
    explicit Scope(SH2Context& c):previous(current) {
        current=nullptr;
        if(!enabled())return; // No guest observation at all when disabled.
        if((c.gbr&0x1FFFFFFFu)!=0x060FFC00u ||
           !pal_effect_scope_matches(true,c.cpu,raw32(c.r[14]+4),c.r[8],c.r[9],c.r[4],
                                     raw8(0x060FFC12),raw16(0x060768EC)))return;
        context=&c;start=sat_vblanks();desired=raw8(0x060FFCEC);current=this;
        std::fprintf(stderr,"PAL_EFFECT_PREP begin vb=%llu countdown=%d desired=%02X actual=%02X\n",
          (unsigned long long)start,int(int8_t(raw8(0x060FFC13))),desired,g_vdp2_regs[0x2C]);
    }
    ~Scope(){current=previous;}
    Scope(const Scope&)=delete;
    Scope& operator=(const Scope&)=delete;
};
inline bool ready(SH2Context& c) {
    Scope* s=current;
    if(!s || s->context!=&c || s->cut || raw32(c.r[14]+8)!=0x060224E4u)return false;
    // Called only at f06021FD8's original loop comparison. All earlier
    // rendering, input cancellation and the original 50-iteration cap remain.
    const uint64_t elapsed=sat_vblanks()-s->start;
    if(!pal_effect_wait_complete(true,c.r[2],c.r[1],elapsed,g_vdp2_regs[0x2C],s->desired))return false;
    s->cut=true;
    std::fprintf(stderr,"PAL_EFFECT_PREP early_exit vb=%llu loops=%u elapsed_vb=%llu countdown=%d desired=%02X actual=%02X\n",
      (unsigned long long)sat_vblanks(),c.r[1],(unsigned long long)elapsed,
      int(int8_t(raw8(0x060FFC13))),s->desired,g_vdp2_regs[0x2C]);
    return true;
}
}
