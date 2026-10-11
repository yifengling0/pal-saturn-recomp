#include <array>
#include <cassert>
#include <cstring>
#include <stdexcept>
#include "pal_battle_probe.h"
uint8_t g_wram_l[1<<20]{};
uint8_t g_wram_h[1<<20]{};
uint64_t sat_vblanks(){return 12345;}
uint64_t sat_now(){return 987654321;}
int main(){
    SH2Context c{}; c.gbr=0x060ffc00; c.pr=0x06027270; c.cpu=0;
    c.r[4]=0x06076ae0; c.r[5]=9; c.r[6]=0x00290000; c.r[7]=32768;
    std::memcpy(g_wram_h+0x76ae0,"FIREN.AV",9);
    const SH2Context before=c;
    const auto low=std::to_array(g_wram_l), high=std::to_array(g_wram_h);
    { pal_battle_probe::Scope outside(c,0x06020094); }
    {
        pal_battle_probe::Scope battle(c,0x060422b8);
        {pal_battle_probe::Scope resource(c,0x06020094);}
        {pal_battle_probe::Scope upload(c,0x0602f590);}
        {pal_battle_probe::Scope decode(c,0x06024220);}
        pal_battle_probe::mark(c,0x060428e0,"background_ready");
        try {
            pal_battle_probe::Scope sync(c,0x0605d68a);
            throw std::runtime_error("unit-only unwind");
        } catch (const std::runtime_error&) {}
    }
    assert(pal_battle_probe::depth==0);
    assert(std::memcmp(&before,&c,sizeof c)==0);
    assert(std::memcmp(low.data(),g_wram_l,sizeof g_wram_l)==0);
    assert(std::memcmp(high.data(),g_wram_h,sizeof g_wram_h)==0);
    assert(pal_battle_probe::raw32(0x25818000)==0); // No MMIO dependency even on unknown address.
    std::puts("PASS: context and WRAM unchanged; scope balance and MMIO avoidance checked");
}
