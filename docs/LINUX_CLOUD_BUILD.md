# Linux cloud build preparation — 2026-10-10

## Source identity and boundaries

- User repository: `https://github.com/yifengling0/pal-saturn-recomp`, branch `master`, observed commit `8a26a3f4727ed4a57ad41a6d3edf43303087aeb2`.
- Materialized from GitHub's authenticated Download ZIP. The ZIP has no Git history; the local `work/linux-verify-20261010` branch has a synthetic baseline, NOT the remote commit identity. The original ZIP is preserved beside this checkout.
- Runtime source cloned with Git and checked out at `086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`. No ROM, BIOS, MDF, CUE or commercial game modules were downloaded or supplied for this validation.
- This report is separate from historical Windows evidence. No game boot, graphics fix, movement fix or HarmonyOS validation is claimed.

## Current verified results

- Debian 13.6 x86_64; GCC/G++ 14.2.0; Python 3.12.14.
- Isolated `build/venv`: CMake 4.4.4, Ninja 1.13.2, pytest 9.1.1, hatchling 1.32.4. Exact installed Python dependency versions are in `tools/requirements-linux.txt`.
- Original validation wrapper: **26 passed**, actual log `logs/wrapper-tests.log` in delivery.
- New Linux preparation/driver tests: **12 passed** (external runtime mocked for driver tests). Covers spaces, repeated setup, dirty parser rejection, wrong pin, partial-patch cleanup, changed patch rejection, preserving user changes, parent-repository identity rejection, and failing pipelines.
- PAL_DUMP parser: **28 C++ assertions passed**, compiled with `g++ -std=c++20 -Wall -Wextra -Werror`.
- Shell syntax checks and Python byte-compilation of Linux helpers passed.
- Runtime execution authorized on 2026-10-10 14:15 UTC. Actual upstream Python tests: **206 passed**.
- Actual generated/native SH-2 selftest: **775 functions, 9300 vectors, 0 failures**.
- Actual headless runtime tests: **44 passed**; GPL VDP1 variant: **44 passed**.
- Four-patch focused regressions: core tests **10 assertions** (same-base overlay swap, call/return, aliases, fallback, mirrored stores), hardware tests **9 assertions** (single-file mixed audio/data, MMIO register read/write watch). The core regression correctly fails against unpatched runtime, exit 134.
- `linuxbuild.py check` executed successfully against the installed patched runtime using GCC C++20. The no-game generated `saturn` executable also linked the game's diagnostic hook.
- Synthetic disc and real game runs are tracked separately; no PAL game pass has been established at this checkpoint.

## Fixes made locally

1. `PAL_DUMP=r14:24` previously failed because only two-character names r0..r9 were recognized. Invalid register text could yield an out-of-range index. The shared strict parser now accepts only r0..r15 or a complete 32-bit hex address; standalone tests cover valid/invalid inputs.
2. README's `git am` is incorrect for the four raw diff patches and its `git -C` relative patch paths were wrong. Linux setup uses absolute paths and `git apply --check` plus `git apply`, preparing in a temporary checkout before publishing it.
3. Keep `third_party/saturn-recomp` clean at the pin for `pal_validate` identity checks. Build from separate `third_party/saturn-recomp-pal`; a manifest binds the pin, patch inputs and resulting Git diff. Repeated setup verifies rather than overwrites changed work.
4. `check_linux.sh` uses native Linux executables, no Windows include or static-link workaround, separate directories, two build jobs by default and fail-fast pipe handling. It never labels pytest failures as harmless.
5. `linuxbuild.py` preserves the historical game module addresses/hooks/seeds while replacing Windows host paths in memory. Uses a separate headless Linux build and GCC; never edits historical game.toml or calls a Windows-only prerequisites path. Missing module files stop with `blocked-input`.

## Reproduction

From repository root, with Python 3.11+, Git and a C++20 GCC installed:

```bash
bash tools/setup_linux.sh
bash tools/check_linux.sh
build/venv/bin/python tools/linuxbuild.py check
```

The first editable install exposed a missing dynamic Hatchling dependency, `editables`; fixed by pinning `editables==0.6` explicitly, then reran successfully.

Setup installs only into `build/venv`; it neither changes system security settings nor installs anything with elevated privileges. `check_linux.sh` includes the game's diagnostic C++ source in its generated no-game-data binary, so both the hook compilation and runtime can be checked without game modules. Logs go to `build/linux-check/logs`. Default builds are headless: no SDL window, controller-device or audio-device validation is implied. The optional GPL VDP1 test changes the resulting binary's licensing conditions; no release/distribution is performed.

## Ready-for-image entry (NOT YET RUN)

Provide the complete original Taiwan-version dump. Preserve MDF/MDS originals if supplied; converting them is a separate verified step. Prefer CUE plus every referenced BIN/audio file. Do not merely remove unsupported explicit PREGAP/POSTGAP statements. Inputs and existing saves must be kept read-only; use a new output folder outside the image directory.

