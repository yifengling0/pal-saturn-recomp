# First-combat observation build, prepared without running the game

2026-10-10 15:49 UTC. Current live002 remains owned by the route worker. This plan does not start, stop, attach to or feed input to that live process. Baseline executable SHA256 verified before preparation:
`f5aa1c835d82700ab802ce589ac242534d589de679c8db9753a84ab1aedbf030`.

## Prepared deliverables

- `prepare_probe.py`: defaults to validation only; with `--output` creates a new, detached generated-code + runtime snapshot under this repository's build directory. Refuses an existing output directory, overlapping paths, changed baseline executable, duplicate/missing instruction match, already-instrumented source, and source/runtime changes during copying. No game/compiler/download runs inside it.
- `pal_battle_probe.h`: observation-only C++ scopes, active only with exact environment `PAL_BATTLE_PROBE=1` and only while a master-CPU060422B8 battle call is on the stack. Does not alter registers, RAM, budget, input, clock or RNG. WRAM observations directly read the host arrays, never MMIO.
- `summarize_probe.py`: pairs entry/exit IDs and groups inclusive duration by function, resource filename and initial caller. Marks log caps, unmatched records or runtime-stop exception unwinds as incomplete. Nested buckets overlap and must not be summed.
- `validation-snapshot/`: already-prepared, private generated/runtime sources for review or building. Its manifest hashes every source/runtime input, baseline executable, generator and header. No game executable has been built there.

## Eight scope probes

|Guest PC|Scope|Main measurement|
|---|---|---|
|060422B8|battle|Arms tracing for the fight; logs group and all subsequent phases|
|06020094|resource|Filename, initial caller, sector, requested bytes, destination; covers ABC,FFF,FBP,FIREN and audio banks|
|0602F590|sprite_upload|Actor frame-table build and CPU upload; reports actual packed-pixel cursor delta|
|0603108C|effect_prepare|FIREN read plus DMA/palette setup, effectID r4|
|06024220|effect_decode|One visual-effect frame decode/draw, r6 source and r7 framebuffer|
|0603E818|animation_ticks|r4 requested ticks and inclusive render/wait duration|
|0602222C|frame_present|Guest frame submission/sync boundary, not confirmed SDL presentation|
|0605D68A|frame_sync|Whole synchronization call; no per-spin-loop logging|

Four lightweight markers are grouped under the battle scope:0604270C enemy_ready,06042712 party_ready,060428E0 background_ready,060428F8 display_enabled. These occur before the named guest instruction, after the preceding call has completed. They do not introduce another safe point.

All records contain VBlank, guest nanoseconds and host steady-clock nanoseconds. Entry/exit records retain the original caller and r4–r7. Each record also captures:
- scene/requested scene060768EE/E0
- game input held/pressed/released0607682A/C/E, driver-held0605D1DA, menu edge06076830
- battle tick06076990, effect frame/count060769C8/DA
- sprite count060769B2 and packed pixel bytes060769B4
- frame interval/countdown at actualGBR+18/+19

Input fields are snapshots of existing guest state, not new input samples. Correlate with the exact accepted replay file and baseline runtime's normal pad log. Do not call host_pad or pad_now from observation code, because sampling could consume or reorder input. Presentation evidence still needs `--shot`/video frames aligned to VBlank; the probe does not claim an image reached the display.

`bytes_req=0 whole_file=1` means the API requested the whole file, not that zero bytes were read. The probe reports requested byte counts, not a guessed successful transfer count. `result` is rawr0 and is not interpreted as bytes. Actor `upload_bytes` is the verified packed-pixel cursor delta. Effects decode byte consumption is not fabricated.

## Validation already performed

