# PAL input response investigation (2026-10-10, in progress)

## Reproduced user-visible problem

The user's target is precise, immediate short-press movement, not simply a lower
framerate. Default Linux SDL pacing was independently measured at 59.9401 and
59.8954 VBlank/s over two 594-field windows. The guest intentionally uses a
three-field movement interval. This does not establish acceptable input latency.

With the unchanged game executable, RIGHT down at VB3400 and up at3412 produces:
- SMPC response in3405, containing the correct pressed pad bits;
- guest driver buffer update3411 and game input-cache update3412;
- direction consumption/turn3417, first position change3423;
- first displayed displacement3431.

The last point is31 VBlank labels after down, about517ms at59.94Hz; these are
virtual-frame measurements, not sub-frame wall-clock timestamps. A separate
one-field pulse matrix loses5 of6 starting phases. Six-field taps register but
only turn. Original game report caching, infrequent polling and turn-only first
input all contribute. No generic SMPC protocol correction is justified by this
experiment. Native SDL current-state-only sampling is a separate possible loss
layer; it has not yet been measured as native tap failure rates.

Menus: twelve-field DOWN pulses succeed in all six phases. Two pulses separated
by30 released fields move the selection twice. The menu remembers its previous
selection; this must not be mistaken for a missed press. Shorter1/2/3-field menu
pulses do share the guest sampling limitation.

## Opt-in experimental PAL policy

This is an explicit game-specific control improvement, not original hardware
behaviour. It is disabled by default. `PAL_RESPONSIVE_INPUT=1` enables it only in
the isolated experimental executable. The released baseline is not replaced.

- Sample a separate direction intent at each guest VBlank during field rendering.
- Retain at most one unconsumed tap; newest direction replaces stale directions.
- A step turns and moves together through the original collision function.
- Released input cancels repeat; a tap released before consumption may still
  receive its one requested step.
- Initial repeat threshold is12 fields, followed by the original3-field cadence.
- Opposite simultaneously-held directions cancel. Orthogonal overlaps prefer
  the most recently pressed direction while it remains held.
- Preserve original menu/interaction actions. Clear intent at UI, blocking script
  and scene boundaries, and require release for a held direction across a boundary.
- No direct position writes, global timer changes, battle speed changes, or VDP
  display-buffer substitution.

First real-disc results from experimental executable SHA256
`676b51310696356c067610877f63ed67a25be68b28d6efdb1e2f55fe522d0832`:
- Off mode:186 overlapping per-VBlank PNGs byte-identical to baseline, exit0.
- On mode:1/2/3/6-field taps across all six phases each produce exactly one actual
  (+16,+8) step. A12-field tap also produces one step.
- Example first movement3405, first displayed movement3416:250ms less than the
  baseline example, but remaining visual delay is still about267ms.
- Twelve-field menu double-tap screenshots remain unchanged.
- A30-field hold stops repeating on release. Its startup repeat cadence still
  includes an extra6-field gap due to the guest idle/movement interval switch;
  this is under investigation, not reported as uniformly3-field repetition.

Full phase/boundary testing and native SDL verification are ongoing. The mode
is not yet recommended as a completed default. No98-version timing measurements
have been made; that version is the user's experience reference only.

## Reproduction

After the verified baseline is built:

```sh
build/venv/bin/python tools/prepare_responsive_lab.py \
  --out build/my-responsive-lab
# For an actual window, add --sdl-prefix build/prefix.
PAL_RESPONSIVE_INPUT=1 build/my-responsive-lab/recomp-build/saturn \
  --cue /path/to/verified/pal_t37401h_13tr.cue \
  --save /path/to/a/copy-of-a-test-save.bup --settings -
```

The builder refuses an existing output directory, copies the verified runtime
and generated code locally, records provenance, and builds only the experiment.
The commercial generated code/save/disc files remain private local inputs and
are not included in the source/recovery deliverable.

