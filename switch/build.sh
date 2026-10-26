#!/usr/bin/env bash
# Input must be the fully generated preview7 --pal-options build (recomp + runtime).
# See README.md. No copyrighted disc is downloaded or bundled by this script.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
: "${DEVKITPRO:?Set DEVKITPRO to the official devkitPro SDK root}"
: "${PAL_GENERATED:?Set PAL_GENERATED to the complete generated build directory}"
: "${SDL_SWITCH_SOURCE:?Set SDL_SWITCH_SOURCE to devkitPro/SDL switch-sdl-3.4 checkout}"
PIN=c329016c0e338ab4397ad930f83330c9fe058348
[[ $(git -C "$SDL_SWITCH_SOURCE" rev-parse HEAD) == "$PIN" ]] || { echo 'Wrong SDL3 revision'; exit 2; }
[[ -z $(git -C "$SDL_SWITCH_SOURCE" status --porcelain --untracked-files=no) ]] || { echo 'SDL3 tracked source is modified'; exit 2; }
[[ -f "$PAL_GENERATED/recomp/pal-options-manifest.json" ]] || { echo 'Missing PAL options generation manifest'; exit 2; }
[[ -f "$PAL_GENERATED/runtime/src/app/main.cpp" ]] || exit 2
export DEVKITA64="$DEVKITPRO/devkitA64"
BUILD=${PAL_SWITCH_BUILD:-"$ROOT/build/switch"}
mkdir -p "$BUILD"
# Fail rather than silently mix old generated sources with a fresh runtime.
[[ ! -e "$BUILD/recomp" && ! -e "$BUILD/runtime" ]] || { echo 'Choose a fresh PAL_SWITCH_BUILD directory'; exit 2; }
cp -a "$PAL_GENERATED/recomp" "$PAL_GENERATED/runtime" "$BUILD/"
cmake -S "$SDL_SWITCH_SOURCE" -B "$BUILD/sdl" -G Ninja \
 -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/Switch.cmake" \
 -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$DEVKITPRO/portlibs/switch" \
 -DSDL_STATIC=ON -DSDL_SHARED=OFF -DSDL_TESTS=OFF -DSDL_TEST_LIBRARY=OFF -DSDL_EXAMPLES=OFF
cmake --build "$BUILD/sdl" --parallel "${JOBS:-3}"
cmake --install "$BUILD/sdl"
cmake -S "$BUILD/recomp" -B "$BUILD/native" -G Ninja \
 -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/Switch.cmake" \
 -DCMAKE_BUILD_TYPE=Release -DSATURN_NO_SDL=OFF -DSATURN_VDP1_GPL=OFF \
 -DSATURN_EXTRA="$ROOT/switch/platform.cmake"
cmake --build "$BUILD/native" --parallel "${JOBS:-3}"
python3 "$ROOT/switch/verify_nro.py" "$BUILD/native/pal-saturn-recomp.nro"