- Validation-only run: all8 entries and4 markers exactly once (`validation-only.json`).
- New output generation succeeded (`prepare-validation.log`); a second request for the same directory refused with exit1 (`reject-existing.log`).
- All5 modified generated C++ translation units passed `g++ -std=c++20 -Werror=format -fsyntax-only` using the detached runtime headers.
- Native fixture-only self-test compiled with `-Wall -Wextra -Werror`; two executions passed with probe off/on. It never boots game data or connects to any live process.
- Disabled probe emitted no records. Enabled fixture produced5 matched scope pairs and1 marker; battle-external resource call was filtered; filename/sector/byte fields matched; thrown test exception correctly marked `unwind=1`; scope nesting returned to0.
- SH2Context and both1MiB WRAM fixture arrays were byte-identical after observation. Raw read of a CD-port address returns0 rather than invoking MMIO.
- Summary parser found4 normal groups,1 unwind and no unmatched IDs or anomalies; the unwind made the summary explicitly incomplete.
- Every original generated/runtime source hash still matched the preparation manifest afterward. No main source/runtime changes were made by this worker.

These are source/fixture validations, not actual-game replay equivalence or combat timings.

## Review/build commands for the parent

From repository ROOT, validation-only:

```bash
python tools/battle_probe/prepare_probe.py --root "$PWD"
```

To prepare another snapshot, choose a genuinely new path:

```bash
python tools/battle_probe/prepare_probe.py --root "$PWD" \
  --output build/battle-probe-review-001
```

Or build the already-prepared `validation-snapshot` after review:

```bash
D="$PWD/build/battle-analysis-001/validation-snapshot"
cmake -S "$D/recomp" -B "$D/compile" -G Ninja \
  -DSDL3_DIR="$PWD/build/prefix/lib/cmake/SDL3"
cmake --build "$D/compile" --target saturn -j4
sha256sum "$D/compile/saturn"
```

No SATURN_EXTRA should be passed. The copied CMake rejects nonemptySATURN_EXTRA and any runtime outside the detached snapshot, preventing incorporation of the new PAL input layer. Existing optional PALDIAG callbacks are not added to this isolated build; all gameplay instructions remain in the copied translation.

Once a legal pre-battle save or complete baseline replay is available, the parent can run its authorized isolated replay with this executable and `PAL_BATTLE_PROBE=1`, a fresh output/save-copy and the exact same RTC/input/window/audio mode. Do not add or alter button events for the diagnostic comparison. Do not start another live session whilelive002 is active. No game-run command is supplied because its exact valid save/input boundary is not yet established here.

Summarize a future log:

```bash
python tools/battle_probe/summarize_probe.py /verified/path/to/run.log > /new/path/to/summary.json
```

Before interpreting slowdown, require an off-probe replay comparison against baseline: same scene transitions, actor state and selected screenshot hashes. Then compare probe-on and probe-off outputs. Host timings include logging overhead; guest timing should remain unchanged because noSH2_POLL is inserted. Logs cap at20000 records and explicitly reportLIMIT/incomplete; stop using a capped log as complete evidence.

## Reading the future result

- Split initial setup using the four markers; resource filename/caller associates each read with enemy, party, background or audio preparation.
- Separate FIREN read06020094 from total effect setup0603108C and per-frame decode06024220.
- Compare frame decode versus0603E818/0605D68A, preserving the game's interval2 and explicit two-tick effect-frame wait. Do not change those merely because they dominate measured duration.
- A guest-present return is not the first visible frame. Use the corresponding image sequence to measure that additional gap.
- Time inside battle060422B8 after setup is combat duration. Never label its whole scope as loading time.

## Compilation and pre-battle equivalence check

The detached SDL-capable probe executable was compiled successfully: SHA256 `e5028504872bbd76d7403c3826594403aa627780d9c74eefaeb1fbabc8424018`. Before reaching combat, disabled and enabled probe runs each reproduced all93 baseline per-VBlank PNGs byte-for-byte, returned0 and left the source save unchanged. Neither emitted battle records, as expected outside battle. This verifies the off/battle-exclusion path, not combat performance or battle-active equivalence. Evidence: `build/battle-analysis-001/prebattle-parity.json`.