Evidence directories: `build/linux-input-chain-readonly-004`,
`build/linux-sdl-wall-timing-001`, `build/linux-sdl-input-audit-001`, and the
experimental matrix directory reported alongside each run. See their exact
commands, executable hashes, logs, source-save checks, and PNGs before making
stronger claims about latency or coverage.

## Subsequent v2 boundary results

Experimental SHA256
`6ded9b873aa7bd51991cceab0c227f01ba75ca94b464784bca013dd429e31b95`:
- The repeat-delay phase now keeps the existing three-field movement cadence
  while suppressing displacement until repeat is due. Six30-field hold cases
  each took seven steps; repeated steps after the first repeat are three fields
  apart, and no logical repeat occurs after key-up.
- Opposite-direction overlap cancels an unconsumed direction tap as well as repeat.
- Genuine scene2→scene4 transition with DOWN held across loading stops at the
  destination; release and repress produces one new step. No held input leaks
  through the scene boundary.
- Menu held-key exit and re-arm tests pass. Mode-off186-frame parity passes again.

Native SDL edge combinations are separately covered by pure-policy tests and
review; they must not be claimed as real device tests. The latest prototype adds
one-shot focused-window keyboard direction edges, filters repeat events, clears
on host menu/focus boundaries, and preserves the latest orthogonal edge. The
current host's normal opposite-direction cancellation must also clear its edge.

## Separately gated scheduler experiment

`PAL_RESPONSIVE_ALIGN=1` and `PAL_RESPONSIVE_WAKE=1` are experimental and both off
by default. They only take effect with responsive input enabled. ALIGN clamps
the previous idle countdown to at most2 when a new field step selects interval3.
WAKE clamps a remaining idle countdown to1 only inside the field's actual sync
wait, with ready-command and prior-DMA-complete guards. They never write zero or
negative values, and retain the original erase-before-change sequence.

These experiments may advance one field/NPC/script/RNG iteration. They are not
pure presentation changes, not hardware fixes, and are not accepted until trace,
frame, and non-player cadence comparisons are reviewed. No battle timing change
is intended or established. Current in-progress executable:
`6c780c5477d9fc67d3a9f00da6c2b95fed46d8a2ced587c9c134d9ebeb2923ce`.

## Final scope tightening and v4 regression

The builder now treats the call at06026E84 as a script boundary rather than a
second field-input collection window. Frozen headless v4 executable SHA256:
`5c8d1adf1b950d41a26ecf9ecb4753ba3e3639d3cb10b1229e498264084196d4`.
With ALIGN and WAKE both disabled,49 independent real-disc runs exited0:

-30 combinations of1/2/3/6/12-field taps and six phases produced exactly one step.
- Holds retained three-field repeat cadence after the initial repeat delay;
  release produced no trailing repeat. Opposite pending inputs cancelled.
- Menu, genuine scene transition and fishwife dialogue boundaries passed.
- Default unset mode reproduced186 original frames exactly. The overlapping
  earlier-version samples reproduced1078 images and their recorded input traces.
- A natural first battle was reached nine fields earlier because precise input
  changed approach movement. After aligning the actual battle-entry event,
 191 consecutive frames and1303 input/menu writes matched baseline; no field
  intent or position update escaped into the battle. A render-loop index differed
  by one, so this does not assert complete RAM equivalence.

Reports: `build/linux-input-v4-readonly-013/REPORT.md` and
`build/linux-input-battle-v4-readonly-016/REPORT.md`. Source backups and frozen
binaries were unchanged. The blocked branch of the newly guarded script call
was not necessarily executed merely because these regression routes passed.

Separately, native SDL v3 with both timing experiments enabled had seven observed
short presses produce one position step at sampled down+1 field, and three holds
produced no new step after release. Its actual12-second video and report are in
`build/linux-native-response-001`. Sampled input-to-logic is not physical
keyboard-to-visible latency; the recording is30fps. A native held-direction
across menu-close case was not established. The experiments' field/NPC/script/RNG
side effects remain, so that native result does not promote the fast profile to
default or validate it for every battle.

## Victory-to-field held-direction regression

