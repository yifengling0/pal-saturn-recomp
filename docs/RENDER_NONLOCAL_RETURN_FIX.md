# Render helper one-frame return lowering

## Verified failure and cause

A normal Linux playthrough encountered Caiyi battle group 39, survived six rounds,
and exited with code 1 while stepping without keys toward the next round. The
runtime fatal was `returned to 060343B8, expected 0605E3A0`. This was a CPU return
check, not a controller timeout, forced shutdown, or party death.

The original PROG caller `0605E398` saves PR at `0605E39A`, then calls
`06060870` at `0605E39C`. On three rejection conditions, the helper branches to
`060608AA`, executes `lds.l @r15+,pr`, and returns at `060608AC` with `mov #0,r0`
in the delay slot. This intentionally consumes the caller's saved PR and returns
one level above it. The captured PC/PR `060343B8` and restored SP agree with that
path. The generated host caller previously demanded its local continuation
`0605E3A0`, treating a legal guest return as fatal.

This is distinct from the previously fixed default-callback discovery bug. No
callback seed, global return handler, IRQ handling, game script, HP, inventory,
ROM, or saved game needs modification.

## Bounded fix

`tools/pal_render_returns.py` runs after fresh generation, before optional input
or timing transforms, in both portable Windows and Linux drivers. It requires:

- PROG.BIN SHA-256 `808acfdb56a885a3949a8f3910705e077edb974d9985327e887acfba20afad6d`
- TRUE.BIN SHA-256 `41722e108b9091d6b7554a4350a0bf960a668da2879752708d6e5e820baa9d07`
- Base address `06020000` for each module
- Exact full-body hashes of five callers and three callees; only the generated
  coverage-array index is normalized

The five original instruction addresses are:

| Module | Caller | Call | Local continuation | Helper |
| --- | --- | --- | --- | --- |
| PROG | 0605E398 | 0605E39C | 0605E3A0 | 06060870 |
| PROG | 06065E26 | 06065E28 | 06065E2C | 06065DC8 |
| PROG | 06065E8C | 06065E8E | 06065E92 | 06065DC8 |
| TRUE | 06038F72 | 06038F74 | 06038F78 | 06038F14 |
| TRUE | 06038FD8 | 06038FDA | 06038FDE | 06038F14 |

The two other helpers use the same pop-PR idiom, with `add r2,r4` in the return
delay slot. Their call sites supply record advances of 20 or 28 bytes.

At each edge, host locals record the guest stack pointer, its saved PR, and r4.
All original guest instructions, delay slots, and polls execute unchanged. A
host-frame return is allowed only when PC and PR both equal the saved PR, SP
advanced by exactly four bytes, and the helper's rejection signature matches.
Otherwise the original strict `SH2_RET` still runs. The unwind check precedes
normal-PC handling, because the outer return address can equal the local one.
Nothing is written to guest registers or memory by this host guard.

The diagnostic `--probe-literals` generation has its own exact full-body pins.
These were generated with the pinned compiler's existing observation pass; no
arbitrary probe text is removed or ignored during verification.

`src/pal_game/pal_render_returns.cmake` independently pins the eight final bodies
in the actual linked `recomp` target. Stale, altered, or duplicate functions fail
configuration, including direct CMake and OHOS `--skip-learn` reuse. This is a
build guard, not evidence that an OHOS package has been built or run.

## Audit scope

Read-only scanning covered 1,011 generated PROG functions and 760 generated TRUE
functions. Of functions which pop PR without their own push, PROG had 25 and
TRUE had 20. Shared epilogues/tail dispatch were separated from explicit BSR/JSR
calls; the five edges above are the confirmed direct-call cases. This does not
prove coverage of undiscovered code or unresolved indirect targets.

## Tests and reproduction

Asset-free guard tests:

```
python -m pytest -q tools/tests/test_render_return_guards.py
```

The compiled test covers 63 cases across the five edges: normal and legal
cross-frame returns, caller/local-PC collision, wrong PC/PR/SP, invalid reject
signatures, wrong indirect target, 32-bit record-address wrap, baseline failures,
and guest-register/poll/delay-slot preservation.

Private full-generated-code and CMake checks:

```
PAL_RENDER_GENERATED=/path/to/original/recomp python -m pytest -q -s tools/tests/test_render_returns.py
```

These compile the five complete real callers and three real helpers twice,
before and after lowering. Five accepted paths produce identical guest registers
and memory; all seven helper rejection paths fail in the baseline and succeed in
the candidate, including caller/local-PC collision. The CMake test rejects old,
altered and duplicate generation and accepts the exact candidate. The same tests
also run against private literal-probe generation. No generated ROM-derived code
is checked into the repository.

The candidate Linux executable was rebuilt from a private copy of the proven
runtime and generation plus only the five lowering edits. Its SHA-256 is
`9c3b238bf03d2a52ecd5c3110e9d37c6c54c0142cafd130a2b6c377bff2e0b26`.
The source baseline matches remote `822e94623f4eccb56990b72b5d523103e6cf08dd`
across all 389 tracked blobs. A fresh official-driver build from an empty output directory generated all 2,284
functions and linked successfully; its executable has exactly the same SHA-256.
All generated C++/headers and all 114 runtime input files also match the candidate
byte-for-byte (only provenance/report metadata differ).

Final automated suite: 376 tests and 201 subtests passed; one optional upstream
settings-migration test was initially skipped because its explicit environment
variable was unset; that optional case was then enabled and passed in a separate
four-test keyboard-helper run. Independent review also ran the real-function harness under
AddressSanitizer/UndefinedBehaviorSanitizer successfully (LeakSanitizer disabled
for the execution environment's ptrace restriction).

## Normal-play acceptance (2026-10-13)

A separate SDL session loaded the preserved normal pre-battle save, replayed the
Caiyi battle through ordinary controls, and reached the previously failing
transition. After round six at VBlank 48041, a no-key 600-VBlank step completed
at 48641: battle-active changed from 65535 to 0, the party returned to garden
scene 109 at (704,1456), and Li/Yue recovered to 346/265 and 400/214 HP/MP.
Caiyi and Jinyuan departed normally; no CPU fatal occurred. Two Tianxian Yulu
items were stolen through normal battle commands. The session used the exact
candidate/clean-driver executable hash above. Evidence is retained privately as
session 042's runtime and controller logs.

This verifies the specific real-play regression, not full-game completion.
Windows and OHOS device playthroughs remain unverified by this Linux result.
The preserved pre-battle backup SHA-256 is
`49c25dfe7c0f60ce71269f9d148e0175913531befaf176d40b2d6ad2c3bd8335`.
No battle or script state is patched to reach that gate.
