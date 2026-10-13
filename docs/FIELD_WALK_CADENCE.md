# Gentle continuous field walking

## Scope and control

The live-host field input path now uses a gentle cadence by default. Set
`PAL_FIELD_WALK_CADENCE=original` for an A/B comparison. `gentle` selects the new
cadence; unknown values fail closed to the original cadence. `PAL_FIELD_INPUT=0`
and pure headless/scripted playback retain their original behavior.

A newly accepted press or direction change retains the original movement and
first interval. Subsequent successful continuous steps use `4,4,3,4,3` VBlanks:
18 rather than 15 VBlanks per five repeated steps, a 16.7% steady-state speed
reduction. There is no initial repeat delay, dropped movement attempt, smaller
collision-grid displacement, extra mover invocation, or global frame/audio clock
change. A pending short tap is still acknowledged and consumed only once.

This is selected only after the original collision/mover has actually displaced
the player, for an acknowledged live field hold in the current scene. Blocked
movement, released contacts, new presses, guest UI, actual script waits, scene
carry/reveal and unknown interval modes reset or bypass the cadence. The original
scene negative-countdown displacement guard continues to use its original proof
and interval. The host keeps keyboard, touch and controller ownership unchanged.

## Timing limits, explicitly

The original field loop couples player movement, ordinary NPC/event updates and
the render wait. Consequently, while a successful manual hold uses the gentle
cadence, ordinary field NPC/event iterations share that cadence. Relative chase
movement remains in the same original loop. This is not a player-only independent
physics clock and must not be described as one.

The longer interval is installed after `06026E74`'s original mover and restored
immediately after the field render/wait call at `06026E76`, before later script,
UI or battle calls. Their subsequent intervals are unchanged. A countdown already
loaded by a gentle step can still add at most one VBlank (about 16.7 ms at 60 Hz)
to a newly arriving turn/press or the first subsequent script wait. We deliberately
do not rewrite the countdown or skip its original erase/render stage to erase
this bounded difference. First-input responsiveness is not claimed identical in
every phase, nor is this a fix to the original idle-to-movement transition.

The underlying game chooses a 6-VBlank idle interval and 3-VBlank movement interval.
An already-running idle countdown can therefore make the first two committed
steps 6 VBlanks apart even before this change. Inspect actual committed positions,
not only the interval constant, when comparing responsiveness.

## Verification

- Pure planner tests preserve every original generated instruction, including the
  one mover and render call. The added wait restoration hook is paired at E76.
- Portable integration covers fresh taps, direction changes, holds, release,
  collision, source changes, scene debt, real UI/script boundaries, non-live paths,
  unknown intervals, repeated observation and exact 18/5 cadence over 100 cycles.
- Only the proved field wait interval is changed by the cadence outcome helper;
  tests compare the remaining fixture WRAM and registers.
- The original and unknown option values retain interval3 over 1,000 repetitions.
- Header identity remains checked by the field planner and detached-generation
  manifests. An old generated header cannot silently inherit the new behavior.

Actual SDL software-renderer input tests and their measured results are recorded
below. SDL queue injection is not a physical OpenHarmony touchscreen/keyboard
measurement; phone/tablet feel remains a device validation item.

### Measured SDL comparison (2026-10-13)

A private copy of the normal Yangzhou well pre-medicine-chest BUP was loaded
through the game's original save menu, then handed to the live host at VB3401.
An explicitly test-only injector scheduled real SDL finger events at exact
VBlanks. Both runs used SDL's dummy/software renderer and the deterministic guest
clock, not `--realtime`. No ROM, guest position, HP, inventory or source BUP was
edited. The same binary was run with `original` and `gentle`.
A separate pure-headless replay produced byte-identical screenshots and unchanged
save copies with both settings, confirming that the live-only option does not
change the scripted path.

- DOWN/turn events scheduled for VB3421, 3445 and 3469 were dispatched at those
  exact VBlanks. First movement was VB3423 in both runs; both direction changes
  were committed at VB3447 and VB3471 in both runs.
- In a continuous segment, original positions committed at VB3471, 3474, 3477,
  3480, 3483, 3486 (five intervals = 15). Gentle committed at VB3471, 3475, 3478,
  3482, 3486, 3489 (five intervals = 18). Every repeated interval was 3 or 4.
- Release at VB3493 produced no later held-motion step. The gentle final held
  step was VB3489; original was VB3492.
- Two separate 1-VBlank taps (VB3505–3506 and VB3521–3522) each produced exactly
  one step in both runs. They remained eligible once even when already released
  at the next original field decision.
- A second actual SDL virtual-gamepad run exercised holds, collision, immediate
  opposite-direction changes and taps through the same production host ledger.
- All four deterministic runs exited normally; their source BUP hashes were
  rechecked unchanged. The gameplay-only fixture/sanitizer checks remain distinct
  from these real generated-game/SDL checks.

Earlier exploratory runs used `--realtime`, which follows wall-clock elapsed
rather than deterministic guest cycles. Under concurrent work they produced
large negative countdowns in the original build too. Those exploratory results
are **not** used for this cadence acceptance or latency claim.

The exact test commands, event journals, position logs and per-run checksums are
kept with the private test output. No proprietary generated game code, extracted
assets or saves are included in this repository. No physical OHOS device was
available for this validation.
