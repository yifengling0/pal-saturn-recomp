// Portable integration of the actual field helper, release policy and ledger.
// All memory and host events below are invented fixtures. No ROM, generated
// guest instruction bodies, SDL, game data, renderer or device is required.
//
// Compile with src/pal_game, runtime/include, runtime/src/host and the test
// runner's minimal saturn/sh2.h on the include path. The runner must declare
// uint32_t ld8/ld16/ld32; the writable fixture functions are defined here.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <functional>
#include <map>
#include <utility>
#include <saturn/sh2.h>
#include "pal_field_input_ledger.h"

static std::map<uint32_t, uint8_t> memory;
uint32_t ld8(uint32_t a) { return memory[a]; }
uint32_t ld16(uint32_t a) { return (ld8(a) << 8) | ld8(a + 1); }
uint32_t ld32(uint32_t a) { return (ld16(a) << 16) | ld16(a + 2); }
void st8(uint32_t a, uint32_t v) { memory[a] = uint8_t(v); }
void st16(uint32_t a, uint32_t v) { st8(a, v >> 8); st8(a + 1, v); }
void st32(uint32_t a, uint32_t v) { st16(a, v >> 16); st16(a + 2, v); }
static uint64_t fixture_vblank = 1234;
uint64_t sat_vblanks() { return fixture_vblank; }

// Model the SDL host's ownership boundary, not SDL itself. Production ledger
// logic is used unchanged. Events queued during suspension must be drained
// before activation, and a queued hard boundary must veto that activation.
namespace pal_field_host {
Ledger fixture_ledger;
bool fixture_available = true;
unsigned hard_calls = 0, scene_calls = 0;
std::function<void()> queued = [] {};
void pump_fixture_events() {
    auto events = std::move(queued);
    queued = [] {};
    events();
}
bool available() { return fixture_available; }
void context(bool active, bool discard) {
    if (discard) ++hard_calls;
    if (active && !discard && fixture_ledger.scene_suspended()) {
        const auto epoch = fixture_ledger.epoch();
        pump_fixture_events();
        if (epoch != fixture_ledger.epoch() || !fixture_ledger.scene_suspended()) return;
    }
    fixture_ledger.context(active, discard);
}
void scene_suspend(bool preserve_existing_only) {
    ++scene_calls; fixture_ledger.scene_suspend(preserve_existing_only);
}
Read begin() { pump_fixture_events(); return fixture_ledger.begin(); }
bool current(const Read& read) { return fixture_ledger.current(read); }
bool acknowledge(const Read& read) { return fixture_ledger.acknowledge(read); }
} // namespace pal_field_host

#include "pal_field_input.h"
using namespace pal_field_host;
namespace field = pal_field_input;
namespace release = pal_release_runtime;
constexpr uint16_t Up = 0x1000, Left = 0x4000;
constexpr uint64_t Key = (uint64_t(1) << 60) | 79;
static SH2Context c;
static unsigned cases;

