#include <array>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include "pal_release_runtime.h"
namespace rt=pal_release_runtime;
static std::array<uint8_t,0x100000> ram;
static unsigned checks;
uint32_t ld8(uint32_t a) { assert(a>=0x06000000 && a<0x06100000); return ram[a-0x06000000]; }
uint32_t ld16(uint32_t a) { return (uint16_t(ld8(a))<<8)|ld8(a+1); }
uint32_t ld32(uint32_t a) { return (uint32_t(ld16(a))<<16)|ld16(a+2); }
static void put8(uint32_t a,uint8_t v) { ram.at(a-0x06000000)=v; }
static void put16(uint32_t a,uint16_t v) { put8(a,v>>8);put8(a+1,v); }
static void put32(uint32_t a,uint32_t v) { put16(a,v>>16);put16(a+2,v); }
static void ck(bool v) { ++checks; assert(v); }
static constexpr uint32_t F=0x060FE000,C=0x060FDFDC;
template<class Fn> static auto pure(Fn fn) {
    const auto before=ram;
    auto result=fn(); ck(before==ram); return result;
}
static SH2Context converter(uint16_t buttons=0x8000,uint16_t action=6) {
    SH2Context c; c.r[14]=C; c.pr=0x06022E9C; // Last leaf PR is deliberately NOT field return.
    put32(C,pal_field_release::DeltaX); put32(C+4,pal_field_release::DeltaY);
    put32(C+8,F); put32(C+24,pal_field_release::FieldReturn); put32(C+28,F);
    put16(C+14,1);put16(C+16,1);put16(C+22,uint16_t(~buttons));put16(F,action);
    pure([] { rt::capture_field_frame(F);return 0; }); return c;
}
static void reset() {
    ram.fill(0); rt::field_enter(); put16(rt::Scene,7);put16(rt::NextScene,7);
    put16(rt::Pad,0x7FFF);
}
static void write(uint32_t pc,uint32_t caller) {
    SH2Context c;c.r[14]=0x060FC000;
    put32(c.r[14]+(pc==0x06026FAC?4:12),caller);
    pure([&] {rt::writer_pre(c,pc);return 0;}); put8(rt::Gate,0xFF);
}
static void resource(uint32_t caller=0x060327D4) {
    { rt::ResourceScope scope(caller); write(0x060323B8,caller); }
    // Writer frame/store setup is test fixture data, checked separately by pure().
    ck(!rt::resource_active());
}
static SH2Context outer;
static bool on;
static void loaded() {
    reset();converter();put16(rt::SceneChange,12);put16(rt::NextScene,8);
    ck(rt::scene_transition_start()==on);
    {rt::SceneScope scene(0x06026DAE);write(0x06026FAC,0x06026DAE);
     put16(rt::Scene,8);put16(rt::SceneChange,0);}
    ck(rt::scene_transition_end()==on);
    outer=SH2Context{};outer.r[14]=F;outer.r[0]=outer.r[1]=1;outer.r[8]=0x06033654;
    put8(0x060FFC12,3);put8(0x060FFC13,0);
}
static void deltas(uint16_t dir) {
    int x=0,y=0;
    if(dir==0x8000){x=1;y=1;} if(dir==0x4000){x=-1;y=-1;}
    if(dir==0x1000){x=1;y=-1;} if(dir==0x2000){x=-1;y=1;}
    put16(pal_field_release::DeltaX,uint16_t(x));put16(pal_field_release::DeltaY,uint16_t(y));
}
static void slot(int count,uint16_t action=6) {
    auto c=converter(0x8000,action);ck(rt::permits(c)==on);deltas(0x8000);
    put8(0x060FFC13,uint8_t(count));
}
static bool query(uint64_t now) {
    const auto regs=outer;
    const bool result=pure([&]{return rt::should_defer_displacement(outer,now);});
    ck(std::memcmp(&regs,&outer,sizeof(regs))==0);return result;
}
int main() {
    on=rt::enabled();loaded();
    // A carry flag without a real captured permission cannot qualify itself.
    deltas(0x8000);put8(0x060FFC13,0xD8);ck(!query(3502));
    for(int count=-40;count<0;++count) {
        slot(count);ck(query(3502)==on);ck(!rt::state.displacement_deadline_active);
    }
    // No first negative-debt step; first nonnegative slot starts the stamp.
    slot(0);ck(!query(3503));ck(rt::state.displacement_deadline_active==on);
    ck(!query(3503)); // Same transaction query is idempotent.
    for(uint64_t now:{3503u,3503u,3504u,3505u}) {slot(2);ck(query(now)==on);}
    slot(2);ck(!query(3506));slot(2);ck(query(3506)==on);
    slot(-1);ck(query(3509)==on);slot(0);ck(!query(3509));
    slot(1);ck(query(3508)==on); // Backward/unknown epoch time fails closed.
    // An admitted wall attempt still consumes the slot; displacement is not ACK.
    loaded();slot(0);ck(!query(100));slot(2);ck(query(100)==on);
    // All four directions from actual FIELD1 permission, independent of raw cache.
    for(uint16_t dir:{uint16_t(0x1000),uint16_t(0x2000),uint16_t(0x4000),uint16_t(0x8000)}) {
        loaded();slot(-1);ck(rt::permits_field(outer,dir,dir,true,true)==on);
        deltas(dir);ck(query(400)==on);
    }
    // FIELD1 current/source rejection replaces and invalidates earlier raw proof.
    loaded();slot(-1);ck(!rt::permits_field(outer,0x8000,0x8000,false,true));ck(!query(400));
    loaded();slot(-1);ck(!rt::permits_field(outer,0x8000,0x8000,true,false));ck(!query(400));
    // An acknowledged apply rejected later leaves zero delta and reserves nothing.
    loaded();slot(0);deltas(0);ck(!query(400));ck(!rt::state.displacement_deadline_active);
    // Wrong actual direction cannot borrow the permission of another direction.
    loaded();slot(-1);deltas(0x4000);ck(!query(400));ck(!rt::state.displacement_deadline_active);
    // The original converter may emit action0 with a held movement delta.
    loaded();slot(-1,0);ck(query(400)==on);
    for(unsigned action:{1u,2u,7u,10u,11u,13u}) {
        loaded();slot(-1);put16(F,action);ck(!query(400));ck(ld16(F)==action);
    }
    // Every confirmation/cancel/shortcut bit remains protected, even with direction.
    for(uint16_t bit=8;bit<0x1000;bit<<=1) {
        loaded();slot(-1);ck(!rt::permits_field(outer,0x8000,0x8000|bit,true,true));ck(!query(400));
    }
    for(unsigned interval:{0u,1u,2u,4u,6u,255u}) {
        loaded();slot(1);put8(0x060FFC12,interval);ck(query(400)==on);
        ck(!rt::state.displacement_deadline_active);ck(ld8(0x060FFC12)==interval);
    }
    loaded();slot(-1);outer.r[14]=F+4;ck(!query(400));
    loaded();slot(-1);put8(rt::Gate,0);ck(!query(400));
    loaded();slot(0);ck(!query(400));rt::hard_boundary();ck(!rt::state.displacement_deadline_active);
    {auto c=converter();ck(!rt::permits(c));deltas(0x8000);put8(0x060FFC13,255);}
    ck(!query(400)); // Protected FF cannot regain permission.
    // Actual neutral clears the native stamp and removes the carry-only scope.
    loaded();slot(0);ck(!query(400));put8(rt::Gate,0);rt::neutral_post();
    ck(!rt::state.displacement_deadline_active);resource();slot(-1);ck(!query(400));
    // A new authorized scene cannot inherit the previous scene's deadline.
    loaded();slot(0);ck(!query(400));put16(rt::SceneChange,12);put16(rt::NextScene,9);
    ck(rt::scene_transition_start()==on);ck(!rt::state.displacement_deadline_active);
    // Overflow has no representable safe future deadline and fails closed.
    loaded();slot(0);const uint64_t max=std::numeric_limits<uint64_t>::max();
    ck(query(max-1)==on);ck(!rt::state.displacement_deadline_active);
    slot(0);ck(query(max)==on);ck(!rt::state.displacement_deadline_active);
    loaded();slot(0);ck(!query(max-3));slot(0);ck(query(max-3)==on);
    slot(0);ck(query(max)==on);slot(0);ck(query(0)==on);
    std::printf("PASS %u scene-debt admission checks; continuity=%d\n",checks,on);
}
