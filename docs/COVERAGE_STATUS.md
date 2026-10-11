# Current verification scope

Updated 2026-10-11 00:37 UTC. This is a bounded acceptance record, not a claim
that the whole game has been completed or every mechanic has been tested.
The main route uses the original-timing executable with all experimental
input/spell/presentation switches off. Exact saves, inputs and hashes are in
AUTOPLAY_PROGRESS.md and the separate private checkpoint package.

## Confirmed in actual Taiwan-disc play

- Intro playback, field rendering, ordinary movement, dialogue, scene exits,
  story flags, quest-item acquisition and consumption.
- Inn errands, island statue puzzle, medicine/aunt recovery, sword training,
  multiple story battles, Suzhou rescue/banquet and the Lin-family tournament.
  Hidden Dragon Cave Snake Man defeated in15 rounds, Fox Woman in9; stone key used, rear door opened and captive-girl rescue dialogue completed.
- Bai He medicine quest: ginkgo collection, borrowing/using/returning a fishing
  rod, catching carp, placing a trap and capturing/releasing the deer for antler.
  Ingredient delivery and treatment are still in progress.
- Inventory, one-item shop purchase and pawn sale with exact money/quantity
  changes; equipment replacement and stat deltas; rejected equipment recipient.
- Party joining/leaving and story-driven leader changes. Manual party-order
  controls are not thereby verified.
- Normal attacks, defense, single-target and group magic, ally-target healing,
  self-target healing with an observed cap, HP/MP item restoration with caps,
  consumable throwing and item depletion.
- Successful escape in earlier road battles, experience/money rewards, level-up
  changes and item drops; stealing has both an observed failed attempt and a
  later successful item acquisition retained after victory.
- Single-party and two-party battles, three-enemy group damage, and victory
  return to the field. An enemy split-like HP redistribution was observed;
  its exact AI rule has not been independently identified.
- Multiple normal in-game saves and fresh-process loads, including after story,
  battle, purchase/equipment, party change and cave progress.

These are tested instances. They do not establish every item, spell, enemy,
status effect, quest branch, ending or save slot. Manual revival remains unverified. One naturally inflicted hypnosis was
cleared with Bing Xin Jue; poison and other status cures remain unverified.
A scripted story recovery is not counted as a manual revival.

## Fix and regression evidence

- SH-2 DMA burst completion bug fixed: the old loop copied only a quarter of
  the requested blocks while reporting completion. The actual inn scene and
  subsequent story recovered. This was not an RBG rendering fix.
- Post-fix regression evidence includes206 upstream Python tests,26 image
  validation tests,44 runtime tests,44 GPL renderer tests and9300 instruction
  vectors, plus core/hardware/DMA-specific tests. These are the recorded
  post-fix runs, not a claim that all were rerun after every documentation edit.
- The32 repository-tool tests were rerun on20:38 UTC and passed in0.94 seconds.
- Replayed whole input prefixes match original game frames in bounded audits;
  latest group-spell audit has706/706 replay frames and16/16 main-route frames
  identical, with actual MP charge and victory recovery observed.

## Input and spell options

| Mode | Actual acceptance | Remaining limit |
|---|---|---|
| Original timing | Main story route described above | Whole game and Windows startup still unverified |
| Precise input v4, no extra wake/alignment |51 isolated runs; bounded tap/hold/release and menu/scene/battle-return tests | Not a universal physical-keyboard latency proof |
| Experimental fast input | A tested visible response31→9VB | Adds NPC/script/RNG opportunities; remains opt-in |
| Quick spell v3 | Healing, Sword Technique and one Yue Ru group-spell animation/victory/save/load case | RNG/idle phases can differ; small early-menu RGB differences retained |
| Completed-frame preview | Rejected: visible backward frames | Not an available or accepted feature |

The original group spell has14 effect frames with4VB holds. Its first visible
energy occurs166VB after final party confirmation in the recorded encounter.
This is not labelled entirely as resource loading; exact phases and limitations
are in BATTLE_TIMING.md. No global clock slowdown or unsupported RNG compensation
has been applied.

## Platform and presentation limits

Real Linux SDL windows have shown startup, inn dialogue, movement and scene
changes. Later automated route evidence uses the real renderer's headless game
frames; it is not presented as new physical keyboard or audio-device testing.
Cloud real audio-device opening failed; dummy audio tests do not establish a
working physical sound-device path. The user's Windows startup/audio stall
has not been reproduced on Windows. SDL v4 headless equivalence is not a new
native keyboard acceptance run.

Verified source and Windows option integration were published on the feature
branch fix/linux-sdl-dma-20261010 in commits6de5e9d and eae3cda. The downloaded
remote tree matches the207 local tracked files at aa6d347 exactly; master was
not merged. No GitHub Actions workflows exist, so no remote CI pass is claimed.
Source recovery packages exclude ROM, BIOS, extracted modules, generated
commercial game source/executables and saves. Only this task's generated saves
and input records go into the separate private checkpoint package.
