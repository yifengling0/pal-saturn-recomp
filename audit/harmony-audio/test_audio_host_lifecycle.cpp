// Include the selected runtime host.cpp directly. Only external SDL/audio endpoints are
// mocked; host_audio_open/push/report and its integrated helper are real code.
// No SDL_Init, real window, audio renderer, device or game is created.
#ifndef HOST_SOURCE
#error "Compile with HOST_SOURCE pointing at the runtime src/host/host.cpp under test"
#endif
// Keep three real stream endpoints reachable for the device-free SDL pull case.
// Rename the host's wrappers instead of ELF-interposing these SDL entry points.
#include <SDL3/SDL.h>
static auto real_put = SDL_PutAudioStreamData;
static auto real_queued = SDL_GetAudioStreamQueued;
static auto real_callback = SDL_SetAudioStreamGetCallback;
extern "C" bool SDLCALL test_put(SDL_AudioStream*, const void*, int);
extern "C" int SDLCALL test_queued(SDL_AudioStream*);
extern "C" bool SDLCALL test_callback(SDL_AudioStream*, SDL_AudioStreamCallback, void*);
#define SDL_PutAudioStreamData test_put
#define SDL_GetAudioStreamQueued test_queued
#define SDL_SetAudioStreamGetCallback test_callback
#include HOST_SOURCE
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <thread>
#ifdef _WIN32
#include <io.h>
#define TEST_DUP _dup
#define TEST_DUP2 _dup2
#define TEST_CLOSE _close
#define TEST_FILENO _fileno
#else
#include <unistd.h>
#define TEST_DUP dup
#define TEST_DUP2 dup2
#define TEST_CLOSE close
#define TEST_FILENO fileno
#endif

SaturnConfig g_cfg;
std::atomic<const char*> g_host_call{nullptr};
std::atomic<int> g_host_paused{0};
uint64_t sat_vblanks() { return 0; }

namespace mock {
struct Put { std::vector<unsigned char> data; int bytes; bool succeeded; };
static std::vector<Put> puts;
static std::vector<bool> put_results;
static std::vector<std::string> notes;
static bool open_ok = true, format_ok = true, resume_ok = true, pause_ok = true, callback_ok = true;
static std::string driver = "mock_audio";
static bool null_driver = false;
static SDL_AudioStreamCallback get_callback = nullptr;
static int pause_calls = 0;
static SDL_AudioSpec device{SDL_AUDIO_S16, 2, 44100}, requested{};
static int quantum = 4096, queued_bytes = 400, open_calls = 0;
static int query_calls = 0, resume_calls = 0, gain_calls = 0;
static SDL_AudioStreamCallback requested_callback = nullptr;
static std::string hint_name, hint_value;
static SDL_AudioStream* real_stream = nullptr;
static SDL_AudioStream* stream() { return real_stream ? real_stream : reinterpret_cast<SDL_AudioStream*>(2); }
}

void sat_note(const char* fmt, ...) {
    char text[2048];
    va_list ap; va_start(ap, fmt); std::vsnprintf(text, sizeof text, fmt, ap); va_end(ap);
    mock::notes.emplace_back(text);
}

