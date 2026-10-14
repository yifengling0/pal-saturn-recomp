#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>

namespace pal_pcm {
constexpr int kRate = 44100;
constexpr int kBatch = 256;
constexpr int kCapacity = 11025;

// One guest producer and one output callback. Publish only complete stereo frames.
template<int Capacity = kCapacity>
class Queue {
    static_assert(Capacity > 0);
    static_assert(std::atomic<uint64_t>::is_always_lock_free);
    std::array<int16_t, Capacity * 2> pcm_{};
    alignas(64) std::atomic<uint64_t> written_{0};
    alignas(64) std::atomic<uint64_t> read_{0};
public:
    void reset() { written_ = 0; read_ = 0; } // only with the renderer released
    int queued() const {
        const auto r = read_.load(std::memory_order_acquire);
        const auto w = written_.load(std::memory_order_acquire);
        return static_cast<int>(w - r);
    }
    bool put(const int16_t* pcm, int frames, int limit = Capacity) {
        if (frames < 0 || frames > Capacity || limit <= 0 || limit > Capacity) return false;
        const auto w = written_.load(std::memory_order_relaxed);
        const auto r = read_.load(std::memory_order_acquire);
        if (w - r + frames > static_cast<uint64_t>(limit)) return false;
        const int at = static_cast<int>(w % Capacity);
        const int first = std::min(frames, Capacity - at);
        std::memcpy(pcm_.data() + at * 2, pcm, first * 4);
        std::memcpy(pcm_.data(), pcm + first * 2, (frames - first) * 4);
        written_.store(w + frames, std::memory_order_release);
        return true;
    }
    int get(int16_t* pcm, int frames) {
        if (frames <= 0) return 0;
        const auto r = read_.load(std::memory_order_relaxed);
        const auto w = written_.load(std::memory_order_acquire);
        frames = std::min(frames, static_cast<int>(w - r));
        const int at = static_cast<int>(r % Capacity);
        const int first = std::min(frames, Capacity - at);
        std::memcpy(pcm, pcm_.data() + at * 2, first * 4);
        std::memcpy(pcm + first * 2, pcm_.data(), (frames - first) * 4);
        read_.store(r + frames, std::memory_order_release);
        return frames;
    }
};

class Batch {
    std::array<int16_t, kBatch * 2> pcm_{};
    int frames_ = 0;
public:
    int pending() const { return frames_; }
    void reset() { frames_ = 0; }
    template<class Put> bool flush(Put&& put) {
        if (!frames_) return true;
        if (!put(pcm_.data(), frames_)) return false;
        frames_ = 0;
        return true;
    }
    template<class Put> int add(const int16_t* pcm, int frames, Put&& put) {
        int used = 0;
        while (used < frames) {
            if (frames_ == kBatch && !flush(put)) break;
            const int n = std::min(frames - used, kBatch - frames_);
            std::memcpy(pcm_.data() + frames_ * 2, pcm + used * 2, n * 4);
            frames_ += n;
            used += n;
        }
        if (frames_ == kBatch) flush(put);
        return used;
    }
};

// Three obtained callbacks cover the 60 Hz producer phase and normal scheduling.
constexpr int prime_frames(int quantum) {
    if (quantum <= 0 || quantum > 1024) return 0;
    const int frames = std::max(1764, quantum * 3);
    return ((frames + kBatch - 1) / kBatch) * kBatch;
}

// Keep one callback of headroom above priming, including across pause/resume.
// The larger ring capacity is storage, not permission to accumulate latency.
constexpr int queue_limit(int prime, int quantum) {
    const int headroom = std::clamp(quantum, 0, kCapacity);
    const int target = std::clamp(prime, kBatch, kCapacity) + headroom;
    return std::min(kCapacity, ((target + kBatch - 1) / kBatch) * kBatch);
}
} // namespace pal_pcm
