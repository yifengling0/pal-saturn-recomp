#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

// Semantic PC keys choose exactly one Saturn button per physical press. Native
// Saturn bindings and physical gamepads never pass through this translator.
namespace pal_keyboard {
inline constexpr uint16_t Start = 0x0800, Confirm = 0x0400, Cancel = 0x0100, Menu = 0x0040;
inline constexpr uint16_t Strongest = 0x0008, Repeat = 0x0010; // native Saturn L / Z
inline constexpr uint16_t Defend = 0x0040, Throw = 0x0020; // native Saturn X / Y, battle only
inline constexpr uint16_t Items = 0x0080;                      // native Saturn R
// The PAL98 shortcut letters pick the Saturn button that does the same thing in the
// context the guest is really in: the field's R/L quick pages, and nothing at all
// while a menu, dialogue or battle phase owns the screen.
struct Context { uint16_t confirm = Start, cancel = Cancel, item = 0, spell = 0; };
inline Context context;
inline uint64_t boundary = 0;
inline bool battle_commands = false;
inline uint64_t battle_boundary = 0;
// Advances only after the original command reader returns a real event.
inline uint64_t battle_consumed = 0;
inline void battle_event_consumed() { ++battle_consumed; }

// A PC surround request navigates the original menus. It never writes action,
// damage, RNG, inventory or target data. Real guest input always wins.
struct AllAttackIntent {
    enum Stage { Idle, SelectOther, WaitCursor, ConfirmMain, AwaitMainReturn, AwaitOther, ConfirmOther };
    Stage stage = Idle;
    uint16_t actor = 0, member = 0;
    uint64_t epoch = 0, started = 0, released = 0, last_vblank = 0;
    uint32_t cursor_address = 0;
    bool other_ready = false;
    void stop() { stage = Idle; cursor_address = 0; other_ready=false; }
    bool live(uint64_t vb) {
        if (stage != Idle && (vb < started || vb < last_vblank || vb - started >= 240)) stop();
        if (stage != Idle) last_vblank=vb;
        return stage != Idle;
    }
    bool same(uint16_t a, uint16_t m) const { return actor == a && member == m; }
    void request(bool main, uint16_t a, uint16_t m, uint64_t e, uint64_t vb) {
        if (live(vb) || !main || a > 2 || m > 5) return;
        actor=a; member=m; epoch=e; started=vb; released=vb; last_vblank=vb; stage=SelectOther;
    }
    // Native pad levels wake the guest's blocking reader. Only a matching
    // actual guest event acknowledges a pulse; no synthetic return or jump.
    uint16_t pad(uint64_t vb) {
        if (!live(vb)) return 0;
        if (stage==SelectOther) return 0x2000; // Saturn Down
        if (vb-released<7) return 0;
        return stage==ConfirmMain || (stage==ConfirmOther && other_ready) ? Confirm : uint16_t(0);
    }
    void main_ready(uint16_t cursor,uint16_t a,uint16_t m,uint64_t e,uint64_t vb) {
        if (!live(vb)) return;
        if (!same(a,m) || epoch!=e) {stop();return;}
        if (stage==WaitCursor) {if(cursor==3) stage=ConfirmMain; else stop();}
    }
    void main_event(uint16_t event,uint16_t a,uint16_t m,uint64_t e,uint64_t vb) {
        if (!live(vb)) return;
        if (!same(a,m) || epoch!=e) {stop();return;}
        if(stage==SelectOther && event==4) {stage=WaitCursor;released=vb;}
        else if(stage==ConfirmMain && event==1) {stage=AwaitMainReturn;released=vb;}
        else stop();
    }
    void main_return(int result,uint16_t a,uint16_t m,uint64_t e,uint64_t vb) {
        if (!live(vb)) return;
        if(stage==AwaitMainReturn && result==3 && same(a,m) && epoch==e) stage=AwaitOther;
        else stop();
    }
    bool other_enter(bool exact_call,uint32_t ptr,uint16_t a,uint16_t m,uint64_t vb) {
        if (!live(vb)) return false;
        if(stage!=AwaitOther || !exact_call || !same(a,m) || (ptr&1)) {stop();return false;}
        cursor_address=ptr;stage=ConfirmOther;other_ready=false;return true;
    }
    void other_wait(uint32_t ptr,uint16_t cursor,uint16_t a,uint16_t m,uint64_t vb) {
        if (!live(vb)) return;
        if(stage==ConfirmOther && ptr==cursor_address && cursor==0 && same(a,m)) other_ready=true;
        else stop();
    }
    void other_event(uint16_t /*original*/,uint32_t ptr,uint64_t vb) {
        if(live(vb) && stage==ConfirmOther && ptr==cursor_address) stop();
    }
};
inline AllAttackIntent all_attack;
inline uint16_t battle_actor=0xFFFF, battle_member=0xFFFF;

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

inline void clear() { all_attack.stop(); ++boundary; close_battle_commands(); menu_intent = 0; }
inline void field() { all_attack.stop(); if (battle_commands) close_battle_commands(); context = {Confirm, Menu, Items, Strongest}; }
inline void ui(bool start = false) { if (all_attack.stage != AllAttackIntent::ConfirmOther) all_attack.stop(); if (battle_commands) close_battle_commands(); context = {start ? Start : Confirm, Cancel, 0, 0}; }
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
    explicit BattleCommandsScope(bool in_battle, uint16_t actor=0xFFFF, uint16_t member=0xFFFF) {
        all_attack.stop(); battle_actor=actor; battle_member=member;
        close_battle_commands();
        battle_commands = in_battle;
    }
    ~BattleCommandsScope() { if (all_attack.stage != AllAttackIntent::AwaitOther) all_attack.stop(); close_battle_commands(); }
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

// Battle commands retain a fresh tap until the original blocking menu reader
// consumes an event. This queue never applies to field input or other menus.
// Acknowledgement retires all competing shortcuts; held keys require UP first.
struct BattlePressLatch {
    PressLatch presses;
    uint16_t pending = 0;
    int pending_key = -1;
    uint64_t seen_boundary = battle_boundary, seen_consumed = battle_consumed;
    void block() { presses.block(); pending=0; pending_key=-1; }
    void sync() {
        if (seen_boundary != battle_boundary || seen_consumed != battle_consumed) {
            seen_boundary = battle_boundary;
            seen_consumed = battle_consumed;
            block();
        }
    }
    void down(int key, uint16_t bit, bool repeat, bool focused, bool blocked) {
        sync();
        if (key < 0 || static_cast<size_t>(key) >= presses.keys.size()) return;
        const bool fresh = !repeat && !presses.keys[key].down;
        presses.down(key, battle_commands ? bit : uint16_t(0), repeat, focused, blocked);
        // First eligible edge wins: the ROM rejects simultaneous command bits.
        // Losing edges remain physically latched but are never queued behind it.
        if (fresh && !pending && presses.read(key)) {
            pending=presses.read(key); pending_key=key;
        }
    }
    void up(int key) { presses.up(key); } // pending survives a same-pump UP
    uint16_t read(int key) {
        sync();
        return battle_commands && key == pending_key ? pending : uint16_t(0);
    }
};
}

