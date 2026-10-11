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
  validation tests,44 runtime tests,44 GPL renderer tests and 9300 instruction
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

## Saturn-specific external reports awaiting reproduction (2026-10-11)

These are investigation leads, not confirmed failures of this port. Keep the
original timing profile as the reproduction baseline. Record image hash,
version, input, source save, actual/expected outcome and exit/log evidence before
changing code. Separate hardware correctness, original-game logic and opt-in
experience changes; do not remove a beneficial original exploit by assumption.

| ID / category | Reported symptom / source | Evidence quality | Current status / next reproducible check |
|---|---|---|---|
| SS-EXT-001 / possible story soft lock | Cannot return after leaving the city following Fire Qilin; [2021 PTT recollection](https://www.ptt.cc/bbs/Old-Games/M.1617708676.A.202.html) | One retrospective player account; no save or exact inputs supplied | Unreproduced. Reach the relevant story state normally, save before/after boss and exit, test both directions and reload without overwriting baseline |
| SS-EXT-002 / transition presentation | On first Fairy Island arrival, background black while characters/dialogue remain; save/restart reportedly restores it, later recurs; [2023 player article](https://news.17173.com/content/01312023/090039866.shtml) | Claimed play experience; details such as stated save size need independent checking | Unreproduced as this specific original-game issue. Our early DMA short-copy fix does not establish a common cause. Keep paired VDP1/VDP2 evidence and game resource reads around future transitions |
| SS-EXT-003 / possible repeat-item exploit | Comment claims Saturn Demon Locking Tower can raise attributes to maximum; [PTT comment mirror](https://disp.cc/ptt/C_Chat/1QKoCVEj) | Single brief comment without steps; lowest confidence | Unverified. Obtain exact location/steps and test inventory/flag persistence before classifying; no default removal planned |


| SS-EXT-004 / excluded cross-version attribution | “Disappearing” trap passage in an SS-labelled repost matches a [New PAL guide](https://pal.52pk.com/pal1_gonglue/02.htm), including wording/errors and unrelated mechanics | Cross-version mislabelling; excluded as Saturn-specific bug evidence | Keep only general placed-item leave/re-enter/save/load regression. Normal placement, herding, antler collection and release already passed; inventory consumption alone is expected |
| SS-EXT-005 / original visual differences | Real-hardware reply confirms no character fade and slow sword-teaching demonstration; [TGFC discussion](https://bbs.tgfcer.com/thread-7425346-4-1.html) | Player recollection; transparency was asked about but not conclusively answered | Treat missing fade as a possible version difference. Scripted demonstrations and inventory/menu resource waits remain separate from the tested spell-frame cadence |

| SS-EXT-006 / final boss interaction direction | Same [17173 author](https://news.17173.com/content/01312023/090039866.shtml) says final Bai Yue interaction requires approaching from behind, not front/side | One retrospective account; unverified | At final chapter, retain pre-interaction save and try ordinary directions. Distinguish intended facing/interaction geometry from soft lock; do not preemptively modify story flags |

The same TGFC thread's Soul Stealing “fast completion” comment is a strategy,
not proof of a bug. Do not weaken it without a separately justified change.
The [1997 official PC experience-reset patch discussion](https://www.palhero.net/pal-gov/pal/allhell7.html)
is excluded from Saturn evidence. No complete official Saturn errata or
universal Saturn fix pack was verified, and no external patch was downloaded or
executed. Multiple copies of one anecdote do not constitute independent evidence.

Release acceptance for each confirmed change: focused red/green case, baseline
mode retained where behavior is intentionally changed, nearby story transitions,
normal BUP save/load, affected input/audio/render regressions, and published
source commit plus verified download. External anecdotes alone are not grounds
for a patch or an all-game completion claim.


## Reproduced cold opening movie freeze (2026-10-11)

Windows and Linux no-input baselines freeze identically after A1 video chunk 43.
The movie clock and sound CPU continue running; a sound-driver progress pointer
cached before driver installation leaves the audio ring blocked. The bounded
post-install cache refresh now completes all 265 A1 and 930 A2 chunks and returns
to title without input. Fresh full build: 10/10 corrected opening checkpoints,
12/12 original first-battle, 94/94 precise walking and 44/44 quick group-spell
pictures; each gameplay BUP matches its original reference. 71 tool tests and 6
subtests pass. See [INTRO_AUDIO_STREAMING.md](INTRO_AUDIO_STREAMING.md) for
causal evidence, exact commands, binary hash and remaining Windows/audio bounds.
This does not establish original-hardware BIOS state or fix the separate
Windows synthetic selftest 0xC0000409 report, whose failure evidence is pending.


## Guarded battle-animation replacement (2026-10-11)

The earlier accelerated missing-sprite candidate remains rejected. A new
manual erase/change-pair implementation preserves the original IRQ and DMA
submission path rather than forcing a shortened wait to return. Four spells at
four rates have complete per-index visual checks, including post-effect cleanup;
12 legal victory/save/load closures passed. Second Sword-cast differences are
complete original enemy idle poses, verified by full texture hashes and draw
commands. Default full RAM/video/BUP parity passed.

Fresh integrated builds include the cold opening fix: headless SHA256
`4a514371d87c829e9791540e0e322ed481dac28c365d28205a7e786687ffefba`, SDL
`8ccacd88375f8b80a8ae24e674adc8a0b4f7ddaa74c27edd71593ba6548c4446`.
Each passes four Thunder profiles with300/300 same-VB reference images and
same-profile BUP parity. The complete build also retains10 corrected opening,
12 first-battle,94 precise walking and44 quick group-spell reference images,
plus gameplay BUP parity.72 tool tests and6 subtests pass.

The new launcher requires `effect_cadence_v4_manual_pair` for rates above1 and
rejects the old unsafe `effect_cadence_v1` capability. Default remains1.
See [EFFECT_ANIMATION_SPEED.md](EFFECT_ANIMATION_SPEED.md) for the limited effect
whitelist, non-equivalent idle/RNG timing,2x Thunder release-tail boundary, and
unproven arbitrary post-submission ProgramStart recovery. No full-game or
physical Windows sound-device pass follows from these tests.

One maximum-options first-round smoke also passed: precise + paired walking +
CD4 + quick preparation + animation2, compared with animation1 under the same
other options. All7 effect frames and all entities remain complete, damage60
and7MP cost occur, and the command menu returns. This does not assert every
option combination or whole-battle completion for this specific new replay.

## Windows feedback and input follow-up (2026-10-11)

The user reports that Windows gameplay works and walking is substantially
improved, with residual first-step and turn latency. A PC keyboard profile
(Enter confirmation/interactions and Esc game-menu/cancel) is requested;
implementation and native-key-event coverage are still pending here. Existing
Saturn gamepad semantics and saved custom keyboard mappings must be preserved.

The current inn trace resolves precise input3400 to player step3405, original
submission3411 and complete paired RGB3413, versus original DISPLAY3416.
This isolates remaining player-slot and submission delay; it is not a
physical-keyboard end-to-end measurement or evidence that global movement
speed should change. Earlier wake/align experiments that add NPC/RNG ticks
remain disabled. Any further display path needs complete coherent frame
ownership, monotonic presentation and unchanged guest-state traces.

Mainline now has a normal temple-exterior save and fresh-process load check;
see AUTOPLAY_PROGRESS.md. Later story sites remain untested.

## PC98 keyboard mapping acceptance (2026-10-11)

Context-aware Enter/Esc mapping and independent Saturn keyboard profiles are
implemented. Fresh integrated native SDL confirms title/load, field/status
menu, NPC interaction and dialogue continuation; a legacy custom F10/Esc/Return
map retains its behavior and exact settings bytes. Separate native traces cover
attack/target confirm/cancel.148 tool tests+35 subtests pass. The final SDL
binary also retains all10/12/94/44 opening/battle/precise/group-effect reference
pictures and the gameplay save hashes. See PC_KEYBOARD.md for exact identity.

Short presses can still end before a host pad sample, independently reproduced
with direct Z on the immutable previous binary. Mapping acceptance does not
claim this existing sampling weakness is fixed. The additional early-complete-
frame experiment and any semantic pending-edge queue are excluded from this
mapping batch; further first-step latency work remains separate.

## Jade Buddha Temple chapter (2026-10-11 05:26 UTC)

The stable Release-source original-tempo mainline has now completed both
consecutive temple battles, including the abbot's two actual summons, reward
processing, Luo Han Robe acquisition, Jade Buddha Beads and the temple's
vanishing scene transition. Normal menus equipped the beads on Ling and the
robe on Li. Both post-battle and post-equipment saves loaded successfully in
fresh processes; final equipment fields and decoded field RGB match. See
[JADE_BUDDHA_VALIDATION.md](JADE_BUDDHA_VALIDATION.md) for identities, limits and
private replay/save hashes. This supersedes the earlier temple-exterior pause;
Black Water Town and the tomb gate remain the next untested mainline segment.
