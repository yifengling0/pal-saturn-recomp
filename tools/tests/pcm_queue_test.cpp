#include "pal_pcm_queue.h"
#include <cassert>
#include <iostream>
#include <thread>
#include <vector>

int main() {
    // Guest-sized 4/5-frame pushes, arbitrary callback sizes, ring wrapping,
    // and a final partial batch must preserve every stereo sample in order.
    constexpr int count = 100003;
    std::vector<int16_t> input(count * 2), actual;
    for (int i = 0; i < count; ++i) { input[2*i] = static_cast<int16_t>(i); input[2*i+1] = static_cast<int16_t>(-i); }
    pal_pcm::Queue<769> queue;
    pal_pcm::Batch batch;
    int submissions = 0;
    auto drain = [&](int frames) {
        int16_t out[882 * 2];
        const int n = queue.get(out, frames);
        actual.insert(actual.end(), out, out + n * 2);
    };
    auto put = [&](const int16_t* pcm, int frames) {
        ++submissions;
        if (queue.queued() + frames > 769) drain(441);
        return queue.put(pcm, frames);
    };
    for (int at = 0; at < count;) {
        const int n = std::min((at % 2) ? 4 : 5, count - at);
        assert(batch.add(input.data() + at * 2, n, put) == n);
        at += n;
        if (at % 19 == 0) drain(37);
    }
    assert(batch.flush(put));
    while (queue.queued()) drain(882);
    assert(input == actual);
    assert(submissions == (count + 255) / 256);
    assert(batch.pending() == 0);

    // A full output queue must retain the unsent batch for a later retry.
    pal_pcm::Queue<256> small;
    pal_pcm::Batch held;
    assert(small.put(input.data(), 256));
    auto try_put = [&](const int16_t* pcm, int n) { return small.put(pcm, n); };
    assert(held.add(input.data() + 512, 256, try_put) == 256);
    assert(held.pending() == 256);
    assert(held.add(input.data() + 1024, 5, try_put) == 0);
    int16_t out[512];
    assert(small.get(out, 256) == 256);
    assert(held.flush(try_put));
    assert(small.get(out, 256) == 256);
    assert(std::equal(out, out + 512, input.data() + 512));

    // A real producer/consumer pair exercises publication and wraparound.
    pal_pcm::Queue<1027> concurrent;
    std::vector<int16_t> received(count * 2);
    std::thread producer([&] {
        for (int at = 0; at < count;) {
            const int n = std::min(256, count - at);
            // The storage ring is larger than the admitted latency budget.
            if (concurrent.put(input.data() + at * 2, n, 769)) at += n;
            else std::this_thread::yield();
            assert(concurrent.queued() <= 769);
        }
    });
    for (int at = 0; at < count;) {
        const int n = concurrent.get(received.data() + at * 2, std::min(441, count - at));
        at += n;
        if (!n) std::this_thread::yield();
    }
    producer.join();
    assert(input == received);
    assert(concurrent.queued() == 0);
    assert(pal_pcm::prime_frames(882) == 2816);
    assert(pal_pcm::prime_frames(441) == 1792);
    assert(pal_pcm::prime_frames(4096) == 0);

    // Lowering a route's budget holds samples until they can be consumed;
    // it must not shrink the ring, evict PCM, or over-admit on resume.
    pal_pcm::Queue<769> route;
    assert(route.put(input.data(), 512, 512));
    assert(!route.put(input.data()+1024, 1, 512));
    assert(!route.put(input.data()+1024, 1, 256));
    assert(route.queued() == 512);
    assert(route.get(out, 256) == 256);
    assert(std::equal(out, out+512, input.data()));
    assert(!route.put(input.data()+1024, 1, 256));
    assert(route.get(out, 256) == 256);
    assert(std::equal(out, out+512, input.data()+512));
    assert(route.put(input.data()+1024, 256, 256));
    assert(route.get(out, 256) == 256);
    assert(std::equal(out, out+512, input.data()+1024));
    assert(pal_pcm::queue_limit(2816, 882) == 3840);
    assert(pal_pcm::queue_limit(1792, 441) == 2304);
    assert(pal_pcm::queue_limit(11025, 4096) == 11025);
    std::cout << "PCM order, stereo, batch tail, overflow retry, and concurrent wrap: PASS\n";
}
