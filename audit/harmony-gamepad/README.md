# Harmony physical controller host regression tests

These Linux tests compile the actual supplied runtime host and real shared SDL3. A small mocked Game Controller Kit service provides controlled OS callbacks through the genuine public API declarations. They do not emulate the OS and are not a HAP, SDK, Bluetooth, USB, or hardware acceptance test.

## Requirements

- Python 3.8+, C++17 compiler (tested GCC 14), POSIX threads and dynamic loader
- Shared SDL3 build/install (tested 3.4.18); virtual joysticks enabled
- Patched runtime containing `host_pump_input`, `host_shutdown_input` and startup enumeration; a generated PC98-profile runtime is also supported
- Production bridge sources under `harmony/pal-saturn-openharmony/entry/src/main/cpp`, or supplied via `--bridge-dir`
- Official Game Controller Kit public headers: default fixture is five upstream Apache-2.0 headers, not a full SDK. To test another set, pass `--sdk-headers` pointing to the parent of `GameControllerKit`.

From the repository root:

```sh
python3 audit/harmony-gamepad/run_tests.py \
  --runtime build/pal-keyboard-runtime \
  --sdl-prefix /path/to/SDL3-prefix
```

For a standalone adapter review, also pass `--bridge-dir /path/to/bridge/sources`. The output location is configurable with `--output`; the compiler is configurable with `--cxx` or `CXX`. Run against the raw patched runtime and the final keyboard-profile-generated runtime independently.

Sanitizers:

```sh
python3 audit/harmony-gamepad/run_tests.py \
  --runtime build/pal-keyboard-runtime \
  --sdl-prefix /path/to/SDL3-prefix \
  --sanitizers
```

`--no-leak-check` is only for environments where LeakSanitizer cannot run (for example, ptrace). A run using that option establishes ASan/UBSan results, not leak freedom.

## Coverage

- SDL gamepad initialization implies joystick initialization
- Preconnected enumeration even after ADDED events have been consumed; duplicate ADDED does not allocate extra player slots
- OS callback thread never mutates SDL until the host pump
- Buttons, digital and analog directions, triggers, existing configurable deadzone, clamping and non-finite input
- Trigger-button/trigger-axis and C/right-shoulder overlaps do not release another held source
- Startup connect/disconnect race, hotplug, reconnect, two independent players
- Focus loss, queued-input cancellation, neutral restore, background topology updates, menu BACK behavior
- Subscription/enumeration failure unwind, bounded queue overflow neutralization, in-flight shutdown and late callbacks
- Raw unmapped SDL joysticks remain unmapped and produce diagnostics
- Native SDL backend preference, simulated only by marking one real SDL virtual test device nonvirtual at the API boundary
- Missing runtime library, missing API symbol and explicitly disabled bridge

The bridge deliberately prefers an existing physical SDL gamepad backend over its virtual devices to avoid duplicates. Mixed native/bridge-only controller fleets are not supported by that conservative fallback policy. The current Harmony SDL configuration documents only dummy/virtual drivers.

SDL menu events preserve transitions processed during a pump. Gameplay still samples the final held state, like the existing native pad path; this change does not claim to fix guest-level very-short-press consumption.

## Device acceptance still required

Build with the user's actual DevEco/NDK and SDL source, then verify the startup logs, startup-connected and hotplug controllers, all controls, touch-auto visibility, background/foreground, menu return and disconnect while held. Expected diagnostics progress from `API 21 callbacks registered` to `attached SDL id` and then `first input reached SDL id`. API registration alone is not proof of a working controller.

No controller serial number, physical address or OS device ID is persisted or logged by the bridge. Diagnostic names and ephemeral SDL IDs are logged.
