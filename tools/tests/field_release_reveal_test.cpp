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
static bool loaded(bool on) {
    reset();auto c=converter();put16(rt::SceneChange,12);put16(rt::NextScene,8);
    ck(rt::scene_transition_start()==on);
    {rt::SceneScope scene(0x06026DAE);write(0x06026FAC,0x06026DAE);
     put16(rt::Scene,8);put16(rt::SceneChange,0);}
    ck(rt::scene_transition_end()==on);ck(rt::state.scene_reveal_pending==on);
    c=converter();ck(rt::permits(c)==on);return on;
}
static bool reveal(uint32_t pc=0x06026E88) {
    return pure([&]{return rt::reveal_before(pc);});
}
static bool end_script() { return pure([] {return rt::script_after();}); }
int main() {
    const bool on=rt::enabled();
    // A completed scene authorizes exactly its natural post-move reveal.
    loaded(on);rt::script_before();ck(reveal()==on);ck(!rt::state.scene_reveal_pending);
    ck(rt::reveal_requires_scene_held()==on);ck(rt::note_wait()==!on);ck(!rt::note_wait());
    rt::reveal_after();ck(end_script()==!on);auto c=converter();ck(rt::permits(c)==on);
    // Same visual function's next invocation is not permanently exempt.
    rt::script_before();ck(!reveal());ck(rt::note_wait());rt::reveal_after();
    ck(end_script());c=converter();ck(!rt::permits(c));
    // Valid no-op reveal also consumes the one-shot ticket and balances.
    loaded(on);rt::script_before();ck(reveal()==on);rt::reveal_after();
    ck(!end_script());ck(!rt::state.scene_reveal_pending);
    // Real neutral retires carry identity but never bypasses confirmation bits.
    loaded(on);put8(rt::Gate,0);rt::neutral_post();rt::script_before();
    ck(reveal()==on);ck(!rt::reveal_requires_scene_held());rt::reveal_after();ck(!end_script());
    resource();c=converter(0x8400,0);ck(!rt::permits(c));
    // UI, hard, wrong caller, scene replacement and nested scope veto tickets.
    loaded(on);rt::ui_before();rt::ui_after();rt::script_before();ck(!reveal());
    ck(rt::note_wait());rt::reveal_after();ck(end_script());ck(!rt::state.scene_reveal_pending);
    loaded(on);rt::hard_boundary();rt::script_before();ck(!reveal());
    ck(rt::note_wait());rt::reveal_after();ck(end_script());
    loaded(on);rt::script_before();ck(!reveal(0x0602B08E));rt::reveal_after();ck(end_script()==on);
    loaded(on);rt::script_before();put16(rt::Scene,9);ck(!reveal());rt::reveal_after();ck(end_script()==on);
    loaded(on);rt::script_before();ck(reveal()==on);put16(rt::SceneChange,12);
    rt::reveal_after();ck(end_script()==on);ck(!rt::scene_soft());
    loaded(on);rt::script_before();ck(reveal()==on);ck(!reveal());
    rt::reveal_after();rt::reveal_after();ck(end_script());ck(!rt::scene_soft());
    loaded(on);rt::script_before();ck(reveal()==on);rt::script_before();
    ck(end_script()==on);rt::reveal_after();ck(end_script()==on);
    loaded(on);rt::script_before();ck(reveal()==on);ck(!rt::fade_before(0x0602B04A));
    rt::fade_after();rt::reveal_after();ck(end_script()==on);
    // A script wait before/after the exact call is still hard.
    loaded(on);rt::script_before();ck(rt::note_wait());ck(!reveal());rt::reveal_after();ck(end_script());
    loaded(on);rt::script_before();ck(reveal()==on);rt::reveal_after();ck(rt::note_wait());ck(end_script());
    // An unmatched reveal lifetime fails closed.
    loaded(on);rt::script_before();rt::reveal_after();ck(end_script());
    std::printf("PASS %u one-shot reveal checks; continuity=%d\n",checks,on);
}