Two additional precise-v4 processes passed, bringing this bounded regression
set to51 real-disc runs. With ALIGN and WAKE disabled, a fresh UP press closed
the final luck reward and remained held across battle return. After field
control resumed,106 fields of continued holding produced no intent or movement.
Release for30 fields followed by a one-field UP tap produced exactly one
collision-approved step, with no trailing step.

The independent ordinary-input replay reproduced12 RGB images and5777 input /
watched-store trace records exactly. Both processes exited0 and left their
source checkpoint unchanged. This proves the tested first victory boundary,
not every battle or reward path. Evidence:
`build/linux-v4-postbattle-boundary-readonly-020/REPORT.md`.

The SDL-linked v4 build also succeeds (SHA256
`93858367610e16a90d5c8ea9687f89abbc57f95cb37c25022ff8c958f38f6e80`).
Its headless replay of this boundary reproduces all12 images and leaves the
checkpoint unchanged, exit0. The profile launcher now points to this newer
SDL build by default; `PAL_RESPONSIVE_EXE` still overrides it. Native window
input was previously tested with v3 only; this build/replay is not an additional
physical keyboard or audio-device test.

## Further latency audit, without a new timing change

A read-only follow-up traced the existing precise first-step delay as5 fields
before consumption plus6+1+3+1 from the approved step to the first visible PNG.
The latter includes an old idle countdown and two real framebuffer exchanges,
not a single host display sleep. The already queued previous draw can still
consume VRAM after its DMA reports complete. The normal manual render branch
also does not test the ready flag before submitting; a slave can still write
header data after setting ready.

Consequently, shortening the shared countdown and then merely holding the next
NPC scan is not a proven safe remedy. Command-bank reset, sound service and
post-wait script dispatch have already advanced before that scan. Reordering
the player's collision transaction also changes which NPC state and trigger
positions it observes. No new scheduling patch or default flag change was made.

The bounded next observation records render-version ownership while preserving
the original wait/deadline. Only an isolated logging build is contemplated;
source/reference report: `build/audit-input-latency-002/REPORT.md`. This is not a
claim of a newly measured latency improvement or a test of the1998 PC version.

## Rejected completed-frame preview prototype

The render ownership observation was followed by one isolated, default-off
host presentation selector. It only selected a fully completed DRAW whose
VDP2 registers, VRAM and palette matched the recorded producer version. Real
DMA, framebuffer swaps and completion interrupts retained their original times.
This prototype is rejected and is not part of the profile launcher or stable
source path.

In the25-field window, token100 appeared at3413 rather than3416, but at3415 a
strict VDP2 register mismatch forced fallback to token99 and visibly restored
the old player/background position.24,194 RGB pixels changed in that rollback;
there were five draw-version regressions in total. All selected images matched
actual reference images, but their temporal ordering was wrong. Earliest-first
visibility alone is therefore not an acceptable latency metric.

Default-off25 PNGs matched the reference. Across the prototype on/off runs,
25 complete2MiB high/low RAM snapshots,25 video dumps,200,151 watched events
and14,220 ordered NPC/script/RNG/sound/wait/DMA/swap ledger events matched.
The complete RAM snapshots compare this isolated executable's on/off paths;
the original frozen executable did not acquire the new full-RAM probe.
The interpolation fallback A/B also matched. This is a bounded noninterference
check, not a whole-machine savestate proof or native display latency test.

The minimal ordering failure stopped expansion to held input, turning, menus,
scene transitions and battle boundaries. Those are untested, not passed. The
failed case, isolated patch and paired-frame evidence remain in
`build/completed-frame-preview-001/REPORT.md` and its adjacent files; no generated
commercial source or image data is included in the repository.

Any later proposal must preserve complete compositor-version ownership and
monotonic presentation order, clear ownership safely at menu/scene/focus/load
boundaries, and avoid reusing stale images through fades or overlays. Ignoring
the differing register or holding an old framebuffer without that lifecycle
proof is not an accepted solution. No replacement queue architecture was built.
