#pragma once
#include <cstdint>
#include <initializer_list>

// PAL-specific control policy, deliberately separate from Saturn pad emulation.
// A new direction gets one step, then a 200 ms repeat delay and the original
// three-VBlank repeat cadence. A released tap is retained for one consumption.
struct PalInputIntent {
    uint16_t previous = 0, held = 0, pending = 0;
    uint64_t repeat_at = 0;
    bool armed = false;
    static uint16_t direction(uint16_t bits) {
        bits &= 0xF000;
        if ((bits & 0xC000) == 0xC000 || (bits & 0x3000) == 0x3000) return 0;
        // Match PAL's single-direction policy; a new edge is preferred below.
        for (uint16_t b : {uint16_t(0x8000),uint16_t(0x4000),uint16_t(0x2000),uint16_t(0x1000)})
            if (bits & b) return b;
        return 0;
    }
    void clear(uint16_t bits) {
        previous = bits & 0xF000; held = pending = 0; repeat_at = 0;
        armed = previous == 0;
    }
    void sample(uint16_t bits, uint64_t vb, bool field) {
        bits &= 0xF000;
        if (!field) { clear(bits); return; }
        if (!armed) { previous = bits; if (!bits) armed = true; return; }
        uint16_t edge = direction(bits & ~previous);
        const uint16_t valid = direction(bits);
        if (bits && !valid) pending = 0;
        held = valid ? ((held & bits) ? held : valid) : 0;
        if (edge && held) { pending = edge; held = edge; repeat_at = vb + 12; }
        previous = bits;
    }
    void edge(uint16_t bits, uint64_t vb, bool field) {
        const uint16_t d=direction(bits);
        if(field && armed && d && !(previous && !direction(previous))) {pending=d;if(previous&d)held=d;repeat_at=vb+12;}
    }
    uint16_t take(uint64_t vb) {
        if (pending) { uint16_t result = pending; pending = 0; return result; }
        if (held && vb >= repeat_at) { repeat_at = vb + 3; return held; }
        return 0;
    }
};
