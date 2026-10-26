#pragma once
#include <cstdint>

// The original manual mover probes two neighbouring directions when its first
// map/event collision test fails. Keep that policy for scripted movement only.
namespace pal_obstacle_stop {
inline constexpr uint32_t Hook = 0x06033752u;
inline constexpr uint32_t ManualReturn = 0x06026E74u;
inline bool frame_address(uint32_t frame) {
    // Four local bytes followed by saved PR, r14 and r8 in high work RAM.
    return !(frame & 3u) && frame >= 0x06000000u && frame <= 0x060FFFF0u;
}
inline bool matches(uint32_t cpu, uint32_t address, uint32_t frame,
                    uint32_t caller, uint32_t direction, uint32_t max_direction,
                    uint16_t move_count, uint16_t instruction) {
    return cpu == 0 && address == Hook && frame_address(frame) &&
           caller == ManualReturn && direction <= 3 && max_direction == 3 &&
           move_count == 0 && instruction == 0xE303u;
}
} // namespace pal_obstacle_stop
