#pragma once
#include <cstdint>
#include <cstring>
namespace pal_effect_cadence {
enum class Speed : unsigned { original=1, five_fourths=5, three_halves=3, twice=2 };
inline Speed parse_speed(const char* p) noexcept {
    if(p && !std::strcmp(p,"1.25")) return Speed::five_fourths;
    if(p && !std::strcmp(p,"1.5")) return Speed::three_halves;
    if(p && !std::strcmp(p,"2")) return Speed::twice;
    return Speed::original; // Unset, 1, malformed and unsupported values fail closed.
}
constexpr unsigned expected_frames(unsigned effect) noexcept {
    return effect==33 ? 20 : effect==10 ? 26 : effect==43 ? 14 : effect==1 ? 7 : 0;
}
// Ceiling cumulative rational time bounds total error to <1 VBlank without
// ever dropping a decoded frame. Reset per cast, not at arbitrary host time.
constexpr unsigned cumulative(Speed speed,unsigned frames) noexcept {
    return speed==Speed::five_fourths ? (frames*16+4)/5 :
           speed==Speed::three_halves ? (frames*8+2)/3 :
           speed==Speed::twice ? frames*2 : frames*4;
}
constexpr unsigned frame_fields(Speed speed,unsigned frame) noexcept {
    return cumulative(speed,frame+1)-cumulative(speed,frame);
}
constexpr unsigned sync_fields(unsigned frame_fields,unsigned sync) noexcept {
    return sync==0 ? (frame_fields+1)/2 : frame_fields/2;
}
constexpr bool matches(unsigned cpu,uint32_t gbr,unsigned battle,unsigned effect,
        unsigned count,unsigned frame,unsigned next,unsigned interval,unsigned bank) noexcept {
    return cpu==0 && (gbr&0x1FFFFFFFu)==0x060FFC00u && battle==0xFFFF &&
           expected_frames(effect)!=0 && count==expected_frames(effect) &&
           frame<count && frame==next && interval==2 && (bank&7)==7;
}
} // namespace pal_effect_cadence
