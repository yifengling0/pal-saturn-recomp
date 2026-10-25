# Asset-free SCSP audio regression

Run from the PAL repository root after `tools/setup_linux.sh`:

```sh
build/venv/bin/python audit/scsp-audio/run.py --out build/scsp-audio
```

The runner builds the same test fixture against the clean pinned audio source
and the current patched runtime, requires the baseline to fail, requires the
candidate to pass, exercises the real state loader, checks twelve synthetic
M68K-to-PCM/WAV runs, and compares the optimized DSP against its full128-step
reference. `tools/check_linux.sh` runs it before the asset-free instruction/runtime checks.
Those synthetic instruction targets deliberately do not attach the PAL game layer;
real game builds still enforce the original disc and generated-hook identity gate.

`--baseline-runtime` and `--runtime` select explicit source directories. Tests
never download ROMs or bypass the game asset identity gate. Generated WAVs are
synthetic fixtures, not game recordings. `sound_pipeline` uses the real SH2-side
sound-RAM bridge, M68K, SCSP, batching and WAV writer, not actual guest SH2 code;
its host sink records bytes instead of using SDL/OHAudio or a physical device.
The DSP equivalence check is an optimization test, not a hardware oracle.

Optional sanitizer build (LSan is not tested in this environment):

```sh
cmake -S audit/scsp-audio -B build/scsp-sanitized -G Ninja -DSANITIZE=ON
cmake --build build/scsp-sanitized --parallel 2
ASAN_OPTIONS=detect_leaks=0 build/scsp-sanitized/scsp_regressions
ASAN_OPTIONS=detect_leaks=0 build/scsp-sanitized/state_loader build/scsp-state-fixtures
ASAN_OPTIONS=detect_leaks=0 build/scsp-sanitized/sound_pipeline build/scsp-synthetic-pcm 37 sdir-tl255
```

The imported upstream DSP regressions are covered by `UPSTREAM_LICENSE.txt`.

## Cross-compile scope

`ohos/CMakeLists.txt` is an optional production-object compilation fixture for
SDK/toolchain diagnostics without generated game code. It builds actual core,
SDL host, and OHOS audio bridge objects, but does **not** link a game, HAP, or
fake replacement modules. Full HAP validation uses `tools/ohosbuild.py` with
freshly generated, identity-verified real game sources instead.

The SCSP and state-loader fixtures also compile/link as Windows PE targets. The
complete `sound_pipeline` execution suite is Linux-only; a successful cross-link
is not Windows execution or device audio validation.
