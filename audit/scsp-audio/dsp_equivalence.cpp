// Compare the production optimized DSP to an unoptimized 128-step reference.
// Seeded programs and RAM are synthetic. Only public writes and state APIs.
#include "sound.h"
#include "state.h"
#include <cstdio>
static uint32_t rng;
uint32_t random32(){rng^=rng<<13;rng^=rng>>17;return rng^=rng<<5;}
uint64_t hash(const void* p,size_t n,uint64_t h=1469598103934665603ull){
    auto b=(const uint8_t*)p;while(n--)h=(h^*b++)*1099511628211ull;return h;
}
void step(){int16_t out[2];const int16_t l=random32(),r=random32();scsp_sample(l,r,out);}
int main(){
    for(unsigned seed=1;seed<=512;++seed){
        rng=seed;scsp_reset();for(unsigned i=0;i<0x80000;++i)g_sound_ram[i]=random32();
        for(int i=0;i<128;++i)scsp_write(0xC00+i*4,random32()&0xFFFFFF,4);
        for(int i=0;i<32;++i)scsp_write(0xE00+i*4,random32()&0xFFFFFF,4);
        for(int i=0;i<64;++i)scsp_write(0x700+i*2,random32(),2);
        for(int i=0;i<32;++i)scsp_write(0x780+i*2,random32(),2);
        scsp_write(0x402,random32()&0x1FF,2);
        for(int i=0;i<512;++i)scsp_write(0x800+i*2,random32(),2);
        step();step(); // Warm cross-sample carry before changing the tail.
        const int last=int(seed%129)-1;
        for(int st=last+1;st<128;++st)for(int k=0;k<4;++k)scsp_write(0x800+st*8+k*2,0,2);
        for(int sample=0;sample<4;++sample){
            int16_t out[2];const int16_t l=random32(),r=random32();scsp_sample(l,r,out);
            State chip,carry;scsp_state(chip);scspdsp_state(carry);
            uint64_t h=hash(chip.data.data(),chip.data.size());h=hash(carry.data.data(),carry.data.size(),h);h=hash(out,sizeof out,h);
            std::printf("%u %d %d %016llx\n",seed,last,sample,(unsigned long long)h);
        }
    }
}
