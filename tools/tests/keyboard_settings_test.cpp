// Optional integration against the public upstream Settings implementation only.
#include "settings.h"
#include <cstdlib>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
namespace {
int checks = 0;
void check(bool ok, const char* name) {
    ++checks;
    if (!ok) { std::cerr << "FAIL: " << name << '\n'; std::exit(1); }
}
}
int main() {
    std::vector<std::string> errors;
    Settings fresh;
    check(fresh.get("controls", "keyboard_profile") == "pc98", "fresh config selects pc98");
    check(fresh.get("keyboard", "start") == "Return", "original Saturn mapping preserved");
    check(fresh.get("keyboard pc98", "start") == "Tab", "PC98 physical start is Tab");
    check(fresh.get("keyboard pc98", "confirm") == "Return, Keypad Enter, Space", "PC98 confirms");
    check(fresh.get("keyboard pc98", "menu_cancel") == "Escape", "PC98 cancellation");
    check(fresh.get("gamepad", "a") == "a", "gamepad default independent");
    check(std::string(Settings::default_text()).find("PAL_KEYBOARD_PROFILE_V2") != std::string::npos, "version marker emitted");
    const std::string old = "; keep custom choices\n[keyboard]\na = Return\nb = Escape\nstart = F2\n[gamepad]\na = b\n";
    Settings legacy;
    legacy.read(old, errors);
    check(errors.empty(), "legacy settings valid");
    check(legacy.get("controls", "keyboard_profile") == "saturn", "legacy profile defaults to Saturn");
    check(legacy.get("keyboard", "a") == "Return" && legacy.get("keyboard", "b") == "Escape", "legacy custom bindings retained");
    check(legacy.get("gamepad", "a") == "b", "custom gamepad untouched");
    auto saved = legacy.write_over(old);
    check(saved.find("keyboard_profile = saturn") != std::string::npos, "saved migration explicitly preserves Saturn");
    check(saved.find("; keep custom choices") != std::string::npos, "legacy comment retained");
    Settings reload;
    reload.read(saved, errors);
    check(errors.empty() && reload.get("controls", "keyboard_profile") == "saturn", "saved legacy profile reloads");
    legacy.set("controls", "keyboard_profile", "pc98");
    check(legacy.get("keyboard", "start") == "F2", "profile switching does not replace old bindings");
    Settings empty;
    empty.read("", errors);
    check(empty.get("controls", "keyboard_profile") == "saturn", "existing empty file stays legacy");
    Settings generated;
    generated.read(Settings::default_text(), errors);
    check(errors.empty() && generated.get("controls", "keyboard_profile") == "pc98", "generated default file is explicit pc98");
    Settings explicit_pc;
    explicit_pc.read("[controls]\nkeyboard_profile = pc98\n[keyboard pc98]\nconfirm = J\nmenu_cancel = K\n", errors);
    check(errors.empty() && explicit_pc.get("keyboard pc98", "confirm") == "J", "semantic rebind parsed");
    check(explicit_pc.get("keyboard pc98", "menu_cancel") == "K", "semantic cancel rebind parsed");
    Settings invalid;
    invalid.read("[controls]\nkeyboard_profile = unknown\n", errors);
    check(errors.size() == 1, "invalid profile reports one error");
    check(invalid.get("controls", "keyboard_profile") == "pc98", "invalid explicit profile falls back to fresh default");
    errors.clear();
    check(fresh.get("keyboard pc98", "strongest") == "F", "fresh strongest is F only");
    check(fresh.get("keyboard pc98", "all_attack") == "A", "A ordinary all attack");
    check(fresh.get("keyboard pc98", "defend") == "D", "D defend");
    check(fresh.get("keyboard pc98", "throw") == "W", "W battle throw");
    check(fresh.get("keyboard pc98", "repeat") == "R", "fresh repeat is R");
    check(fresh.get("keyboard pc98", "item") == "E", "fresh item page is E");
    check(fresh.get("keyboard pc98", "spell") == "F", "fresh spell page is F");
    check(fresh.get("keyboard pc98", "status") == "S", "fresh status walk is S");
    check(fresh.get("keyboard pc98", "equip") == "W", "fresh equipment walk is W");
    check(fresh.get("keyboard pc98", "system") == "Q", "fresh save/load walk is Q");
    // The PAL98 letters own the Saturn buttons they replace, so those rows ship unbound.
    for (const char* key : {"y", "z", "l", "r"})
        check(fresh.get("keyboard pc98", key).empty(), "replaced Saturn binding starts unbound");
    check(fresh.get("keyboard pc98", "x") == "V", "Saturn X keeps one unclaimed key");
    Settings old_pc;
    old_pc.read("[controls]\nkeyboard_profile = pc98\n[keyboard pc98]\na = F\nb = R\nconfirm = J\n", errors);
    check(errors.empty(), "old PC settings parse without new shortcut fields");
    check(old_pc.get("keyboard pc98", "strongest") == "F" && old_pc.get("keyboard pc98", "repeat") == "R", "missing shortcuts retain fresh defaults");
    check(old_pc.get("keyboard pc98", "a") == "F" && old_pc.get("keyboard pc98", "b") == "R", "old ordinary F/R preserved for host collision priority");
    Settings custom_pc;
    custom_pc.read("[controls]\nkeyboard_profile = pc98\n[keyboard pc98]\nstrongest = G\nrepeat = T\n", errors);
    check(errors.empty() && custom_pc.get("keyboard pc98", "strongest") == "G" && custom_pc.get("keyboard pc98", "repeat") == "T", "battle shortcuts can be rebound");
    Settings disabled_pc;
    disabled_pc.read("[controls]\nkeyboard_profile = pc98\n[keyboard pc98]\nstrongest = \nrepeat = \n", errors);
    check(errors.empty() && disabled_pc.get("keyboard pc98", "strongest").empty() && disabled_pc.get("keyboard pc98", "repeat").empty(), "explicit empty battle shortcuts stay disabled");
    namespace fs = std::filesystem;
    const fs::path dir = "checked-settings-cases";
    fs::create_directory(dir);
    SettingsLoadStatus status = SettingsLoadStatus::Loaded;
    check(settings_load_checked((dir / "absent.ini").string(), status).empty() &&
          status == SettingsLoadStatus::Missing, "nonexistent path is Missing");
    check(settings_load_checked(dir.string(), status).empty() &&
          status == SettingsLoadStatus::Error, "directory is Error, never Missing");
    const auto empty_path = dir / "empty.ini";
    { std::ofstream file(empty_path); }
    check(settings_load_checked(empty_path.string(), status).empty() &&
          status == SettingsLoadStatus::Loaded, "existing empty file is Loaded");
    const auto loaded_path = dir / "legacy.ini";
    { std::ofstream file(loaded_path, std::ios::binary); file << old; }
    check(settings_load_checked(loaded_path.string(), status) == old &&
          status == SettingsLoadStatus::Loaded, "existing legacy file loads unchanged");
    const auto large_path = dir / "large.ini";
    const std::string large(12500, 'x');
    { std::ofstream file(large_path, std::ios::binary); file << large; }
    check(settings_load_checked(large_path.string(), status) == large &&
          status == SettingsLoadStatus::Loaded, "multi-block read is complete");
    std::error_code ec;
    fs::create_symlink("missing-target.ini", dir / "dangling.ini", ec);
    if (!ec) {
        check(settings_load_checked((dir / "dangling.ini").string(), status).empty() &&
              status == SettingsLoadStatus::Error, "dangling symlink is Error, never Missing");
    } else {
        std::cout << "SKIP: this platform cannot create dangling symlinks\n";
    }
    fs::remove_all(dir);
    std::cout << "PASS: " << checks << " upstream Settings migration checks\n";
}
