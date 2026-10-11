// OpenHarmony entry: SDL's OHOS bootstrap dlopen()s libmain.so for SDL_main() and runs it on its own
// thread. There is no command line on this platform, so the disc, settings and save paths come from
// the game folder: <Download>/<bundleName>/ first, then the app's own files dir.
#include <hilog/log.h>

#include <SDL3/SDL.h>

#include <AbilityKit/ability_runtime/application_context.h>
#include <filemanagement/environment/oh_environment.h>

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <string>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <vector>

// src/app/main.cpp is compiled with -Dmain=saturn_main for this target.
extern int saturn_main(int argc, char** argv);
extern "C" const char* pal_movie_cache_feature();

#ifndef PAL_BUNDLE_NAME
#define PAL_BUNDLE_NAME "com.palhero.palsaturn"
#endif

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

std::vector<std::string> list_dir(const std::string& dir)
{
    std::vector<std::string> out;
    DIR* d = ::opendir(dir.c_str());
    if (!d) return out;
    while (const dirent* e = ::readdir(d))
        if (std::strcmp(e->d_name, ".") && std::strcmp(e->d_name, "..")) out.push_back(e->d_name);
    ::closedir(d);
    std::sort(out.begin(), out.end());
    return out;
}

bool ends_with(const std::string& s, const char* ext)
{
    const std::size_t n = std::strlen(ext);
    if (s.size() < n) return false;
    for (std::size_t i = 0; i < n; ++i)
        if (std::tolower((unsigned char)s[s.size() - n + i]) != std::tolower((unsigned char)ext[i])) return false;
    return true;
}

// The disc to mount: <root>/disc/ first, then <root>. CUE beats BIN; the drive needs the track table.
std::string find_disc(const std::string& root)
{
    for (const std::string& where : { join(root, "disc"), root }) {
        std::string bin;
        for (const std::string& name : list_dir(where)) {
            const std::string p = join(where, name);
            if (!is_file(p)) continue;
            if (ends_with(name, ".cue")) return p;
            if (bin.empty() && ends_with(name, ".bin")) bin = p;
        }
        if (!bin.empty()) return bin;
    }
    return "";
}

// A path out of an OH_AbilityRuntime getter, which writes into a buffer we size.
std::string oh_path(AbilityRuntime_ErrorCode (*get)(char*, const int32_t, int32_t*))
{
    std::vector<char> buf(512, 0);
    int32_t written = 0;
    if (get(buf.data(), (int32_t)buf.size() - 1, &written) != ABILITY_RUNTIME_ERROR_CODE_NO_ERROR) return "";
    return std::string(buf.data(), ::strnlen(buf.data(), buf.size()));
}

std::string download_dir()
{
    char* raw = nullptr;
    const FileManagement_ErrCode rc = OH_Environment_GetUserDownloadDir(&raw);
    std::string out = (rc == 0 && raw) ? raw : "";
    if (rc != 0) note("OH_Environment_GetUserDownloadDir error %d", (int)rc);
    std::free(raw);
    if (!out.empty()) while (out.size() > 1 && out.back() == '/') out.pop_back();
    return out;
}

// The folder the player drops the disc into; creating it is the only way to learn whether the public
// Download directory is reachable at all, and it leaves somewhere to put files when it is.
bool ensure_dir(const std::string& p)
{
    if (is_dir(p)) return true;
    if (::mkdir(p.c_str(), 0775) == 0) { note("created %s", p.c_str()); return true; }
    note("cannot make %s: %s", p.c_str(), std::strerror(errno));
    return false;
}

// The Download folder is where the player puts their own disc, but writing there needs a user-grant
// permission, so ask for it and wait for the answer: the run needs its paths before it starts.
std::atomic<int> download_granted(-1);

void SDLCALL download_permission_result(void*, const char*, bool granted)
{
    download_granted = granted ? 1 : 0;
}

// The first folder that holds a disc, in the order the player is most likely to have used.
bool scan(const std::vector<std::string>& roots, std::string& root, std::string& cue)
{
    for (const std::string& r : roots) {
        note("look in %s [%s]", r.c_str(), is_dir(r) ? "dir" : "no dir");
        if (!is_dir(r)) continue;
        const std::string found = find_disc(r);
        if (found.empty()) continue;
        root = r;
        cue = found;
        return true;
    }
    return false;
}

