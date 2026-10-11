# Optional battle-effect animation cadence

> **Safety update 2026-10-11:** animation rates above1 are temporarily blocked by
> the launcher. Direct environment requests also warn and fall back to1 after
> rebuilding. Real Thunder footage revealed missing character/enemy frames at
>1.5/2; prior same-mode replay equality did not prove original-picture integrity.
> Keep animation1. Quick preparation and precise input are separate options.
> Historical measurements below remain evidence, not current accelerated-mode acceptance.


Currently use only `--effect-animation-speed 1` with
`tools/run_pal_profile.py`. Requests for `1.25`, `1.5` or `2` exit with code3
before starting the game. Default1 preserves original behavior. This option
is independent of `--quick-spell`, which shortens preparation before effects.
It does not change walking, global CPU/VBlank clocks or audio sample rate.

The disabled candidate targeted the standard bank7 frame loops for healing (effect33,
20 frames), Sword Technique (effect10,26 frames), Yue Ru's group spell
(effect43,14 frames), and Ling's learned Thunder spell (effect1,7 frames). Unknown effects, frame counts, caller paths, scheduler
phases or ownership chains retain original timing. Other Ling spells remain outside the whitelist. For example, Wind uses two
passes of its20-frame resource; it is not silently treated as a single pass.

| Effect-frame waits | Original | 1.25 | 1.5 | 2 |
|---|---:|---:|---:|---:|
| Healing,20 frames |80VB|64VB|54VB|40VB|
| Sword,26 frames |104VB|84VB|70VB|52VB|
| Group,14 frames |56VB|45VB|38VB|28VB|
| Thunder,7 frames |28VB|23VB|19VB|14VB|

Each decoded effect frame remains present. The two original logical update /
composition calls per frame remain, with at least one real VBlank per call.
Fractional rates use ceiling cumulative rational waits; error is below one VB
for this effect-frame wait sum, not for the entire spell. Sword's separate
sound-related extra tick, preparation, target selection, damage and turn logic
are not globally sped up.

## Historical logic/timing results (visual acceptance withdrawn)

The original three tested spells at 1/1.25/1.5/2 have completed battle, returned to map, written
normal BUP saves and independently loaded them; saved-map and reloaded-map
pixels match. Cases include two Sword casts and three group targets, real MP
cost and observed damage. Fixed old input scripts can cease matching changed
reward pages; these cases use newly recorded legal inputs, not guest writes.
The updated nested-scope/task-mode guards preserve the earlier 1.5 results
across820/820 sampled frames.

Random/idle timing and some outcomes can differ. This is an optional experience
change, not a claim of identical RNG or byte-identical saves across rates.
Default 1 adds no guest reads from cadence hooks. Fiber task execution and
`--state-in` runtime snapshots disable the cadence scope because a replaced
fiber stack cannot safely retain these RAII contexts; normal in-game BUP saves
are unaffected. Nested scope identity and exception unwinding are tested.

SCSP trigger order/count and primary-spell tails were checked for the tested
rates. Faster animation can trigger an effect sound earlier, but its playback
sample rate/pitch is not accelerated. Existing enemy-effect overlaps remain. At2x, the Sword sound itself still lasts
about705ms and its tail continues roughly8VB beyond the disappearing sword
effect / initial damage display, ending naturally before the next sound. This
is an expected audio-original-speed difference, not audio/visual timing parity.
This is not a guarantee about every sound or actual Windows sound-device output.
The cloud has no working physical audio device.

## Ling Thunder: historical first-round logic results

The ordinary three-character party save has Ling at level6 with Thunder learned;
no higher-level spell is injected. Against a900HP tiger, Li and Yue defend while
Ling casts. With quick preparation enabled, rates1/1.25/1.5/2 retain all7 decoded
frames and both original ticks per frame. The tested round deals59 damage,
charges7MP (217→210), completes the enemy response and returns to the menu.
The unshortened preparation reference deals60, demonstrating the already-known
random timing difference; cross-profile damage identity is not forced.

Thunder at2x has a new small audio boundary: after KEYOFF, the remaining release
tail would last about3.584ms; the next hit sound reuses the same slot0.7168ms
later, taking over roughly2.8672ms of that tail. Rates1/1.5 do not have this
particular takeover. Trigger count/order remains unchanged. This is disclosed,
not hidden as audio equivalence; no global sound clock or unrelated turn wait
is changed to compensate. Actual Windows audibility remains unverified.

These historical Thunder results cover the first complete round, not an independently
completed900HP battle/save/load at every rate. The three earlier spell closures
must not be used as proof of that additional claim.

## Current safe example (PowerShell)

```powershell
& $py tools\run_pal_profile.py original --quick-spell --effect-animation-speed 1 --exe $exe -- --cue $cue --save $copiedSave --settings - --out build\win-spell-safe
```

Use separate copies of the same source save. The launcher clears inherited
options and checks the executable hash/capability sidecar. This pipeline was
compiled and replayed on Linux with C++20; native Windows validation remains
with the user's local test.

## Safety-gate executable verification

A fresh Linux headless options build was run with a direct environment request
for animation2, bypassing the launcher only to test the runtime safety stop.
It exited0, emitted exactly one fallback warning and zero accelerated-frame
records. All205 Thunder screenshots and the resulting BUP matched the
quick-preparation/original-animation reference. Binary SHA256:
`4f8f9384402881e9acb9506cacea70b9c819e141a5f31678a3a74ed04bda047b`.
The launcher independently rejected animation2 with exit3 even when pointed at
a previous executable. This confirms the safety behavior, not a repaired
accelerated renderer. Native Windows execution remains unverified.
