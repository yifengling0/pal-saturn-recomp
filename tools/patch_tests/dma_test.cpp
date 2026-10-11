#include "saturn.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
int main() {
    g_cpu=&g_master; g_master.cpu=0;g_cfg.save="-";
    unsigned cases=0;
    for(unsigned size:{16u,64u,65536u,155040u}) {
        onchip_reset(0);
        constexpr uint32_t src=0x00200000,dst=0x06080000;
        for(unsigned i=0;i<size;++i)g_wram_l[i]=uint8_t((i*37+11)%255+1);
        std::memset(g_wram_h+0x80000,0xCD,size+16);
        onchip_write(g_master,0xFFFFFF80,src,4);
        onchip_write(g_master,0xFFFFFF84,dst,4);
        onchip_write(g_master,0xFFFFFF88,size/4,4);
        onchip_write(g_master,0xFFFFFF8C,0x5E01,4);
        onchip_write(g_master,0xFFFFFFB0,0x9,4);
        if(std::memcmp(g_wram_l,g_wram_h+0x80000,size)) {
            unsigned first=0;while(first<size&&g_wram_l[first]==g_wram_h[0x80000+first])++first;
            std::fprintf(stderr,"FAIL DMA size=%u first mismatch=%u SAR=%08X DAR=%08X\n",size,first,
                onchip_read(g_master,0xFFFFFF80,4),onchip_read(g_master,0xFFFFFF84,4));return 1;
        }
        assert(onchip_read(g_master,0xFFFFFF80,4)==src+size);
        assert(onchip_read(g_master,0xFFFFFF84,4)==dst+size);
        assert(onchip_read(g_master,0xFFFFFF88,4)==0);
        assert((onchip_read(g_master,0xFFFFFF8C,4)&3)==3);
        for(unsigned i=0;i<16;++i)assert(g_wram_h[0x80000+size+i]==0xCD);
        ++cases;
    }
    // Byte/word/longword modes and channel 1 must retain their exact counts.
    for(unsigned channel:{0u,1u})for(unsigned ts:{0u,1u,2u,3u}) {
        onchip_reset(0);uint32_t base=0xFFFFFF80u+channel*16;
        unsigned unit=1u<<ts;if(ts==3)unit=16;
        unsigned bytes=64,count=ts==3?bytes/4:bytes/unit;
        for(unsigned i=0;i<bytes;++i)g_wram_l[i]=uint8_t(i+1);
        std::memset(g_wram_h+0x80000,0xCD,bytes+16);
        onchip_write(g_master,base,0x00200000,4);
        onchip_write(g_master,base+4,0x06080000,4);
        onchip_write(g_master,base+8,count,4);
        onchip_write(g_master,base+12,0x5201|(ts<<10),4);
        // DMAOR disabled: no writes and no transfer-end yet.
        assert(g_wram_h[0x80000]==0xCD);
        assert(!(onchip_read(g_master,base+12,4)&2));
        onchip_write(g_master,0xFFFFFFB0,9,4);
        assert(!std::memcmp(g_wram_l,g_wram_h+0x80000,bytes));
        assert(onchip_read(g_master,base,4)==0x00200000+bytes);
        assert(onchip_read(g_master,base+4,4)==0x06080000+bytes);
        assert(onchip_read(g_master,base+8,4)==0);
        assert((onchip_read(g_master,base+12,4)&3)==3);
        for(unsigned i=0;i<16;++i)assert(g_wram_h[0x80000+bytes+i]==0xCD);
        // TE already set: another DMAOR write must not restart a zero TCR transfer.
        g_wram_l[0]=0xAB;onchip_write(g_master,0xFFFFFFB0,9,4);
        assert(g_wram_h[0x80000]==1);
        ++cases;
    }
    std::printf("DMA burst: %u cases passed; exact bytes, final addresses, count, TE and tail guards\n",cases);
}
