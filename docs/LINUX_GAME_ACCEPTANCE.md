# Linux PAL startup/playability checkpoint — 2026-10-10

## Result and scope

The Taiwan image now reaches an interactive inn room with correct background, portraits and dialogue. Real SDL keyboard input advances dialogue and moves the character with camera scrolling. Deterministic input crosses from scene 2 to scene 4 (inn corridor). The game's own menu saves to backup memory; a new process reads that save and restores the original character position. This is startup playability evidence, not a full-game completion or Windows certification.

The fix is one line in upstream SH-2 DMA, delivered as `patches/0005-sh2-dma-burst-count.patch`. Earlier black-background diagnoses incorrectly blamed RBG and mistook opening AVI frames for gameplay. See `DMA_BURST_FIX.md` for exact data-copy evidence and regression.

## Provenance

- User repository snapshot: `yifengling0/pal-saturn-recomp`, master `8a26a3f4727ed4a57ad41a6d3edf43303087aeb2`
- Local Git baseline is a synthetic commit of the downloaded archive; it is not the remote commit
- Runtime: `callumjenkins/saturn-recomp` pin `086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`, original four patches plus new 0005
- Clean parser checkout: `third_party/saturn-recomp`; patched runtime: `third_party/saturn-recomp-pal`
- Original four-patch runtime preserved separately; installer refuses mismatched/modified checkouts rather than overwriting them
- SDL3 official release 3.4.18, commit `829a65d769d935c4852f8159e964312c0957260a`
- Debian 13.6 x86_64, GCC14.2.0, Python3.12.14, CMake4.4.4, Ninja1.13.2
- Tested SDL executable: `build/linux-game-sdl/recomp-build/saturn`
- Executable SHA256: `f5aa1c835d82700ab802ce589ac242534d589de679c8db9753a84ab1aedbf030`

User-supplied image resource site: `http://workserver.gnway.cc:8099/`. Only image data was obtained, no server executable was run.

Private local data directory used in this workspace:
`/workspace/scratch/1afc2db30ae6/pal-saturn-resources-20261010/`

- `pal_t37401h_v1000_jt.bin`: 573,401,136 bytes; SHA256 `4c76366e3178289c3e73264d8f3a0b9b8b3d78f7baa0862561ce48ce4199d4b5`
- `pal_t37401h_13tr.cue`: SHA256 `27b0f9fd3a6198a7c8369004188775a75b914a13d28ecf44e6494ffc1e8e7b7d`
- Identity: T-37401H / V1.000 / 19981101 / JT
- The twelve audio-track starts independently match ISO WAV directory records. The alternative two-track CUE was preserved but not used
- Both hashes match historical evidence; input files remain unchanged. Disc/module/game executable data is excluded from the recovery source package

## Reproduce the build

Start in a fresh restored source checkout and follow `LINUX_CLOUD_BUILD.md` for validated module extraction:

```bash
bash tools/setup_linux.sh
bash tools/check_linux.sh
bash tools/setup_sdl_linux.sh
build/venv/bin/python tools/linuxbuild.py build --sdl-prefix "$PWD/build/prefix" --recompile
```

`--recompile` is intentional when changing generator inputs or patches. For an existing four-patch checkout, preserve it first and create a fresh five-patch checkout. Never alter the provenance marker to pretend a checkout is current. Windows users must apply 0005 to the runtime their Python installation actually imports and rebuild; copying the patch beside an existing executable does not change that executable.

From an actual graphical desktop terminal:

```bash
CUE=/absolute/path/to/pal_t37401h_13tr.cue
EXE="$PWD/build/linux-game-sdl/recomp-build/saturn"
"$EXE" --cue "$CUE" --save - --settings - --clock 1998-11-01T12:00:00 \
  --out build/window-new --vblanks 13200 \
  --input @tools/acceptance_inputs/scene-transition.txt \
  --shot 12000,12220,12460,13200 --record-input build/window-new/recorded.txt
```

The default SDL window is paced. `--realtime` has different clock semantics and is unnecessary. `--resume N` fast-forwards and then hands controllers back to live input; do not use it for a full scripted transition replay. `--interp` means video interpolation, not a CPU interpreter. `--save -` gives isolated transient backup memory; `--settings -` uses defaults. Default keyboard: arrows, Return=Start, Z=A, X=B, C=C, A=Saturn X/menu. The cloud shell and native desktop have distinct display environments; run windowed commands from the native desktop terminal instead of guessing DISPLAY.

## Verified behavior

