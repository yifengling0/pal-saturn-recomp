#pragma once
#include <cstdint>
// PAL comfort experiment, not a Saturn timing fix. Only the observed bank7
// battle-effect caller is eligible; bank4 and all other waits remain original.
constexpr bool pal_effect_scope_matches(bool enabled, unsigned cpu,
    uint32_t caller, uint32_t mode, uint32_t bank, uint32_t original,
    uint32_t interval, uint32_t battle_mode) {
    return enabled && cpu==0 && caller==0x06031172u && mode==1 && bank==7 &&
        original==200 && interval==2 && battle_mode==0xFFFF;
}
constexpr bool pal_effect_wait_complete(bool active, uint32_t original_limit,
    uint32_t completed, uint64_t elapsed_vblanks, uint8_t actual, uint8_t desired) {
    return active && original_limit==50 && completed>=2 && completed<50 &&
        elapsed_vblanks>=2 && (desired&7)==7 && actual==desired;
}
