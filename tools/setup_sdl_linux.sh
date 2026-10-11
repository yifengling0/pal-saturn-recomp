#!/usr/bin/env bash
# Build SDL3 under build/prefix without sudo or changing system packages/settings.
# Debian 13 runtime libraries are expected. Development .deb files are downloaded
# from the system's already-configured, signed Debian repositories and extracted
# into build/sdl/sysroot; no package maintainer scripts are executed.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
B="$ROOT/build/sdl"
PREFIX="$ROOT/build/prefix"
SDL_SRC="$ROOT/third_party/SDL"
SDL_TAG=release-3.4.18
SDL_COMMIT=829a65d769d935c4852f8159e964312c0957260a
JOBS=${JOBS:-2}
export PATH="$ROOT/build/venv/bin:$PATH"
command -v cmake >/dev/null
command -v ninja >/dev/null
command -v dpkg-deb >/dev/null
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer' >&2; exit 2; }
mkdir -p "$B/apt/lists/partial" "$B/debs" "$B/sysroot" "$PREFIX"
packages=(libx11-dev x11proto-dev libxext-dev libxcursor-dev libxi-dev
  libxfixes-dev libxrandr-dev libxrender-dev libxss-dev libxtst-dev
  libgl-dev libglx-dev libegl-dev libasound2-dev libpulse-dev
  libdbus-1-dev libxau-dev libxdmcp-dev libxcb1-dev)
missing=()
for package in "${packages[@]}"; do
  compgen -G "$B/debs/${package}_*.deb" >/dev/null || missing+=("$package")
done
if ((${#missing[@]})); then
  /usr/bin/apt-get -o "Dir::State::lists=$B/apt/lists" \
    -o "Dir::Cache=$B/apt/cache" -o APT::Get::List-Cleanup=0 update \
    2>&1 | tee "$B/apt-update.log"
  (cd "$B/debs" && /usr/bin/apt-get -o "Dir::State::lists=$B/apt/lists" \
    download "${missing[@]}") 2>&1 | tee "$B/download.log"
fi
for package in "$B/debs"/*.deb; do dpkg-deb -x "$package" "$B/sysroot"; done
for package in "$B/debs"/*.deb; do dpkg-deb -f "$package" Package Version; done > "$B/debian-packages.freeze.txt"
(cd "$B/debs" && sha256sum ./*.deb) > "$B/debian-packages.sha256"
# -dev packages contain linker-name symlinks; point missing sonames to the
# already installed runtime libraries. Only local sysroot links are changed.
python3 - "$B/sysroot/usr/lib/x86_64-linux-gnu" <<'PY'
from pathlib import Path
import sys
for link in Path(sys.argv[1]).iterdir():
    if link.is_symlink() and not link.exists():
        target = Path('/usr/lib/x86_64-linux-gnu') / link.readlink().name
        if target.exists():
            link.unlink()
            link.symlink_to(target)
PY
if [[ ! -d "$SDL_SRC/.git" ]]; then
  git clone --depth 1 --branch "$SDL_TAG" https://github.com/libsdl-org/SDL.git "$SDL_SRC"
fi
actual=$(git -C "$SDL_SRC" rev-parse HEAD)
[[ "$actual" == "$SDL_COMMIT" ]] || { echo "Unexpected SDL commit: $actual" >&2; exit 3; }
git -C "$SDL_SRC" diff --quiet --exit-code || { echo 'SDL source has local modifications; refusing to overwrite them.' >&2; exit 3; }
printf 'SDL tag=%s commit=%s\n' "$SDL_TAG" "$SDL_COMMIT" > "$B/source.freeze.txt"
export PKG_CONFIG_PATH="$B/sysroot/usr/lib/x86_64-linux-gnu/pkgconfig:$B/sysroot/usr/share/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$B/sysroot"
cmake -S "$SDL_SRC" -B "$B/cmake" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_PREFIX_PATH="$B/sysroot/usr" -DCMAKE_C_FLAGS="-I$B/sysroot/usr/include" \
  -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF \
  -DSDL_WAYLAND=OFF -DSDL_X11=ON -DSDL_ALSA=ON -DSDL_PULSEAUDIO=ON \
  2>&1 | tee "$B/configure.log"
cmake --build "$B/cmake" --parallel "$JOBS" 2>&1 | tee "$B/build.log"
cmake --install "$B/cmake" 2>&1 | tee "$B/install.log"
"${CC:-cc}" -std=c11 -O2 -Wall -Wextra "$ROOT/tools/sdl_probe.c" \
  -I"$PREFIX/include" -L"$PREFIX/lib" -Wl,-rpath,"$PREFIX/lib" \
  -lSDL3 -o "$B/sdl-probe"
printf '\nSDL prefix: %s\nProbe: %s/sdl-probe [seconds] [framebuffer.bmp]\n' "$PREFIX" "$B"
printf 'Run the probe from an existing desktop terminal. Do not guess DISPLAY or copy session credentials.\n'
