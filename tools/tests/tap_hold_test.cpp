// Deterministic proof for pal_tap_hold.h: what a press costs the game in VBlanks, and what the host
// owes it back. No ROM, no window, no SDL.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include "pal_tap_hold.h"

// The pad bits a test names, as host.h lays them out.
static const uint16_t Down = 1u << 13, Up = 1u << 12, Left = 1u << 14, Right = 1u << 15;
static const uint16_t Moving = Down | Up | Left | Right;
static const uint16_t Y = 1u << 5, C = 1u << 9;

int main(int argc, char** argv) {
    PalTapHold taps;
    if (argc > 1) {   // PAL_TAP_HOLD=0: the game sees exactly what the controllers report
        taps.press(Y);
        assert(taps.publish(0, 5, Moving) == 0);
        assert((taps.publish(C, 6, Moving) & C) == C);
        assert(taps.publish(0, 7, Moving) == 0);
        printf("PASS: PAL_TAP_HOLD=%s publishes the polled state alone\n", argv[1]);
        return 0;
    }
    assert(taps.publish(0, 0, Moving) == 0);

    // A tap the polls never met: the event alone has to put it in front of the game, and a button
    // that only answers a box then stays for the margin.
    taps.press(Y);
    for (uint64_t vblank = 10; vblank < 10 + kPalMinPressVblanks; ++vblank)
        assert((taps.publish(0, vblank, Moving) & Y) == Y);
    assert((taps.publish(0, 10 + kPalMinPressVblanks, Moving) & Y) == 0);

    // A direction travels the hero every frame it is published, so it is held only to the measured
    // minimum the game notices, never a frame more.
    taps.press(Right);
    assert((taps.publish(0, 20, Moving) & Right) == Right);
    assert((taps.publish(0, 21, Moving) & Right) == Right);
    assert((taps.publish(0, 22, Moving) & Right) == 0);

    // A press the host did poll counts from the frame it appeared on, for the same length.
    assert((taps.publish(C, 30, Moving) & C) == C);
    assert((taps.publish(0, 31, Moving) & C) == C);
    assert((taps.publish(0, 32, Moving) & C) == C);
    assert((taps.publish(0, 33, Moving) & C) == 0);

    // A long press gets no tail: it ends when the player let go, so held buttons never pile up.
    for (uint64_t vblank = 40; vblank <= 50; ++vblank) assert((taps.publish(Y, vblank, Moving) & Y) == Y);
    assert(taps.publish(0, 51, Moving) == 0);

    // What the menu consumed is not owed to the game, whether it was queued or still held.
    taps.press(Y);
    taps.forget(Y);
    assert(taps.publish(0, 60, Moving) == 0);
    assert((taps.publish(Left, 61, Moving) & Left) == Left);
    taps.forget(Left);
    assert(taps.publish(0, 62, Moving) == 0);

    // One pad's tap must not turn up on another player's pad.
    PalTapHold other;
    taps.press(Y);
    assert(other.publish(0, 70, Moving) == 0);
    assert((taps.publish(0, 70, Moving) & Y) == Y);

    printf("PASS: buttons hold for %llu VBlanks, directions for %llu\n",
           (unsigned long long)kPalMinPressVblanks, (unsigned long long)kPalMinDirectionVblanks);
    return 0;
}
