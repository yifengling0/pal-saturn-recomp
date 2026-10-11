#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

// Semantic PC keys choose exactly one Saturn button per physical press. Native
// Saturn bindings and physical gamepads never pass through this translator.
namespace pal_keyboard {
inline constexpr uint16_t Start = 0x0800, Confirm = 0x0400, Cancel = 0x0100, Menu = 0x0040;
inline constexpr uint16_t Strongest = 0x0008, Repeat = 0x0010; // native Saturn L / Z
inline constexpr uint16_t Items = 0x0080;                      // native Saturn R
// The PAL98 shortcut letters pick the Saturn button that does the same thing in the
// context the guest is really in: the field's R/L quick pages, and nothing at all
// while a menu, dialogue or battle phase owns the screen.
struct Context { uint16_t confirm = Start, cancel = Cancel, item = 0, spell = 0; };
inline Context context;
inline uint64_t boundary = 0;
inline bool battle_commands = false;
inline uint64_t battle_boundary = 0;
inline void close_battle_commands() { battle_commands = false; ++battle_boundary; }
inline void clear() { ++boundary; close_battle_commands(); }
inline void field() { if (battle_commands) close_battle_commands(); context = {Confirm, Menu, Items, Strongest}; }
inline void ui(bool start = false) { if (battle_commands) close_battle_commands(); context = {start ? Start : Confirm, Cancel, 0, 0}; }
inline void boot() { clear(); context = {Start, Cancel, 0, 0}; }

// Only the original battle four-icon command menu owns this scope. No input
// function, poll, guest register, RNG, action queue or MP is changed by it.
// A separate boundary keeps the established Enter/Escape behavior unchanged.
struct BattleCommandsScope {
    explicit BattleCommandsScope(bool in_battle) {
        close_battle_commands();
        battle_commands = in_battle;
    }
    ~BattleCommandsScope() { close_battle_commands(); }
    BattleCommandsScope(const BattleCommandsScope&) = delete;
    BattleCommandsScope& operator=(const BattleCommandsScope&) = delete;
};

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

// New battle shortcuts have their own latch: presses outside the main command
// menu are consumed as zero, never queued for a later menu/turn. Crossing a
// scope boundary retires the bit but keeps the physical hold until key-up.
struct BattlePressLatch {
    PressLatch presses;
    uint64_t seen_boundary = battle_boundary;
    void sync() {
        if (seen_boundary != battle_boundary) {
            seen_boundary = battle_boundary;
            presses.block();
        }
    }
    void down(int key, uint16_t bit, bool repeat, bool focused, bool blocked) {
        sync(); // Retire old presses before accepting a fresh edge.
        presses.down(key, battle_commands ? bit : uint16_t(0), repeat, focused, blocked);
    }
    void up(int key) { presses.up(key); }
    void block() { presses.block(); }
    uint16_t read(int key) {
        sync();
        return battle_commands ? presses.read(key) : uint16_t(0);
    }
};
}
