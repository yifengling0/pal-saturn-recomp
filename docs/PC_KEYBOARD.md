# PC keyboard profile

This PAL-specific keyboard profile follows familiar PC confirmation/menu keys;
it does not claim a frame-by-frame reproduction of the 1998 PC game.

## Build and select

Rebuild with the current `tools/winbuild.py`. Both its ordinary build and
`--pal-options` build inject the keyboard context hooks into PROG and TRUE and
use an owned runtime copy. Other experience options retain their existing
separate switches and defaults. The legacy `tools/linuxbuild.py` diagnostic
route is not the PC-profile build entry; on Linux the same portable
`winbuild.py` entry supports `--headless` or an explicit `--sdl-dir`.

A new settings file, or `--settings -`, defaults to `pc98`. An existing settings
file without the new key retains its original Saturn keyboard bindings. To
upgrade an existing configuration, either use the executable's `--launcher`
Controls page and choose **PC98 keyboard**, or add this section to its settings:

```ini
[controls]
keyboard_profile = pc98
```

Use `saturn` to return to the old `[keyboard]` map. PC98 bindings live in a
separate `[keyboard pc98]` section; old custom keys and physical gamepad mappings
are not overwritten. F10 in a running game opens the host pause menu, not the
launcher's Controls page. No new keyboard-profile command-line/environment
switch is implied by this document.

For testing without touching existing settings, pass a new private path such
as `--settings build/run/pc98-test/settings.ini` after creating its parent
folder. Do not overwrite a personal settings file or save file for a test.

## Keys

- Arrow keys: movement/menu navigation
- Enter, keypad Enter, Space: confirm/interact; title/load contexts use START
  only when the game's active wait actually requires it
- Esc: game menu in the field, cancel/back where the game supports it.
  Plain non-cancellable dialogue still uses Enter to continue/close; Esc does
  not force a story skip or accidentally open the field menu.
