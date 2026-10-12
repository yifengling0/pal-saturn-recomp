#pragma once
#include <array>
#include <cstdint>

// T-37401H V1.000: the Yangzhou well chest announces object 103 but its
// original shared script passes object zero. Never generalize this to other
// callers of opcode 31 or the three other events sharing that script.
namespace pal_medicine_chest {
struct Snapshot {
    uint32_t pc, cpu;
    uint16_t scene, chapter_base, event_index;
    uint32_t script_pointer;
    uint16_t script_pc;
    uint32_t object, count;
    std::array<uint16_t, 4> command;
    std::array<uint16_t, 3> code;
    uint32_t call_target;
};
inline bool matches(const Snapshot& s) {
    return s.pc == 0x06028700u && s.cpu == 0 && s.scene == 93 &&
        s.chapter_base == 1454 && s.event_index == 206 &&
        s.script_pointer == 0x060A008Au && s.script_pc == 36788u &&
        s.object == 0 && s.count == 1 &&
        s.command == std::array<uint16_t, 4>{31, 0, 0, 0} &&
        s.code == std::array<uint16_t, 3>{0xD807, 0x480B, 0x0009} &&
        s.call_target == 0x0604F210u;
}
} // namespace pal_medicine_chest
