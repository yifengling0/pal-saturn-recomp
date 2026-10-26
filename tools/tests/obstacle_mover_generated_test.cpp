// Fixture only: generated original functions are supplied in a temporary include.
#include <saturn/sh2.h>
#include "pal_obstacle_stop.h"
#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <vector>
#include <utility>
uint8_t g_wram_h[1 << 20]{}, g_wram_l[1 << 20]{};
uint32_t g_sh2_watch_lo=0, g_sh2_watch_len=0;
static uint8_t ran[1024]{};
static SH2HookFn callback;
static std::vector<int> answers;
static std::vector<std::pair<uint32_t,uint32_t>> probes;
static unsigned standing, walking;
void sh2_hook_add(uint32_t a, SH2HookFn f) { assert(a==pal_obstacle_stop::Hook); callback=f; }
void sh2_hook(SH2Context& c,uint32_t a) { assert(a==pal_obstacle_stop::Hook); if(callback) callback(c,a); }
void sh2_watch_store(uint32_t,uint32_t,int) { std::abort(); }
uint32_t sh2_io_read(uint32_t,int) { std::abort(); }
void sh2_io_write(uint32_t,uint32_t,int) { std::abort(); }
void sh2_call(SH2Context&,uint32_t) { std::abort(); }
void sh2_poll(SH2Context&) { std::abort(); }
void sh2_bad_return(SH2Context&,uint32_t) { std::abort(); }
void f_06033FA0(SH2Context& c) {
    assert(c.r[6]==0 && probes.size()<answers.size());
    c.r[0]=answers[probes.size()];
    probes.emplace_back(c.r[4],c.r[5]); c.pc=c.pr;
}
void f_06032D18(SH2Context& c) { ++standing; c.pc=c.pr; }
void f_06033480(SH2Context& c) { ++walking; c.pc=c.pr; }
#include "mover-functions.inc"
int main() {
    const bool fixed=std::strcmp(std::getenv("PAL_OBSTACLE_STOP"),"0")!=0;
    assert(bool(callback)==fixed);
    const int dx[]={-1,-1,1,1}, dy[]={1,-1,-1,1};
    unsigned scenarios=0;
    for(uint32_t caller:{0x06026E74u,0x06023818u,0x060238B0u})
    for(unsigned direction=0;direction<4;++direction)
    for(unsigned scenario=0;scenario<5;++scenario) {
        memset(g_wram_h,0,sizeof g_wram_h);
        probes.clear(); standing=walking=0;
        // Direct clear; first alternate clear; second alternate clear; all blocked;
        // first alternate clearance passes but endpoint fails, second succeeds.
        answers = scenario==0 ? std::vector<int>{1} :
                  scenario==1 ? std::vector<int>{0,1,1} :
                  scenario==2 ? std::vector<int>{0,0,1,1} :
                  scenario==3 ? std::vector<int>{0,0,0} : std::vector<int>{0,1,0,1,1};
        st16(pal_obstacle_stop::Hook,0xE303);
#include "mover-switch.inc"
        st16(0x060768E8,dx[direction]); st16(0x060768EA,dy[direction]);
        st8(0x06076970,direction);
        st32(0x06076968,512); st32(0x0607696C,512);
        st16(0x060768E2,4096); st16(0x060768E4,4096);
        SH2Context c{}; c.budget=1000; c.pr=caller;
        c.r[15]=0x060FF000; c.r[14]=0x060ABC00; c.r[8]=0x12345678;
        f_06033654(c);
        assert(c.pc==caller && c.pr==caller && c.r[15]==0x060FF000);
        assert(c.r[14]==0x060ABC00 && c.r[8]==0x12345678);
        assert(ld8(0x06076970)==direction);
        assert(probes.front()==std::make_pair(uint32_t(512+16*dx[direction]),uint32_t(512+8*dy[direction])));
        const bool stop=scenario==3 || (fixed && caller==0x06026E74 && scenario!=0);
        assert(standing==unsigned(stop) && walking==unsigned(!stop));
        if(stop) {
            assert(ld32(0x06076968)==512 && ld32(0x0607696C)==512);
        } else if(scenario==0) {
            assert(ld32(0x06076968)==uint32_t(512+16*dx[direction]));
            assert(ld32(0x0607696C)==uint32_t(512+8*dy[direction]));
        } else {
            // Alternate endpoint is the last successful collision probe.
            assert(ld32(0x06076968)==probes.back().first);
            assert(ld32(0x0607696C)==probes.back().second);
            assert(probes.back()!=probes.front());
        }
        assert(probes.size()==((fixed && caller==0x06026E74 && scenario!=0)?1:answers.size()));
        ++scenarios;
    }
    // Manual movement boundary semantics must be identical with the hook on/off.
    // The collision stub deliberately accepts the target so the original clamp
    // and partial-axis rollback execute, rather than stopping in collision first.
    for(unsigned direction=0;direction<4;++direction)
    for(unsigned scenario=0;scenario<7;++scenario) {
        memset(g_wram_h,0,sizeof g_wram_h);
        probes.clear(); standing=walking=0; answers={1};
        st16(pal_obstacle_stop::Hook,0xE303);
        uint32_t x=512,y=512;
        const uint32_t edge_x=dx[direction]<0?0:4096;
        const uint32_t edge_y=dy[direction]<0?0:4096;
        if(scenario==0 || scenario==2) x=edge_x;
        if(scenario==1 || scenario==2) y=edge_y;
        if(scenario==3) x=dx[direction]<0?8:4088;
        if(scenario==4) y=dy[direction]<0?4:4092;
        const bool idle=scenario==5, turn=scenario==6;
        st16(0x060768E8,idle?0:dx[direction]);
        st16(0x060768EA,idle?0:dy[direction]);
        st8(0x06076970,turn?(direction+1)%4:direction);
        st32(0x06076968,x); st32(0x0607696C,y);
        st16(0x060768E2,4096); st16(0x060768E4,4096);
        SH2Context c{}; c.budget=1000; c.pr=pal_obstacle_stop::ManualReturn;
        c.r[15]=0x060FF000; c.r[14]=0x060ABC00; c.r[8]=0x12345678;
        f_06033654(c);
        assert(c.pc==pal_obstacle_stop::ManualReturn && c.pr==c.pc);
        assert(c.r[15]==0x060FF000 && c.r[14]==0x060ABC00 && c.r[8]==0x12345678);
        assert(ld8(0x06076970)==direction);
        assert(standing==unsigned(idle||turn) && walking==unsigned(!idle&&!turn));
        if(idle||turn) {
            assert(probes.empty());
        } else {
            assert(probes.size()==1);
            assert(probes.front()==std::make_pair(uint32_t(x+16*dx[direction]),uint32_t(y+8*dy[direction])));
        }
        if(scenario<=2 || idle || turn) {
            // Exactly at an edge: clamped axis is unchanged, so the original
            // direct-move path rolls the other axis back too (no wall sliding).
            assert(ld32(0x06076968)==x && ld32(0x0607696C)==y);
        } else if(scenario==3) {
            // Near an edge: clamp only the overshoot, retain legal other motion.
            assert(ld32(0x06076968)==edge_x);
            assert(ld32(0x0607696C)==uint32_t(y+8*dy[direction]));
        } else {
            assert(ld32(0x06076968)==uint32_t(x+16*dx[direction]));
            assert(ld32(0x0607696C)==edge_y);
        }
        ++scenarios;
    }
    std::printf("original mover: %u scenarios passed (stop policy %s)\n",scenarios,fixed?"on":"off");
}