1. **Same-frame repair:** `linux-run-001/shot-6100.png` was black except a small character. `linux-dma-fixed-001/shot-6100.png` now contains the room, furniture, portrait and text, SHA256 `920cfc9de4b0b987dc73a15b5d61f5c40991b61e82fc435f4820b59c65ed9e80`. Same image, RTC and input; 6,500 VBlanks, exit 0.
2. **Memory-copy mechanism:** corrected map source/destination both have 3,953 nonzero bytes and FNV `3AC122B5`; old destination had 1,379 and `520FBFDF`. Observation-only probe output matches normal patched screenshots exactly.
3. **Actual SDL dialogue:** `linux-window-004` shows the room in the native window and GUI keyboard Z/A advances the dialogue; PAL records `6279:A,6282:`. `pal-fixed-room-confirm-12s.mp4` is a real desktop recording.
4. **Actual SDL movement:** `linux-window-005` records real Left/Right, visible character motion and camera scrolling; exit 0 at20,000 VB. Cloud GUI Down events did not reach PAL's input recorder in that run, so no claim is made about those attempted events. The scripted Down path works.
5. **Quantified movement:** watch log `linux-movement-watch-001` ties real writes to `s16[06076928/2A]`. Start `(1344,288)`; RIGHT120VB → `(1472,352)`; DOWN120VB → `(1344,416)`. LEFT/UP subsequently change position. These net120VB displacements include collision: RIGHT actually changes coordinates eight times at3VB intervals and then stops at an obstacle. They must not be interpreted as a uniform speed measurement. Isometric cardinal inputs yield diagonal screen motion; no movement-speed or tick-rate modification was made.
6. **Scene transition:** `linux-stairs-001` at VB12184 writes requested/current scene4 (`060768E0/EE`), from initial scene2. VB12460 shows the inn corridor; VB13200 shows new dialogue there. VB12220 is the transition's black frame, not a hang. The same complete input was also replayed in the actual SDL window at normal default pacing (`linux-window-006`, no resume); its scene4 screenshot matches the headless same-frame SHA exactly and it exits0 at13,200 VB.
7. **Actual game save:** `linux-save-001` uses Saturn X/menu → fourth item → save. BUP logs `SDW_JPNV_00`, 25,600 bytes; scene2 and position `(1344,288)`.
8. **Cross-process load:** `linux-load-001` opens a copy of that new save, first moves to `(1472,352)`, then uses the actual menu “读取进度 → 本机进度”. Scene2 and `(1344,288)` are restored, with the room visible at VB13500. This is game backup memory, not a runtime state snapshot. Source and copied BUP SHA256 before/after: `9291c9526d1d2173594a24d6eb363e2b3972636769d20587700c1e74d32c116f`.

For save/load reproduction, use the corresponding input files under `tools/acceptance_inputs/`, `--vblanks13000` for save and13500 for load, with separate fresh `--out` directories. Use a new `--save /path/to/test.bup` for save; copy it to another new path for load. Never use a player's existing save for this test.

## Regression results

All post-fix `tools/check_linux.sh` stages passed:

- Upstream Python206; game validation26; local tooling17; PAL_DUMP parser28 checks
- Opcode775 functions / 9,300 vectors / zero failures
- Runtime44/44 and GPL renderer44/44
- Four-patch targeted core10 and hardware9 assertions
- DMA12 cases: byte/word/longword/burst modes, both channels, disabled/enabled DMAOR, full data, final addresses, TCR, TE and untouched tail bytes
- DMA red test before fix:64-byte request copied16 and falsely completed; all green after fix
- Fresh bundle restore and repeat installer identity checks passed

## Audio and remaining uncertainty

Post-fix Linux successful dummy-audio test completed6,500 VB in108.448 seconds, no STALL/FATAL, all11 PNGs +11 VDP dumps + WAV byte-identical to the headless patched baseline. It reported one underrun and4,470 dropped blocks at the250ms queue cap; this is not a physical sound-device quality test. The cloud native environment has no usable sound card; desktop videos are silent.

The user's Windows startup/audio freeze was not reproduced on Windows. A separate fault-injection experiment can produce a watchdog `SDL_GetAudioStreamQueued` stall by holding SDL's stream lock, but that is a diagnostic signature, not proof of the user's cause. No Windows package/executable or real Windows audio device has been validated here.

Later locations, combat, all dialogue/cache-sensitive paths, every graphics effect, full story completion, gamepad hardware and long-term save compatibility remain untested. Runtime warnings include unsupported RBG and line/vertical-cell scroll on some paths. The tested room does not establish their correctness. DMA interrupts and all exceptional DMA boundary cases remain outside this minimal fix. No source push, PR, release or public game-data distribution has occurred.
