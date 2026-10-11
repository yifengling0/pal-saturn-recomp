// Pure policy regression test. The runtime header is supplied by the runner.
#include "pal_audio_jitter_policy.h"
#include <climits>
#include <cstdio>
namespace p = pal_audio_jitter_policy;
namespace q = pal_audio_queue_policy;
static int checks, failures;
#define CHECK(x) do { ++checks; if (!(x)) { ++failures; std::printf("FAIL %d: %s\n", __LINE__, #x); } } while (0)

int main() {
    const auto large = p::initial(4096, 44100);
    CHECK(large.frames == 4410 && large.quantum_source_frames == 4096 && large.uncapped_frames == 12288 && large.capped && large.maximum_target == 6047);
    CHECK(p::initial(960, 48000).frames == 2646);
    CHECK(p::initial(4096, 48000).quantum_source_frames == 3764);
    CHECK(p::initial(4096, 48000).frames == 4410 && p::initial(4096,48000).maximum_target == 6379);
    CHECK(p::initial(4096, 22050).frames == 4410);
    CHECK(!p::initial(0, 44100).valid && p::initial(0, 44100).frames == 4410);
    CHECK(!p::initial(4096, -1).valid);
    CHECK(p::initial(INT_MAX, 1).frames == 4410);
    CHECK(p::initial(INT_MAX, INT_MAX).quantum_source_frames == 44100);
    p::State s; s.reset(4410, 0, 5292);
    CHECK(s.observe(3000000000ULL, 0, 0, 735).silence_frames == 0); // empty alone does nothing
    CHECK(s.observe(0, 1, 0, 735).silence_frames == 0); // startup consumed
    CHECK(s.observe(3000000000ULL, 1, 0, 735).silence_frames == 0); // no stale startup
    auto growth = s.observe(3000000000ULL, 2, 0, 735);
    CHECK(growth.silence_frames == 882 && growth.target_after_success == 5292);
    s.commit(growth, false, 3000000000ULL);
    CHECK(s.target == 4410 && !s.has_grown);
    CHECK(s.observe(4000000000ULL, 2, 0, 735).silence_frames == 0); // no old-event retry
    growth = s.observe(4000000000ULL, 3, 0, 735);
    s.commit(growth, true, 4000000000ULL);
    CHECK(s.target == 5292 && s.has_grown);
    CHECK(s.observe(6000000000ULL, 4, 0, 735).budget_exhausted);
    CHECK(s.observe(7000000000ULL, 5, 0, 735).silence_frames == 0);
    s.reset(4410);
    growth = s.observe(3000000000ULL, 1, 0, 735);
    s.commit(growth, true, 3000000000ULL);
    CHECK(s.observe(3500000000ULL, 2, 0, 735).silence_frames == 0);
    CHECK(s.observe(5000000000ULL, 2, 0, 735).silence_frames == 0);
    CHECK(s.observe(5000000000ULL, 3, -1, 735).silence_frames == 0);
    CHECK(s.observe(5000000000ULL, 4, 3, 735).silence_frames == 0);
    CHECK(s.observe(5000000000ULL, 5, 0, 11026).silence_frames == 0);
    CHECK(s.observe(5000000000ULL, 6, (11025-735-881)*4, 735).silence_frames == 0);
    growth = s.observe(5000000000ULL, 7, (11025-735-882)*4, 735);
    CHECK(growth.silence_frames == 882);
    s.commit(growth, true, 5000000000ULL);
    CHECK(s.target == 6174);
    CHECK(s.observe(4000000000ULL, 8, 0, 735).silence_frames == 0); // nonmonotonic rejected
    std::uint64_t epoch = 9; int added = 1764;
    for (std::uint64_t time=7; time<40; ++time) {
        growth=s.observe(time*1000000000ULL, epoch++, 0, 735);
        added+=growth.silence_frames; s.commit(growth, true, time*1000000000ULL);
    }
    CHECK(added == 9702-4410 && s.target == 9702); // finite lifetime padding budget
    CHECK(q::plan_push(-1, 735, 0).error == q::QueueError::query_failed);
    CHECK(q::plan_push(0, 735, 0).recovery_silence_frames == 0);
    CHECK(q::plan_push(11025*4, 1, 0).dropped_real_frames == 1);

    std::printf("%d policy checks, %d failures; no SDL or device dependency\n", checks, failures);
    return failures ? 1 : 0;
}
