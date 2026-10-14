# Gentle continuous field walking

## Scope and control

The live-host field input path now uses a gentle cadence by default. Set
`PAL_FIELD_WALK_CADENCE=original` for an A/B comparison. `gentle` selects the new
cadence; unknown values fail closed to the original cadence. `PAL_FIELD_INPUT=0`
and pure headless/scripted playback retain their original behavior.

A newly accepted press or direction change retains the original movement and
first interval. Subsequent successful continuous steps use `5,4` VBlanks:
45 rather than the previous 36 VBlanks per ten repeated steps, a further 20%
steady-state speed reduction on both Windows and HarmonyOS. Compared with the
original 3-VBlank interval, the total reduction is 33.3%. There is no initial
repeat delay, dropped movement attempt, smaller
collision-grid displacement, extra mover invocation, or global frame/audio clock
change. A pending short tap is still acknowledged and consumed only once.

This is selected only after the original collision/mover has actually displaced
the player, for an acknowledged live field hold in the current scene. Blocked
movement, released contacts, new presses, guest UI, actual script waits, scene
carry/reveal and unknown interval modes reset or bypass the cadence. The
negative-countdown displacement guard also covers a completed guest return that
still has its release latch set. Each keyboard, touch and controller source keeps
its own validated physical level and transaction identity.

## Held directions after dialogue and loading

Guest UI, dialogue waits and scene loading discard pending direction taps while
retaining physical direction levels. At the next natural field decision, the
host drains queued events and polls the current keyboard, gamepad and touch
levels. A direction still held is admitted without requiring release/repress;
this also applies to a direction first pressed or changed during the dialogue.
A released tap or canceled contact cannot produce a deferred field step.

Only completed guest scopes can reach this field decision. The original converter
still owns nonmovement actions, and a latched return admits only current,
direction-only input. Confirm/cancel/menu buttons do not become walking commands.
The latch's native provenance can be retired at this exact return boundary;
neither the guest latch byte nor its countdown is overwritten. Negative countdown
debt still suppresses displacement, with no accumulated extra steps when it clears.
After resumption the accepted live hold uses the same `5,4` walking cadence.

Host focus loss, backgrounding, host menus, canceled touches and disconnected
controllers retain their input invalidation. A host-blocked held contact cannot
be revived by a later guest callback; a physical release and fresh press are
required. New field transactions also reject a changed aggregate held snapshot.

Portable checks cover 73 field/scene cases and eight guest-return ledger cases,
including keyboard/gamepad/touch holds, dialogue-time presses, queued releases,
held confirmation, host boundaries and the unchanged walking cadence. The older
scene-only ledger API remains separately tested; the live field return explicitly
reconciles current held levels after the complete guest boundary.

## Timing limits, explicitly

The original field loop couples player movement, ordinary NPC/event updates and
the render wait. Consequently, while a successful manual hold uses the gentle
cadence, ordinary field NPC/event iterations share that cadence. Relative chase
movement remains in the same original loop. This is not a player-only independent
physics clock and must not be described as one.

The longer interval is installed after `06026E74`'s original mover and restored
immediately after the field render/wait call at `06026E76`, before later script,
UI or battle calls. Their subsequent intervals are unchanged. A countdown already
loaded by a gentle step can still add at most two VBlanks (about 33.3 ms at 60 Hz)
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
  unknown intervals, repeated observation and exact 9/2 cadence over 100 cycles.
- Both 4- and 5-VBlank overrides are restored after the original wait, including
  a boundary during the wait. A changed interval belonging to the guest is retained.
- Only the proved field wait interval is changed by the cadence outcome helper;
  tests compare the remaining fixture WRAM and registers.
- The original and unknown option values retain interval3 over 1,000 repetitions.
- Header identity remains checked by the field planner and detached-generation
  manifests. An old generated header cannot silently inherit the new behavior.

The earlier SDL software-renderer input tests and their measured results are
recorded below. They measured the previous cadence, not the current 9/2 cadence.
SDL queue injection is not a physical OpenHarmony touchscreen/keyboard measurement;
phone/tablet feel remains a device validation item.

### Held-return revision: build and regression verification (2026-10-14)

The user accepted the walking feel of master `9d6662e`. The held-return revision
retains that cadence and passed 407 tool tests plus 201 subtests, with eight skips.
Windows with SDL and the mapping-only headless target both compiled successfully;
the new API also has unavailable/no-op implementations in the no-host and stub
targets. Windows packaging passed its identity gate. HarmonyOS ARM64 and x86_64
were packaged with the current host and guest header dependencies and `-O2`.
The native libraries matched their stripped outputs; official signature
verification passed. The HAP update on MLR-AL10 preserved application identity
and first-install time. Physical dialogue/scene-return feel remains to be tested
on the user's same scene.

- Shared field helper SHA-256:
  `300285c753c72c3438f3b2300ce7a1f718e8c56ea7c34735e894f5176ec8a84a`.
- Windows package: `PAL-Saturn-Windows-9d6662e-held-return-r2.zip`;
  executable SHA-256:
  `6f733a9ddcd2bd6a080add6636ec8289a8d4acf00a51d534fe43d767638b1e4a`.
- HarmonyOS package: `PAL-Saturn-9d6662e-held-return-r2-release-signed.hap`;
  SHA-256: `64d4a6a854bcce38669968821dc024477db3adf3ef005073d926624adfa791c9`.

### Walking-speed-only 9/2 revision: previous verification (2026-10-14)

The shared-header change was built on master `adb7392`, including its HarmonyOS
orientation-menu fix. The complete tool suite passed: 406 tests and 201 subtests,
with 8 skips. The cadence integration checks 1,000 repeated intervals, fresh
presses/turns, release/collision, both override restorations and guest-owned
interval updates. The 20% figure describes steady continuous walking; the initial
step and a pending original countdown can affect a short movement segment.

Windows was fully regenerated and compiled, then passed the distribution identity
gate. HarmonyOS ARM64 and x86_64 were built from the same generated guest code.
Each platform's compiled field-loop object records the current header dependency
and is newer than that header. Both HarmonyOS guests use `-O2`; the signed HAP's
native libraries match the corresponding stripped build outputs, and official
`verify-app` succeeded. These checks establish build inclusion, not a new physical
input timing measurement.

The Windows package was launched from the opening sequence using the existing
window settings and a new working copy of the private pre-battle save. Its live
log confirmed Direct3D11 presentation, WASAPI audio and serial-fiber CPU handoff.
The signed HAP was installed as an update on the connected MLR-AL10 tablet;
application identity and first-install time were preserved. Continuous walking
feel on physical devices has not yet been reassessed for this revision.

- Shared helper SHA-256:
  `7ef4f3b89dcd2783cd66f10a0b7d8b88115406bc9afec4e910f878cf8e78f2a1`.
- Windows package: `PAL-Saturn-Windows-adb7392-walk80.zip`;
  executable SHA-256:
  `c01e4758e74d9a6fddbdbfba2567d8dfa807105235e1c04f86bac9edb0d68abd`.
- HarmonyOS package: `PAL-Saturn-adb7392-walk80-release-signed.hap`;
  SHA-256: `67f749c135bda12d9c9c25dedc3cb20335d35ea1a259b94bb3b1425aa54dfe50`.

### Previous 18/5 cadence: measured SDL comparison (2026-10-13)

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
