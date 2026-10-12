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

// The Saturn field command menu is a four-entry ring (狀態 / 仙術 / 物品 / 系統) whose cursor
// survives closing it, so a PAL98 letter cannot be a fixed button script. The index lives at
// 0x060768DA: the menu reads it when it opens and writes it on every step, and nothing refreshes
// a menu that is already open, so a letter closes whatever is up, forces the wanted entry into
// that same word, and only then opens and confirms what the menu itself now shows.
inline constexpr uint32_t MenuCursor = 0x060768DA;
inline constexpr uint16_t StatusEntry = 0, SpellEntry = 1, ItemEntry = 2, SystemEntry = 3;
struct FieldMenu {
    uint16_t cursor = 0;
    uint64_t epoch = 0;                     // counts passes through the menu, so a host can see one
};
inline FieldMenu field_menu;
inline void field_menu_at(uint16_t cursor) { ++field_menu.epoch; field_menu.cursor = cursor; }
inline uint16_t menu_intent = 0;   // host to guest: put this entry (1-based) in the menu's own cursor

inline void clear() { ++boundary; close_battle_commands(); menu_intent = 0; }
inline void field() { if (battle_commands) close_battle_commands(); context = {Confirm, Menu, Items, Strongest}; }
inline void ui(bool start = false) { if (battle_commands) close_battle_commands(); context = {start ? Start : Confirm, Cancel, 0, 0}; }
inline void boot() { clear(); context = {Start, Cancel, 0, 0}; }

// One walk at a time, pure so it is testable without SDL, the guest or a window.
// The wanted entry is never chased with fake arrow presses: the injected hook writes it
// straight into the menu's own cursor word, and the walk only paces what a player would
// have pressed anyway - close, open, then confirm once the guest reports it is in the menu.
struct WalkStep { uint16_t bits = 0; bool ask = false; };
struct MenuWalk {
    static constexpr uint16_t Idle = 0xFFFF;
    static constexpr uint8_t Closing = 0, Opening = 1, Confirming = 2;
    uint16_t target = Idle, bit = 0;
    uint8_t hold = 0, gap = 0, phase = Closing;
    uint64_t seen = 0;                      // the guest's menu epoch when this walk started
    uint16_t waits = 0;
    uint64_t started = 0, last_vblank = 0;
    bool clocked = false;
    WalkStep cached{};

    void ask(uint16_t entry) {
        target = entry; phase = Closing; bit = 0; hold = gap = waits = 0; menu_intent = 0; clocked = false; cached = {};
    }
    void stop() {
        target = Idle; phase = Closing; bit = 0; hold = gap = waits = 0; menu_intent = 0; clocked = false; cached = {};
    }

    // epoch is the guest's own menu counter, so the confirm waits for a menu that really opened.
    // Every pulse covers the measured six-VBlank INTBACK cadence. Extra reads
    // within one VBlank cannot shorten it or consume the timeout budget.
    WalkStep tick(uint64_t epoch, uint64_t vblank) {
        if (clocked && vblank < last_vblank) { stop(); return {}; }
        if (clocked && vblank == last_vblank) return {cached.bits, false};
        if (target == Idle && !hold) return {0, false};
        if (!clocked) { started = vblank; clocked = true; }
        last_vblank = vblank;
        if (vblank - started >= 240) { stop(); return {}; }
        ++waits;
        cached = advance(epoch);
        return cached;
    }
    WalkStep advance(uint64_t epoch) {
        if (hold) { --hold; return {bit, false}; }
        if (gap) { --gap; return {0, false}; }
        if (target == Idle) return {0, false};
        if (phase == Closing) {
            phase = Opening; bit = Cancel; hold = 6; gap = 7; return {bit, true};
        }
        if (phase == Opening) {
            // Only a pass after this press proves the menu we are about to confirm is our own.
            seen = epoch; phase = Confirming; bit = Menu; hold = 6; gap = 7; return {bit, true};
        }
        if (epoch == seen) return {0, true};                // the guest has not entered the menu yet
        bit = Confirm; hold = 6; target = Idle; phase = Closing;
        return {bit, false};
    }
};

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
