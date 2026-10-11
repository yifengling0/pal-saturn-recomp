#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

// Semantic PC keys choose exactly one Saturn button per physical press. Native
// Saturn bindings and physical gamepads never pass through this translator.
namespace pal_keyboard {
inline constexpr uint16_t Start = 0x0800, Confirm = 0x0400, Cancel = 0x0100, Menu = 0x0040;
struct Context { uint16_t confirm = Start, cancel = Cancel; };
inline Context context;
inline uint64_t boundary = 0;
inline void clear() { ++boundary; }
inline void field() { context = {Confirm, Menu}; }
inline void ui(bool start = false) { context = {start ? Start : Confirm, Cancel}; }
inline void boot() { clear(); context = {Start, Cancel}; }

// SDL scancode-indexed, but deliberately SDL-independent for exhaustive tests.
// A repeated KEYDOWN cannot change its meaning after a menu or scene transition.
struct PressLatch {
    struct Press { bool down = false; uint16_t bit = 0; };
    std::array<Press, 512> keys{};
    void down(int key, uint16_t bit, bool repeat, bool focused, bool blocked) {
        if (key < 0 || static_cast<size_t>(key) >= keys.size()) return;
        auto& p = keys[key];
        if (repeat || p.down) return;
        p = {true, focused && !blocked ? bit : uint16_t(0)};
    }
    void up(int key) {
        if (key >= 0 && static_cast<size_t>(key) < keys.size()) keys[key] = {};
    }
    void reset() { keys = {}; }
    void block() { for (auto& p : keys) p.bit = 0; }
    uint16_t read(int key) const {
        return key >= 0 && static_cast<size_t>(key) < keys.size() ? keys[key].bit : 0;
    }
};
}
