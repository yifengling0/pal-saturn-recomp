#pragma once
#include "pal_effect_cadence.h"
#include <saturn/sh2.h>
#include <cstdio>
#include <cstdlib>
#include <exception>
extern uint64_t sat_vblanks();
extern bool pal_effect_cadence_scope_supported() noexcept;
extern uint8_t g_vdp2_regs[0x200];
namespace pal_effect_cadence {
// Safety stop: shortened sync can skip the original VDP1 swap/DMA phase.
// Keep the failed candidates and tests; restore acceleration only after complete
// relative-to-original sprite/effect visibility regression passes.
inline Speed speed() noexcept {
    static const Speed s=[] {
        const Speed requested=parse_speed(std::getenv("PAL_EFFECT_ANIMATION_SPEED"));
        if(requested!=Speed::original)
            std::fprintf(stderr,"PAL_EFFECT_ANIMATION_SPEED: rates above 1 temporarily disabled (missing-sprite regression); using original rate 1.\n");
        return Speed::original;
    }();
    return s;
}
inline uint8_t raw8(uint32_t a) noexcept {
    const uint32_t p=a&0x1FFFFFFFu;
    if(p>=0x06000000u && p<0x06100000u)return g_wram_h[p&0xFFFFF];
    if(p>=0x00200000u && p<0x00300000u)return g_wram_l[p&0xFFFFF];
    return 0;
}
inline uint16_t raw16(uint32_t a) noexcept {return uint16_t(raw8(a))<<8|raw8(a+1);}
inline uint32_t raw32(uint32_t a) noexcept {return uint32_t(raw16(a))<<16|raw16(a+2);}
struct Cast;
struct Frame;
struct Wait;
struct Sync;
inline thread_local Cast* cast=nullptr;
inline thread_local Frame* frame=nullptr;
inline thread_local Wait* wait=nullptr;
inline thread_local Sync* sync=nullptr;
struct Cast {
    Cast* previous;SH2Context* c=nullptr;unsigned effect=0,count=0,next=0;bool armed=false;
    explicit Cast(SH2Context& x) noexcept:previous(cast) {
        cast=nullptr;
        if(speed()==Speed::original)return; // Default does not read guest state.
        if(!pal_effect_cadence_scope_supported())return; // Fiber/state-in can discard RAII scopes.
        if(x.cpu!=0 || (x.gbr&0x1FFFFFFFu)!=0x060FFC00u || raw16(0x060768EC)!=0xFFFF)return;
        c=&x;cast=this;
    }
    ~Cast() noexcept {cast=previous;}
    Cast(const Cast&)=delete;Cast& operator=(const Cast&)=delete;
};
struct Prepare {
    SH2Context& c;Cast* owner=nullptr;unsigned effect=0;int exceptions=0;
    explicit Prepare(SH2Context& x) noexcept:c(x) {
        if(speed()==Speed::original)return;
        if(cast)cast->armed=false;
        if(cast && cast->c==&c && c.pr==0x0603BEE0u && expected_frames(c.r[4])) {
            owner=cast;effect=c.r[4];exceptions=std::uncaught_exceptions();
        }
    }
    ~Prepare() noexcept {
        if(!owner || cast!=owner || std::uncaught_exceptions()!=exceptions)return;
        unsigned count=raw16(0x060769DA);
        if(count!=expected_frames(effect) || (raw32(0x00290200)&0x20000000u) ||
           raw8(0x060FFC12)!=2 || (raw8(0x060FFCEC)&7)!=7 ||
           raw8(0x060FFCEC)!=g_vdp2_regs[0x2C])return;
        owner->effect=effect;owner->count=count;owner->next=0;owner->armed=true;
    }
    Prepare(const Prepare&)=delete;Prepare& operator=(const Prepare&)=delete;
};
struct Frame {
    Frame* previous;SH2Context* c=nullptr;Cast* owner=nullptr;unsigned index=0,fields=4;int exceptions=0;
    explicit Frame(SH2Context& x) noexcept:previous(frame) {
        frame=nullptr;
        if(speed()==Speed::original)return;
        // Only the tested standard single-target/healing and group frame loops.
        if(!cast || cast->c!=&x || !cast->armed ||
           (x.pr!=0x0603C26Au && x.pr!=0x0603F240u))return;
        index=raw16(0x060769C8);
        if(!matches(x.cpu,x.gbr,raw16(0x060768EC),cast->effect,
            raw16(0x060769DA),index,cast->next,raw8(0x060FFC12),g_vdp2_regs[0x2C])) {
            cast->armed=false;return;
        }
        c=&x;owner=cast;fields=frame_fields(speed(),index);
        exceptions=std::uncaught_exceptions();frame=this;
    }
    ~Frame() noexcept {
        if(owner){if(std::uncaught_exceptions()==exceptions)++owner->next;else owner->armed=false;}
        frame=previous;
    }
    Frame(const Frame&)=delete;Frame& operator=(const Frame&)=delete;
};
struct Wait {
    Wait* previous;Frame* owner=nullptr;unsigned calls=0;uint64_t start=0;
    explicit Wait(SH2Context& c) noexcept:previous(wait) {
        wait=nullptr;
        if(!frame || frame->c!=&c || c.r[4]!=2 || c.r[5]!=0)return;
        owner=frame;start=sat_vblanks();wait=this;
    }
    ~Wait() noexcept {
        if(owner)std::fprintf(stderr,"PAL_EFFECT_CADENCE effect=%u frame=%u fields=%u actual_vb=%llu syncs=%u vb=%llu\n",
          owner->owner->effect,owner->index,owner->fields,(unsigned long long)(sat_vblanks()-start),calls,(unsigned long long)start);
        wait=previous;
    }
    Wait(const Wait&)=delete;Wait& operator=(const Wait&)=delete;
};
struct Sync {
    Sync* previous;SH2Context* c=nullptr;uint64_t start=0;bool cut=false;unsigned fields=2;
    explicit Sync(SH2Context& x) noexcept:previous(sync) {
        sync=nullptr;
        if(!wait || !wait->owner || wait->owner!=frame || !frame->owner ||
           frame->owner!=cast || !cast->armed || wait->owner->c!=&x || x.pr!=0x06022354u ||
           raw32(x.r[14]+4)!=0x0603E8E8u || wait->calls>=2)return;
        fields=sync_fields(wait->owner->fields,wait->calls++);
        // Fail closed for a different scheduler phase. No forced catch-up,
        // no interval mutation, and never skip a real composed-field sync.
        if(fields!=1 || raw8(x.gbr+18)!=2 || raw8(x.gbr+19)!=1)return;
        c=&x;start=sat_vblanks();sync=this;
    }
    ~Sync() noexcept {sync=previous;}
    Sync(const Sync&)=delete;Sync& operator=(const Sync&)=delete;
};
inline void shorten_sync(SH2Context& c) noexcept {
    if(sync && sync->c==&c && c.t && c.r[0]==0 && sat_vblanks()>sync->start) {
        c.t=false;sync->cut=true;
    }
}
inline void finish_sync(SH2Context& c) noexcept {
    // The original instruction still performs the only guest countdown write.
    // Its residual is zero after the early field; subtract just that saved field
    // so the following ordinary sync keeps the normal countdown=1 phase.
    // If asynchronous work already consumed another field, leave it original.
    if(sync && sync->c==&c && sync->cut && c.r[0]==2 && raw8(c.gbr+19)==0)c.r[0]=1;
}
} // namespace pal_effect_cadence
