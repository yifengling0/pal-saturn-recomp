# First natural battle acceptance — Linux, 2026-10-10

## Observed result

The unmodified-input, five-patch baseline completed its first natural encounter on Fairy Island: field contact, battle entry, three normal attacks, enemy turns, one healing spell, victory, results, return to the field and an actual game save. This establishes one early combat loop, not all battle mechanics or full-game completion.

The executable was `build/linux-game-sdl/recomp-build/saturn`, SHA256 `f5aa1c835d82700ab802ce589ac242534d589de679c8db9753a84ab1aedbf030`. The input responsiveness and countdown experiments were not active. The live controller supplied button states and observed bounded memory/frame data; it did not write game memory, teleport, modify enemy statistics or force a battle. These runs used accelerated headless execution; VBlank counts are guest time, not measured wall time.

## Reproduction identity

- Disc BIN SHA256: `4c76366e3178289c3e73264d8f3a0b9b8b3d78f7baa0862561ce48ce4199d4b5`.
- Thirteen-track CUE SHA256: `27b0f9fd3a6198a7c8369004188775a75b914a13d28ecf44e6494ffc1e8e7b7d`.
- RTC: `1998-11-01T12:00:00`.
- Starting **game backup**: village-before-buying-shrimp checkpoint, SHA256 `253eef1229bb62e148545d22c5ec6573ff2a1b76dc53eb79641f9caf5f848153`.
- Input-only replay: `tools/acceptance_inputs/first-battle.txt`, 452 pad-state events (recounted from the unchanged input file and replay log), SHA256 `9bd9976ba2d3b6e501f9de73d3ce4275e062df70470210f3728db781d861b597`.
- Stop after 25,761 VBlanks. Copy the source backup to a new test path; the replay deliberately saves at its end. Never test against a player's only save.

The source backup and commercial disc are private test data and are not distributed in this repository. The replay assumes that exact checkpoint; using another save is not an equivalent test. `--resume` would stop consuming the script and must not be used for the complete replay.

## Events and limits

| VBlank | Direct observation |
|---:|---|
| 23,343 | Battle scene and command menu; two green enemies; HP150/150, MP100/100 |
| 23,541 | Only available spell is 氣療術: costs6 MP, describes healing75 HP |
| 23,769 | Item list contains 破天鎚; no combat-item use claimed |
| 23,919 | First normal attack target confirmed |
| 23,961 | Sword action and damage74 visible |
| 24,021 | Target HP40→-34 and subsequent disappearance |
| 24,201 | Player menu returns after the surviving enemy's action |
| 24,267 | Healing spell confirmed |
| 24,459 | Golden healing effect visible |
| 24,639 | Player menu returns, HP150/150 and MP94/100 |
| 24,879 | Later attack shows damage74 and defeats the remaining enemy |
| 24,999 | Victory results: experience2, money0; subsequent result reports 吉運 +2 |
| 25,323 | Returned to scene16 field |
| 25,761 | Game-menu save complete at world(656,1544) |

Between the heal and final strike, a second normal attack reduced the remaining enemy's HP40→15; its damage number was not captured. An enemy turn reduced player HP150→149, establishing that enemy damage was applied. Healing was cast while full: MP expenditure and the effect were verified, but recovery of missing HP was not. No item reward was observed. Once one enemy remained, A directly executed an attack rather than requiring a second target confirmation.

The final backup SHA256 is `d5fb225425b5e33f165df7c0ff3b2915acfb504246d25f8c05602b866b99bcb6`; the log records `BUP: wrote SDW_JPNV_00 (25600 bytes)`. No FATAL appeared. The live process was paused afterward, so this is not an exit-code claim for that still-open controller.

## Timing interpretation

An observation-only probe reproduced the battle screenshot identically with the probe disabled and enabled. The first measured battle setup ran from VB23220 to23273, 887.3984ms guest time. Six requests total261 sectors, whose expected transfer time at the current runtime's300 data sectors/second is870ms. The measured resource-call total was876.2368ms. Sprite upload accounted for about8.09ms; no FIREN effect decoder was called during entry.

This supports simulated data-transfer waiting as the dominant cost **inside measured setup**, not a slow host disk. The black transition begins before the battle function, so887ms does not describe the whole visible transition. Action/animation intervals need their own measurements. Sparse manually requested screenshots are evidence of states, not exact animation start/end times. Repeated runs and per-spell segmentation remain in progress.

## Still unverified

- Damaged-target healing amount, attacking magic, combat item consumption, defense, escape, defeat/game-over, party combinations and later encounters.
- Native SDL presentation and sound for this exact complete battle replay; the separately verified native field window does not establish combat audio.
- Windows startup audio freeze reported by the user, and full-game completion.

## Cross-process post-battle load

A fresh baseline process subsequently loaded a copy of the final backup through the normal title/load input (`build/linux-boot-load-004/input.txt`). At VB3401 it restored scene16 and world(656,1544), with the island path and character visibly rendered. It quit with exit0; both source and copied BUP retained the final hash above. Evidence: `build/linux-postbattle-load-001/{commands.jsonl,result.json,frame-00003401-001.png}`. This verifies persistence of the saved location across processes, not every character-stat field.
