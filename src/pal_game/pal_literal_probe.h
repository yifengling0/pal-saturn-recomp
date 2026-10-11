#pragma once
#include <cstdio>
#include <cstring>
#include <cstdint>
// Optional symbol: instruction-only selftest links no machine clock.
extern uint64_t sat_vblanks() __attribute__((weak));
inline void pal_literal_probe(SH2Context& c, const char* module, uint32_t pc,
                              uint32_t slot, unsigned size, uint32_t folded) {
    uint32_t p=slot&0x1fffffff;
    const uint8_t* mem=nullptr;
    if(p>=0x06000000 && p<0x08000000)mem=g_wram_h;
    else if(p>=0x00200000 && p<0x00300000)mem=g_wram_l;
    if(!mem)return;
    uint32_t actual=0;
    for(unsigned i=0;i<size;++i)actual=(actual<<8)|mem[(p+i)&0xfffff];
    if(size==2)actual=uint32_t(int32_t(int16_t(actual)));
    if(actual==folded)return;
    struct Seen {const char* module;uint32_t pc;};
    static Seen seen[64];static unsigned count;
    for(unsigned i=0;i<count;++i)if(seen[i].pc==pc&&!std::strcmp(seen[i].module,module))return;
    if(count>=64)return;
    seen[count++]={module,pc};
    std::fprintf(stderr,"PAL_LITERAL_MISMATCH module=%s pc=%08X slot=%08X size=%u folded=%08X memory=%08X pr=%08X vb=%llu\n",
        module,pc,slot,size,folded,actual,c.pr,(unsigned long long)(sat_vblanks?sat_vblanks():0));
}
