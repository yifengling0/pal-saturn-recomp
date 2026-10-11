# SDL3 Linux environment verification (2026-10-10)

## Result

An isolated SDL3 3.4.18 build works on the existing dot cloud Linux desktop.
The ROM-free probe displayed a real 800×480 X11 window with the OpenGL renderer,
animated a green rectangle, received Space and Escape keyboard events, and
exited with status 0 after presenting 416 frames in 7.814 seconds. The window
and graphics were also inspected through the native desktop screenshot tool.
This test did **not** use SDL's dummy or offscreen video drivers.

This establishes the SDL environment only. It does not establish that PAL,
its launcher, its game code, its assets, or its game audio work. No ROM or BIOS
was fetched or used by this probe.

## Remaining hardware/session limits

- ALSA lists its default playback endpoint but opening it fails because no card
  is present (`ALSA: Couldn't open audio device: No such file or directory`).
- An explicit second run with `SDL_AUDIO_DRIVER=pulseaudio` fails audio
  initialization (`Could not setup connection to PulseAudio`). That run still
  renders via X11/OpenGL and exits successfully after approximately two seconds.
- SDL reports zero gamepads. No physical controller was tested.
- Wayland was intentionally disabled for this X11-only environment build.
- No assumption is made about physical GPU acceleration or audible output.

The probe's zero exit code indicates graphics-loop completion. Audio and
controller availability must be read from the explicit log fields, not inferred
from the exit code.

## Reproduce the isolated build

From the project root on this Debian 13 x86-64 environment:

```sh
JOBS=2 tools/setup_sdl_linux.sh
```

This downloads development `.deb` packages from the machine's existing signed
Debian repositories into `build/sdl/debs`, extracts them into
`build/sdl/sysroot`, builds SDL from its official repository, and installs it to
`build/prefix`. It uses no sudo and installs no system packages. Package
maintainer scripts are not run. Existing runtime shared libraries satisfy the
local linker-name symlinks. The package list and archive hashes are saved in
`build/sdl/debian-packages.freeze.txt` and `build/sdl/debian-packages.sha256`.
The script was rerun successfully against the local cache.

Official SDL source:
https://github.com/libsdl-org/SDL/tree/release-3.4.18

Pinned commit: `829a65d769d935c4852f8159e964312c0957260a`

The installed CMake package is `build/prefix/lib/cmake/SDL3/SDL3Config.cmake`.
Pass the absolute `build/prefix` path as the project's `--sdl-prefix` argument,
or use it as `CMAKE_PREFIX_PATH` when configuring a separate SDL-enabled build.

## Reproduce the visible probe

Run from a terminal **inside the existing desktop session**:

```sh
build/sdl/sdl-probe 30 build/sdl/desktop-framebuffer.bmp
```

The shell executor and desktop session have separate display namespaces; the
shell has neither `DISPLAY` nor `WAYLAND_DISPLAY`. The native desktop terminal
has an active X11 display. The `/workspace/scratch/1afc2db30ae6` tree is shared,
while the shell's `/tmp` is not shared with the desktop. A short launcher script
placed in the shared scratch tree was entered through the native terminal's
normal keyboard API. No display sockets or credentials were copied, and no
session or security settings were changed.

## Evidence in this checkout

- `build/sdl/desktop-environment.log`: existing desktop display and shared tree
- `build/sdl/desktop-probe.log`: default audio attempt, graphics, keyboard, exit
- `build/sdl/desktop-pulse-probe.log`: explicit PulseAudio failure and graphics
- `build/sdl/desktop-framebuffer.bmp`: actual SDL-rendered frame, not a mockup;
  it contains only application pixels, not desktop decorations
- `build/sdl/configure.log`, `build.log`, `install.log`, `setup-recheck.log`
- `build/sdl/source.freeze.txt`, `debian-packages.freeze.txt`,
  `debian-packages.sha256`, `probe.sha256`
- `tools/sdl_probe.c`: standalone ROM-free probe source
