# Flexible layout validation (2026-10-22)

Runtime change: patch 0032. Patch 0033 changes only upstream test expectations:
legacy settings intentionally persist `layout_version=1` since before this release.
The two old exact-text assertions failed with both the preview.4 baseline and new
Settings implementation; they now explicitly check the required persisted marker.
No production settings behavior was changed to make those tests pass.

## Completed checks

- Repository tests with all private input opt-ins enabled: **418 passed, 201 subtests, zero skipped**.
- Upstream Python and wrapper validation: **232 passed, 8 subtests**.
- Upstream runtime C++ suite after test-only 0033: **45 tests, zero failed**.
- Independent layout tests compile actual Settings/geometry and extracted production
  host editor/event functions, not a separately implemented behavioral model.
  Both desktop and mobile macro variants run. Reset, cancellation, failed-save
  rollback, restart persistence, orientation isolation, pointer capture and bounds
  are exercised.
- Production Linux: actual optimized (`-O3 -DNDEBUG`) build, `--help`, missing-disc
  failure and verified original-disc 1500 VBlank boot smoke passed. Smoke is not
  gameplay, audio quality, or end-to-end completion evidence.
- Production Windows: optimized x86-64 PE cross-build and import inspection passed.
  No native Windows or Wine execution is claimed.

## Actual SDL UI regression

The complete compiled game was run using SDL's offscreen software renderer and
real SDL event queue. A test-only Linux mobile host uses the production host and
Settings sources compiled with `PAL_OHOS_DEFAULTS` and `PAL_OHOS_DISPLAY`, plus a
flat `Fold{}` / no-op orientation bridge. A local test hook injects SDL events,
resizes the actual window and reads pixels from its renderer. Neither the bridge
nor injection hook is part of a release package.

Verified with actual touch events:

1. 1200 x 600 landscape window: explicit below split creates game 1200 x 360 and
   controls 1200 x 240; menu correctly displays “上下”.
2. Picture dragging saves normalized x=21/y=22 at scale=70. Button dragging saves
   D-pad x=2521/y=5080 in the separate touch profile.
3. Resize within landscape releases the old drag while preserving its draft.
4. Changing to 600 x 1000 portrait cancels an unsaved touch draft without copying
   it into portrait. Portrait right split and picture x=0/y=80 remain independent.
5. Returning to landscape restores its below split, picture and D-pad positions.
6. Full process restart restores both profiles and leaves the saved configuration
   file hash unchanged.
7. The unmodified production desktop Linux executable ignores the mobile profiles,
   stays full-window in both aspect ratios, and opens/closes its menu with actual
   keyboard AC Back events.

Screenshot and executable SHA256 values are in `UI-EVIDENCE.json`. Screenshots show
real startup logo/movie content, not an asserted gameplay milestone. UI screenshots
are evidence of offscreen rendering, not of a physical desktop or HarmonyOS device.

## Remaining platform boundaries

Physical DPI, multitouch drivers, actual folding hardware, HarmonyOS lifecycle,
physical-device GPU, Windows input/audio and full gameplay are not verified here.
The inherited mixed-input-source held-direction restore ordering is unchanged;
this work does not claim to resolve its last-key-priority limitation.

At this checkpoint the official HarmonyOS SDK download is blocked, so no new HAP
or complete three-platform release is claimed. Final build provenance must record
an actual successful new HAP before publication; old binaries must not substitute.
