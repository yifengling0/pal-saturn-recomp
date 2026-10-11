#pragma once
#include <cstdint>

// PAL T-37401H TRUE movie player caches the sound-driver table before installing
// that driver. Only repair the proven cold-zero-derived cache pair, after the
// original installation returns. This is a game compatibility correction, not
// a fabricated SCSP clock or a claim about the original BIOS's sound RAM.
namespace pal_audio_stream_init {
struct Pointers { uint32_t table; uint32_t progress; };
inline bool plan(uint32_t offset, uint32_t old_table, uint32_t old_progress,
                 Pointers& result) noexcept {
    constexpr uint32_t base = 0x25A00000u;
    constexpr uint32_t progress_offset = 0xA0u;
    constexpr uint32_t ram_size = 0x80000u;
    if (old_table != base || old_progress != base + progress_offset ||
        offset == 0 || (offset & 3u) != 0 ||
        offset > ram_size - progress_offset - 4u) return false;
    result = {base + offset, base + offset + progress_offset};
    return true;
}
} // namespace pal_audio_stream_init
