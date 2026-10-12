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
  - `E` 物品/包袱 - the field's item page (the Saturn pad's R quick page)
  - `F` 仙術 - the field's spell page (the Saturn pad's L quick page); in the
    battle main command menu the same key is the original strongest fill
  - `A` 圍攻 - the battle main command menu's strongest fill for the remaining
    party; a no-op on the field map, as it is on PC
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
  `D` 防御 and the battle-only `E` 物品 / `W` 投擲 / `Q` 逃跑 stay unbound: the
  battle command menu has not been reproduced in this build, so its cursor
  variable has not been measured. Guessing a button script there would be worse
  than no key at all.
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
