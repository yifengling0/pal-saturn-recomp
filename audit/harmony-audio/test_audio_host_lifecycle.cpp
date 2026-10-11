// Include the selected runtime host.cpp directly. Only external SDL/audio endpoints are
// mocked; host_audio_open/push/report and its integrated helper are real code.
// No SDL_Init, real window, audio renderer, device or game is created.
#ifndef HOST_SOURCE
#error "Compile with HOST_SOURCE pointing at the runtime src/host/host.cpp under test"
#endif
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
static SDL_AudioStreamCallback get_callback = nullptr;
static int pause_calls = 0;
static SDL_AudioSpec device{SDL_AUDIO_S16, 2, 44100}, requested{};
static int quantum = 4096, queued_bytes = 400, open_calls = 0;
static int query_calls = 0, resume_calls = 0, gain_calls = 0;
static SDL_AudioStreamCallback requested_callback = nullptr;
static std::string hint_name, hint_value;
static SDL_AudioStream* stream() { return reinterpret_cast<SDL_AudioStream*>(2); }
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
extern "C" const char* SDLCALL SDL_GetCurrentAudioDriver() { return mock::driver.c_str(); }
extern "C" bool SDLCALL SDL_SetAudioStreamGetCallback(SDL_AudioStream*, SDL_AudioStreamCallback cb, void*) {
    if (!mock::callback_ok) return false;
    mock::get_callback = cb; return true;
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
    ++mock::query_calls; return mock::queued_bytes;
}
extern "C" bool SDLCALL SDL_PutAudioStreamData(SDL_AudioStream*, const void* data, int bytes) {
    const std::size_t index = mock::puts.size();
    const bool ok = index < mock::put_results.size() ? mock::put_results[index] : true;
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
    mock::driver = "mock_audio"; mock::get_callback = nullptr; mock::pause_calls = 0;
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

    reset(); mock::driver = "ohaudio";
    CHECK(host_audio_open()); CHECK(g_audio_jitter && g_audio_observer && mock::get_callback);
    CHECK(g_initial_zeros == 4410 && g_lead == 4410 && mock::puts.size() == 1);
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
    CHECK(g_recovery_zeros == 882 && g_lead == 5292 && g_audio_growth_events == 1);
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
        CHECK(g_initial_zeros == 4410 && g_recovery_zeros == old_padding && g_lead == old_lead);
        g_audio_adapt_started=Clock::now()-std::chrono::seconds(3);
        mock::get_callback(nullptr, mock::stream(), 4096*4, 4096*4);
        host_audio_push(small.data(),735);
        CHECK(g_recovery_zeros == 1637 && g_lead == 6047); // repeated menus cannot replenish budget
    }
    CHECK(mock::pause_calls == 10 && mock::resume_calls == 11);
    CHECK(g_audio_resets == 20); conserved();
    g_audio_format_dirty = true; g_audio_lifecycle_epoch.fetch_add(1);
    mock::device.freq=48000; mock::quantum=960;
    host_audio_push(small.data(),735);
    CHECK(g_audio_device_rate==48000 && g_audio_device_quantum==960 && g_audio_format_changes==1);
    CHECK(g_lead==6047 && g_recovery_zeros==1637); // requery diagnostics, do not discard or re-prime
    const auto report=capture_report();
    CHECK(report.find("callback_other_thread=1")!=std::string::npos);
    CHECK(report.find("source shortage estimates, not hardware underruns")!=std::string::npos);

    reset(); mock::driver="ohaudio"; CHECK(host_audio_open()); g_audio_adaptive=true;
    g_audio_adapt_started=Clock::now()-std::chrono::seconds(3); mock::queued_bytes=0;
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4);
    mock::put_results={true,false,true}; // initial success, growth failure, real success
    host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_pcm_accepted==735 && g_audio_growth.target==4410 && g_put_errors==1);
    CHECK(same_pcm(mock::puts.back(),small)); conserved();

    reset(); mock::driver="ohaudio"; CHECK(host_audio_open()); g_audio_adaptive=true;
    g_audio_adapt_started=Clock::now()-std::chrono::seconds(3); mock::queued_bytes=0;
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4);
    mock::put_results={true,true,false};
    host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==882 && g_pcm_accepted==0 && g_pcm_failed==735 && g_lead==5292); conserved();

    reset(); mock::driver="ohaudio"; CHECK(host_audio_open()); g_audio_adaptive=true;
    g_audio_adapt_started=Clock::now()-std::chrono::seconds(3); mock::queued_bytes=(11025-735-881)*4;
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4);
    host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_pcm_accepted==735); conserved();
    mock::queued_bytes=0; host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0); // no stale capacity-blocked event
    mock::get_callback(nullptr,mock::stream(),4096*4,4096*4); mock::queued_bytes=-1;
    host_audio_push(small.data(),735); mock::queued_bytes=0; host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_query_errors==1); conserved();

    reset(); mock::driver="ohaudio"; mock::callback_ok=false; CHECK(host_audio_open());
    CHECK(!g_audio_observer); mock::queued_bytes=0; host_audio_push(small.data(),735);
    CHECK(g_recovery_zeros==0 && g_pcm_accepted==735);
    mock::pause_ok=mock::resume_ok=false; audio_pause_for_menu(); audio_resume_after_menu();
    CHECK(g_audio_pause_errors==1 && g_audio_resume_errors==1);
    std::printf("%d actual-host audio cases, %d checks, %d failures; no GUI/audio device created\n", cases, checks, failures);
    return failures ? 1 : 0;
}
