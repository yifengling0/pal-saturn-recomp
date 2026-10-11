#pragma once
#include <saturn/sh2.h>
#include <cstdio>
#include <cstdint>
#include <initializer_list>
extern uint64_t sat_vblanks() __attribute__((weak));
inline uint8_t pal_raw_byte(uint32_t a) {
    auto p=a&0x1fffffff;
    if(p>=0x06000000 && p<0x08000000)return g_wram_h[p&0xfffff];
    if(p>=0x00200000 && p<0x00300000)return g_wram_l[p&0xfffff];
    return 0;
}
inline void pal_resource_probe(SH2Context& c,uint32_t pc) {
    static unsigned counts[3]{};
    unsigned slot=pc==0x06020094?0:pc==0x0602FA8C?1:2;
    if(counts[slot]++>=512)return;
    std::fprintf(stderr,"PAL_RESOURCE pc=%08X pr=%08X vb=%llu r4=%08X r5=%08X r6=%08X r7=%08X",pc,c.pr,
        (unsigned long long)(sat_vblanks?sat_vblanks():0),c.r[4],c.r[5],c.r[6],c.r[7]);
    if(slot==0) {
        std::fputs(" name=",stderr);
        for(unsigned i=0;i<40;++i){auto ch=pal_raw_byte(c.r[4]+i);if(!ch)break;std::fputc(ch>=32&&ch<127?ch:'.',stderr);}
    } else {
        for(auto address:{0x0609CDB0u,0x0609C770u,0x06089C20u}) {
            std::fprintf(stderr," mem%08X=",address);
            for(unsigned i=0;i<32;++i)std::fprintf(stderr,"%02X",pal_raw_byte(address+i));
        }
    }
    std::fputc('\n',stderr);
    if(counts[slot]==512)std::fprintf(stderr,"PAL_RESOURCE pc=%08X limit reached\n",pc);
}

inline void pal_resource_result(SH2Context& c) {
    static unsigned count; if(count++>=512)return;
    std::fprintf(stderr,"PAL_RESOURCE_RESULT vb=%llu result=%08X\n",
        (unsigned long long)(sat_vblanks?sat_vblanks():0),c.r[0]);
}

inline void pal_map_snapshot(SH2Context&,uint32_t pc) {
    static unsigned count; if(count++>=32)return;
    std::fprintf(stderr,"PAL_MAP_SNAPSHOT pc=%08X vb=%llu",pc,(unsigned long long)(sat_vblanks?sat_vblanks():0));
    for(auto base:{0x00200000u,0x0608C310u,0x00210000u}) {
        unsigned nonzero=0;uint32_t fnv=2166136261u;
        for(unsigned i=0;i<65536;++i){auto b=pal_raw_byte(base+i);nonzero+=b!=0;fnv=(fnv^b)*16777619u;}
        std::fprintf(stderr," base%08X_nz=%u_fnv=%08X",base,nonzero,fnv);
    }
    std::fputs(" vars=",stderr);for(unsigned i=0;i<8;++i)std::fprintf(stderr,"%02X",pal_raw_byte(0x060769C0+i));
    std::fputc('\n',stderr);
}

inline void pal_map_draw(SH2Context& c) {
    static uint64_t last=~uint64_t(0);auto vb=sat_vblanks?sat_vblanks():0;
    if(vb==last || (vb>5700 && vb%100))return;last=vb;
    std::fprintf(stderr,"PAL_MAP_DRAW vb=%llu camera=",(unsigned long long)vb);
    for(unsigned i=0;i<12;++i)std::fprintf(stderr,"%02X",pal_raw_byte(0x060768C0+i));
    unsigned nonzero=0;uint32_t fnv=2166136261u;
    for(unsigned i=0;i<65536;++i){auto b=pal_raw_byte(0x0608C310+i);nonzero+=b!=0;fnv=(fnv^b)*16777619u;}
    std::fprintf(stderr," mapnz=%u fnv=%08X\n",nonzero,fnv);
}