- Tab: direct Saturn START
- Z/X/C: Saturn A/B/C. V: Saturn X, for the rare screen that needs it directly.
- PAL98 shortcut letters, each one taking the Saturn button that does the same
  thing in the screen the game is actually on:
  - `E` 物品/包袱 - native Saturn R: field item page, or the battle main
    command menu's original usable-item list, followed by target selection
  - `F` 仙術 - the field's spell page (the Saturn pad's L quick page); in the
    battle main command menu the same key is the original strongest fill
  - `A` 圍攻 - navigate the original battle Other → first entry, which selects
    ordinary physical attacks for the remaining party and enables the Saturn
    continuous surround mode. Esc/B cancels that native mode. It does not select
    strongest magic; F retains that separate action. A is inert on the field map.
  - `D` 防御 - native Saturn X in the battle main command menu
  - `W` 投擲 - native Saturn Y in the battle main command menu, then the original
    throwable-item list and target selection. Outside battle W still opens the
    equipment/item page. These two meanings latch only in their own contexts.
  - `R` 重複 - repeat the previous commands (the Saturn pad's Z)
  A letter listed for both a field page and the battle menu is resolved by the
  context: each latch zeroes the press outside its own screen, so a held key
  cannot carry a field spell page into a battle turn or the other way round.
- `S` 狀態, `W` 装备 and `Q` 系統/退出 have no Saturn button to borrow, so the
  host drives the game's own command menu instead of replaying arrow presses:
  it cancels whatever is on screen, writes the wanted entry into the menu's own
  cursor word (`0x060768DA`) through a hook in the field loop, and presses X then
  A once the guest reports it actually entered the menu. Arrows the player presses
  in between cannot change where the letter lands, and a menu that never opens is
  given up on after four seconds rather than fought.
  - `S` 狀態 -> 狀態, which is also the Saturn equipment page (stats, portrait
    and the seven equipment slots in one screen; measured, `build/run/fm7`)
  - `W` 装备 -> 物品, because the Saturn release equips from the item page and
    has no separate equip screen
  - `Q` 系統 -> 系統, which is 儲存進度 / 讀取進度 on Saturn, not the PC 退出 screen
  Battle-only `Q` 逃跑 remains unbound; use the original Other → flee menu.
  E/W/D/F/R operate only at the
  original four-icon battle command menu; they do not interrupt an animation or
  replace a target choice. A has a 240-VBlank timeout and waits for guest menu
  acknowledgements. Any real competing input, focus loss or background entry
  cancels its pending navigation.
  The exact previously shipped `strongest = F, A` plus default `all_attack = A`
  preset is interpreted as F strongest / A surround in memory. Existing files
  are not rewritten on read. Other custom bindings and explicit empty bindings
  retain precedence; disable `all_attack` to retain a custom F,A strongest pair.
- F10: host pause menu in PC98. Saturn profile keeps a custom F10 game binding;
  otherwise F10 is an additional host-menu key.

Each semantic key locks to one Saturn button on key-down until release. Holding
Esc cannot change its X/menu press into B/cancel merely because a menu opened.
Focus loss, scene/program boundaries and host/profile changes clear or block
old semantic presses. The current mapping does not add a pending-input queue.

## Verification status

Native Linux SDL events have exercised title/internal-save loading, field menu,
status, item-use navigation, layered cancel and host pause. Long Esc maps to a
single context-specific button, including OS key repeats. A separate full guest
replay of recorded native pad input reproduced five same-VB pictures and
confirmed ordinary Enter and Z are both accepted as action1.

Some 50 ms presses reach SDL but end before a host pad sample; this existing
sampling limitation is under separate investigation. A longer press is not a
substitute for fixing that red case, and this profile does not claim all short
presses are reliable. Early observations based on a screenshot returned during
a key action were invalidated; only separately settled screenshots and guest
traces are used.

### Integrated acceptance (2026-10-11)

The final integrated SDL executable SHA256 is
`c2d69106890756f2616ba18108aaf6308bc95a9ab9269f5b120183d86c73fddc`.
Native Enter title/load/status/NPC interaction and dialogue continuation passed;
Esc600ms opens only one menu, then a new press returns one menu level. F10 host
pause passed. A legacy custom map (F10=A, Esc=B, Return=C, F2=START) was exercised
with actual keys; its settings bytes and source BUP were unchanged. Both runs
exited0. A separate candidate native trace also verifies battle attack/target
confirmation and target cancellation. Physical gamepad hardware was not present.

The same final SDL executable, using headless deterministic scripts, matches
10 corrected cold-opening pictures,12 original first-battle pictures,94 precise
walking pictures and44 quick group-spell pictures; gameplay BUPs match their
stable references.148 tool tests and35 subtests pass, including synthetic
migration, checked-read errors, context boundaries, source identity, no-partial-
write validation, symlink/hardlink containment and strict manifest no-op tests.
Ordinary mapping-only and enhanced headless builds both compiled successfully.

The immutable previous SDL binary also loses some50ms direct-Z taps before
recording a pad state. This establishes that the sampling limitation predates
PC98; it does not establish equal loss rates or fix the issue. There is no
pending-edge change in this batch. Early screenshot-timing mistakes remain
excluded from the acceptance record.

Windows compilation/runtime acceptance of this new profile still requires a
local test; Linux validation and the user's confirmation of the previous
Windows build do not substitute for that test.

### W/D/A battle acceptance (2026-10-12)

This update completes PC98 battle W (throw), D (defend), and A (surround).
A now follows the game's Other → surround command instead of aliasing F. The
original game fills ordinary attacks for the remaining actors; commands already
chosen for earlier actors are preserved. The Saturn continuous-surround mode
can be stopped with Esc/B. F still uses the game's strongest-magic selection,
which is not a promise of maximum damage per MP. R repeats the previous party
commands. The physical Saturn gamepad map is unchanged.

If an existing PC98 configuration has exactly the former default strongest
binding `F,A`, with A otherwise at its default, it is migrated in memory to F
plus the separate A command. Explicit custom bindings keep priority. Existing
settings files are not rewritten by this migration.

Rebuild the generated game sources as well as the runtime; replacing only the
host executable's old runtime sources is insufficient. Use the normal current
`tools/winbuild.py --pal-options` generation/build workflow on PC, or the normal
`tools/ohosbuild.py` workflow on OHOS. Do not reuse an old generated tree with
`--skip-learn` for this first update. Existing legal disc and save paths remain
valid. In PC98, test W then Esc, D on one turn, and A then Esc on another; test F
and R separately. The old Saturn keyboard profile deliberately retains its own
bindings.

Actual Linux SDL keyboard events, on a private copy of legitimate saves:

- Single-actor battle: W opened the original throw list; Esc returned without
  changing inventory. D committed original action 5. A committed action 6 and
  enabled native continuous surround; Esc cleared that mode.
- Two-actor battle: W selected a bee hive (item 115) through the original list.
  A on the second actor preserved the first actor's throw and selected the
  second actor's ordinary attack. The throw executed, inventory changed 4 → 3,
  and the battle returned normally to the field after victory.
- Next battle: F selected original magic actions for both actors (IDs 346 and
  340). R on the following turn repeated both magic actions. Neither became A's
  ordinary-attack command.
- Field Q → normal save and a fresh load of the starting save were exercised;
  the load picture matched the previous stable executable byte for byte.

Final Linux executable SHA256:
`25aa20fa364f81896b1ee997055eb69223a060201af67d48036544a40199e325`.
Tests: 44 keyboard tests (including actual upstream Settings integration),
39 preparation tests, 20 field-input tests, one default-map regression, and
77 OHOS launcher tests pass. The C++ intent fixture includes 170 checks covering
context/actor changes, timeout and VB rollback, real-input preemption, release,
custom mappings and incomplete/cancelled navigation. Exact source guards were
independently replayed from the prepared runtime; observed hashes were not
blindly allowed.

The independent OHOS build compiled and linked both ARM64 and x86_64, with all
11 AllAttackIntent functions visible in ARM64 debug symbols. Its unsigned HAP
SHA256 is `cc3ac72b8ac69b272b730cf5964eda36210031c74be6618c6430d88bd6965b10`.
This verifies compilation and linkage, not physical OHOS keyboard/gamepad
behavior. Windows native and OHOS device acceptance remain local tests.

One single-actor test deliberately continued at low HP and lost before a queued
throw executed. That run only proves command selection; the two-actor run above
provides the actual inventory-consumption and victory evidence. No original save
was overwritten. Native semantic-key event logs are retained separately because
the old pad-only recording cannot reproduce every PC shortcut intent.


## 2026-10-13: battle items and command taps

E now shares the configured item key across two isolated contexts. In battle it
uses native R → event 11 → command -11 → the original use-item list (filter 1),
then the game's target selection. It does not choose an item, modify HP, deduct
inventory, or clear an earlier actor's command itself. W still uses Y → event 8
→ command -8, selecting the original throw list (filter 4).

A fresh E/W/D/F/R tap in the four-icon command menu survives a DOWN+UP pair in
one SDL event pump. It is retired when the original blocking command reader
returns any event, or the menu/actor scope ends. Holding a key cannot replay it
for the next actor. Multiple command edges before consumption use the first
eligible edge only, because the ROM rejects combined command button bits;
losing edges never queue a second action. Real keyboard, touch and gamepad input
wins over a pending shortcut. Projection happens after tap carry, so a retired
command cannot leak into the item/target menu via the touch-tap stretcher.

The acknowledgement hook is immediately after the original reader call at
0604A12E, not a replacement for that reader or its return value. Field walking,
item-acquired prompt confirmation and audio source code are unchanged.

Mapping boundaries: A surrounds from the current actor onward and retains
native continuous surround, F uses native strongest selection, R repeats each
remaining actor's previous command, D defends the current actor, W opens throw,
E opens use-item. Earlier actors' selected commands remain owned by the original
game. Q battle flee is intentionally not mapped by this update. The Saturn
keyboard profile and physical gamepad mappings remain independent.


Verified on 2026-10-13 with a private copy of an ordinary Toad Mountain BUP,
real SDL dummy video/audio and SDL keyboard events / virtual gamepad input:

- Before the tap repair, same-pump E DOWN+UP left the battle menu unchanged;
  a 14-VBlank press opened the original item list. The repaired same-pump tap
  opens that list. E+W in one pump follows E only, with native item mode 0.
- E list cancellation and target cancellation left 止血草 quantity at 7 and
  both actors' actions unset. Target cancel follows the original intermediate
  use/throw submenu; a second Esc returns to the command menu.
- A held E selected the first actor's item through normal Enter and target
  confirmation. Holding/repeating E across the second actor did not reopen the
  list. Releasing E and tapping again did open it. Cancelling that second list
  preserved the first actor's action 3 / item 99. D's same-pump tap selected
  action 5 for the second actor. Execution consumed exactly one herb, 7 → 6,
  and released the reservation. Later idle frames left the quantity at 6.
- A shortcut pressed during the enemy animation was discarded, not queued.
- W's same-pump tap opened throw mode 1. The original list selected bee hive
  item 115 for actor 0 (action 4); A's same-pump tap on actor 1 selected normal
  attack 6 while preserving the throw. Execution consumed one hive, 4 → 3,
  then returned to the field. Esc was used to stop native continuous surround.
- F's same-pump tap in the next battle selected native action 2, magic IDs
  346 and 340. R's same-pump tap on the following turn repeated those commands.

The diagnostic executable differed only by an input-only SDL event scheduler;
no guest memory writes, edited HP/inventory/party/story state, or live desktop
session were used. Its scheduler is absent from the separately generated formal
Linux executables and both HAP ABIs. The original source BUP hash was unchanged.

Final checks: 389 tools tests and 201 subtests passed, zero skips; ordinary and
accelerated Linux builds passed; the unsigned release HAP built ARM64 and x86_64.
Each HAP ABI embeds final host identity
`7c48c8ad21c9bedc51ac4390ebef9d66516966a9e574e924056bd23f8e1875a3`,
contains the battle acknowledgement and existing walking/audio implementation,
and uses release -O2 compilation. This is not Windows or physical Harmony device
acceptance; those hardware runs remain unperformed.
