#include <array>
#include <cassert>
#include <cstdio>
#include "pal_release_runtime.h"
namespace rt=pal_release_runtime;
static std::array<uint8_t,0x100000> ram;
static unsigned checks;
uint32_t ld8(uint32_t a) { assert(a>=0x06000000 && a<0x06100000); return ram[a-0x06000000]; }
uint32_t ld16(uint32_t a) { return (uint16_t(ld8(a))<<8)|ld8(a+1); }
uint32_t ld32(uint32_t a) { return (uint32_t(ld16(a))<<16)|ld16(a+2); }
static void put16(uint32_t a,uint16_t v) { ram.at(a-0x06000000)=v>>8;ram.at(a+1-0x06000000)=v; }
static void ck(bool v) { ++checks; assert(v); }
static void reset(bool slot=true) {
    ram.fill(0);rt::field_enter();put16(rt::Scene,102);put16(rt::NextScene,103);
    put16(rt::Pad,0x7FFF);
    if(slot) rt::capture_field_frame(0x060FE000);
    rt::script_before();
}
static void scene() { put16(rt::SceneChange,12); }
static bool enter(uint32_t pc=0x0602B04A) {
    const auto before=ram;bool yes=rt::fade_before(pc);ck(before==ram);return yes;
}
static bool finish() {
    const auto before=ram;bool hard=rt::script_after();ck(before==ram);return hard;
}
int main() {
    const bool on=rt::enabled();
    // Natural portal: freeze before the first fade poll, no early scene token.
    reset();ck(enter()==on);ck(!rt::scene_soft());
    ck(rt::note_wait()==!on);ck(!rt::note_wait());
    scene();ck(!rt::can_scene_suspend()); // still inside the script/fade
    rt::fade_after();ck(!rt::can_scene_suspend());
    ck(finish()==!on);ck(rt::scene_soft()==on);ck(!rt::state.script_depth);
    // FIELD0 cannot adopt input first pressed or changed during the fade.
    reset();put16(rt::Pad,0xFFFF);ck(enter()==on);put16(rt::Pad,0x7FFF);
    rt::fade_after();scene();ck(!finish());ck(rt::state.scene_buttons==0);
    reset();ck(enter()==on);put16(rt::Pad,0xBFFF);rt::fade_after();scene();
    ck(!finish());ck(rt::state.scene_buttons==0);
    reset();ck(enter()==on);put16(rt::Pad,0xFFFF);rt::fade_after();scene();
    ck(!finish());ck(rt::state.scene_buttons==0);
    reset();ck(enter()==on);put16(rt::Pad,0x7BFF);rt::fade_after();scene();
    ck(!finish());ck(rt::state.scene_buttons==0);
    reset();put16(rt::Pad,0x7BFF);ck(enter()==on);put16(rt::Pad,0x7FFF);
    rt::fade_after();scene();ck(!finish());ck(rt::state.scene_buttons==0);
    reset();put16(rt::Pad,0x7FF8);ck(enter()==on);rt::fade_after();scene();
    ck(!finish());ck(rt::state.scene_buttons==(on ? 0x8000 : 0));
    // A no-op fade still froze host input and must discard it without a scene.
    reset();ck(enter()==on);rt::fade_after();ck(finish()==on);ck(!rt::scene_soft());
    // A real pure fade without scene also hard-clears, including deferred wait.
    reset();ck(enter()==on);ck(rt::note_wait()==!on);rt::fade_after();
    ck(finish());scene();ck(!rt::scene_transition_start());
    // Non-opcode80 caller gets no privilege even at the same fade function.
    reset();ck(!enter(0x0602179A));ck(rt::note_wait());rt::fade_after();scene();
    ck(finish());ck(!rt::scene_soft());
    // Initial entry and loader scripts do not extend this exception.
    reset(false);ck(!enter());ck(rt::note_wait());rt::fade_after();scene();ck(finish());
    reset();scene();rt::state.scene_depth=1;ck(!enter());ck(rt::note_wait());
    rt::fade_after();ck(finish());ck(!rt::scene_soft());rt::state.scene_depth=0;
    // An ordinary wait before or after the scoped fade is a sticky veto.
    reset();ck(rt::note_wait());ck(!enter());rt::fade_after();scene();ck(finish());ck(!rt::scene_soft());
    reset();ck(enter()==on);rt::fade_after();ck(rt::note_wait());scene();ck(finish());ck(!rt::scene_soft());
    // UI or an arbitrary hard boundary cannot be rescued by a later scene.
    reset();ck(enter()==on);rt::ui_before();rt::ui_after();rt::fade_after();scene();
    ck(finish());ck(!rt::scene_soft());
    reset();ck(enter()==on);rt::hard_boundary();rt::fade_after();
    rt::script_before();ck(finish());scene();ck(finish());ck(!rt::scene_soft());
    // A nested script's wait cannot borrow the outer exact fade's privilege.
    reset();ck(enter()==on);rt::script_before();ck(rt::note_wait());
    ck(finish());rt::fade_after();scene();ck(finish());ck(!rt::scene_soft());
    // A nested fade cannot borrow the outer exact scope either.
    reset();ck(enter()==on);ck(!enter());ck(rt::note_wait());
    rt::fade_after();rt::fade_after();scene();ck(finish());ck(!rt::scene_soft());
    // Inner script's own exact fade is deliberately conservative and hard.
    reset();rt::script_before();ck(!enter());ck(rt::note_wait());rt::fade_after();
    ck(finish());scene();ck(finish());ck(!rt::scene_soft());
    // Unknown or nested scopes veto a provisional fade even with no wait.
    reset();ck(enter()==on);ck(!enter());rt::fade_after();rt::fade_after();
    scene();ck(finish());ck(!rt::scene_soft());
    reset();ck(enter()==on);rt::fade_after();ck(!enter(0x0602179A));
    rt::fade_after();scene();ck(finish()==on);ck(!rt::scene_soft());
    reset();ck(enter()==on);rt::fade_after();rt::script_before();
    ck(finish()==on);scene();ck(finish()==on);ck(!rt::scene_soft());
    // Resource sync is still only resource sync. It does not poison a portal.
    reset();ck(enter()==on);rt::fade_after();
    {rt::ResourceScope resource(0x060327D4);ck(!rt::note_wait());}
    scene();ck(!finish());ck(rt::scene_soft()==on);
    // Sequential exact fades are paired; no leaked scope makes future waits safe.
    reset();ck(enter()==on);rt::fade_after();ck(enter()==on);
    ck(rt::note_wait()==!on);rt::fade_after();scene();ck(finish()==!on);ck(rt::scene_soft()==on);
    reset();rt::fade_after();scene();ck(finish());ck(!rt::scene_soft());
    std::printf("PASS %u fade-scope checks; continuity=%d\n",checks,on);
}
