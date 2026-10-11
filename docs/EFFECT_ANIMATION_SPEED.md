# Optional battle-effect animation cadence

## Current implementation and old-build safety

The guarded manual-pair implementation replaces the rejected shortened-wait
candidate. Default animation 1 remains unchanged. Rates 1.25/1.5/2 require a fresh
options executable advertising `effect_cadence_v4_manual_pair`; the launcher
rejects old `effect_cadence_v1` binaries, even if their old sidecar is intact.
Rebuild after updating. Do not run an old accelerated executable through a
hand-written environment-variable command.

This option is independent of quick preparation. It changes only the identified
battle-effect frame waits, not walking, CPU/VBlank clocks or sound sample rate.
Unknown effects, resource frame counts, caller paths and unsafe scheduler
conditions retain original timing. Requested acceleration is not a promise to
shorten every unsupported path.

## Why the previous candidate was rejected

The original game uses a two-field manual VDP1 erase/change/DMA sequence. The
old implementation returned from a sync before its change/submission phase,
leaving a later erase without the corresponding display swap. Real Thunder
recordings exposed disappearing party/enemy sprites. A trial one-cycle mode
also left a pending erase when switching back and was rejected.

Matching a replay against another run of the same buggy mode was insufficient.
The new acceptance compares complete images with the original picture states,
checks each effect index and each party/enemy separately, and includes the
post-effect cleanup. Frozen bad fixtures still reproduce 0/9/14 missing-entity
VBs for the old 1/1.5/2 modes; the checking threshold was not relaxed.

The replacement keeps the original interval 2. At an eligible short sync it
prepares the manual erase, then lets the original OUT interrupt perform its
change and DMA sequence. The original wait returns naturally. Both original
logical updates per effect frame remain; no forced early-return or fabricated
clock advance is used. The following OUT and composed picture are checked,
including the final shortened frame.

## Scope and cadence

Tested standard bank7 loops:

| Effect | Resource frames | Original frame waits | 1.25 | 1.5 | 2 |
|---|---:|---:|---:|---:|---:|
| Healing |20|80VB|64VB|54VB|40VB|
| Sword Technique |26|104VB|84VB|70VB|52VB|
| Yue Ru group spell |14|56VB|45VB|38VB|28VB|
| Ling Thunder |7|28VB|23VB|19VB|14VB|

Sword additionally retains its separate 2VB update; its measured full frame
window is 106/86/72/54VB. The cumulative rational schedule distributes
fractional waits with error below one VB for the listed effect-wait sum. Each
sync retains at least one real field when shortened. A refused guard uses the
ordinary path rather than catching up later or dropping an effect frame.

The guard checks CPU/module context, active cast/frame ownership, exact caller,
resource/index sequence, interval/countdown, palette bank, special VDP1 mode,
slave-list readiness, original DMA-ready state, active raster and manual FBCR.
Unsupported fiber and state-in execution is excluded. Default 1 returns before
new guest/MMIO reads.

Other Ling spells are not silently included. Wind, for example, uses two passes
of its 20-frame resource and is outside this bounded whitelist.

## Visual and gameplay evidence

- Healing, Sword and group spell at all four rates: every first-effect VB has a
  complete original-equivalent image at the same effect index, with all effect
  frames present and post-effect cleanup checked.
- Second Sword cast: each draw has exactly one remaining enemy and one hero.
  Both complete enemy idle textures match the original byte for byte; image
  differences are explained by original idle-pose selection and normal hit
  displacement, not absent/partial/duplicated sprites. This is not a claim of
  identical battle RNG/idle timing across rates.
- Twelve original legal victory routes complete, return to map, save normally
  and independently reload. Their same-rate final saves match the prior tested
  routes. Distinct rates need not produce identical outcomes or BUP bytes.
- Thunder: all four rates, quick preparation on/off and original confirm-skip
  paths have bounded first-round tests. The native three-rate SDL comparison
  retains all 7 visible lightning patterns and all three party members/tiger,
  returns to the command menu and matches 78/78 independent same-VB pictures.
  This short video is not a full 900HP tiger-victory claim at every rate.

For the filmed Thunder round, all modes charge 7MP and deal 59 damage; the
unshortened-preparation reference deals 60. The filmed visible effect lasts about
0.483/0.317/0.233 seconds at 1/1.5/2. The first value occupies 29 captured 60fps
frames versus 28 guest VBs because of capture/presentation boundary quantization.
The whole action, preparation, damage and enemy turn are not globally sped up.

## Sound and exception boundaries

Sound trigger count/order is retained in the tested cases, and sample rate/pitch
is unchanged. Sword's sound can continue beyond the accelerated visual effect.
Thunder at2x reuses a sound slot 0.7168ms after KEYOFF while its release would
last 3.584ms, ending about 2.8672ms of that tail early. The lower three rates do not
have this particular boundary. Do not claim audio equivalence or infer audible
quality from the silent cloud recording; a physical Windows sound device still
needs local verification.

Submitting a hardware erase cannot be rolled back by a C++ destructor. Tests
prove zero writes before a rejected/early-aborted submission and correct TLS
scope cleanup after an exception; they do not prove arbitrary mid-submission
`ProgramStart` recovery. Normal tested effect/battle exits contain no such
program-start exception. Fiber/state snapshots are excluded rather than
pretending to restore discarded stacks.

## Example (PowerShell)

```powershell
& $py tools\run_pal_profile.py original --quick-spell --effect-animation-speed 1.5 --exe $exe -- --cue $cue --save $copiedSave --settings - --out build\spell-15
& $py tools\run_pal_profile.py original --quick-spell --effect-animation-speed 2 --exe $exe -- --cue $cue --save $anotherCopiedSave --settings - --out build\spell-2
```

Use separate copied saves. The launcher checks executable identity and the new
manual-pair capability. Native Windows execution is not implied by Linux C++20
builds, replay tests or mock Windows argument tests.

## Combined-options smoke boundary

A separate legal replay tested precise input + paired walking presentation +
data CD4 + quick preparation + animation2, against the same combination with
animation1. It normally reached the900HP tiger, charged7MP, dealt60 damage and
returned to the menu. Both dense windows retain all7 lightning patterns, all
three party members and the tiger, with no missing/partial/extra sprites or
post-effect residue. The2x effect is visible at VB5213–5226; the1x comparison
continues through5240. This is one combined first-round regression, not every
Cartesian product of options, a complete tiger victory, or cross-profile RNG
equivalence. The ordinary CD1 navigation script was not reused as a false
pass when precise movement changed its route; the combination has its own
recorded legal navigation.