extern "C" bool SDLCALL SDL_SetHint(const char* name, const char* value) {
    mock::hint_name = name; mock::hint_value = value; return true;
}
extern "C" SDL_AudioStream* SDLCALL SDL_OpenAudioDeviceStream(
    SDL_AudioDeviceID, const SDL_AudioSpec* spec, SDL_AudioStreamCallback callback, void*) {
    ++mock::open_calls; mock::requested = *spec; mock::requested_callback = callback;
    return mock::open_ok ? mock::stream() : nullptr;
}
extern "C" SDL_AudioDeviceID SDLCALL SDL_GetAudioStreamDevice(SDL_AudioStream*) { return 42; }
extern "C" bool SDLCALL SDL_GetAudioDeviceFormat(SDL_AudioDeviceID, SDL_AudioSpec* spec, int* frames) {
    if (!mock::format_ok) return false;
    *spec = mock::device; *frames = mock::quantum; return true;
}
extern "C" const char* SDLCALL SDL_GetError() { return "injected mock error"; }
extern "C" const char* SDLCALL SDL_GetCurrentAudioDriver() { return mock::null_driver ? nullptr : mock::driver.c_str(); }
extern "C" bool SDLCALL SDL_SetAudioStreamGetCallback(SDL_AudioStream*, SDL_AudioStreamCallback cb, void*) {
    if (!mock::callback_ok) return false;
    mock::get_callback = cb;
    return mock::real_stream ? real_callback(mock::real_stream, cb, nullptr) : true;
}
extern "C" bool SDLCALL SDL_PauseAudioStreamDevice(SDL_AudioStream*) {
    ++mock::pause_calls; return mock::pause_ok;
}
extern "C" bool SDLCALL SDL_SetAudioStreamGain(SDL_AudioStream*, float) {
    ++mock::gain_calls; return true;
}
extern "C" bool SDLCALL SDL_ResumeAudioStreamDevice(SDL_AudioStream*) {
    ++mock::resume_calls; return mock::resume_ok;
}
extern "C" int SDLCALL SDL_GetAudioStreamQueued(SDL_AudioStream*) {
    ++mock::query_calls;
    return mock::real_stream ? real_queued(mock::real_stream) : mock::queued_bytes;
}
extern "C" bool SDLCALL SDL_PutAudioStreamData(SDL_AudioStream*, const void* data, int bytes) {
    const std::size_t index = mock::puts.size();
    const bool injected_ok = index < mock::put_results.size() ? mock::put_results[index] : true;
    const bool ok = injected_ok && (!mock::real_stream || real_put(mock::real_stream, data, bytes));
    const auto* begin = static_cast<const unsigned char*>(data);
    mock::puts.push_back({std::vector<unsigned char>(begin, begin + bytes), bytes, ok});
    return ok;
}

static int checks = 0, failures = 0, cases = 0;
#define CHECK(e) do { ++checks; if (!(e)) { ++failures; std::printf("FAIL line %d: %s\n", __LINE__, #e); } } while (0)

static void reset() {
    ++cases;
    g_audio_jitter = g_audio_observer = g_audio_skip_gap = g_audio_adaptive = false;
    g_audio_lifecycle_epoch = 0; g_audio_format_dirty = false;
    mock::driver = "mock_audio"; mock::null_driver = false; mock::get_callback = nullptr; mock::pause_calls = 0;
    mock::pause_ok = mock::callback_ok = true;
    SDL_ResetHint("PAL_AUDIO_ADAPTIVE_LEAD");
    g_cfg = SaturnConfig{};
    g_settings = Settings{};
    g_win = reinterpret_cast<SDL_Window*>(1);
    g_audio = mock::stream();
    g_lead = 2205;
    g_underruns = g_dropped = g_query_errors = g_put_errors = 0;
    g_pcm_attempted = g_pcm_accepted = g_pcm_dropped = g_pcm_failed = 0;
    g_initial_zeros = g_recovery_zeros = g_max_push_gap_us = 0;
    g_audio_started = Clock::now(); g_audio_last_push = {};
    mock::puts.clear(); mock::put_results.clear(); mock::notes.clear();
    mock::device = {SDL_AUDIO_S16, 2, 44100}; mock::requested = {};
    mock::quantum = 4096; mock::queued_bytes = 400;
    mock::open_ok = mock::format_ok = mock::resume_ok = true;
    mock::open_calls = mock::query_calls = mock::resume_calls = mock::gain_calls = 0;
    mock::hint_name.clear(); mock::hint_value.clear();
}

static std::vector<int16_t> pcm(int frames) {
    std::vector<int16_t> data(static_cast<std::size_t>(frames) * 2);
    for (std::size_t i = 0; i < data.size(); ++i) data[i] = static_cast<int16_t>(i * 97 + 1);
    return data;
}
static bool zero(const mock::Put& put) {
    return std::all_of(put.data.begin(), put.data.end(), [](auto b) { return b == 0; });
}
static bool same_pcm(const mock::Put& put, const std::vector<int16_t>& data) {
    return put.bytes == static_cast<int>(data.size() * sizeof(int16_t))
        && std::memcmp(put.data.data(), data.data(), put.data.size()) == 0;
}
static void conserved() {
    CHECK(g_pcm_attempted == g_pcm_accepted + g_pcm_dropped + g_pcm_failed);
}

