# Android / Switch build validation — 2026-10-26

## Shared baseline

- PAL source: `d7d9306c7e7063dd136f468a0ba55a8aeb011573` (preview.7).
- Clean runtime/recompiler: `086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`.
- Existing reviewed PAL patch set is applied by `tools/setup_linux.sh`.
- Full PAL options generation: `tools/winbuild.py build --pal-options --headless --build-dir build/mobile-base --jobs 4` (the historical driver name also supports Linux).
- Private, user-provided original disc was hash-verified before extraction. No disc, saves or extracted/generated original-game source belongs in the source recovery patch.

## Baseline checks actually completed

`PATH="$PWD/build/venv/bin:$PATH" build/venv/bin/python -m pytest tools/tests -q`

Result: **414 passed, 7 skipped, 201 subtests passed**. This includes tests conditional on the generated runtime now being available. An earlier pre-generation pass is not the final test count.

The generated Linux headless executable linked successfully and ran the actual private disc for 6,000 VBlanks, exiting normally at the requested limit:

- 5,439 VDP1 frame changes / draws;
- 4,414,251 audio samples, 3,067,888 non-silent;
- original disc header `T-37401H V1.000`, areas `JT`;
- cold movie sound-cache callback observed.

This is shared-core/data-flow evidence only. It does **not** establish physical audio quality, Android device behavior, Switch hardware performance, or complete-game compatibility.

## Distribution boundaries

Only new platform adapters and build instructions are included in the source patch. The application binaries contain statically recompiled original-game logic as well as runtime code; they must not be described as entirely MIT-licensed or as containing no derivative game code. Original resource images remain user supplied and are never packaged.

Android uses a locally debug-signed, sideloadable APK unless explicitly stated otherwise. Switch targets an open-source homebrew NRO, not a Nintendo retail package or proprietary SDK build. No hardware security modification instructions are included.

## Final platform artifacts

- Android: `pal-saturn-preview7-android.1-arm64-debug.apk`, 14,369,955 bytes, SHA256 `98e6ebe7acb530c65bb49fde703b3bc667bf292ae0cd4139dc4c88a1a3e88b99`.
  - `org.palsaturn.android`, versionCode 8, versionName `0.1.0-preview.7-android.1`, minSdk 26 / targetSdk 35.
  - Android debug v2 signature verified; zipalign 16KiB validation passes; `libmain.so`, `libSDL3.so`, `libc++_shared.so` are AArch64 with 0x4000 LOAD alignment.
  - Native SDL_main / real SDL host links successfully; no raw disc, resource tracks or save data packaged.
  - 21 pure-Java import cases passed and the actual 573MB private original disc passed the production import entry. Exact 13-track TOC and total 243,793 sectors are checked, including sector-aligned truncation; this is not a whole-disc content hash check.
  - Private atomic generations and cross-process locks protect old resources and saves during failure, cancellation or gameplay. Back-key to SDL AC_BACK to host-menu chain was checked in source; not a physical-phone test.
- Switch ZIP: `pal-saturn-recomp-preview7-switch-homebrew.zip`, 5,292,619 bytes, SHA256 `bfcf7ff3d83d5a9fd35c29945eab929053c50cb07c384845015c180cbf627b60`.
  - NRO: 13,482,181 bytes; SHA256 `69b7d64ccf7f68d9746311beb8e3b13d0d160186b82670d1e3c573dd3bc25dfe`.
  - A fresh tracked build script cross-compiles actual devkitPro SDL3.4.0/libnx video, audio and joystick backends. NRO0 segments/NACP and AArch64 ELF verified; no resource ROMFS.
  - Single-BIN and 13-file layout tests, exact TOC/length and aligned-truncation rejection passed. The actual unchanged runtime cdrom.cpp opened the normalized CUE, read sector 150, resolved the CD-DA boundary and located PROG.BIN.
  - No Switch hardware test was available.

The source change is additive (`android/`, `switch/`, `tools/androidbuild.sh` and this document). Existing Windows/Linux/OHOS core files are unchanged. Builds do not silently fall back to a headless host. Source recovery excludes toolchains, debug keystore, original discs, saves and generated game C++.

See `android/README.zh-CN.md` and `switch/README.md` for exact import paths, resource-layout limitations, source pins, licenses and reproducible build commands. SDK acceptance was explicitly authorized for this task; scripts do not auto-accept future legal terms.
