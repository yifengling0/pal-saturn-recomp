# Harmony touch UI regression tests

These tests compile the supplied, patched runtime's real `host.cpp`, `settings.cpp`
and layout headers. There is no bundled or reconstructed host implementation.
They do not create an SDL window, run a game, open an audio device or connect to
OHOS hardware. The optional text suite uses a software renderer on an SDL surface
and the runtime's actual font code.

## Requirements

- Linux, Python 3 and a C++17 compiler (GCC or Clang with an ELF linker supporting
  `--gc-sections`). No Python packages are needed.
- A native SDL3 installation with `include/SDL3/SDL.h` and `lib/libSDL3.so`.
  Use the project's normal native SDL build prefix, not cross-compiled OHOS libraries.
- The runtime after the touch/editor/Chinese UI patch. These tests target raw
  host source before optional PC98 keyboard transformation. The physical bridge
  and audio have their own adjacent audit suites.

Run from any working directory; all input paths are explicit:

```sh
python3 audit/harmony-touch/run_tests.py \
  --runtime build/upstream/runtime \
  --sdl-prefix build/prefix \
  --build-dir build/audit-touch
```

The two positional arguments are equivalent:

```sh
python3 audit/harmony-touch/run_tests.py build/upstream/runtime build/prefix \
  --build-dir build/audit-touch
```

`--build-dir` is optional; by default a new directory is created using the system
temporary-directory API, and its location is printed. All executables, logs,
command records, tested-input hashes and disposable INI files stay there. The
runner never edits the runtime or test sources. Do not point a test-output
directory at real user settings; existing test-named files there are overwritten.
The runner rejects output anywhere inside the runtime or test-source tree.
When reusing a build directory, `tested-manifest.json` is marked running before
compilation, failed on compiler/test errors, and passed only after every requested
suite finishes; stale logs alone are not evidence of a passing current run.
Select another compiler with `--cxx clang++` or `CXX`.

## Four core C++ suites

- `geometry_tests.cpp`: 14,595 checks for phone/tablet and portrait/landscape
  layouts, density 1/2/3, size/spacing extremes, hit geometry, equal ABCXYZ sizes,
  aligned shoulders, minimum supported utility targets and simultaneous keys.
- `position_tests.cpp`: 27,272 checks for six normalized movable groups, complete
  bounding-box clamping, resizing and position conversion.
- `actual_host_tests.cpp`: 5,561 checks through the actual host menu/event paths:
  paginated settings reachability, 48-unit targets on the tested supported sizes,
  slider finger ID zero/multitouch, lower-edge minus, cancel/focus/resize cleanup,
  fit/stretch, independent menu recovery, quit confirmation, editing without
  guest input, Cancel/Done/Reset and persisted preferences. The UI draw calls and
  OS/game/audio side effects are stubbed here; actual font metrics are separate.
- `settings_tests.cpp`: 352 checks each for desktop and OHOS defaults, migration,
  validation, persistence, explicit old choices, and preservation of independent
  keyboard/gamepad/PC98 settings. Reset touch must not reset those sections or
  the picture mode.

Expected core total on the integrated UI revision: **48,132 checks**. These are
software assertions over synthetic dimensions, not a physical device test.

## Optional Chinese/English font bounds

`host_text_bounds_v3.cpp` is an optional fifth source. Pass the directory containing
the generated `inter_regular.h` and `inter_semibold.h` from the normal runtime
build's `saturn-fonts` output:

```sh
python3 audit/harmony-touch/run_tests.py \
  --runtime build/upstream/runtime --sdl-prefix build/prefix \
  --build-dir build/audit-touch \
  --fonts-dir build/recomp-build/saturn-fonts
```

This adds 4,396 Chinese and 4,397 English actual-font bounds checks across 168
menu geometry combinations and 45 editor dimension/density/size combinations
per language, including a finite positive-width requirement for every measurement
so font-initialization failures cannot pass as zero-width text. Without `--fonts-dir`, the runner explicitly reports this suite
as NOT RUN. It is not silently treated as passing.

No fonts are copied by this audit package. Inter headers come from the normal
build. The patched runtime already contains the renamed Noto subset, glyph list,
generation instructions and SIL Open Font License in `third_party/pal-menu-cjk`.
No original system TTC, binary, log, temporary settings or screenshot belongs in
this source directory.

## Limits

Passing does not establish a HAP/SDK build, correct ArkUI/native-view sizing,
real display density, system Back dispatch, actual gesture-safe insets, physical
controller behavior, audio quality or every possible screen size. Synthetic
render coordinates and zero/unverified OS insets cannot prove those conditions.
The production pipeline additionally verifies the 15 files changed by the UI
patch; this audit does not assert that every unrelated runtime file matches an
upstream checkout. Keep native/device checks separate from this result.
