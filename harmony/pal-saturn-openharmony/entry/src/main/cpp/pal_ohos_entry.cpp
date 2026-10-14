// OpenHarmony entry: SDL's OHOS bootstrap dlopen()s libmain.so for SDL_main() and runs it on its own
// thread. There is no command line on this platform, so the disc, settings and save paths come from
// the preflight page, which provisions Download or imports files before creating the SDL surface.
#include <hilog/log.h>

#include <SDL3/SDL.h>

#include <AbilityKit/ability_runtime/application_context.h>
#include "pal_ohos_launch.h"
#include "pal_ohos_audio.h"

#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <vector>

// src/app/main.cpp is compiled with -Dmain=saturn_main for this target.
extern int saturn_main(int argc, char** argv);
extern void host_shutdown_input();
extern "C" const char* pal_movie_cache_feature();
// Strong references make a stale host object fail at link time. These are
// implemented by the actual host.cpp, not stamped onto this entry wrapper.
extern "C" int pal_host_ui_feature_version();
extern "C" const char* pal_host_ui_source_hash();
extern "C" const char* pal_vdp2_compose_source_hash();
extern "C" const char* pal_cpu_handoff_source_hash();

namespace {

void note(const char* fmt, ...)
{
    char buf[768];
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    OH_LOG_Print(LOG_APP, LOG_INFO, 0x2C00, "PAL/OHOS", "%{public}s", buf);
}

bool is_dir(const std::string& p)
{
    struct stat st;
    return !p.empty() && ::stat(p.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
}

bool is_file(const std::string& p)
{
    struct stat st;
    return !p.empty() && ::stat(p.c_str(), &st) == 0 && S_ISREG(st.st_mode);
}

std::string join(const std::string& a, const std::string& b) { return b.empty() ? a : a + "/" + b; }

// A path out of an OH_AbilityRuntime getter, which writes into a buffer we size.
std::string oh_path(AbilityRuntime_ErrorCode (*get)(char*, const int32_t, int32_t*))
{
    std::vector<char> buf(512, 0);
    int32_t written = 0;
    if (get(buf.data(), (int32_t)buf.size() - 1, &written) != ABILITY_RUNTIME_ERROR_CODE_NO_ERROR) return "";
    return std::string(buf.data(), ::strnlen(buf.data(), buf.size()));
}

// A disc with no game data on it, for the selftest build: the runtime opens the window in video_init(),
// before it looks for a module, so this is enough to see SDL, the surface and the sound on a device
// where nobody has copied an image yet. --launcher then keeps that window up instead of exiting.
bool write_selftest_disc(const std::string& root)
{
    const std::string disc = join(root, "disc");
    if (!is_dir(root) && ::mkdir(root.c_str(), 0775) != 0) {
        note("selftest: cannot make %s: %s", root.c_str(), std::strerror(errno));
        return false;
    }
    if (!is_dir(disc) && ::mkdir(disc.c_str(), 0775) != 0) {
        note("selftest: cannot make %s: %s", disc.c_str(), std::strerror(errno));
        return false;
    }
    const std::string bin = join(disc, "synthetic.bin"), cue = join(disc, "synthetic.cue");
    if (!is_file(bin)) {
        FILE* f = std::fopen(bin.c_str(), "wb");
        if (!f) { note("selftest: cannot write %s: %s", bin.c_str(), std::strerror(errno)); return false; }
        const std::vector<char> zeros(2048, 0);
        for (int i = 0; i < 512; ++i) std::fwrite(zeros.data(), 1, zeros.size(), f);
        std::fclose(f);
    }
    if (!is_file(cue)) {
        FILE* f = std::fopen(cue.c_str(), "wb");
        if (!f) { note("selftest: cannot write %s: %s", cue.c_str(), std::strerror(errno)); return false; }
        std::fprintf(f, "FILE \"synthetic.bin\" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n");
        std::fclose(f);
    }
    return is_file(cue) && is_file(bin);
}

// A HarmonyOS app has no console, and the runtime talks on stdout. Hand it a pipe and put every line
// in hilog, the way --log does for a file.
void capture_output()
{
    int fds[2];
    if (::pipe(fds) != 0) { note("pipe failed: %s", std::strerror(errno)); return; }
    ::dup2(fds[1], STDOUT_FILENO);
    ::dup2(fds[1], STDERR_FILENO);
    ::close(fds[1]);
    std::setvbuf(stdout, nullptr, _IOLBF, 0);   // a pipe would otherwise sit on the notes for kilobytes
    std::thread([fd = fds[0]] {
        std::string pending;
        char chunk[1024];
        ssize_t got = 0;
        while ((got = ::read(fd, chunk, sizeof chunk)) > 0) {
            pending.append(chunk, (std::size_t)got);
            for (std::size_t nl = pending.find('\n'); nl != std::string::npos; nl = pending.find('\n')) {
                note("%s", pending.substr(0, nl).c_str());
                pending.erase(0, nl + 1);
            }
        }
        if (!pending.empty()) note("%s", pending.c_str());
    }).detach();
}

}  // namespace

extern "C" int SDL_main(int argc, char** argv)
{
    (void)argc;
    (void)argv;
    capture_output();
    const std::string files = oh_path(OH_AbilityRuntime_ApplicationContextGetFilesDir);
    pal_ohos::LaunchPaths selected;
    const bool prepared = !files.empty() &&
        pal_ohos::read_launch_paths(join(files, "pal-launch-paths.txt"), selected);
    std::string root = prepared ? selected.root : "";
    std::string cue = prepared ? selected.cue : "";
    std::string home = prepared ? selected.home : "";
#ifdef PAL_OHOS_SELFTEST
    if ((!prepared || !is_file(cue)) && !files.empty() && write_selftest_disc(join(files, "selftest"))) {
        root = join(files, "selftest");
        home = root;
        const std::string selftest_saves = join(root, "saves");
        if (!is_dir(selftest_saves) && ::mkdir(selftest_saves.c_str(), 0775) != 0) return 2;
        cue = join(join(root, "disc"), "synthetic.cue");
        note("selftest: booting a synthetic disc, the device has no image yet");
    }
#endif
    if (cue.empty() || !is_file(cue) || !is_dir(home)) {
        note("launch selection unavailable; use the setup page to rescan or import CUE + BIN");
        return 2;
    }
    // The preflight verified this exact home, preserving the existing save.
    // Do not probe public Download, ask a PC-only permission, or silently fall
    // back to a new save directory after SDL has started.
    const std::string saves = join(home, "saves");
    if (!is_dir(saves) || ::access(saves.c_str(), W_OK) != 0) {
        note("prepared save directory is no longer writable; restart and retry setup");
        return 2;
    }

    std::vector<std::string> args{ "saturn", "--cue", cue, "--save", join(saves, "pal-saturn.bup"),
                                   "--clock", "1998-11-01T12:00:00", "--fullscreen",
                                   // sat_data_dir() has no home on HarmonyOS, so the settings have to be named
                                   "--settings", join(home, "settings.ini") };
    // 默认直接进游戏。advanced.txt 可外部配置，仅在启动时读取以打开完整 launcher；
    // 当前没有游戏内编辑这个标记的入口，也不会因此保存当前进度或自动重启。
    if (is_file(join(home, "advanced.txt"))) args.push_back("--launcher");

    note("launching the prepared disc and save directory");

    std::vector<char*> argv_out;
    for (std::string& a : args) argv_out.push_back(a.data());
    argv_out.push_back(nullptr);
    note("PAL features: %s", pal_movie_cache_feature());
    const int host_ui_version = pal_host_ui_feature_version();
    note("PAL host UI: version=%d source_bytes_sha256=%s", host_ui_version, pal_host_ui_source_hash());
    note("PAL production: compose=cached-frame-v1 source_bytes_sha256=%s handoff=serial-fiber-v1 source_bytes_sha256=%s",
         pal_vdp2_compose_source_hash(), pal_cpu_handoff_source_hash());
    if (host_ui_version != 13) {
        note("host UI version mismatch: require 13; rebuild the verified OHOS runtime");
        return 2;
    }
    const int result = saturn_main((int)argv_out.size() - 1, argv_out.data());
    pal_ohos_audio::close();
    host_shutdown_input();
    return result;
}
