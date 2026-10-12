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
int main() {
    const bool on=rt::enabled();
    reset(); resource(); auto c=converter();
    ck(pure([&]{return rt::permits(c);})==on);
    SH2Context outer;outer.r[14]=F;
    ck(rt::permits_field(outer,0x8000,0x8000,true,false)==on);
    ck(!rt::permits_field(outer,0x8000,0x8000,false,false));
    ck(!rt::permits_field(outer,0x8000,0,true,false));
    ck(!rt::permits_field(outer,0x8000,0x8400,true,false));
    ck(rt::permits_field(outer,0x8000,0x8007,true,false)==on); // unused low3 bits
    c=converter(0x8007);ck(rt::permits(c)==on);
    c=converter(); put32(C+24,0x06022E9C);ck(!rt::permits(c));
    c=converter(); put32(C+28,F+4);ck(!rt::permits(c));
    c=converter(); put32(C+8,F+4);ck(!rt::permits(c));
    c=converter(); put32(C,pal_field_release::DeltaX+2);ck(!rt::permits(c));
    c=converter(); put32(C+4,pal_field_release::DeltaY+2);ck(!rt::permits(c));
    c=converter(0x8400,0);ck(!rt::permits(c)); // confirm mixed with direction
    for(auto action:{1u,2u,7u,10u,11u,13u}) {c=converter(0x8000,action);ck(!rt::permits(c));ck(ld16(F)==action);}
    c=converter(); rt::hard_boundary();ck(!rt::permits(c));resource();c=converter();ck(!rt::permits(c));
    put8(rt::Gate,0);pure([]{rt::neutral_post();return 0;});resource();c=converter();ck(rt::permits(c)==on);
    reset();write(0x0602C384,0);resource();c=converter();ck(!rt::permits(c));
    reset();resource(0x0602A88C);c=converter();ck(!rt::permits(c));
    reset(); c=converter();
    rt::script_before();
    {rt::ResourceScope a(0x060327D4);ck(!rt::note_wait());
     {rt::ResourceScope b(0x060327D4);write(0x060323B8,0x060327D4);ck(!rt::note_wait());}}
    rt::script_after();c=converter();ck(rt::permits(c)==on);
    rt::script_before();ck(rt::note_wait());ck(rt::protected_scope());
    {rt::ResourceScope a(0x060327D4);ck(!rt::note_wait());write(0x060323B8,0x060327D4);}
    rt::script_after();c=converter();ck(!rt::permits(c));

    reset(); // No natural field slot: initial game/title/save entry cannot carry.
    put16(rt::SceneChange,1);put16(rt::NextScene,8);ck(!rt::scene_transition_start());
    reset();c=converter();put16(rt::SceneChange,1);put16(rt::NextScene,8);
    ck(rt::scene_transition_start()==on);
    {rt::SceneScope scene(0x06026DAE);write(0x06026FAC,0x06026DAE);put16(rt::Scene,8);
     ck(!rt::note_wait()); // Ordinary scene/render wait is not a script wait.
     {rt::ScriptScope script;{rt::ResourceScope resource(0x060327D4);ck(!rt::note_wait());}}
     put16(rt::SceneChange,0);}
    ck(rt::scene_soft()==on);ck(rt::scene_transition_end()==on);ck(!rt::scene_soft());
    c=converter();ck(rt::permits(c)==on);
    ck(!rt::permits_field(outer,0x8000,0x8000,true,false));
    ck(rt::permits_field(outer,0x8000,0x8000,true,true)==on);
    c=converter(0x4000,5);put16(C+14,uint16_t(-1));put16(C+16,uint16_t(-1));ck(!rt::permits(c));
    put8(rt::Gate,0);rt::neutral_post();resource();c=converter();ck(rt::permits(c)==on);
    // Loading script genuine wait revokes the token; subsequent resource cannot upgrade FF.
    reset();c=converter();put16(rt::SceneChange,1);put16(rt::NextScene,8);rt::scene_transition_start();
    {rt::SceneScope scene(0x06026DAE);write(0x06026FAC,0x06026DAE);put16(rt::Scene,8);
     {rt::ScriptScope script;ck(rt::note_wait());resource();}
     put16(rt::SceneChange,0);}
    ck(!rt::scene_soft());ck(!rt::scene_transition_end());c=converter();ck(!rt::permits(c));
    reset();resource();c=converter();rt::ui_before();rt::ui_after();ck(!rt::permits(c));
    std::printf("PASS %u read-only wrapper checks; continuity=%d\n",checks,on);
}