// A single ROM-proven mode-10 message wait owns these edges. This is not a
// global input queue: old presses, repeated DOWN, focus loss and the next box
// cannot reuse an edge. Host callbacks are absent in headless/scripted builds.
#include <set>
#include <map>
#include <tuple>
namespace pal_prompt {
using Source = std::tuple<uint64_t, uint64_t, uint64_t>;
struct Ledger {
    std::map<Source,uint16_t> down;
    std::set<Source> pending;
    uint64_t generation = 0;
    bool active = false, spent = false;
    uint64_t begin() { pending.clear(); active=true; spent=false; return ++generation; }
    void end(uint64_t token) { if(token==generation) {active=false; pending.clear();} }
    // Interrupt the input opportunity, not the still-running ROM wait. Keep
    // physical holds retired until UP; resume may accept only a new DOWN.
    void cancel() { pending.clear(); }
    void press(Source source, bool eligible, uint16_t bits=0x0400) {
        auto entry=down.emplace(source,uint16_t(bits & 0x0600));
        if (!entry.second) { entry.first->second |= uint16_t(bits & 0x0600); return; }
        if (active && !spent && eligible) pending.insert(source);
    }
    void release(Source source, bool canceled=false) {
        down.erase(source);
        if(canceled) pending.erase(source);
    }
    uint16_t held() const { uint16_t bits=0; for(const auto& entry:down) bits|=entry.second; return bits; }
    bool consume(uint64_t token) {
        if(token!=generation || !active || spent || pending.empty()) return false;
        pending.clear(); spent=true; return true;
    }
};
inline Ledger ledger;
inline bool (*host_begin)() = nullptr;
inline bool (*host_valid)() = nullptr;
inline void (*host_consume)() = nullptr;
struct Scope {
    uint64_t token=0;
    bool enabled=false, retired=false;
    explicit Scope(bool exact) {
        // Nested or unknown calls must not claim the outer wait's edges.
        if(exact && !ledger.active && host_begin && host_valid && host_consume && host_begin()) {
            token=ledger.begin(); enabled=true;
        }
    }
    ~Scope() { if(enabled) { if(!retired) host_consume(); ledger.end(token); } }
    bool accept() {
        if(!enabled) return false;
        if(!host_valid()) {ledger.cancel();return false;}
        if(!ledger.consume(token)) return false;
        host_consume(); retired=true; return true;
    }
    Scope(const Scope&)=delete;
};
}
