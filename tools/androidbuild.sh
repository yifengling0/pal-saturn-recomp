#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
: "${ANDROID_SDK_ROOT:?set existing licensed Android SDK root}"
: "${JAVA_HOME:?set JDK 21 root}"
: "${PAL_SDL:?set SDL 3.4.18 source root}"
: "${PAL_GENERATED:=$ROOT/build/mobile-base}"
: "${GRADLE:=gradle}"
: "${JOBS:=4}"
NDK="$ANDROID_SDK_ROOT/ndk/28.2.13676358"
BUILD="$ROOT/build/android-arm64"
cmake -S "$ROOT/android/app/src/main/cpp" -B "$BUILD" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=26 -DANDROID_STL=c++_shared -DCMAKE_BUILD_TYPE=Release \
  -DPAL_ROOT="$ROOT" -DPAL_RECOMP="$PAL_GENERATED/recomp" -DPAL_RUNTIME="$PAL_GENERATED/runtime" -DPAL_SDL="$PAL_SDL"
cmake --build "$BUILD" --target saturn SDL3-shared -j "$JOBS"
mkdir -p "$BUILD/jniLibs/arm64-v8a"
cp "$BUILD/recomp/libmain.so" "$BUILD/sdl/libSDL3.so" "$BUILD/jniLibs/arm64-v8a/"
cp "$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$BUILD/jniLibs/arm64-v8a/"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" --strip-unneeded "$BUILD/jniLibs/arm64-v8a/"*.so
cd "$ROOT/android"
"$GRADLE" --no-daemon --gradle-user-home "$ROOT/build/gradle-home" \
  -PsdlJava="$PAL_SDL/android-project/app/src/main/java" -PnativeLibs="$BUILD/jniLibs" :app:assembleDebug
"$ANDROID_SDK_ROOT/build-tools/35.0.0/apksigner" verify --verbose app/build/outputs/apk/debug/app-debug.apk
sha256sum app/build/outputs/apk/debug/app-debug.apk