```bash
cd validation
../build/venv/bin/python -m pal_validate prepare \
  --image /absolute/path/to/disc/game.cue \
  --toolchain ../third_party/saturn-recomp --run-upstream \
  --provenance-note 'User-provided Taiwan disc; confirm original or patched' \
  --out ../build/input-001
```

Check `report.json`, disc product/version/areas and hashes against the repository's historic Taiwan T-37401H evidence before reusing module addresses or seeds. Extraction output is under the reported extraction directory: intentionally copy only verified module files `0`, `PROG.BIN`, `TRUE.BIN` into `build/disc-extract/` after checking the actual names and version. Then:

```bash
build/venv/bin/python tools/linuxbuild.py build --recompile
build/linux-game/recomp-build/saturn --cue /absolute/path/to/disc/game.cue \
  --headless --save - --vblanks 1500 --out build/linux-run-001
```

Missing image, mismatched version, unknown call targets, fatal logs or incomplete coverage are blockers, not passes. `--interp` means video interpolation, not a SH-2 interpreter. Cache-sensitive dialogue, overlays, scene input, movement and repeated clean-save runs still need real-image evidence.

## Historical evidence requiring re-check

`docs/P1_RECOMP_REPORT.md` §4.14 says `0x4300 & 0x30 = 0x30`; the correct result is **0**. The same section cites a log with `0013`. These values must be reconciled against correctly decoded same-frame dumps before concluding the observed black screen is caused by RBG. Source inspection confirms incomplete RBG implementation, but that alone does not establish the game's root cause. Historical text has been retained; no speculative RBG implementation was added.

The original 44 runtime tests have no compiled game modules and do not by themselves validate patch 0003's overlay call/return behavior. The new dedicated core regression supplies two synthetic modules at the same address and validates the intended direct-call path, including its return; real-image runs remain necessary. A historical `learn` command exit status alone must not be treated as game-boot success: the existing driver can return zero despite runtime fatal output.

## 2026-10-10 real-image and SDL checkpoint

The ready-for-image procedure above has now been executed against the user-supplied Taiwan T-37401H V1.000 (19981101, JT) image. BIN SHA256 is `4c76366e3178289c3e73264d8f3a0b9b8b3d78f7baa0862561ce48ce4199d4b5`; the preserved 13-track CUE SHA256 is `27b0f9fd3a6198a7c8369004188775a75b914a13d28ecf44e6494ffc1e8e7b7d`. Both match historical repository evidence. Its audio track positions independently match the twelve ISO WAV records. The alternative two-track CUE was retained but not used. Image bytes remain unchanged after tests.

`build/real-input-001` contains input validation and extraction evidence. Only three verified modules were copied into `build/disc-extract`. The SDL build generated 2,283 functions / 209,370 instructions. `tools/run_pal_smoke.py` records the complete command, fixed RTC, input script, before/after image hashes, screenshots, dumps and true exit status; reaching its frame limit does not assert playability.

SDL3 release 3.4.18 was built into `build/prefix`. Use `tools/setup_sdl_linux.sh`, then `build/venv/bin/python tools/linuxbuild.py build --sdl-prefix "$PWD/build/prefix" --recompile`. The cloud native desktop successfully displayed the actual PAL window through X11/OpenGL. The shell display environment differs from the native terminal. Actual-window runs are `build/linux-window-002` (opening movie) and `003` (post-movie failure and recorded direction keys). PAL's own input recorder captured `6546:RIGHT,6666:,6684:DOWN`; this establishes input reception, not full movement correctness. There is no working physical cloud sound card. Videos are silent desktop recordings. The second video excludes the explicit `--resume 5900` fast-forward and contains the following normal-paced interval.

### Current failure and corrected interpretation

The visible outdoor/cave scenes at VB2700/4500 are **opening A3.AVI video frames decoded by TRUE**, not interactive maps. ISO extent and actual CD reads independently confirm this. Once PROG resumes, the background is black with a small character and later some door elements; normal gameplay remains unresolved.

The correctly decoded BE register dump has BGON `0x0043`, with rotation enable mask `0x30` clear. CHCTLA `0x1212` selects 8bpp NBG bitmaps. At VB6100 both selected bitmap source regions are zero. VDP1 contains 330 scaled-sprite commands reusing a black palette-254 tile plus a character sprite; the large nonzero framebuffer byte count is largely black pixels. This evidence does not justify treating the missing RBG implementation as the cause.

An observation-only folded-literal probe (`--probe-literals`) inserts checks at 18,910 static positions, preserves original assignments and reads raw Work RAM without MMIO/poll side effects. Along this 6,500-VBlank path, no mismatch was observed and sampled PNGs match baseline byte-for-byte. This does not assert every instrumented position executed. CCR writes observed in the diagnostic window were `0x11`. Resource-loading investigation is ongoing; complete CD-read traces currently show no ABC.J, FFF.J or MAPIC.JOE reads on this path.

No game image, extracted commercial module or generated game code belongs in a recovery source package or Git commit. No publication or push has occurred.
