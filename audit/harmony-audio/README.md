# Host audio regression tests

These tests read the selected runtime directly. They never generate, copy over,
patch, or otherwise modify its sources. No OHOS SDK, HAP, display, or audio device
is opened. They are native regression tests, not an OHAudio playback certification.

## Requirements

- Python 3.9 or newer
- An existing C++17 GCC/Clang-compatible compiler (`--cxx` or `CXX`)
- Full host suite: an existing native SDL3 installation with
  `include/SDL3/SDL.h` and `lib` (or `lib64`)

The runner does not download or install anything. Linux GCC with SDL 3.4.18 is
verified. It uses GNU-style compiler/linker flags; MSVC is not supported by this
runner. Other native toolchain/platform combinations have not been validated.
Do not pass an OHOS cross-compiled SDL library to a native host test.

## Run

From any working directory, supply the actual prepared runtime and SDL prefix:

```sh
python path/to/tests/audio/run_audio_tests.py \
  --runtime path/to/prepared-runtime \
  --sdl-prefix path/to/native-sdl-install \
  --build-dir build/audio-tests
```

The runtime path must contain `src/host/host.cpp`, `settings.cpp`,
`pal_audio_queue_policy.h`, and `pal_audio_jitter_policy.h`. The host implementation
must include the corresponding lifecycle/diagnostic changes. The test includes
that exact `host.cpp` through `HOST_SOURCE`; it does not test a copied algorithm.

Environment equivalents are `PAL_RUNTIME`, `SDL3_PREFIX`, and `CXX`. Explicit
arguments override environment defaults. Paths with spaces are supported when
quoted normally by the shell.

Run only the pure helper test, without SDL:

```sh
python path/to/tests/audio/run_audio_tests.py \
  --runtime path/to/prepared-runtime --policy-only
```

UBSan is enabled by default. Use `--no-sanitizer` only if the selected native
toolchain does not provide it, and keep that limitation with the test result.
The runner exits nonzero on a compile failure, test failure, or detected input
source change. Logs, executables, and `results.json` go only to `--build-dir`
(default: `build/audio-tests` under the current working directory).

## Coverage and interpretation

Verified with the 0019 driver-identity fix: 31 pure-policy checks and 36 host
scenarios / 510 assertions pass with UBSan; selected source hashes are unchanged.
The policy-only environment-variable path and an output directory containing
spaces were also exercised. Missing runtime input fails before creating outputs.

- `test_audio_jitter_policy.cpp`: pure C++ checks for device/source unit conversion,
  reported-quantum headroom, warmup/cooldown, invalid inputs, finite padding budget,
  successful-Put-only growth, stale-epoch suppression, queue errors, and capacity.
- `test_audio_host_lifecycle.cpp`: includes the actual selected `host.cpp` and
  mocks device endpoints and uses both mock queues and one genuine device-free SDL
  stream. It covers the actual `OHAudio` registration name, case variants, null and
  unrelated drivers, unchanged generic-driver behavior,
  OHAudio source-empty without unconditional refill, PCM byte identity and frame
  accounting, API failures, capacity priority, an observer invoked on another
  thread, ten repeated menu-audio pause/resume boundaries, retained last-push
  endpoint, no repeated priming, persistent growth budget, and device-change
  requery. It calls the same audio boundary helpers used by the menu; it does not
  simulate menu drawing, touch input, or actual OHOS background behavior.
- Optional adaptation is disabled by default in production. Tests explicitly
  enable it for bounded-policy cases. The runner clears the adaptation environment
  hint so a developer's local setting cannot change the baseline cases.

An empty SDL input queue is not proof of hardware underrun. The observer's
additional-byte count estimates missing source data; it is not OHAudio's native
underflow counter. Passing these tests verifies the stated code contracts, not
that audible stutter is gone. Keep on-device cold-start/menu/background tests and
real PCM/wall-time diagnostics as a separate acceptance step.

The larger synthetic scheduling sweep, real SDL stream test, dummy-device A/B
runs, and rejected 200 ms lead experiment belong to the accompanying audit
evidence rather than this minimal repository suite.

The 2026-10-13 identity regression, old-host red test, real SDL PCM pull check,
and on-device acceptance checklist are documented in
[`HARMONY_AUDIO_DRIVER_IDENTITY.md`](../../docs/HARMONY_AUDIO_DRIVER_IDENTITY.md).
