# Optional complete paired-frame presentation

`tools/run_pal_profile.py precise --paired-frames --exe EXE -- GAME_ARGS`
selects `PAL_PAIRED_FRAME_QUEUE=1`, with precise input enabled and the separate
alignment/wake experiments disabled. Default is off; `--interp` bypasses this
queue. This is a bounded experimental presentation improvement, not a change to
Saturn hardware event timing or a claim that all input delay is eliminated.

## Why a complete RGB snapshot

The rejected earlier preview merely selected the newer VDP1 framebuffer. It
could later fall back to an older frame and visibly flash backward. That code
is not included. The new path checks PAL producer ownership, exact submitted
DMA descriptors/payload, VDP2 register/VRAM/CRAM pairing and actual completed
VDP1 drawing. It immediately composes an immutable full RGB image, then uses a
bounded two-entry monotonic queue. A handoff retains a complete image only until
normal DISPLAY catches up. Real display-off presents black immediately; no
unfinished framebuffer is sampled.

Menu, dialogue, scene, battle, focus, state-load and interpolation boundaries
invalidate eligibility. Failed pairing falls back to the original renderer.
The queue never writes guest RAM, adds guest polls or advances CPU/VDP events.
A completed image may expose a valid intermediate field that the old display
schedule skipped, so not every new screenshot must exist in the baseline set.

## Verified bounds (2026-10-11)

- First visible response in the minimal inn case: VB3416 to VB3413, 3VB or about
  50.05ms of guest time. This is not a physical-keyboard end-to-end measurement.
- Extended matrix: 1985VB per side, no presentation serial regression; complete
  WRAM/video states, 31,474,470 ordered watch records and 869,423 observation
  records agree. Covers short-tap phases, hold/release, fast turns, menu,
  scene2→4, battle entry/return, NPC dialogue and interpolation bypass.
- Both previously captured flashback failures are absent. Menu retirement and
  battle display-off have dedicated regression cases.
- Log-free portable source: six actual-ROM smoke cases, including default off,
  queue on, INPUT=0 and interpolation bypass, match the observed prototype.
- New combined SDL executable, run headlessly: 25/25 RGB frames, 25/25 complete
  video dumps and BUP match the log-free queue reference. Combined default,
  precise and quick-spell modes also retain their prior exact replay results.

Physical focus/host-menu behavior and a native walking comparison are being
verified separately; synthetic lifecycle tests and successful SDL compilation
alone do not establish those UI results. Arbitrary VDP2-only effects or abnormal
no-further-swap scenarios remain outside the bounded coverage. Windows native
execution is still untested in the cloud.

## Build provenance

`winbuild.py --pal-options` injects all options in one in-memory transaction,
validates every source/PC/header before writes and records final hashes in one
manifest. No second installer is appended over an existing manifest. The queue
planner checks exact runtime versions and refuses unknown code or stale output.
The executable capability manifest must contain `paired_frame_queue_v3` and the
actual executable hash. Never reuse an old binary with a copied sidecar.
