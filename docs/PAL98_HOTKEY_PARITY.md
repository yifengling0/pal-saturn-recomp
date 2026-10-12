# PAL98 hotkey parity on the Saturn build

2026-10-11. The PC keyboard profile aims at the 1998 PC game's shortcut letters.
The Saturn release is pad-only, so a letter can only be honoured where the Saturn
game has a button that does the same thing, or by driving its menu for the player.
This page records which is which, and what was measured rather than assumed.

## The 1998 shortcut set

Non-battle (98柔情版; the DOS release only had S and E):

| Key | Screen |
|---|---|
| `S` | 狀態 |
| `E` | 物品 / 包袱 |
| `W` | 装备 |
| `F` | 仙術 |
| `Q` | 系統 / 退出 |

Battle:

| Key | Command |
|---|---|
| `A` | 圍攻 (the whole party attacks) |
| `D` | 防御 |
| `S` | 狀態 |
| `E` | 物品 |
| `W` | 投擲 |
| `F` | 自動法術 |
| `Q` | 逃跑 |
| `R` | 重複上一次動作 |

Arrows move, Enter confirms, Esc interrupts (in battle it stops an 圍攻 that is
still running).

## What the Saturn release actually offers

Measured on the accelerated Windows build with deterministic `--input` replays
from the village checkpoint (`build/run/field-menu-1`, `build/run/fm2`,
`build/run/fm3`; the village frame is static, control run `build/run/menu-ctl`
reproduced `7f410a40b8…` at every sample, so a changed picture is a changed
input).

| Saturn button | Field effect |
|---|---|
| `A` | interact / confirm |
| `B` | cancel - closes the command menu, the 系統 page and the quick pages |
| `X` | opens the command menu: 狀態 / 仙術 / 物品 / 系統 |
| `L` | quick spell page - party list, then that character's spell list |
| `R` | quick item page - the 包袱 itself, with the item description pane |
| `Y`, `Z`, `START` | nothing on the field map |

In the battle main command menu (four icons) the original game already answers
`L` with "strongest" and `Z` with "repeat the previous commands"; that was
verified earlier with real SDL keys against a native pad replay
(`docs/HARMONY_AUDIO_GAMEPAD_SHORTCUTS.md`).

The command menu is a four-entry ring, not a two-column grid. `UP` from 狀態
lands on 系統 and `DOWN` from 系統 lands back on 狀態. **The cursor survives
closing and reopening the menu**: open, step down once, cancel, open again and
the highlight is still on 仙術. The index is a 16-bit word at `0x060768DA`, and
stepping down four times walks it `1, 2, 3, 0`. Three properties of it were
measured before the shortcut was written, because each one kills a design that
looks reasonable on paper:

| Measurement | Where | What it rules out |
|---|---|---|
| Writing `0x060768DA` while the menu is **open** leaves the picture alone (`3810`/`4260`/`4410` in `build/run/fm5` are the cursor-0 picture even though the word said `1`/`2`/`3`) | `build/run/fm2` vs `build/run/fm5` | "just poke the cursor whenever the key is pressed" |
| Writing it **before** the menu opens moves both the highlight and the confirmation: `4110` in the two runs is the same picture, and `A` then opened 系統 (`4560`) | `build/run/fm5`, `build/run/fm6` | - |
| The field loop's call at `0604A8C0` is reached **once per menu event**, not once per frame: instrumenting the generated build printed the hook at the open and at each step, while the field task's own per-frame marker went silent for the whole time the menu was up | `build/run/fm8` | a per-frame "keep nudging until the cursor matches" loop |

The same instrumented run shows the field task ends every frame with
`pal_keyboard::field()` and stops running while a menu owns the screen, so
"context is field" is a reliable gate for a shortcut that ends in an `A` press.

## Historical mapping (2026-10-11; superseded below)

