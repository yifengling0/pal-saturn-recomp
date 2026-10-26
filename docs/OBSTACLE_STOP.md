# Stop manual movement at obstacles

## Scope and root cause (verified, 2026-10-26)

Baseline: `63d1c90564749705c0a26600295baebf9207680f`.
The original-disc PROG mover `06033654`, not the keyboard adapter, tries
neighbouring directions after the requested step is blocked. Its passability
callee `06033FA0` combines map collision and event/entity collision. Thus a wall,
furniture, NPC or chest can induce the same sidestep; this is not pathfinding.

At `06033752`, the requested collision check has failed and local move count is
zero. The original facing switch may select two neighbouring probes and a
successful two-unit slide. The hook sets only temporary register `r1` to the
switch's out-of-range value, 4, selecting the existing `06033B90` stop/update
path. No position, facing, map, event, collision, camera or NPC RAM is written.

Only manual field caller `06026E74` is changed. Script callers `06023818` and
`060238B0` keep their original obstacle policy. The original caller comes from
saved PR at `r14+4`; current PR has already been overwritten by the collision
callee. Frame range/alignment, CPU, opcode, direction and zero move count are
guarded. Exact disc identity and the actual linked generation's unique PROG
hook are build-time requirements. Missing/drifted/duplicated/non-PROG hooks fail
configuration rather than silently changing unrelated code.

The original bounds clamp `06033538`, coordinate rollback `06033C1A`, party
updates and script/event scheduling are unchanged. Input dead zones, one-tap
walking, keyboard/controller/virtual-pad routing and SCSP are unchanged.
The policy runs after those input paths converge in the manual mover.

## Comparison switch

Default: stop instead of sidestepping when manual movement is obstructed.
Set `PAL_OBSTACLE_STOP=0` before launch to retain original-disc sidestepping.
This switch is independent of walking speed and optional PAL input settings.

## Automated reproduction

Run from the repository with its prepared Python environment and C++ compiler:

```sh
python -m pytest tools/tests/test_obstacle_stop.py -q
python -m pytest tools/tests/test_harmony_movie_linkage.py -q
```

The callback test links the production implementation and checks all directions,
script exclusion, frame/opcode/count guards, original-policy registration and
that all RAM and every other CPU register remain unchanged. CMake fixtures
exercise valid, missing, duplicate, changed and wrong-module hooks. The target
attachment test covers both desktop `saturn` and shared-library `main`.

```sh
PAL_OBSTACLE_RECOMP="$PWD/build/recomp" python -m unittest discover \
  -s tools/tests -p test_obstacle_mover_generated.py -v
```

See `tools/tests/test_obstacle_mover_generated.py` for the optional private-asset
integration test: it extracts current generated functions at test time, never
stores original-disc functions in the repository, and compares actual mover
execution with the production callback enabled/disabled. All 176 scenarios pass:
manual/script callers, four directions, direct/alternate/blocked steps, exact
map edges/corners, near-edge clamps, no input and turn-only. Collision queries
and animation callees are controlled stubs; real scene acceptance is separate.

For a real-disc replay after a normal SDL-enabled `tools/winbuild.py build`:

```sh
mkdir -p build/obstacle-check
build/recomp-build/saturn --cue /private/path/pal_t37401h_13tr.cue \
  --headless --save - --input @tools/acceptance_inputs/movement.txt \
  --vblanks 14500 --out build/obstacle-check \
  --shot 12000,12330,12730,13330,13930 --watch 06076928:0607692C
# Repeat in a separate output directory with PAL_OBSTACLE_STOP=0.
```

The checked-in `tools/acceptance_inputs/obstacle_pickup.txt` is a fresh-game
replay derived from the live keyboard recording, with its long idle interval
shortened. Use `--vblanks 16300 --shot 15950,16130,16230` to reproduce stopping,
turning and the cabinet item popup. Headless scripted pad timing differs from
live keyboard one-tap timing; this replay independently verifies item reachability.

## Actual acceptance and limits

- Full tools regression: **421 passed + 201 subtests, zero skips** with
  private generation and SDL fixtures supplied; generated mover: 176 scenarios.
- Linux SDL build and actual original-disc fresh-game replay passed.
- Five comparison screenshots with `PAL_OBSTACLE_STOP=0` are byte-identical to
  the pre-change binary. Default mode matches the first four; at the bedroom
  desk/chair obstacle the fifth shows the intended stop rather than side slide.
  First coordinate difference at VBlank 13847: original `(1408,320)`, fixed
  `(1424,328)`; the latter remains stopped at the requested obstacle.
- Cloud desktop live keyboard: held Left into the bedroom wall, then held again;
  player stayed at `(1280,256)` instead of sliding. Short Down moved one step to
  `(1264,264)` and faced the cabinet; A/`z` interaction displayed **得到止血草**.
  This verifies reachable item interaction after stopping/turning, not just a
  synthetic coordinate test. This object was a cabinet, not a separate chest.
- No physical controller, native Windows or HarmonyOS device acceptance is
  claimed. Platform-neutral callback/target tests are not device tests.
- No exhaustive tour of every scene/chest or full scripted-story playthrough is
  claimed. Script callers are explicitly excluded and tested independently.
- Private disc, generated game functions and save files are not distributed.
