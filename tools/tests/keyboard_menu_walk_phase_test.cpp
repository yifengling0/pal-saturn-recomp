// Independent clock-domain regression: no SDL, ROM, guest source or runtime.
// The guest samples every six emulated VBlanks. A normal host present plus an
// extra field read can straddle that sample in the same VBlank.
#include "pal_keyboard_profile.h"
#include <cstdint>
#include <cstdlib>
#include <iostream>

using namespace pal_keyboard;
namespace {
unsigned cases = 0, checks = 0;
int sample_phase, field_phase, extra_reads, ack_delay;
bool sample_before;
uint16_t wanted;
void check(bool ok, const char* what) {
    ++checks;
    if (ok) return;
    std::cerr << "FAIL: " << what << " target=" << wanted
              << " sample_phase=" << sample_phase << " field_phase=" << field_phase
              << " sample_before=" << sample_before << " extra_reads=" << extra_reads
              << " ack_delay=" << ack_delay << '\n';
    std::exit(1);
}
WalkStep tick(MenuWalk& walk, uint64_t epoch, uint64_t vb) {
#ifdef PAL_MENU_WALK_LEGACY
    (void)vb; // Diagnostic red run against the unchanged pre-fix header.
    return walk.tick(epoch);
#else
    return walk.tick(epoch, vb);
#endif
}
void run_case() {
    ++cases;
    MenuWalk walk;
    walk.ask(wanted);
    uint64_t epoch = 17, ack_at = ~uint64_t(0);
    bool acknowledged = false, neutral_bx = false, neutral_xa = false;
    uint16_t live = 0, sampled = 0;
    unsigned b_edges = 0, x_edges = 0, a_edges = 0;
    unsigned b_frames = 0, x_frames = 0, a_frames = 0;
    auto acknowledge = [&](uint64_t vb) {
        if (!acknowledged && vb >= ack_at) { ++epoch; acknowledged = true; }
    };
    auto poll = [&](uint64_t vb) {
        acknowledge(vb);
        const auto step = tick(walk, epoch, 1000 + vb);
        live = step.bits;
        if (step.ask) menu_intent = uint16_t(walk.target + 1);
        check(live == 0 || live == Cancel || live == Menu || live == Confirm,
              "the walk never publishes overlapping buttons");
        check(live != Confirm || acknowledged, "confirm requires an actual new menu acknowledgement");
        return step;
    };
    auto sample = [&](uint64_t vb) {
        const uint16_t rising = uint16_t(live & ~sampled);
        if (!live && b_edges && !x_edges) neutral_bx = true;
        if (!live && x_edges && !a_edges) neutral_xa = true;
        if (rising & Cancel) ++b_edges;
        if (rising & Menu) {
            ++x_edges;
            check(neutral_bx, "the guest samples a release between cancel and open");
            ack_at = vb + uint64_t(ack_delay);
        }
        if (rising & Confirm) {
            ++a_edges;
            check(neutral_xa, "the guest samples a release between open and confirm");
        }
        sampled = live;
        acknowledge(vb);
    };
    for (uint64_t vb = 0; vb < 120; ++vb) {
        if (sample_before && int(vb % 6) == sample_phase) sample(vb);
        const auto first = poll(vb);
        b_frames += first.bits == Cancel;
        x_frames += first.bits == Menu;
        a_frames += first.bits == Confirm;
        if (!sample_before && int(vb % 6) == sample_phase) sample(vb);
        if (int(vb % 6) == field_phase) {
            for (int read = 0; read < extra_reads; ++read) {
                const auto extra = poll(vb);
                check(extra.bits == first.bits, "extra field polls cannot shorten any pulse");
                check(!extra.ask, "same-VBlank polls never re-arm a consumed intent");
            }
        }
    }
    check(b_frames == 7 && x_frames == 7 && a_frames == 7,
          "all three pulses last exactly seven emulated VBlanks");
    check(b_edges == 1 && x_edges == 1 && a_edges == 1,
          "every sample phase observes exactly one cancel, open and confirm edge");
    check(walk.target == MenuWalk::Idle && !live, "walk completes and stays released");
    walk.stop();
    check(menu_intent == 0, "cleanup never leaves a guest intent armed");
}
}
int main() {
    for (const auto target : {StatusEntry, ItemEntry, SystemEntry}) {
        wanted = target;
        for (sample_phase = 0; sample_phase < 6; ++sample_phase)
            for (field_phase = 0; field_phase < 6; ++field_phase)
                for (const bool before : {false, true}) {
                    sample_before = before;
                    for (const int reads : {1, 2, 17}) {
                        extra_reads = reads;
                        for (const int delay : {0, 1, 7, 35}) {
                            ack_delay = delay;
                            run_case();
                        }
                    }
                }
    }
    std::cout << "PASS: " << cases << " clock/sample phase cases, " << checks
              << " checks; no game or SDL execution\n";
}
