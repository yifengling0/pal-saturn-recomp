// Pure, invented host-key tests. No SDL, game source, ROM, or guest execution.
#include "pal_keyboard_profile.h"
#include <cstdlib>
#include <iostream>
#include <vector>

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
    // A PAL98 letter with no Saturn button behind it. Pacing is measured in
    // emulated VBlanks, not the number of host reads in one VBlank.
    {
        MenuWalk walk;
        auto poll = [&](uint64_t epoch, uint64_t vb) {
            const auto first = walk.tick(epoch, vb);
            for (int extra = 0; extra < 17; ++extra) {
                const auto again = walk.tick(epoch, vb);
                check(again.bits == first.bits, "extra same-VBlank polls retain the published pulse");
                check(!again.ask, "extra same-VBlank polls do not re-arm a consumed menu intent");
            }
            return first;
        };
        check(poll(field_menu.epoch, 0).bits == 0, "an idle walk presses nothing");
        walk.ask(SystemEntry);
        const auto epoch = field_menu.epoch;
        for (uint64_t vb = 100; vb < 114; ++vb)
            check(poll(epoch, vb).bits == (vb < 107 ? Cancel : 0),
                  "cancel is held seven VBlanks followed by seven released VBlanks");
        for (uint64_t vb = 114; vb < 128; ++vb)
            check(poll(epoch, vb).bits == (vb < 121 ? Menu : 0),
                  "menu is held seven VBlanks followed by seven released VBlanks");
        const auto waiting = poll(epoch, 128);
        check(waiting.ask && waiting.bits == 0, "no confirm before the guest reports the menu");
        for (uint64_t vb = 129; vb < 136; ++vb)
            check(poll(epoch + 1, vb).bits == Confirm, "confirm stays high through every poll of seven VBlanks");
        check(poll(epoch + 1, 136).bits == 0, "confirm releases after seven VBlanks");
        check(!poll(epoch + 1, 137).ask, "the completed walk leaves no request behind");

        walk.ask(SystemEntry);
        for (uint64_t vb = 200; vb < 214; ++vb) poll(epoch, vb);
        // A menu the player entered before our X press is not our acknowledgement.
        for (uint64_t vb = 214; vb < 228; ++vb) poll(epoch + 1, vb);
        check(poll(epoch + 1, 228).bits == 0, "a menu epoch predating our open press cannot trigger confirm");
        check(poll(epoch + 2, 229).bits == Confirm, "a newer menu epoch can trigger one confirm");
        walk.stop();

        walk.ask(StatusEntry);
        for (uint64_t vb = 300; vb < 335; ++vb) {
            const auto step = poll(epoch, vb);
            if (step.ask) menu_intent = uint16_t(walk.target + 1);
        }
        check(menu_intent == StatusEntry + 1, "the intended entry remains armed while waiting for the guest");
        walk.stop();
        check(menu_intent == 0 && poll(epoch + 1, 334).bits == 0,
              "stop clears intent and invalidates even the current-VBlank cache");

        walk.ask(ItemEntry);
        const auto first = walk.tick(epoch, 1000);
        for (int i = 0; i < 400; ++i)
            check(walk.tick(epoch, 1000).bits == first.bits,
                  "hundreds of same-VBlank reads cannot consume the walk or its timeout");
        check(walk.target == ItemEntry, "same-VBlank polling does not time out");
        check(walk.tick(epoch, 1239).bits != Confirm && walk.target != MenuWalk::Idle,
              "request remains live before the actual 240-VBlank deadline");
        check(walk.tick(epoch, 1240).bits == 0 && walk.target == MenuWalk::Idle,
              "timeout expires at 240 elapsed VBlanks even when intervening reads were skipped");
        check(menu_intent == 0, "timeout disarms the guest intent");
        for (uint64_t vb = 1240; vb < 1270; ++vb) {
            const auto step = poll(epoch + 1, vb);
            check(!step.bits && !step.ask, "no late menu acknowledgement revives a timed-out walk");
        }

        // A host menu, focus loss or scene clear calls stop(). Exercise every
        // pulse and neutral phase, including the final held-confirm VBlank.
        for (const uint64_t interrupted : {0, 7, 14, 21, 28, 34}) {
            walk.ask(StatusEntry);
            for (uint64_t vb = 0; vb <= interrupted; ++vb) {
                const auto step = poll(vb >= 28 ? epoch + 1 : epoch, 2000 + vb);
                if (step.ask) menu_intent = StatusEntry + 1;
            }
            walk.stop();
            check(menu_intent == 0 && poll(epoch + 2, 2000 + interrupted).bits == 0,
                  "lifecycle stop is immediate in every walk phase");
            check(poll(epoch + 3, 2100).bits == 0, "lifecycle stop never resumes on a newer menu epoch");
        }
        walk.ask(StatusEntry);
        poll(epoch, 3000);
        walk.ask(SystemEntry);
        check(poll(epoch, 3000).bits == Cancel && walk.target == SystemEntry,
              "replacement starts a new request even within the same VBlank");
        walk.stop();
    }
    std::cout << "PASS: " << checks << " context/latch checks; no game or SDL execution\n";
}