// What the public Download folder actually allows once the permission is granted: reading the game
// needs a listing, saves need a write, and the folder layout needs mkdir (which is refused).
void probe_download(const std::string& dl)
{
    note("download listing: %d entries", (int)list_dir(dl).size());
    const std::string probe = join(dl, ".pal-probe");
    if (FILE* f = std::fopen(probe.c_str(), "wb")) {
        std::fclose(f);
        ::remove(probe.c_str());
        note("download accepts new files");
    } else {
        note("cannot make %s: %s", probe.c_str(), std::strerror(errno));
    }
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
    const std::string bundle = oh_path(OH_AbilityRuntime_ApplicationContextGetBundleName);
    const std::string name = bundle.empty() ? PAL_BUNDLE_NAME : bundle;
    const std::string files = oh_path(OH_AbilityRuntime_ApplicationContextGetFilesDir);
    const std::string dl = download_dir();

    std::vector<std::string> roots;
    if (!dl.empty()) roots.push_back(join(dl, name));
    if (!files.empty()) roots.push_back(join(files, name));
    if (!files.empty()) roots.push_back(files);
    if (roots.empty()) { note("no game folder: neither the download nor the files dir resolved"); return 2; }

    std::string root, cue;
    if (!scan(roots, root, cue) && !dl.empty() && !is_dir(join(dl, name))) {
        // Nothing under Download and we can't even see whether it is there: ask before giving up.
        if (SDL_RequestOpenHarmonyPermission("ohos.permission.READ_WRITE_DOWNLOAD_DIRECTORY",
                                             download_permission_result, nullptr)) {
            note("asking for the Download permission");
            for (int i = 0; i < 300 && download_granted < 0; ++i) SDL_Delay(100);
            note("Download permission %s", download_granted > 0 ? "granted" : "not granted");
            scan(roots, root, cue);
        }
    }
#ifdef PAL_OHOS_SELFTEST
    if (cue.empty() && !files.empty() && write_selftest_disc(join(files, "selftest"))) {
        root = join(files, "selftest");
        cue = join(join(root, "disc"), "synthetic.cue");
        note("selftest: booting a synthetic disc, the device has no image yet");
    }
#endif
    if (cue.empty()) {
        if (!dl.empty()) probe_download(dl);
        if (!dl.empty() && ensure_dir(join(dl, name))) ensure_dir(join(dl, name) + "/disc");
        note("no .cue or .bin in any game folder; copy your own Saturn disc image into one of them");
        return 2;
    }

    // Saves belong next to the disc, unless that folder is read-only, in which case the sandbox keeps them.
    std::string home = root;
    if (::access(root.c_str(), W_OK) != 0 && !files.empty()) {
        note("%s is read-only, saves go to %s", root.c_str(), files.c_str());
        home = files;
    }
    const std::string saves = join(home, "saves");
    if (!is_dir(saves)) ::mkdir(saves.c_str(), 0775);

    std::vector<std::string> args{ "saturn", "--cue", cue, "--save", join(saves, "pal-saturn.bup"),
                                   "--clock", "1998-11-01T12:00:00", "--fullscreen",
                                   // sat_data_dir() has no home on HarmonyOS, so the settings have to be named
                                   "--settings", join(home, "settings.ini") };
    // 默认直接进游戏。玩家要那套完整菜单（多人/按键/显示）时，由划出的"扩展设定"面板在这个文件里
    // 留个记号再重启，运行时才走 --launcher。
    if (is_file(join(home, "advanced.txt"))) args.push_back("--launcher");

    std::string line;
    for (const std::string& a : args) { line += ' '; line += a; }
    note("argv:%s", line.c_str());

    std::vector<char*> argv_out;
    for (std::string& a : args) argv_out.push_back(a.data());
    argv_out.push_back(nullptr);
    note("PAL features: %s", pal_movie_cache_feature());
    return saturn_main((int)argv_out.size() - 1, argv_out.data());
}