static std::string capture_report() {
    std::FILE* file = std::tmpfile();
    if (!file) { CHECK(false); return {}; }
    std::fflush(stderr);
    const int saved = TEST_DUP(TEST_FILENO(stderr));
    if (saved < 0) { CHECK(false); std::fclose(file); return {}; }
    if (TEST_DUP2(TEST_FILENO(file), TEST_FILENO(stderr)) < 0) {
        CHECK(false); TEST_CLOSE(saved); std::fclose(file); return {};
    }
    host_audio_report();
    std::fflush(stderr);
    TEST_DUP2(saved, TEST_FILENO(stderr)); TEST_CLOSE(saved);
    std::rewind(file);
    std::string out;
    char buf[4096];
    while (const auto n = std::fread(buf, 1, sizeof buf, file)) out.append(buf, n);
    std::fclose(file);
    return out;
}

int main() {
    // SDL's pinned OHAudio bootstrap and real device logs spell it "OHAudio".
    // The old lowercase-only mock hid the production branch-selection failure.
    const struct { const char* name; bool ohaudio; } drivers[] = {
        {"OHAudio", true}, {"ohaudio", true}, {"OHAUDIO", true}, {"pulse", false},
        {"dummy", false}, {"", false}, {"OHAudio-extra", false}, {nullptr, false}
    };
    for (const auto& item : drivers) {
        const char* driver = item.name;
        reset(); mock::null_driver = !driver; mock::driver = driver ? driver : "";
        const bool oh = item.ohaudio;
        CHECK(host_audio_open());
        CHECK(g_audio_jitter == oh && g_audio_observer == oh);
        CHECK((mock::get_callback != nullptr) == oh);
        CHECK(!g_audio_adaptive); // never silently turn the rejected tuning experiment on
        CHECK(g_initial_zeros == (oh ? 4978 : 4410) && g_lead == (oh ? 4978 : 4410));
        const auto original = pcm(735);
        // A downstream pull may exactly drain the source queue with NO shortage.
        // Repeated zero-queue observations must not add 100 ms holes on OHAudio.
        for (int pull = 0; pull < 20; ++pull) {
            if (mock::get_callback) mock::get_callback(nullptr, mock::stream(), 0, 4096 * 4);
            mock::queued_bytes = 0;
            host_audio_push(original.data(), 735);
            CHECK(same_pcm(mock::puts.back(), original));
        }
        CHECK(g_pcm_accepted == 20 * 735 && g_pcm_dropped == 0 && g_pcm_failed == 0);
        CHECK(g_recovery_zeros == (oh ? 0 : 20 * 4410));
        CHECK(g_audio_short_calls == 0 && g_audio_growth_events == 0);
        if (oh) {
            CHECK(g_audio_get_calls == 20 && g_audio_max_request_bytes == 4096 * 4);
            for (int cycle = 0; cycle < 5; ++cycle) {
                const auto before = mock::puts.size();
                audio_pause_for_menu(); audio_resume_after_menu();
                CHECK(mock::puts.size() == before);
                g_audio_lifecycle_epoch.fetch_add(1); // recognized background/foreground signal
                host_audio_push(original.data(), 735);
            }
            CHECK(g_audio_resets == 15 && g_recovery_zeros == 0 && g_lead == 4978);
            CHECK(capture_report().find("observer=1 adaptive=0") != std::string::npos);
        }
        conserved();
    }
    // A failed identity regression should report its checks, not call a null observer below.
    if (failures) { std::printf("driver identity: %d failures\n", failures); return 1; }
    reset(); g_win = nullptr;
    CHECK(!host_audio_open()); CHECK(mock::open_calls == 0); CHECK(mock::puts.empty());

    reset(); mock::open_ok = false;
    CHECK(!host_audio_open()); CHECK(g_audio == nullptr); CHECK(mock::puts.empty()); CHECK(!mock::notes.empty());

    reset();
    CHECK(host_audio_open()); CHECK(g_lead == 4410); CHECK(g_initial_zeros == 4410);
    CHECK(mock::requested.freq == 44100 && mock::requested.channels == 2 && mock::requested.format == SDL_AUDIO_S16);
    CHECK(mock::requested_callback == nullptr);
    CHECK(mock::hint_name == SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES && mock::hint_value == "1024");
    CHECK(mock::puts.size() == 1 && mock::puts[0].bytes == 4410 * 4 && zero(mock::puts[0]));
    CHECK(mock::gain_calls == 1 && mock::resume_calls == 1); CHECK(g_pcm_accepted == 0);

    reset(); mock::device.freq = 48000; mock::quantum = 960;
    CHECK(host_audio_open()); CHECK(g_lead == 2646); CHECK(g_initial_zeros == 2646);
    CHECK(mock::puts.size() == 1 && mock::puts[0].bytes == 2646 * 4);

    reset(); mock::format_ok = false;
    CHECK(host_audio_open()); CHECK(g_lead == 2205); CHECK(g_initial_zeros == 2205);

    reset(); mock::device.freq = 0;
    CHECK(host_audio_open()); CHECK(g_lead == 2205); CHECK(g_initial_zeros == 2205);

    reset(); mock::queued_bytes = -1; auto small = pcm(735);
    host_audio_push(small.data(), 735);
    CHECK(g_query_errors == 1 && g_pcm_failed == 735 && g_pcm_attempted == 735);
    CHECK(g_underruns == 0 && g_recovery_zeros == 0 && mock::puts.empty()); conserved();

    reset(); mock::queued_bytes = 3;
    host_audio_push(small.data(), 735);
    CHECK(g_query_errors == 1 && g_pcm_failed == 735 && g_underruns == 0 && mock::puts.empty()); conserved();

    reset(); mock::queued_bytes = 0; g_lead = 4410; auto big = pcm(8000);
    host_audio_push(big.data(), 8000);
    CHECK(mock::puts.size() == 2); CHECK(mock::puts[0].bytes == 3025 * 4 && zero(mock::puts[0]));
    CHECK(same_pcm(mock::puts[1], big)); CHECK(g_recovery_zeros == 3025 && g_pcm_accepted == 8000);
    CHECK(g_recovery_zeros + g_pcm_accepted == 11025 && g_underruns == 1); conserved();

    reset(); mock::queued_bytes = 0; g_lead = 4410; auto full = pcm(11025);
    host_audio_push(full.data(), 11025);
    CHECK(mock::puts.size() == 1 && same_pcm(mock::puts[0], full));
    CHECK(g_recovery_zeros == 0 && g_pcm_accepted == 11025 && g_underruns == 1); conserved();

    reset(); mock::queued_bytes = 0; auto oversized = pcm(11026);
    host_audio_push(oversized.data(), 11026);
    CHECK(mock::puts.empty() && g_dropped == 1 && g_pcm_dropped == 11026 && g_underruns == 0); conserved();

    reset(); mock::queued_bytes = 4000 * 4;
    host_audio_push(big.data(), 8000);
    CHECK(mock::puts.empty() && g_pcm_dropped == 8000 && g_dropped == 1); conserved();

    reset(); mock::queued_bytes = 100 * 4;
    host_audio_push(small.data(), 735);
    CHECK(mock::puts.size() == 1 && same_pcm(mock::puts[0], small));
    CHECK(g_pcm_accepted == 735 && g_recovery_zeros == 0 && g_underruns == 0); conserved();

    reset(); mock::put_results = {false};
    host_audio_push(small.data(), 735);
    CHECK(g_pcm_accepted == 0 && g_pcm_failed == 735 && g_put_errors == 1); conserved();

    reset(); mock::queued_bytes = 0; g_lead = 4410; mock::put_results = {false, true};
    host_audio_push(small.data(), 735);
    CHECK(mock::puts.size() == 2 && !mock::puts[0].succeeded && mock::puts[1].succeeded);
    CHECK(mock::puts[0].bytes == 4410 * 4 && same_pcm(mock::puts[1], small));
    CHECK(g_recovery_zeros == 0 && g_pcm_accepted == 735 && g_pcm_failed == 0 && g_put_errors == 1); conserved();

    reset(); mock::queued_bytes = 0; g_lead = 4410; mock::put_results = {true, false};
    host_audio_push(small.data(), 735);
    CHECK(g_recovery_zeros == 4410 && g_pcm_accepted == 0 && g_pcm_failed == 735 && g_put_errors == 1); conserved();

    reset(); mock::put_results = {false};
    CHECK(host_audio_open()); CHECK(g_initial_zeros == 0 && g_put_errors == 1 && mock::resume_calls == 1);

    reset(); g_cfg.resume = 100;
    host_audio_push(small.data(), 735);
    CHECK(g_pcm_attempted == 0 && mock::query_calls == 0 && mock::puts.empty());
    g_cfg.resume = 0; g_audio = nullptr; host_audio_push(small.data(), 735);
    CHECK(g_pcm_attempted == 0 && mock::query_calls == 0);
    g_audio = mock::stream(); host_audio_push(small.data(), 0); host_audio_push(small.data(), -1);
    CHECK(g_pcm_attempted == 0 && mock::query_calls == 0);

    reset();
    host_audio_push(small.data(), 735);
    const auto now = Clock::now();
    g_audio_started = now - std::chrono::seconds(10);
    g_audio_last_push = now - std::chrono::seconds(5);
    const auto text = capture_report();
    CHECK(text.find("audio stream: 0 times empty, 0 chunks dropped") != std::string::npos);
    CHECK(text.find("wall_total_s=") != std::string::npos);
    CHECK(text.find("wall_to_last_push_s=5.000000") != std::string::npos);
    CHECK(text.find("attempted=735 accepted=735") != std::string::npos);
    CHECK(mock::puts.size() == 1 && g_pcm_accepted == 735); conserved();

    reset();
    host_audio_push(small.data(), 735);  // accepted
    mock::queued_bytes = -1; host_audio_push(small.data(), 735);  // query failure
    mock::queued_bytes = 4000 * 4; host_audio_push(big.data(), 8000);  // capacity drop
    mock::queued_bytes = 400; mock::put_results = {true, false}; host_audio_push(small.data(), 735);  // real Put failure
    CHECK(g_pcm_accepted == 735 && g_pcm_failed == 1470 && g_pcm_dropped == 8000);
    CHECK(g_query_errors == 1 && g_put_errors == 1); conserved();

    reset(); g_lead = 4410; g_pcm_attempted = g_pcm_accepted = 999;
    g_underruns = g_query_errors = g_put_errors = 3;
    g_initial_zeros = g_recovery_zeros = 17; g_max_push_gap_us = 99;
    g_audio_last_push = Clock::now(); mock::format_ok = false;
    CHECK(host_audio_open()); CHECK(g_lead == 2205);
    CHECK(g_pcm_attempted == 0 && g_pcm_accepted == 0 && g_pcm_failed == 0 && g_pcm_dropped == 0);
    CHECK(g_underruns == 0 && g_query_errors == 0 && g_put_errors == 0);
    CHECK(g_initial_zeros == 2205 && g_recovery_zeros == 0 && g_max_push_gap_us == 0);
    CHECK(g_audio_last_push == Clock::time_point{});

    reset(); mock::resume_ok = false;
    CHECK(host_audio_open()); CHECK(mock::resume_calls == 1);
    CHECK(std::any_of(mock::notes.begin(), mock::notes.end(), [](const auto& line) {
        return line.find("resume failed") != std::string::npos;
    }));
    CHECK(std::any_of(mock::notes.begin(), mock::notes.end(), [](const auto& line) {
        return line.find("driver=mock_audio") != std::string::npos;
    }));

    reset(); mock::driver = "OHAudio";
    CHECK(host_audio_open()); CHECK(g_audio_jitter && g_audio_observer && mock::get_callback);
    CHECK(g_initial_zeros == 4978 && g_lead == 4978 && mock::puts.size() == 1);
    g_audio_adaptive=true;
    mock::queued_bytes = 0;
    host_audio_push(small.data(), 735);
    CHECK(mock::puts.size() == 2 && same_pcm(mock::puts.back(), small));
    CHECK(g_recovery_zeros == 0 && g_underruns == 1);
    mock::get_callback(nullptr, mock::stream(), 0, 4096*4);
    host_audio_push(small.data(), 735);
    CHECK(g_audio_get_calls == 1 && g_audio_short_calls == 0 && g_recovery_zeros == 0);
    CHECK(g_audio_callback_same_thread == 1 && g_audio_callback_other_thread == 0);
    std::thread worker([] { mock::get_callback(nullptr, mock::stream(), 100*4, 4096*4); }); worker.join();
    CHECK(g_audio_callback_other_thread == 1 && g_audio_short_epoch == 1);
    host_audio_push(small.data(), 735); // startup consumes old shortage, does not grow
    CHECK(g_recovery_zeros == 0);
    g_audio_adapt_started = Clock::now() - std::chrono::seconds(3);
    host_audio_push(small.data(), 735);
    CHECK(g_recovery_zeros == 0); // startup epoch must not trigger later
    mock::get_callback(nullptr, mock::stream(), 100*4, 4096*4);
    host_audio_push(small.data(), 735);
    CHECK(g_recovery_zeros == 882 && g_lead == 5860 && g_audio_growth_events == 1);
    CHECK(same_pcm(mock::puts.back(), small)); conserved();
    for (int cycle=0; cycle<10; ++cycle) {
        const auto old_padding = g_recovery_zeros; const auto old_lead = g_lead;
        auto old_endpoint = g_audio_last_push;
        auto old_puts = mock::puts.size();
        audio_pause_for_menu();
        mock::get_callback(nullptr, mock::stream(), 4096*4, 4096*4); // adverse callback while paused
        audio_resume_after_menu();
        CHECK(g_audio_last_push == old_endpoint); // retained for menu Quit report
        CHECK(mock::puts.size() == old_puts); // no clear/prime/padding during pause or resume
        g_audio_last_push = Clock::now()-std::chrono::seconds(30);
        const auto gap_before = g_max_push_gap_us;
        host_audio_push(small.data(), 735);
        CHECK(g_max_push_gap_us == gap_before);
        CHECK(g_initial_zeros == 4978 && g_recovery_zeros == old_padding && g_lead == old_lead);
        g_audio_adapt_started=Clock::now()-std::chrono::seconds(3);
        mock::get_callback(nullptr, mock::stream(), 4096*4, 4096*4);
        host_audio_push(small.data(),735);
        CHECK(g_recovery_zeros == 1069 && g_lead == 6047); // repeated menus cannot replenish budget
    }
    CHECK(mock::pause_calls == 10 && mock::resume_calls == 11);
    CHECK(g_audio_resets == 20); conserved();
    g_audio_format_dirty = true; g_audio_lifecycle_epoch.fetch_add(1);
    mock::device.freq=48000; mock::quantum=960;
    host_audio_push(small.data(),735);
    CHECK(g_audio_device_rate==48000 && g_audio_device_quantum==960 && g_audio_format_changes==1);
    CHECK(g_lead==6047 && g_recovery_zeros==1069); // requery diagnostics, do not discard or re-prime
    const auto report=capture_report();
    CHECK(report.find("callback_other_thread=1")!=std::string::npos);
    CHECK(report.find("source shortage estimates, not hardware underruns")!=std::string::npos);

    reset(); mock::driver="OHAudio"; CHECK(host_audio_open()); g_audio_adaptive=true;
    g_audio_adapt_started=Clock::now()-std::chrono::seconds(3); mock::queued_bytes=0;
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4);
    mock::put_results={true,false,true}; // initial success, growth failure, real success
    host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_pcm_accepted==735 && g_audio_growth.target==4978 && g_put_errors==1);
    CHECK(same_pcm(mock::puts.back(),small)); conserved();

    reset(); mock::driver="OHAudio"; CHECK(host_audio_open()); g_audio_adaptive=true;
    g_audio_adapt_started=Clock::now()-std::chrono::seconds(3); mock::queued_bytes=0;
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4);
    mock::put_results={true,true,false};
    host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==882 && g_pcm_accepted==0 && g_pcm_failed==735 && g_lead==5860); conserved();

    reset(); mock::driver="OHAudio"; CHECK(host_audio_open()); g_audio_adaptive=true;
    g_audio_adapt_started=Clock::now()-std::chrono::seconds(3); mock::queued_bytes=(11025-735-881)*4;
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4);
    host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_pcm_accepted==735); conserved();
    mock::queued_bytes=0; host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0); // no stale capacity-blocked event
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4); mock::queued_bytes=-1;
    host_audio_push(small.data(),735); mock::queued_bytes=0; host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_query_errors==1); conserved();

    reset(); mock::driver="OHAudio"; mock::callback_ok=false; CHECK(host_audio_open());
    CHECK(!g_audio_observer); mock::queued_bytes=0; host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_pcm_accepted==735);
    mock::pause_ok=mock::resume_ok=false; audio_pause_for_menu(); audio_resume_after_menu();
    CHECK(g_audio_pause_errors==1 && g_audio_resume_errors==1);
    // A genuine SDL stream, manually pulled at the measured 4096-frame quantum.
    // No device/init/thread timing is simulated here: this establishes PCM identity
    // and that an exactly drained input stream does not cause inserted 100 ms gaps.
    reset(); mock::driver = "OHAudio";
    SDL_AudioSpec source{SDL_AUDIO_S16, 2, 44100};
    mock::real_stream = SDL_CreateAudioStream(&source, &source);
    CHECK(mock::real_stream != nullptr);
    if (mock::real_stream) {
        CHECK(host_audio_open());
        std::vector<int16_t> prime(4978 * 2, -1);
        CHECK(SDL_GetAudioStreamData(mock::real_stream, prime.data(), 4978 * 4) == 4978 * 4);
        CHECK(std::all_of(prime.begin(), prime.end(), [](int16_t x) { return x == 0; }));
        CHECK(real_queued(mock::real_stream) == 0);
        auto chunk = pcm(4096);
        std::vector<int16_t> pulled(chunk.size());
        for (int cycle = 0; cycle < 20; ++cycle) {
            host_audio_push(chunk.data(), 4096);
            CHECK(real_queued(mock::real_stream) == 4096 * 4);
            CHECK(SDL_GetAudioStreamData(mock::real_stream, pulled.data(), 4096 * 4) == 4096 * 4);
            CHECK(pulled == chunk && real_queued(mock::real_stream) == 0);
            if (cycle % 4 == 0) { audio_pause_for_menu(); audio_resume_after_menu(); }
        }
        CHECK(g_pcm_attempted == 20 * 4096 && g_pcm_accepted == 20 * 4096);
        CHECK(g_audio_get_calls == 21 && g_audio_short_calls == 0);
        CHECK(g_initial_zeros == 4978 && g_recovery_zeros == 0 && g_pcm_dropped == 0 && g_pcm_failed == 0);
        CHECK(g_underruns == 20 && !g_audio_adaptive && g_audio_growth_events == 0);
        conserved();
        // An actual shortage must not leave the stream waiting for a refill
        // threshold, nor insert silence before the next real producer chunk.
        // Run beyond startup warmup so that default-off adaptation is meaningful.
        g_audio_adapt_started = Clock::now() - std::chrono::seconds(3);
        std::fill(pulled.begin(), pulled.end(), -12345);
        CHECK(SDL_GetAudioStreamData(mock::real_stream, pulled.data(), 4096 * 4) == 0);
        CHECK(std::all_of(pulled.begin(), pulled.end(), [](int16_t x) { return x == -12345; }));
        CHECK(g_audio_short_calls == 1 && g_audio_additional_bytes == 4096 * 4);
        CHECK(real_queued(mock::real_stream) == 0);
        const auto partial = pcm(735);
        host_audio_push(partial.data(), 735);
        CHECK(real_queued(mock::real_stream) == 735 * 4);
        CHECK(SDL_GetAudioStreamData(mock::real_stream, pulled.data(), 4096 * 4) == 735 * 4);
        CHECK(std::equal(partial.begin(), partial.end(), pulled.begin()));
        CHECK(std::all_of(pulled.begin() + partial.size(), pulled.end(), [](int16_t x) { return x == -12345; }));
        CHECK(real_queued(mock::real_stream) == 0);
        CHECK(g_audio_short_calls == 2 && g_audio_additional_bytes == (4096 + 4096 - 735) * 4);
        host_audio_push(chunk.data(), 4096);
        CHECK(real_queued(mock::real_stream) == 4096 * 4);
        CHECK(SDL_GetAudioStreamData(mock::real_stream, pulled.data(), 4096 * 4) == 4096 * 4);
        CHECK(pulled == chunk && real_queued(mock::real_stream) == 0);
        CHECK(g_audio_get_calls == 24 && g_audio_short_calls == 2);
        CHECK(g_pcm_accepted == 21 * 4096 + 735 && g_pcm_dropped == 0 && g_pcm_failed == 0);
        CHECK(g_recovery_zeros == 0 && g_initial_zeros == 4978 && g_lead == 4978);
        CHECK(!g_audio_adaptive && g_audio_growth_events == 0);
        conserved();
        SDL_DestroyAudioStream(mock::real_stream); mock::real_stream = nullptr;
        g_audio = nullptr;
    }
    // Running telemetry is producer-only, rate limited, and reports deltas.
    reset(); mock::driver = "OHAudio"; CHECK(host_audio_open());
    const auto telemetry_pcm = pcm(735);
    mock::notes.clear();
    host_audio_push(telemetry_pcm.data(), 735);
    CHECK(mock::notes.empty());
    mock::get_callback(nullptr, mock::stream(), 100, 16384);
    g_audio_live.started = Clock::now()-std::chrono::seconds(6);
    host_audio_push(telemetry_pcm.data(), 735);
    CHECK(mock::notes.size() == 2);
    CHECK(mock::notes[0].find("accepted=1470") != std::string::npos);
    CHECK(mock::notes[0].find("chunk_frames=735..735") != std::string::npos);
    CHECK(mock::notes[1].find("short_calls=1 additional_bytes_est=100") != std::string::npos);
    CHECK(g_recovery_zeros == 0 && g_initial_zeros == 4978);
    mock::notes.clear();
    audio_pause_for_menu(); audio_resume_after_menu();
    g_audio_live.started = Clock::now()-std::chrono::seconds(6);
    host_audio_push(telemetry_pcm.data(), 735);
    CHECK(mock::notes.size() == 2);
    CHECK(mock::notes[0].find("accepted=735") != std::string::npos);
    CHECK(mock::notes[0].find("lifecycle_resets=2") != std::string::npos);
    CHECK(mock::notes[1].find("short_calls=0 additional_bytes_est=0") != std::string::npos);
    // Invalid queue/error paths still emit useful stats instead of going silent.
    mock::notes.clear(); mock::queued_bytes = -1;
    g_audio_live.started = Clock::now()-std::chrono::seconds(6);
    host_audio_push(telemetry_pcm.data(), 735);
    CHECK(mock::notes.size() == 2 && mock::notes[0].find("failed=735") != std::string::npos);

    // Actual SDL stream, deterministic event schedule (no sleep/hardware).
    // Integer cross-multiplied clocks preserve 4096/48000 and 735/44100 exactly.
    // 60 seconds each: phase, variable producer chunks, bounded jitter, menus.
    for (int rate : {44100, 48000}) for (int phase : {0, 314, 734}) {
        reset(); mock::driver = "OHAudio"; mock::device.freq = rate;
        SDL_AudioSpec src{SDL_AUDIO_S16, 2, 44100}, dst{SDL_AUDIO_S16, 2, rate};
        mock::real_stream = SDL_CreateAudioStream(&src, &dst);
        CHECK(mock::real_stream != nullptr);
        if (!mock::real_stream) continue;
        CHECK(host_audio_open());
        const int expected_prime = jitter::initial(4096, rate).frames;
        std::vector<int16_t> in(735*2, 1234), out(4096*2);
        uint64_t produced = 0, missing = 0;
        int pn = 1, cn = 0;
        // <=100 source frames jitter (2.27ms) plus 16.67ms chunk phase fits 20ms.
        while (true) {
            const int64_t pt = (int64_t(pn)*735 + (pn%17 == 0 ? 100 : 0))*rate;
            const int64_t ct = int64_t(phase)*rate + int64_t(cn)*4096*44100;
            const int64_t t = std::min(pt, ct);
            if (t >= int64_t(60)*44100*rate) break;
            if (ct <= pt) {
                const int bytes = SDL_GetAudioStreamData(mock::real_stream, out.data(), 4096*4);
                CHECK(bytes >= 0 && bytes <= 4096*4);
                if (bytes >= 0) missing += (4096*4-bytes)/4;
                ++cn;
            } else {
                // Same PCM amount; exercise non-735 source chunks.
                for (int n : {147, 221, 367}) host_audio_push(in.data(), n);
                produced += 735; ++pn;
                mock::puts.clear();
                if (pn%900 == 0) { audio_pause_for_menu(); audio_resume_after_menu(); }
            }
        }
        CHECK(missing == 0 && g_audio_short_calls == 0);
        CHECK(g_pcm_accepted == produced && g_pcm_dropped == 0 && g_pcm_failed == 0);
        CHECK(g_initial_zeros == (uint64_t)expected_prime && g_recovery_zeros == 0);
        CHECK(!g_audio_adaptive && g_audio_growth_events == 0);
        conserved();
        SDL_DestroyAudioStream(mock::real_stream); mock::real_stream = nullptr; g_audio = nullptr;
    }
    std::printf("%d actual-host audio cases, %d checks, %d failures; no GUI/audio device created\n", cases, checks, failures);
    return failures ? 1 : 0;
}
