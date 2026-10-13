# Mode-10 obtained-item prompt confirmation

## Original behavior and bounded correction

Verified T-37401H V1.000 PROG path:

- Opcode 62 (`06029EE8`) sets dialogue mode `06076902` to 10.
- Text opcode FFFF draws through `06024FD8` / `06025202`, incrementing `060768FC`.
- Next-instruction cleanup `0602313C` calls `060220D0(180)` at `0602315A`, returning to `0602315E`.
- The timer divides its argument by two and runs 90 guest-update/poll cycles. It already supports early acceptance through `06022B8C`; `06022A30` rejects simultaneous buttons. Held direction plus A/C therefore does not dismiss the box. This is not an unconditional fixed-duration lock.

The original-generated-function test observes 90 iterations with no input, 4 with a new sole confirm at iteration 4, and 90 with direction plus confirm. A complete normal-save headless baseline still shows the obtained-item box at VBlank 3900 after opening at 3401 and pressing direction plus A at 3497. Do not equate the argument with VBlanks or promise a particular wall-clock duration.

PC98 semantic confirm has a separate short-tap loss: `PressLatch` UP clears its held bit. The legacy stretcher receives native Saturn key bindings, not the separate semantic-confirm list. Semantic DOWN and UP in one event pump can vanish before the guest poll.

## Exact scope and input lifetime

`pal_prompt_confirm.py` is a pure stage of the keyboard transaction. It verifies the complete original `060220D0` function, then requires caller return `0602315E`, argument 180, mode 10, nonzero message count, and a focused foreground live SDL source outside host menus/editors. Headless, ordinary scripted input, other callers and other modes retain their original semantics. Only this wait's local acceptance result changes after the original update and poll; inventory, scripts, global timers, input conversion and RNG are untouched.

New physical confirmation edges belong to one wait. SDL event timestamps before or equal to entry are rejected. Existing held inputs are snapshotted without an edge. Duplicate DOWN, keyboard repeat and repeated above-threshold trigger samples cannot create a press. DOWN/UP in one pump survives for this wait. Semantic/native keyboard, player-one controller buttons, configured trigger thresholds and touch-button DOWN are covered. Multiple mappings of one physical source retain all A/C bits without another pending edge.

Scoped confirmation bits are kept out of newly published SMPC packets. Acceptance or timeout retires still-held confirmation via the host's release quarantine and forgets stretcher carry, preventing hold-skip of the next dialogue. Interruptions clear pending intent without ending the running wait. Physical release reconciliation handles missed UP while unfocused. Touch cancellation removes its own pending edge. Timed-out intent cannot carry into another message.

## Validation and limits

Portable policy/planner tests need no private assets. Additional tests explicitly skip without their inputs:

- `test_prompt_rom_runtime.py`: `PAL_PROMPT_RECOMP` points to a private original generated directory. Executes four original functions and the transformed wait with a deterministic update harness, not a full game.
- `test_prompt_sdl.py`: `PAL_PROMPT_SDL_PREFIX` points to an SDL3 SDK; `PAL_PROMPT_RUNTIME` contains matching `pal_tap_hold.h`. Executes production host-adapter text unchanged with real SDL events, a dummy window and virtual gamepad. Binding/layout containers are fixtures, not full-application acceptance.

The SDL test covers Return/Space short taps, native confirm, stale opening input, duplicate DOWN, touch, focus recovery, virtual-controller button/trigger hold and repress, and nonlive guards. Full-host syntax compilation separately checks actual runtime/SDK compatibility. Normal-save complete-application acceptance is recorded separately; do not substitute adapter tests for it.

## Build identity and final integration

Ordinary and accelerated manifests record `prompt_planner_sha256` and reject planner changes, including races during generation. Existing helper, complete runtime and function pins remain required. Windows fingerprints include the new planner. OHOS first delegates manifest verification, then checks its final host identity.

When merging another runtime patch, deterministically regenerate both ordinary and accelerated outputs from the verified patch chain. Keep rejection of unrecognized raw/intermediate inputs. Record each resulting `runtime/src/host/host.cpp` normalized-LF SHA256 together with its matching manifest output; those two reviewed final identities feed `OHOS_HOST_UI_SHA256`. Never bless a failing observed file or remove the gate. The prompt host stage follows keyboard translation and `guard_host`; later field guest injection does not alter host text. Audio raw/paired pins and final OHOS pins are different stages.

## Complete application SDL validation (2026-10-13)

The compiled generated game plus complete production host adapter was also run
with the normal Yangzhou pre-chest BUP copied privately. The test-only SDL event
injector used distinct finger IDs for direction and confirm; it did not alter
guest memory or game assets. A private A/B switch disabled only the new prompt
scope for the red comparison. Guest time was deterministic.

Opening touch at VB3421 and releasing at3427 showed the obtained-item prompt.
A same-pump Return DOWN/UP at VB3497 was missed by the original path, whose box
remained at VB3540. The corrected path accepted it at the next original poll,
VB3502 (5 VBlanks), executed the original give-item opcode once, and showed the
closed box at VB3540. A second corrected run held a direction with one finger
and tapped confirmation with another at VB3497; it also accepted at VB3502 and
executed the item grant once. Keeping the original opening finger held did not
dismiss the message. Source BUP hashes were unchanged in every case.

This validates a complete Linux SDL software-renderer application with injected
events. It remains distinct from a physical OpenHarmony device test.