| PC key | what it does | Verified |
|---|---|---|
| `E` 包袱 | Saturn `R`, the field item page | yes, the field item page |
| `F` 仙術 | Saturn `L`, the field spell page | yes, the field spell page |
| `F` 最強 | Saturn `L` in the battle command menu | yes, battle command menu (earlier SDL run) |
| `A` 圍攻 | Saturn `L` in the battle command menu | same button as 最強, battle-gated |
| `R` 重複 | Saturn `Z` in the battle command menu | yes, battle command menu (earlier SDL run) |
| `S` 狀態 | menu entry `0` | yes, `build/run/fm13` |
| `W` 装备 | menu entry `2` 物品 (Saturn equips from the item page) | entry reached the same way as `S` |
| `Q` 系統 | menu entry `3`, which is 儲存進度 / 讀取進度 | yes, `build/run/fm5` |

`F` and `A` are only live inside the battle main command menu, and `E`/`F`'s
field meaning only lives in the field loop, so a press cannot leak from one
screen into the other.

The three letters with no Saturn button behind them are not arrow scripts. The
host sets an intent word; one injected line at `0604A8C0` writes it into
`0x060768DA` on the menu's next event and publishes the counter; and
`MenuWalk` presses `B`, then `X`, then waits for that counter to move before it
presses `A`. Arrows the player presses in between cannot change the outcome,
because the entry is forced rather than chased, and a menu that never reports
itself gets abandoned after four seconds instead of being fought. The pacing was
replayed against the real guest with `--write` standing in for the hook
(`build/run/fm13`): a player who opened the menu and stepped to 仙術 first still
lands on 狀態, and the whole macro takes about 55 frames.

## Historical open items (2026-10-11)

1. The battle command menu was **not** reproduced in this build: replaying
   `tools/acceptance_inputs/first-battle.txt` from the same checkpoint never
   entered the command-menu state (`0x060768EC` never became `0xFFFF`), and the
   pictures show the party still on the map at the end of the script. Battle
   `D` 防御 / `E` 物品 / `W` 投擲 / `Q` 逃跑 therefore need a route to a battle
   first - a save that opens one, or the route worker's live session - before
   their cursor variable and command order can be measured the same way. The
   snapshot route (`--state-at` / `--state-in`) is the candidate.
2. `A` 圍攻 is currently the Saturn 最強 fill, which is the closest thing the
   pad offers but is not the PC behaviour (PC `A` makes the whole party attack).
   Whether it can be a real 圍攻 depends on the same missing battle.
3. 系統 on Saturn is only 儲存進度 / 讀取進度 - it is the save menu, not the PC
   退出 screen. `Q` opens save/load, and `B` closes it.
4. The Windows keyboard path still needs the user's own playtest: the headless
   harness can only inject a virtual gamepad, so the letters above are verified
   as *mechanism* (unit tests plus `--write` replays), not as SDL key events.
   Faking the key from outside is not available here either - `SendInput` from
   an agent shell returns `ERROR_ACCESS_DENIED` for every key, including
   harmless ones, so `build/run/kbtest/drive.py` only works from an interactive
   console.


## Current release mapping (2026-10-12)

The historical A/D/W and missing-battle limitations above no longer describe
the current release. In the battle command menu, W opens the original throw
list, D selects defend, and A navigates Other → surround. A selects ordinary
attacks for the remaining actors while preserving earlier actors' commands,
and starts the game's continuous surround mode; Esc/B cancels it. F keeps the
separate strongest-magic selection and R repeats the previous commands. Battle
E (items) and Q (flee) remain unbound.

On the field S/W/Q open status, equipment/items and save/load respectively.
The repaired VBlank-paced menu navigation has actual Linux SDL key-event
coverage. Current battle acceptance, the matching executable identity, and the
separate Windows/OHOS verification boundaries are in `PC_KEYBOARD.md`, section
“W/D/A battle acceptance (2026-10-12)”. Do not use the earlier headless-only
limitations as the current Linux test result.
