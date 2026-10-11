#include "pal_audio_stream_init.h"
#include <saturn/sh2.h>
#include "saturn.h"

namespace {
constexpr uint32_t kAfterDriverInstall = 0x06021C1Eu;
bool g_registered = false;
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
    RegisterMovieSoundCache() { sh2_hook_add(kAfterDriverInstall, refresh_cold_movie_sound_cache); g_registered = true; }
} register_movie_sound_cache;
} // namespace

// Referenced by the Harmony entry: a missing compatibility object is a link error.
extern "C" const char* pal_movie_cache_feature() {
    return g_registered ? "movie-cache-v1 hook=06021C1E registered=1" : "movie-cache-v1 registered=0";
}
