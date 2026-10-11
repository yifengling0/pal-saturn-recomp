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
the highlight is still on 仙術. The index lives at `0x060768DA` (16-bit, written
by `PROG:06044810` called from `0604A8C4` inside `f_0604A5B8`, the same call the
keyboard planner already wraps with `pal_keyboard::ui()`), and stepping down
four times walks it `1, 2, 3, 0`. While the menu is up the guest is *blocked*
inside that call - the watched range takes no stores at all between presses.

## Mapping shipped now

| PC key | Saturn button | Verified |
|---|---|---|
| `E` 包袱 | `R` | yes, the field item page |
| `F` 仙術 | `L` | yes, the field spell page |
| `F` 最強 | `L` | yes, battle command menu (earlier SDL run) |
| `A` 圍攻 | `L` | same button as 最強, battle-gated |
| `R` 重複 | `Z` | yes, battle command menu (earlier SDL run) |

`F` and `A` are only live inside the battle main command menu, and `E`/`F`'s
field meaning only lives in the field loop, so a press cannot leak from one
screen into the other.

## Still open, and what it needs

`S` 狀態, `W` 装备, `Q` 系統 and the battle `D`/`E`/`W`/`Q` have no Saturn button
to borrow, so they need the menu driven for the player. The pieces are now all
identified:

1. A host→guest intent word next to the existing context in
   `src/pal_game/pal_keyboard_profile.h`.
2. One injected line before the call at `0604A8C0` that writes the wanted index
   into `0x060768DA` and reports back that it applied.
3. A two-step host macro: press `X`, wait for the applied report, press `A`.
   Because the cursor persists, step 2 is mandatory - a fixed "open, down,
   down, confirm" script is wrong unless the player never touches the arrows.
   If the menu is already open the guest is blocked inside the call, so the
   intent must time out and clear rather than fire on the player's next arrow.
4. 系統 on Saturn is only 儲存進度 / 讀取進度 - it is the save menu, not the
   PC 退出 screen. Expect `Q` to open save/load, and keep closing it with `B`.
5. The battle command menu was **not** reproduced in this build: replaying
   `tools/acceptance_inputs/first-battle.txt` from the same checkpoint never
   entered the command-menu state (`0x060768EC` never became `0xFFFF`), and the
   pictures show the party still on the map at the end of the script. Battle
   `D`/`E`/`W`/`Q` therefore need a route to a battle first - a save that opens
   one, or the route worker's live session - before their cursor variable and
   command order can be measured the same way.
