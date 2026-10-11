#include "pal_audio_stream_init.h"
#include <saturn/sh2.h>
#include "saturn.h"

namespace {
constexpr uint32_t kAfterDriverInstall = 0x06021C1Eu;
void refresh_cold_movie_sound_cache(SH2Context& c, uint32_t address) {
    if (address != kAfterDriverInstall || c.cpu != 0 || c.pr != kAfterDriverInstall) return;
    pal_audio_stream_init::Pointers next{};
    const uint32_t offset = ld32(0x25A00404u);
    if (!pal_audio_stream_init::plan(offset, ld32(0x06040C44u), ld32(0x06040C48u), next)) return;
    st32(0x06040C44u, next.table);
    st32(0x06040C48u, next.progress);
    sat_note("PAL movie sound cache refreshed after driver install: table=%08X progress=%08X", next.table, next.progress);
}
struct RegisterMovieSoundCache {
    RegisterMovieSoundCache() { sh2_hook_add(kAfterDriverInstall, refresh_cold_movie_sound_cache); }
} register_movie_sound_cache;
} // namespace
