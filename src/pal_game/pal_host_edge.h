#pragma once
#include <cstdint>

// Direction-only edge retention. The caller maps the configured controls and
// filters events to the focused PAL window; key-up never extends held state.
struct PalHostEdge {
    uint16_t pending=0;
    void down(uint16_t direction, bool repeat, bool focused, bool blocked) {
        if(!focused || blocked) {pending=0;return;}
        if(!repeat && (direction&0xF000)) pending=direction&0xF000;
    }
    void clear(){pending=0;}
    uint16_t take(){const auto value=pending;pending=0;return value;}
};
