#pragma once

#include <fstream>
#include <string>

namespace pal_ohos {
struct LaunchPaths {
    std::string root;
    std::string cue;
    std::string home;
};

inline bool safe_path(const std::string& path)
{
    return !path.empty() && path.front() == '/' && path.size() < 4096 &&
           path.find('\0') == std::string::npos && path.find('\r') == std::string::npos &&
           path.find("/../") == std::string::npos && path.find("/./") == std::string::npos &&
           path.back() != '/';
}

// This app-private, atomically published selection is the only handoff from
// ArkTS preflight to SDL. A partial/corrupt file never launches a different disc.
inline bool read_launch_paths(const std::string& path, LaunchPaths& result)
{
    std::ifstream input(path);
    std::string version, extra;
    LaunchPaths selected;
    if (!std::getline(input, version) || version != "PAL1" ||
        !std::getline(input, selected.root) || !std::getline(input, selected.cue) ||
        !std::getline(input, selected.home) || std::getline(input, extra)) return false;
    if (!safe_path(selected.root) || !safe_path(selected.cue) || !safe_path(selected.home) ||
        selected.cue.compare(0, selected.root.size() + 1, selected.root + "/") != 0) return false;
    result = selected;
    return true;
}
} // namespace pal_ohos
