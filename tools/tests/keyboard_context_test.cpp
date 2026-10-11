// Pure, invented host-key tests. No SDL, game source, ROM, or guest execution.
#include "pal_keyboard_profile.h"
#include <cstdlib>
#include <iostream>

namespace {
int checks = 0;
void check(bool ok, const char* name) {
    ++checks;
    if (!ok) { std::cerr << "FAIL: " << name << '\n'; std::exit(1); }
}
}

int main() {
    using namespace pal_keyboard;
    // These are arbitrary key indices; no dependency on SDL numeric constants.
    constexpr int enter = 40, escape = 41, space = 44, keypad = 88;
    static_assert(Start == 0x0800 && Confirm == 0x0400 && Cancel == 0x0100 && Menu == 0x0040);
    static_assert(Items == 0x0080 && Strongest == 0x0008);
    const auto initial_boundary = boundary;
    boot();
    check(boundary == initial_boundary + 1, "boot increments boundary");
    check(context.confirm == Start && context.cancel == Cancel, "boot START/B context");
    check(context.item == 0 && context.spell == 0, "boot has no field quick pages");
    field();
    check(context.confirm == Confirm && context.cancel == Menu, "field A/X context");
    check(context.item == Items && context.spell == Strongest, "field offers native R then L");
    ui();
    check(context.confirm == Confirm && context.cancel == Cancel, "ordinary UI A/B context");
    check(context.item == 0 && context.spell == 0, "a menu hides the field quick pages");
    ui(true);
    check(context.confirm == Start && context.cancel == Cancel, "start UI START/B context");
    const auto before_clear = boundary;
    clear();
    check(boundary == before_clear + 1, "clear increments boundary");
    check(context.confirm == Start && context.cancel == Cancel, "clear leaves current context intact");

    PressLatch latch;
    for (int i = -1; i <= 512; ++i) check(latch.read(i) == 0, "fresh latch is empty");
    field();
    latch.down(escape, context.cancel, false, true, false);
    check(latch.read(escape) == Menu, "field Escape chooses X only");
    ui();
    latch.down(escape, context.cancel, true, true, false);
    check(latch.read(escape) == Menu, "OS repeat cannot reinterpret held Escape as B");
    latch.down(escape, context.cancel, false, true, false);
    check(latch.read(escape) == Menu, "duplicate nonrepeat keydown cannot remap");
    latch.up(escape);
    check(latch.read(escape) == 0, "keyup clears semantic button");
    latch.down(escape, context.cancel, false, true, false);
    check(latch.read(escape) == Cancel, "fresh Escape adopts UI B context");
    field();
    latch.down(escape, context.cancel, true, true, false);
    check(latch.read(escape) == Cancel, "held B survives returning to field without remap");

    latch.reset();
    boot();
    latch.down(enter, context.confirm, false, true, false);
    check(latch.read(enter) == Start, "boot Enter chooses START only");
    field();
    latch.down(enter, context.confirm, true, true, false);
    check(latch.read(enter) == Start, "held Enter cannot reinterpret START as A");
    latch.down(space, context.confirm, false, true, false);
    latch.down(keypad, context.confirm, false, true, false);
    check(latch.read(space) == Confirm && latch.read(keypad) == Confirm, "new confirm keys latch independent context");
    latch.up(space);
    check(latch.read(space) == 0 && latch.read(keypad) == Confirm, "releasing one semantic key retains another");
    latch.up(enter);
    latch.down(enter, context.confirm, false, true, false);
    check(latch.read(enter) == Confirm, "released Enter takes field A");

    latch.block();
    check(latch.read(enter) == 0 && latch.read(keypad) == 0, "menu/profile boundary blocks all held keys");
    latch.down(enter, Confirm, true, true, false);
    latch.down(keypad, Confirm, false, true, false);
    check(latch.read(enter) == 0 && latch.read(keypad) == 0, "blocked keys remain down until release");
    latch.up(enter);
    latch.down(enter, Confirm, false, true, false);
    check(latch.read(enter) == Confirm, "release permits key after blocking");

    latch.reset();
    latch.down(escape, Cancel, true, true, false);
    check(latch.read(escape) == 0, "repeat alone cannot resurrect reset press");
    latch.down(escape, Cancel, false, false, false);
    check(latch.read(escape) == 0, "unfocused keydown is blocked");
    latch.down(escape, Cancel, false, true, false);
    check(latch.read(escape) == 0, "focus regain cannot activate held key");
    latch.up(escape);
    latch.down(escape, Cancel, false, true, true);
    check(latch.read(escape) == 0, "host menu or Alt+Enter flag blocks new press");
    latch.up(escape);
    latch.down(escape, Cancel, false, true, false);
    check(latch.read(escape) == Cancel, "release restores input after focus/menu block");

    latch.reset();
    for (int i : {-999, -1, 512, 9999}) {
        latch.down(i, Confirm, false, true, false);
        latch.up(i);
        check(latch.read(i) == 0, "invalid key indices are ignored safely");
    }
    for (int i = 0; i < 512; ++i) {
        latch.down(i, (i % 2) ? Confirm : Cancel, false, true, false);
        check(latch.read(i) == ((i % 2) ? Confirm : Cancel), "all valid key slots are independent");
    }
    latch.reset();
    for (int i = 0; i < 512; ++i) check(latch.read(i) == 0, "reset clears all slots");

    // Deliberate mapping-only contract: a complete down/up between reads is lost.
    // This test documents that the helper provides no pending-edge queue/fix.
    latch.down(enter, Confirm, false, true, false);
    latch.up(enter);
    check(latch.read(enter) == 0, "mapping-only helper is not a short-tap queue");
    static_assert(Strongest == 0x0008 && Repeat == 0x0010);
    constexpr int f = 9, r = 21;
    BattlePressLatch battle;
    PressLatch existing;
    existing.down(enter, Confirm, false, true, false);
    field();
    battle.down(f, Strongest, false, true, false);
    check(battle.read(f) == 0, "field strongest is consumed as zero");
    const auto old_general_boundary = boundary;
    {
        BattleCommandsScope main(true);
        check(battle_commands, "main command scope enables shortcuts");
        check(boundary == old_general_boundary, "battle phase leaves Enter/Escape boundary alone");
        check(battle.read(f) == 0, "field hold cannot queue into battle main menu");
        battle.down(f, Strongest, true, true, false);
        battle.down(f, Strongest, false, true, false);
        check(battle.read(f) == 0, "field hold needs real release even with duplicate down");
        battle.up(f);
        battle.down(f, Strongest, false, true, false);
        check(battle.read(f) == Strongest, "fresh F maps only native L");
        battle.down(r, Repeat, false, true, false);
        check(battle.read(r) == Repeat, "fresh R maps only native Z");
    }
    check(!battle_commands && battle.read(f) == 0 && battle.read(r) == 0, "scope exit retires both shortcuts");
    check(existing.read(enter) == Confirm, "battle phase does not retire existing Enter latch");
    {
        BattleCommandsScope next(true);
        check(battle.read(f) == 0 && battle.read(r) == 0, "held F/R cannot repeat across actor/turn menus");
        battle.down(r, Repeat, true, true, false);
        check(battle.read(r) == 0, "OS repeat cannot reactivate retired R");
        battle.up(r);
        battle.down(r, Repeat, false, true, false);
        check(battle.read(r) == Repeat, "release then new R works in next menu");
        battle.block();
        check(battle.read(r) == 0, "host overlay/focus/profile boundary blocks battle shortcut");
        battle.down(r, Repeat, false, true, false);
        check(battle.read(r) == 0, "blocked hold cannot restart until release");
    }
    // Every non-command phase uses the same closed gate. Test each named case.
    for (const char* phase : {"spell list", "item list", "target selection", "enemy animation", "dialogue", "field"}) {
        (void)phase;
        battle.up(f);
        battle.down(f, Strongest, false, true, false);
        check(battle.read(f) == 0, "non-command phase cannot emit native L");
        BattleCommandsScope next(true);
        check(battle.read(f) == 0, "non-command phase cannot queue strongest into next menu");
    }
    battle.up(f);
    {
        BattleCommandsScope main(true);
        // Boundary is deliberately not observed before this fresh edge.
        battle.down(f, Strongest, false, true, false);
        check(battle.read(f) == Strongest, "first edge after boundary survives later pad read");
        clear();
        check(!battle_commands && battle.read(f) == 0, "scene clear closes active command gate");
    }
    check(!battle_commands, "scope unwinding after clear cannot reactivate gate");
    battle.up(f);
    {
        BattleCommandsScope invalid(false);
        battle.down(f, Strongest, false, true, false);
        check(!battle_commands && battle.read(f) == 0, "battle flag false fails closed");
    }
    battle.up(f);
    try {
        BattleCommandsScope main(true);
        battle.down(f, Strongest, false, true, false);
        throw 1;
    } catch (int) {}
    check(!battle_commands && battle.read(f) == 0, "exception unwinding closes gate");
    battle.up(f);
    {
        BattleCommandsScope main(true);
        battle.down(f, Strongest, false, false, false);
        check(battle.read(f) == 0, "unfocused strongest blocked");
        battle.up(f);
        battle.down(f, Strongest, false, true, true);
        check(battle.read(f) == 0, "Alt or host menu blocks strongest");
        battle.up(f);
        battle.down(f, Strongest, false, true, false);
        battle.up(f);
        check(battle.read(f) == 0, "battle helper is mapping only, no short-tap queue");
        ui();
        check(!battle_commands, "explicit UI boundary fails closed");
    }
    std::cout << "PASS: " << checks << " context/latch checks; no game or SDL execution\n";
}
