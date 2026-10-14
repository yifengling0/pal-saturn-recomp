#include "pal_ohos_audio.h"
#include "pal_pcm_queue.h"
#include <hilog/log.h>
#include <ohaudio/native_audiostreambuilder.h>
#include <ohaudio/native_audiorenderer.h>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <condition_variable>
#include <dlfcn.h>
#include <mutex>
#include <thread>

namespace pal_ohos_audio {
namespace {
using Clock = std::chrono::steady_clock;
static_assert(std::atomic<bool>::is_always_lock_free && std::atomic<int>::is_always_lock_free);
void note(const char* format, ...) __attribute__((format(printf, 1, 2)));
void note(const char* format, ...) {
    char line[1536];
    va_list args;
    va_start(args, format);
    std::vsnprintf(line, sizeof line, format, args);
    va_end(args);
    // The control thread must not call the guest logger, which reads the guest clock.
    OH_LOG_Print(LOG_APP, LOG_INFO, 0x2c00, "PAL/OHOS", "%{public}s", line);
}
struct Api {
#define AUDIO_API(name) decltype(&::name) name = nullptr;
    AUDIO_API(OH_AudioStreamBuilder_Create)
    AUDIO_API(OH_AudioStreamBuilder_Destroy)
    AUDIO_API(OH_AudioStreamBuilder_SetSamplingRate)
    AUDIO_API(OH_AudioStreamBuilder_SetChannelCount)
    AUDIO_API(OH_AudioStreamBuilder_SetSampleFormat)
    AUDIO_API(OH_AudioStreamBuilder_SetLatencyMode)
    AUDIO_API(OH_AudioStreamBuilder_SetRendererInfo)
    AUDIO_API(OH_AudioStreamBuilder_SetFrameSizeInCallback)
    AUDIO_API(OH_AudioStreamBuilder_SetRendererWriteDataCallback)
    AUDIO_API(OH_AudioStreamBuilder_SetRendererInterruptCallback)
    AUDIO_API(OH_AudioStreamBuilder_SetRendererErrorCallback)
    AUDIO_API(OH_AudioStreamBuilder_SetRendererOutputDeviceChangeCallback)
    AUDIO_API(OH_AudioStreamBuilder_GenerateRenderer)
    AUDIO_API(OH_AudioRenderer_GetSamplingRate)
    AUDIO_API(OH_AudioRenderer_GetChannelCount)
    AUDIO_API(OH_AudioRenderer_GetSampleFormat)
    AUDIO_API(OH_AudioRenderer_GetFrameSizeInCallback)
    AUDIO_API(OH_AudioRenderer_GetCurrentState)
    AUDIO_API(OH_AudioRenderer_SetVolume)
    AUDIO_API(OH_AudioRenderer_Start)
    AUDIO_API(OH_AudioRenderer_Pause)
    AUDIO_API(OH_AudioRenderer_Stop)
    AUDIO_API(OH_AudioRenderer_Release)
    AUDIO_API(OH_AudioRenderer_GetFastStatus)
    AUDIO_API(OH_AudioRenderer_GetLatency)
#undef AUDIO_API
} api;

// Renderer callback userdata lives until process exit, including failed opens.
struct Output {
    pal_pcm::Queue<> queue;
    pal_pcm::Batch batch;
    OH_AudioRenderer* renderer = nullptr;
    std::thread control;
    std::mutex mutex;
    std::condition_variable wake;
    std::atomic<bool> opened{false}, quit{false}, menu{false}, background{false};
    std::atomic<bool> primed{false}, interrupt{false}, fault{false};
    std::atomic<bool> duck{false}, muted{false};
    std::atomic<uint64_t> route_epoch{0}, lifecycle_epoch{0};
    std::atomic<uint64_t> calls{0}, requested{0}, shorts{0}, missing{0}, played{0};
    std::atomic<uint64_t> errors{0}, control_errors{0}, callback_max{0};
    std::atomic<int> quantum{0}, prime{0}, fast{-1};
    float volume = 1;
    uint64_t attempted = 0, accepted = 0, failed = 0, submissions = 0;
    uint64_t rebases = 0, lost_ns = 0, resets = 0, backpressure = 0, lifecycle_seen = 0;
    uint64_t max_gap_us = 0;
    Clock::time_point last_push{}, started{}, window{};
    struct Snapshot {
        uint64_t accepted = 0, failed = 0, submissions = 0, calls = 0;
        uint64_t requested = 0, shorts = 0, missing = 0, rebases = 0, lost_ns = 0, resets = 0;
    } previous;
    bool skip_gap = false;
} output;

bool load_api() {
    static void* library = dlopen("libohaudio.so", RTLD_NOW | RTLD_LOCAL);
    if (!library) { note("audio pull: libohaudio unavailable: %s", dlerror()); return false; }
#define LOAD(name) api.name = reinterpret_cast<decltype(api.name)>(dlsym(library, #name)); \
    if (!api.name) { note("audio pull: missing %s", #name); return false; }
    LOAD(OH_AudioStreamBuilder_Create)
    LOAD(OH_AudioStreamBuilder_Destroy)
    LOAD(OH_AudioStreamBuilder_SetSamplingRate)
    LOAD(OH_AudioStreamBuilder_SetChannelCount)
    LOAD(OH_AudioStreamBuilder_SetSampleFormat)
    LOAD(OH_AudioStreamBuilder_SetLatencyMode)
    LOAD(OH_AudioStreamBuilder_SetRendererInfo)
    LOAD(OH_AudioStreamBuilder_SetFrameSizeInCallback)
    LOAD(OH_AudioStreamBuilder_SetRendererWriteDataCallback)
    LOAD(OH_AudioStreamBuilder_SetRendererInterruptCallback)
    LOAD(OH_AudioStreamBuilder_SetRendererErrorCallback)
    LOAD(OH_AudioStreamBuilder_SetRendererOutputDeviceChangeCallback)
    LOAD(OH_AudioStreamBuilder_GenerateRenderer)
    LOAD(OH_AudioRenderer_GetSamplingRate)
    LOAD(OH_AudioRenderer_GetChannelCount)
    LOAD(OH_AudioRenderer_GetSampleFormat)
    LOAD(OH_AudioRenderer_GetFrameSizeInCallback)
    LOAD(OH_AudioRenderer_GetCurrentState)
    LOAD(OH_AudioRenderer_SetVolume)
    LOAD(OH_AudioRenderer_Start)
    LOAD(OH_AudioRenderer_Pause)
    LOAD(OH_AudioRenderer_Stop)
    LOAD(OH_AudioRenderer_Release)
#undef LOAD
    api.OH_AudioRenderer_GetFastStatus = reinterpret_cast<decltype(api.OH_AudioRenderer_GetFastStatus)>(dlsym(library, "OH_AudioRenderer_GetFastStatus"));
    api.OH_AudioRenderer_GetLatency = reinterpret_cast<decltype(api.OH_AudioRenderer_GetLatency)>(dlsym(library, "OH_AudioRenderer_GetLatency"));
    return true;
}

OH_AudioData_Callback_Result write_data(OH_AudioRenderer*, void* userdata, void* buffer, int32_t bytes) {
    auto& o = *static_cast<Output*>(userdata);
    if (!buffer || bytes <= 0) return AUDIO_DATA_CALLBACK_RESULT_INVALID;
    std::memset(buffer, 0, bytes);
    if (bytes % 4) { o.errors.fetch_add(1, std::memory_order_relaxed); return AUDIO_DATA_CALLBACK_RESULT_INVALID; }
    // No guest state, allocation, locks, logging, or clock calls on the audio thread.
    if (o.quit.load(std::memory_order_acquire) || o.menu.load(std::memory_order_acquire) ||
        o.background.load(std::memory_order_acquire) || o.interrupt.load(std::memory_order_acquire) ||
        o.fault.load(std::memory_order_acquire) || !o.primed.load(std::memory_order_acquire)) return AUDIO_DATA_CALLBACK_RESULT_VALID;
    const int wanted = bytes / 4;
    const int have = o.queue.get(static_cast<int16_t*>(buffer), wanted);
    o.calls.fetch_add(1, std::memory_order_relaxed);
    o.requested.fetch_add(wanted, std::memory_order_relaxed);
    o.played.fetch_add(have, std::memory_order_relaxed);
    o.callback_max.store(std::max<uint64_t>(o.callback_max.load(std::memory_order_relaxed), wanted), std::memory_order_relaxed);
    if (have < wanted) {
        o.shorts.fetch_add(1, std::memory_order_relaxed);
        o.missing.fetch_add(wanted - have, std::memory_order_relaxed);
    }
    return AUDIO_DATA_CALLBACK_RESULT_VALID;
}

void interrupt(OH_AudioRenderer*, void* userdata, OH_AudioInterrupt_ForceType type, OH_AudioInterrupt_Hint hint) {
    auto& o = *static_cast<Output*>(userdata);
    if (hint == AUDIOSTREAM_INTERRUPT_HINT_RESUME) o.interrupt.store(false, std::memory_order_release);
    if (type == AUDIOSTREAM_INTERRUPT_FORCE && (hint == AUDIOSTREAM_INTERRUPT_HINT_PAUSE || hint == AUDIOSTREAM_INTERRUPT_HINT_STOP))
        o.interrupt.store(true, std::memory_order_release);
    if (hint == AUDIOSTREAM_INTERRUPT_HINT_DUCK) o.duck.store(true, std::memory_order_release);
    if (hint == AUDIOSTREAM_INTERRUPT_HINT_UNDUCK) o.duck.store(false, std::memory_order_release);
    if (hint == AUDIOSTREAM_INTERRUPT_HINT_MUTE) o.muted.store(true, std::memory_order_release);
    if (hint == AUDIOSTREAM_INTERRUPT_HINT_UNMUTE) o.muted.store(false, std::memory_order_release);
}
void error(OH_AudioRenderer*, void* userdata, OH_AudioStream_Result) {
    auto& o = *static_cast<Output*>(userdata);
    o.errors.fetch_add(1, std::memory_order_relaxed);
    o.fault.store(true, std::memory_order_release);
}
void route(OH_AudioRenderer*, void* userdata, OH_AudioStream_DeviceChangeReason) {
    static_cast<Output*>(userdata)->route_epoch.fetch_add(1, std::memory_order_release);
}

void query_route(bool initial) {
    int32_t q = 0;
    if (api.OH_AudioRenderer_GetFrameSizeInCallback(output.renderer, &q) != AUDIOSTREAM_SUCCESS || q <= 0) return;
    output.quantum = q;
    int target = pal_pcm::prime_frames(q);
    if (!initial && !target) target = std::min(5512, std::max(1764, q * 3));
    output.prime = target;
    OH_AudioStream_FastStatus fast{};
    if (api.OH_AudioRenderer_GetFastStatus && api.OH_AudioRenderer_GetFastStatus(output.renderer, &fast) == AUDIOSTREAM_SUCCESS)
        output.fast = static_cast<int>(fast);
    note("audio pull route: hz=44100 quantum=%d fast=%d prime=%d batch=%d queue_limit=%d source_sha=%s", q,
        output.fast.load(), target, pal_pcm::kBatch, pal_pcm::queue_limit(target, q), PAL_OHOS_AUDIO_SOURCE_SHA256);
}

void control() {
    bool running = false;
    uint64_t route_seen = output.route_epoch.load();
    float volume = -1;
    while (!output.quit.load(std::memory_order_acquire)) {
        const bool play = output.primed.load(std::memory_order_acquire) &&
            !output.menu.load(std::memory_order_acquire) && !output.background.load(std::memory_order_acquire) &&
            !output.interrupt.load(std::memory_order_acquire) && !output.fault.load(std::memory_order_acquire);
        const float wanted_volume = output.muted.load() ? 0 : output.volume * (output.duck.load() ? 0.2f : 1.0f);
        if (volume != wanted_volume) {
            if (api.OH_AudioRenderer_SetVolume(output.renderer, wanted_volume) != AUDIOSTREAM_SUCCESS) ++output.control_errors;
            volume = wanted_volume;
        }
        if (play != running) {
            OH_AudioStream_State state{};
            const bool known = api.OH_AudioRenderer_GetCurrentState(output.renderer, &state) == AUDIOSTREAM_SUCCESS;
            const bool satisfied = known && (play ? state == AUDIOSTREAM_STATE_RUNNING : state != AUDIOSTREAM_STATE_RUNNING);
            const auto result = satisfied ? AUDIOSTREAM_SUCCESS : play ? api.OH_AudioRenderer_Start(output.renderer) : api.OH_AudioRenderer_Pause(output.renderer);
            if (result != AUDIOSTREAM_SUCCESS) {
                ++output.control_errors;
                output.fault.store(true, std::memory_order_release);
                note("audio pull: %s failed result=%d", play ? "start" : "pause", static_cast<int>(result));
            } else {
                running = play;
                if (play) {
                    query_route(false);
                    if (api.OH_AudioRenderer_GetLatency) {
                        int32_t ms = -1;
                        const auto result_latency = api.OH_AudioRenderer_GetLatency(output.renderer, AUDIOSTREAM_LATENCY_TYPE_ALL, &ms);
                        note("audio pull: output route latency_ms=%d query_result=%d (route estimate excludes realtime queues)", ms, static_cast<int>(result_latency));
                    }
                }
            }
        }
        const auto changed = output.route_epoch.load(std::memory_order_acquire);
        if (changed != route_seen) { query_route(false); route_seen = changed; }
        std::unique_lock<std::mutex> lock(output.mutex);
        output.wake.wait_for(lock, std::chrono::milliseconds(10));
    }
    if (running) api.OH_AudioRenderer_Stop(output.renderer);
}

void live(bool force = false) {
    const auto now = Clock::now();
    if (!force && now - output.window < std::chrono::seconds(5)) return;
    const auto calls = output.calls.load(), requested = output.requested.load();
    const auto shorts = output.shorts.load(), missing = output.missing.load();
    const auto& p = output.previous;
    note("audio pull live: wall_s=%.3f accepted=%llu failed=%llu submissions=%llu queued=%d pending=%d max_push_gap_us=%llu calls=%llu short_calls=%llu missing_frames=%llu requested_frames=%llu pace_rebases=%llu lost_guest_ms=%.3f lifecycle_resets=%llu quantum=%d callback_max=%llu fast=%d errors=%llu control_errors=%llu backpressure=%llu (source shortage, not hardware underruns)",
        std::chrono::duration<double>(now - output.window).count(),
        (unsigned long long)(output.accepted-p.accepted), (unsigned long long)(output.failed-p.failed),
        (unsigned long long)(output.submissions-p.submissions), output.queue.queued(), output.batch.pending(),
        (unsigned long long)output.max_gap_us, (unsigned long long)(calls-p.calls),
        (unsigned long long)(shorts-p.shorts), (unsigned long long)(missing-p.missing),
        (unsigned long long)(requested-p.requested), (unsigned long long)(output.rebases-p.rebases),
        (output.lost_ns-p.lost_ns)/1000000.0, (unsigned long long)(output.resets-p.resets),
        output.quantum.load(), (unsigned long long)output.callback_max.load(), output.fast.load(),
        (unsigned long long)output.errors.load(), (unsigned long long)output.control_errors.load(),
        (unsigned long long)output.backpressure);
    output.previous = {output.accepted, output.failed, output.submissions, calls, requested, shorts, missing, output.rebases, output.lost_ns, output.resets};
    output.max_gap_us = 0;
    output.window = now;
}

bool publish(const int16_t* pcm, int frames) {
    const auto epoch = output.lifecycle_epoch.load(std::memory_order_acquire);
    if (epoch != output.lifecycle_seen) {
        output.lifecycle_seen = epoch; output.skip_gap = true; ++output.resets;
    }
    // Bound queued latency as well as memory. Repeated platform restarts can
    // defer their first callback; do not retain that delay in every later frame.
    // Backpressure preserves already staged PCM; never evict old samples.
    const int limit = pal_pcm::queue_limit(output.prime.load(), output.quantum.load());
    int waits = 0;
    while (!output.queue.put(pcm, frames, limit)) {
        if (output.fault.load() || output.quit.load() || waits++ >= 100 || output.menu.load() || output.background.load() || output.interrupt.load()) return false;
        ++output.backpressure;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    output.accepted += frames;
    ++output.submissions;
    const auto now = Clock::now();
    if (!output.skip_gap && output.last_push != Clock::time_point{})
        output.max_gap_us = std::max(output.max_gap_us, static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(now-output.last_push).count()));
    output.last_push = now;
    output.skip_gap = false;
    if (!output.primed.load() && output.queue.queued() >= output.prime.load()) {
        output.primed.store(true, std::memory_order_release);
        output.wake.notify_one();
    }
    live();
    return true;
}
} // namespace

bool open(float volume) {
    close();
    if (!load_api()) return false;
    output.queue.reset(); output.batch.reset();
    output.quit = output.menu = output.background = output.primed = output.interrupt = output.fault = false;
    output.duck = output.muted = false;
    output.calls = output.requested = output.shorts = output.missing = output.played = 0;
    output.errors = output.control_errors = output.callback_max = output.route_epoch = output.lifecycle_epoch = 0;
    output.attempted = output.accepted = output.failed = output.submissions = 0;
    output.rebases = output.lost_ns = output.resets = output.backpressure = output.max_gap_us = output.lifecycle_seen = 0;
    output.previous = {}; output.last_push = {}; output.skip_gap = false;
    output.started = output.window = Clock::now();
    output.volume = std::clamp(volume, 0.0f, 1.0f);
    output.quantum = output.prime = 0; output.fast = -1;
    OH_AudioStreamBuilder* builder = nullptr;
    auto result = api.OH_AudioStreamBuilder_Create(&builder, AUDIOSTREAM_TYPE_RENDERER);
    if (result != AUDIOSTREAM_SUCCESS || !builder) return false;
    bool ok = true;
#define SET(name, ...) if (api.name(builder, __VA_ARGS__) != AUDIOSTREAM_SUCCESS) { note("audio pull: %s rejected", #name); ok = false; }
    SET(OH_AudioStreamBuilder_SetSamplingRate, pal_pcm::kRate)
    SET(OH_AudioStreamBuilder_SetChannelCount, 2)
    SET(OH_AudioStreamBuilder_SetSampleFormat, AUDIOSTREAM_SAMPLE_S16LE)
    SET(OH_AudioStreamBuilder_SetLatencyMode, AUDIOSTREAM_LATENCY_MODE_FAST)
    SET(OH_AudioStreamBuilder_SetRendererInfo, AUDIOSTREAM_USAGE_GAME)
    SET(OH_AudioStreamBuilder_SetFrameSizeInCallback, 882)
    SET(OH_AudioStreamBuilder_SetRendererWriteDataCallback, write_data, &output)
    SET(OH_AudioStreamBuilder_SetRendererInterruptCallback, interrupt, &output)
    SET(OH_AudioStreamBuilder_SetRendererErrorCallback, error, &output)
    SET(OH_AudioStreamBuilder_SetRendererOutputDeviceChangeCallback, route, &output)
#undef SET
    if (ok) result = api.OH_AudioStreamBuilder_GenerateRenderer(builder, &output.renderer);
    api.OH_AudioStreamBuilder_Destroy(builder);
    if (!ok || result != AUDIOSTREAM_SUCCESS || !output.renderer) { close(); return false; }
    int32_t hz = 0, channels = 0;
    OH_AudioStream_SampleFormat format{};
    ok = api.OH_AudioRenderer_GetSamplingRate(output.renderer, &hz) == AUDIOSTREAM_SUCCESS && hz == pal_pcm::kRate &&
        api.OH_AudioRenderer_GetChannelCount(output.renderer, &channels) == AUDIOSTREAM_SUCCESS && channels == 2 &&
        api.OH_AudioRenderer_GetSampleFormat(output.renderer, &format) == AUDIOSTREAM_SUCCESS && format == AUDIOSTREAM_SAMPLE_S16LE;
    query_route(true);
    if (!ok || !output.prime.load()) {
        note("audio pull: unsupported obtained format hz=%d ch=%d format=%d quantum=%d; use SDL fallback", hz, channels, static_cast<int>(format), output.quantum.load());
        close(); return false;
    }
    output.opened.store(true, std::memory_order_release);
    output.control = std::thread(control);
    note("audio pull: armed with real PCM prime=%d/44100, capacity=%d/44100, no initial silence", output.prime.load(), pal_pcm::kCapacity);
    return true;
}
bool active() { return output.opened.load(std::memory_order_acquire); }
void push(const int16_t* pcm, int frames) {
    if (!active() || frames <= 0) return;
    output.attempted += frames;
    output.failed += frames - output.batch.add(pcm, frames, publish);
}
void flush() { if (active()) output.batch.flush(publish); }
void pause() {
    if (!active()) return;
    flush(); output.menu.store(true, std::memory_order_release);
    output.skip_gap = true; ++output.resets; output.wake.notify_one();
}
void resume() {
    if (!active()) return;
    output.skip_gap = true; ++output.resets;
    output.menu.store(false, std::memory_order_release); output.wake.notify_one();
}
void background(bool paused) {
    if (output.background.exchange(paused, std::memory_order_acq_rel) != paused)
        output.lifecycle_epoch.fetch_add(1, std::memory_order_release);
}
bool backgrounded() { return output.background.load(std::memory_order_acquire); }
void rebase(uint64_t lost_ns) { if (active()) { ++output.rebases; output.lost_ns += lost_ns; } }
void report() { if (active()) { flush(); live(true); note("audio pull totals: attempted=%llu accepted=%llu played=%llu failed=%llu pending=%d queued=%d", (unsigned long long)output.attempted, (unsigned long long)output.accepted, (unsigned long long)output.played.load(), (unsigned long long)output.failed, output.batch.pending(), output.queue.queued()); } }
void close() {
    output.opened.store(false, std::memory_order_release);
    output.quit.store(true, std::memory_order_release);
    output.wake.notify_one();
    if (output.control.joinable()) output.control.join();
    if (output.renderer) { api.OH_AudioRenderer_Release(output.renderer); output.renderer = nullptr; }
}
} // namespace pal_ohos_audio