static void reset(bool live = true) {
    memory.clear(); fixture_vblank = 1234;
    fixture_ledger = Ledger{};
    fixture_available = live;
    hard_calls = scene_calls = 0;
    queued = [] {};
    field::state = {};
    release::state = {};
    c = {};
    c.r[14] = 0x06001000;
    st16(field::Scene, 1);
    st16(release::NextScene, 2);
    st16(release::Pad, 0xFFFF);
    field::enter();
}
static void field_slot() {
    // Exact planner order: reconcile the host before freezing gate provenance.
    field::begin();
    release::capture_field_frame(c.r[14]);
}
static void apply() {
    // Model completion of the pinned converter observation. Separate release
    // runtime tests validate its real stack-layout guards; no guest body is
    // copied or executed here. The actual permits_field() still runs below.
    release::state.converter_seen = true;
    st16(c.r[14], 0);
    field::apply(c);
}
static void hold() {
    fixture_ledger.observe(Key, Up, true);
    st16(release::Pad, uint16_t(~Up));
}
static bool moved() { return ld16(field::DeltaX) || ld16(field::DeltaY); }
static void established_hold() {
    reset(); field_slot(); hold(); field_slot(); apply(); assert(moved());
}
static void trigger_scene() {
    field::script_before();
    st16(field::SceneChange, 1);
    field::script_after();
}
static void loader(bool script_wait = false, bool resource_wait = false) {
    {
        release::SceneScope scene(0x06026DAEu);
        field::scene_clear();
        const auto frame = c.r[14];
        c.r[14] = 0x06002000;
        st32(c.r[14] + 4, 0x06026DAEu);
        release::writer_pre(c, 0x06026FACu);
        st8(field::ReleaseGate, 0xFF);
        c.r[14] = frame;
        if (script_wait || resource_wait) {
            release::ScriptScope script;
            if (resource_wait) {
                release::ResourceScope resource(0x060327D4u);
                field::note_wait();
            } else field::note_wait();
        }
        st16(field::Scene, ld16(release::NextScene));
        st16(field::SceneChange, 0);
    }
    // The natural field loop processes its ordinary callback after loading.
    field::script_before();
    field::script_after();
}
static void resource_ff(bool wait = false) {
    field::script_before();
    {
        release::ResourceScope resource(0x060327D4u);
        const auto frame = c.r[14];
        c.r[14] = 0x06002000;
        st32(c.r[14] + 12, 0x060327D4u);
        release::writer_pre(c, 0x060323B8u);
        st8(field::ReleaseGate, 0xFF);
        c.r[14] = frame;
        if (wait) field::note_wait();
    }
    field::script_after();
}
static void fade_script(bool request_scene = true, bool wait = true,
                        const std::function<void()>& during = [] {}) {
    field::script_before();
    {
        // This scope surrounds the entire original call, including its poll.
        field::FadeScope fade(0x0602B04Au);
        during();
        if (wait) field::note_wait();
    }
    if (request_scene) st16(field::SceneChange, 1);
    field::script_after();
}
static void arrive_scene() {
    established_hold(); trigger_scene(); loader(); field_slot(); apply(); assert(moved());
}
static void reveal_script(bool wait = true, const std::function<void()>& during = [] {},
                          uint32_t caller = 0x06026E88u) {
    field::script_before();
    {
        field::RevealScope reveal(caller);
        during();
        if (wait) field::note_wait();
    }
    field::script_after();
}
static void run(const char* name, const std::function<void()>& body) {
    body(); ++cases; std::printf("PASS %s\n", name);
}
static void disabled_comparison() {
    reset(); assert(fixture_ledger.active());
    field_slot(); hold(); field_slot(); apply(); assert(moved());
    field::script_before();
    { release::ResourceScope resource(0x060327D4u); field::note_wait(); }
    assert(!fixture_ledger.active());
    field::script_after(); field_slot(); apply(); assert(!moved());
    fixture_ledger.release(Key); hold(); field_slot();
    st8(field::ReleaseGate, 0xFF); apply(); assert(!moved());
    assert(!release::scene_soft());

    reset(); field_slot(); hold(); const auto scenes = scene_calls;
    field::script_before();
    {
        field::FadeScope fade(0x0602B04Au);
        assert(fixture_ledger.active() && scene_calls == scenes);
        field::note_wait(); assert(!fixture_ledger.active());
    }
    field::script_after();
    reset(); field_slot(); hold(); const auto before_reveal = scene_calls;
    field::script_before();
    {
        field::RevealScope reveal(0x06026E88u);
        assert(fixture_ledger.active() && scene_calls == before_reveal);
        field::note_wait(); assert(!fixture_ledger.active());
    }
    field::script_after();
    std::puts("PASS disabled: initial activation, resource/fade hard wait, FF rejection");
}
int main() {
    if (!field::WalkCadence::enabled()) {
        field::WalkCadence cadence;
        Read r{}; r.active=true; r.held=r.direction=Up; r.source=Key; r.press_seq=1;
        for (unsigned i=0;i<1000;++i) assert(cadence.next(r,true)==3);
        std::puts("PASS original/unknown cadence fail-closed"); return 0;
    }
    if (!release::enabled()) { disabled_comparison(); return 0; }
    run("initial entry cannot borrow scene permission", [] {
        reset(); assert(!fixture_ledger.active()); assert(!release::can_scene_suspend());
    });
    run("continuous hold spans scene and successive FF decisions", [] {
        established_hold(); trigger_scene();
        assert(!fixture_ledger.active() && release::scene_soft());
        loader(); assert(fixture_ledger.active() && !release::scene_soft());
        field_slot(); assert(field::state.read.scene_held); apply(); assert(moved());
        assert(ld8(field::ReleaseGate) == 0xFF);
        field_slot(); apply(); assert(moved());
    });
    run("release during scene stops movement", [] {
        established_hold(); trigger_scene(); fixture_ledger.release(Key);
        st16(release::Pad, 0xFFFF); loader(); field_slot(); apply(); assert(!moved());
    });
    run("repress during scene is a new ineligible contact", [] {
        established_hold(); trigger_scene(); fixture_ledger.release(Key);
        fixture_ledger.observe(Key, Up, true); loader(); field_slot(); apply(); assert(!moved());
    });
    run("loader script wait revokes scene permission", [] {
        established_hold(); trigger_scene(); loader(true); field_slot(); apply();
        assert(!moved() && !release::state.carry_required);
    });
    run("loader resource sync preserves genuine hold", [] {
        established_hold(); trigger_scene(); loader(false, true);
        field_slot(); apply(); assert(moved());
    });
    run("guest UI during scene remains hard", [] {
        established_hold(); trigger_scene(); field::ui_before(); field::ui_after();
        loader(); field_slot(); apply(); assert(!moved());
    });
    run("release between frozen read and apply is rejected", [] {
        established_hold(); trigger_scene(); loader(); field_slot();
        fixture_ledger.release(Key); st16(release::Pad, 0xFFFF); apply(); assert(!moved());
    });
    run("held confirm cannot accompany scene direction", [] {
        established_hold(); trigger_scene(); loader();
        st16(release::Pad, uint16_t(~(Up | 0x10))); field_slot(); apply(); assert(!moved());
    });
    run("original neutral acknowledgement permits a fresh gesture", [] {
        established_hold(); field::ui_before(); field::ui_after();
        st8(field::ReleaseGate, 0); release::neutral_post();
        fixture_ledger.release(Key); field_slot(); hold(); field_slot(); apply(); assert(moved());
    });
    run("FIELD0 never grants scene continuation", [] {
        reset(false); field_slot(); assert(release::state.seen_slot);
        st16(release::Pad, uint16_t(~Up)); trigger_scene(); assert(!release::enabled() && !release::scene_soft());
        loader(); assert(!release::scene_soft() && !scene_calls);
    });
    run("FIELD0 script wait stays hard", [] {
        reset(false); field_slot(); field::script_before(); field::note_wait(); field::script_after();
        assert(!release::state.in_field && !release::can_scene_suspend());
    });
    run("FIELD0 UI scope stays hard", [] {
        reset(false); field_slot(); field::ui_before(); field::ui_after();
        assert(!release::state.in_field);
    });
    run("FIELD0 nonmovement action stays hard", [] {
        reset(false); field_slot(); st16(c.r[14], 7); field::apply(c);
        assert(!release::state.in_field);
    });
    run("same-cardinal raw change invalidates frozen continuation", [] {
        established_hold(); trigger_scene(); loader(); field_slot();
        fixture_ledger.observe(Key, Up | 0x8000); apply(); assert(!moved());
    });
    run("resource FF accepts an existing hold without scene token", [] {
        established_hold(); resource_ff(true); field_slot();
        assert(!field::state.read.scene_held); apply(); assert(moved());
    });
    run("resource FF accepts fresh pending input only while held", [] {
        reset(); field_slot(); resource_ff(); hold(); field_slot();
        assert(field::state.read.pending && field::state.read.held); apply(); assert(moved());
    });
    run("released pending input cannot bypass resource FF", [] {
        reset(); field_slot(); resource_ff(); hold(); fixture_ledger.release(Key);
        st16(release::Pad, 0xFFFF); field_slot();
        assert(field::state.read.pending && !field::state.read.held); apply(); assert(!moved());
    });
    run("resource cannot revive a genuinely waiting script", [] {
        established_hold(); field::script_before(); field::note_wait(); resource_ff();
        field::script_after(); field_slot(); apply(); assert(!moved());
    });
    run("scene discards a released old pending tap", [] {
        reset(); field_slot(); hold(); fixture_ledger.release(Key); st16(release::Pad, 0xFFFF);
        trigger_scene(); loader(); field_slot(); apply();
        assert(!moved() && !field::state.read.pending);
    });
    run("fade freezes before its first poll and wait", [] {
        established_hold(); fade_script(true, true, [] {
            assert(!fixture_ledger.active() && fixture_ledger.scene_suspended());
        });
        assert(release::scene_soft()); loader(); field_slot();
        assert(field::state.read.scene_held); apply(); assert(moved() && scene_calls >= 3);
    });
    run("fade immediately discards an old pending tap", [] {
        reset(); field_slot(); hold(); fixture_ledger.release(Key); st16(release::Pad, 0xFFFF);
        fade_script(true, true, [] { assert(!fixture_ledger.begin().pending); });
        loader(); field_slot(); apply(); assert(!moved());
    });
    for (unsigned change = 0; change < 5; ++change) {
        run("fade release/change/repress/new identity never upgrades", [change] {
            established_hold(); fade_script(true, true, [change] {
                if (change == 0) { fixture_ledger.release(Key); st16(release::Pad, 0xFFFF); }
                if (change == 1) { fixture_ledger.observe(Key, Left); st16(release::Pad, uint16_t(~Left)); }
                if (change == 2) { fixture_ledger.release(Key); fixture_ledger.observe(Key, Up, true); }
                if (change == 3) fixture_ledger.observe(Key, Up, true);
                if (change == 4) { fixture_ledger.cancel(Key); fixture_ledger.observe(Key + 1, Up, true); }
            });
            loader(); field_slot(); apply(); assert(!moved());
        });
    }
    run("first press during fade is not carried", [] {
        reset(); field_slot(); fade_script(true, true, [] { hold(); });
        loader(); field_slot(); apply(); assert(!moved());
    });
    run("new fade-time source cannot replace surviving original source", [] {
        established_hold(); fade_script(true, true, [] { fixture_ledger.observe(Key + 1, Left, true); });
        loader(); field_slot(); assert(field::state.read.source == Key); apply(); assert(moved());
    });
    for (bool wait : {false, true}) {
        run("fade without actual scene always hard-clears", [wait] {
            established_hold(); const auto hard = hard_calls; fade_script(false, wait);
            assert(hard_calls > hard); field_slot(); apply(); assert(!moved());
        });
    }
    run("no-wait fade may carry only after a real scene request", [] {
        established_hold(); fade_script(true, false); loader(); field_slot(); apply(); assert(moved());
    });
    run("UI during fade cannot gain scene permission later", [] {
        established_hold(); fade_script(true, true, [] { field::ui_before(); field::ui_after(); });
        loader(); field_slot(); apply(); assert(!moved());
    });
    run("host hard boundary during fade revokes continuation", [] {
        established_hold(); fade_script(true, true, [] { fixture_ledger.context(false, true); });
        loader(); field_slot(); apply(); assert(!moved());
    });
    run("wait outside the exact fade cannot gain permission later", [] {
        established_hold(); field::script_before();
        { field::FadeScope fade(0x0602B04Au); field::note_wait(); }
        field::note_wait(); st16(field::SceneChange, 1); field::script_after();
        loader(); field_slot(); apply(); assert(!moved());
    });
    run("nested no-wait fade fails closed", [] {
        established_hold(); fade_script(true, false, [] { field::FadeScope nested(0xDEADu); });
        loader(); field_slot(); apply(); assert(!moved());
    });
    run("hard script return reaches host before local-depth early return", [] {
        reset(); field_slot(); hold(); field::script_before(); field::script_before();
        release::hard_boundary(); field::script_after();
        assert(field::state.script_depth == 1 && !fixture_ledger.active()); field::script_after();
    });
    run("one-shot reveal carries the same scene hold and repeated FF slots", [] {
        arrive_scene(); assert(release::state.scene_reveal_pending);
        reveal_script(true, [] { assert(!fixture_ledger.active()); assert(release::reveal_requires_scene_held()); });
        assert(!release::state.scene_reveal_pending && fixture_ledger.active());
        field_slot(); apply(); assert(moved()); field_slot(); apply(); assert(moved());
    });
    run("reveal cannot upgrade a new active source after scene", [] {
        arrive_scene(); fixture_ledger.release(Key); hold(); field_slot(); apply(); assert(!moved());
        reveal_script(); field_slot(); apply(); assert(!moved());
    });
    run("reveal preserves only original source beside a newer active source", [] {
        arrive_scene(); fixture_ledger.observe(Key + 1, Left, true);
        reveal_script(); field_slot(); assert(field::state.read.source == Key); apply(); assert(moved());
    });
    run("true neutral permits a legitimate fresh field hold across reveal", [] {
        arrive_scene(); fixture_ledger.release(Key); st16(release::Pad, 0xFFFF);
        st8(field::ReleaseGate, 0); release::neutral_post(); hold(); field_slot(); apply(); assert(moved());
        reveal_script(true, [] { assert(!release::reveal_requires_scene_held()); });
        field_slot(); apply(); assert(moved());
    });
    for (unsigned change = 0; change < 3; ++change) {
        run("release/change/repress during reveal cannot survive", [change] {
            arrive_scene(); reveal_script(true, [change] {
                if (change == 0) { fixture_ledger.release(Key); st16(release::Pad, 0xFFFF); }
                if (change == 1) { fixture_ledger.observe(Key, Left); st16(release::Pad, uint16_t(~Left)); }
                if (change == 2) { fixture_ledger.release(Key); fixture_ledger.observe(Key, Up, true); }
            });
            field_slot(); apply(); assert(!moved());
        });
    }
    run("first DOWN during reveal is not captured", [] {
        arrive_scene(); fixture_ledger.release(Key);
        reveal_script(true, [] { hold(); }); field_slot(); apply(); assert(!moved());
    });
    run("queued reveal DOWN plus UP never becomes a pending tap", [] {
        arrive_scene(); fixture_ledger.release(Key);
        queued = [] { hold(); fixture_ledger.release(Key); st16(release::Pad, 0xFFFF); };
        reveal_script(); field_slot(); assert(!field::state.read.pending); apply(); assert(!moved());
    });
    run("host hard event during reveal revokes continuity", [] {
        arrive_scene(); reveal_script(true, [] { fixture_ledger.context(false, true); });
        field_slot(); apply(); assert(!moved());
    });
    run("guest UI during reveal revokes the ticket and host", [] {
        arrive_scene(); reveal_script(true, [] { field::ui_before(); field::ui_after(); });
        field_slot(); apply(); assert(!moved());
    });
    run("nested no-wait reveal cannot borrow the outer ticket", [] {
        arrive_scene(); reveal_script(false, [] { field::RevealScope nested(0x06026E88u); });
        field_slot(); apply(); assert(!moved());
    });
    run("second reveal wait has no reusable exemption", [] {
        arrive_scene(); reveal_script(); field_slot(); apply(); assert(moved());
        reveal_script(); field_slot(); apply(); assert(!moved());
    });
    run("wrong reveal caller consumes ticket without granting permission", [] {
        arrive_scene(); reveal_script(false, [] {}, 0xDEADu);
        assert(!release::state.scene_reveal_pending); reveal_script(); field_slot(); apply(); assert(!moved());
    });
    run("scene change during reveal is hard and cannot be upgraded", [] {
        arrive_scene(); reveal_script(false, [] { st16(field::SceneChange, 1); });
        assert(!release::scene_soft()); loader(); field_slot(); apply(); assert(!moved());
    });
    run("scene identity change during reveal is hard", [] {
        arrive_scene(); reveal_script(false, [] { st16(field::Scene, 3); });
        field_slot(); apply(); assert(!moved());
    });
    run("ordinary E84 without a ticket and without a wait stays ordinary", [] {
        established_hold(); const auto scenes = scene_calls;
        reveal_script(false); assert(scene_calls == scenes); field_slot(); apply(); assert(moved());
    });
    run("ordinary E84 wait without a ticket remains hard", [] {
        established_hold(); reveal_script(); field_slot(); apply(); assert(!moved());
    });
    run("UI between scene and E84 cancels the one-shot ticket", [] {
        arrive_scene(); field::ui_before(); field::ui_after();
        assert(!release::state.scene_reveal_pending); reveal_script(); field_slot(); apply(); assert(!moved());
    });
    run("negative scene debt changes only displacement, not interval or action", [] {
        arrive_scene(); field_slot(); apply(); assert(moved());
        st8(0x060FFC12, 3); st8(0x060FFC13, uint8_t(-40));
        const auto regs = c; const auto action = ld16(c.r[14]);
        const auto accepted = field::state.accepted;
        field::filter_scene_debt(c);
        assert(!moved() && ld16(c.r[14]) == action);
        for (unsigned i=0;i<16;++i) assert(c.r[i] == regs.r[i]);
        assert(c.pr == regs.pr && ld8(0x060FFC12) == 3 && ld8(0x060FFC13) == 216);
        assert(field::state.accepted == accepted && !fixture_ledger.begin().pending);
    });
    run("recovered scene admits once then follows original interval", [] {
        arrive_scene(); st8(0x060FFC12,3); st8(0x060FFC13,0);
        field_slot(); apply(); field::filter_scene_debt(c); assert(moved());
        field_slot(); apply(); field::filter_scene_debt(c); assert(!moved());
        fixture_vblank += 2; field_slot(); apply(); field::filter_scene_debt(c); assert(!moved());
        ++fixture_vblank; field_slot(); apply(); field::filter_scene_debt(c); assert(moved());
    });
    run("negative slots do not accumulate future displacement", [] {
        arrive_scene(); st8(0x060FFC12,3); st8(0x060FFC13,uint8_t(-40));
        for (unsigned i=0;i<20;++i) {field_slot(); apply(); field::filter_scene_debt(c); assert(!moved());}
        st8(0x060FFC13,0); field_slot(); apply(); field::filter_scene_debt(c); assert(moved());
        field_slot(); apply(); field::filter_scene_debt(c); assert(!moved());
    });
    run("release during debt leaves no queued step", [] {
        arrive_scene(); st8(0x060FFC12,3); st8(0x060FFC13,uint8_t(-2));
        field_slot(); apply(); field::filter_scene_debt(c); assert(!moved());
        fixture_ledger.release(Key); st16(release::Pad,0xFFFF);
        st8(0x060FFC13,0); fixture_vblank += 20;
        field_slot(); apply(); field::filter_scene_debt(c); assert(!moved());
        assert(!fixture_ledger.begin().pending);
    });
    run("ordinary field and resource inputs are outside scene debt limiter", [] {
        established_hold(); st8(0x060FFC12,3); st8(0x060FFC13,uint8_t(-40));
        field::filter_scene_debt(c); assert(moved());
        resource_ff(); field_slot(); apply(); assert(moved()); field::filter_scene_debt(c); assert(moved());
    });
    run("real neutral ends the prior scene movement stamp", [] {
        arrive_scene(); st8(0x060FFC12,3); st8(0x060FFC13,0);
        field_slot(); apply(); field::filter_scene_debt(c); assert(moved());
        fixture_ledger.release(Key); st16(release::Pad,0xFFFF); st8(field::ReleaseGate,0);
        release::neutral_post(); hold(); field_slot(); apply(); assert(moved());
        field::filter_scene_debt(c); assert(moved());
    });
    run("gentle cadence repeats 18 VB in five slots and keeps fresh edges at3", [] {
        field::WalkCadence cadence;
        Read r{}; r.active=true; r.held=r.direction=Up; r.source=Key; r.press_seq=1;
        r.pending=true; assert(cadence.next(r,true)==3); r.pending=false;
        for (unsigned cycle=0;cycle<100;++cycle) {
            unsigned total=0;
            for (unsigned expected : {4u,4u,3u,4u,3u}) {
                const auto interval=cadence.next(r,true);
                assert(interval==expected); total+=interval;
            }
            assert(total==18);
        }
        r.direction=r.held=Left; r.pending=true; ++r.press_seq;
        assert(cadence.next(r,true)==3);
        r.pending=false; assert(cadence.next(r,true)==4);
        r.pending=true; ++r.press_seq; assert(cadence.next(r,true)==3);
    });
    run("release collision and different sources never owe slow phase", [] {
        field::WalkCadence cadence;
        Read r{}; r.active=true; r.held=r.direction=Up; r.source=Key; r.press_seq=1;
        assert(cadence.next(r,true)==3); assert(cadence.next(r,true)==4);
        r.held=0; assert(cadence.next(r,true)==3);
        r.held=Up; ++r.press_seq; assert(cadence.next(r,true)==3);
        assert(cadence.next(r,false)==3); assert(cadence.next(r,true)==3);
        ++r.source; assert(cadence.next(r,true)==3);
        r.scene_held=true; assert(cadence.next(r,true)==3);
        r.scene_held=false; assert(cadence.next(r,true)==3);
        r.active=false; assert(cadence.next(r,true)==3);
        r.active=true; assert(cadence.next(r,true)==3);
    });
    run("outcome changes only successful continuous field wait interval", [] {
        established_hold();
        const auto finish = [](bool displace=true) {
            st8(0x060FFC12,3);
            if (displace) st16(field::PlayerX,ld16(field::PlayerX)+16);
            field::outcome();
        };
        finish(); assert(ld8(0x060FFC12)==3); field::wait_after();
        fixture_vblank+=3; field_slot(); apply();
        const auto before=memory; const auto regs=c;
        finish(); assert(ld8(0x060FFC12)==4);
        for (unsigned i=0;i<16;++i) assert(c.r[i]==regs.r[i]);
        for (const auto& [address,value] : memory) {
            if (address==0x060FFC12 || address==field::PlayerX || address==field::PlayerX+1) continue;
            auto it=before.find(address); assert(value==(it==before.end()?0:it->second));
        }
        field::wait_after(); assert(ld8(0x060FFC12)==3);
        field::wait_after(); assert(ld8(0x060FFC12)==3);
        fixture_vblank+=4; field_slot(); apply(); finish(false);
        assert(ld8(0x060FFC12)==3);
        fixture_ledger.release(Key); field_slot(); apply(); finish(false);
        assert(ld8(0x060FFC12)==3 && !moved());
    });
    run("scene carry script and UI never install gentle interval", [] {
        arrive_scene(); field_slot(); apply();
        st8(0x060FFC12,3); st16(field::PlayerX,ld16(field::PlayerX)+16);
        field::outcome(); assert(ld8(0x060FFC12)==3);
        established_hold(); st8(0x060FFC12,3);
        st16(field::PlayerX,16); field::outcome();
        field_slot(); apply(); ++field::state.script_depth;
        st16(field::PlayerX,32); field::outcome(); assert(ld8(0x060FFC12)==3);
        --field::state.script_depth; field_slot(); apply(); ++field::state.ui_depth;
        st16(field::PlayerX,48); field::outcome(); assert(ld8(0x060FFC12)==3);
    });
    run("non-live and unrecognized modes keep original interval", [] {
        reset(false); st8(0x060FFC12,6); field::outcome(); assert(ld8(0x060FFC12)==6);
        established_hold(); st16(field::PlayerX,16); st8(0x060FFC12,3); field::outcome();
        field_slot(); apply(); st8(0x060FFC12,2); st16(field::PlayerX,32);
        field::outcome(); assert(ld8(0x060FFC12)==2);
        field::wait_after(); assert(ld8(0x060FFC12)==2);
    });
    assert(cases == 67);
    std::printf("PASS %u field/scene integration cases (synthetic memory and host)\n", cases);
}
