#!/usr/bin/env bash
# Windows equivalent of upstream tools/check.sh: every check that needs no game data.
# Upstream's script calls `uv run`; this host has no uv, so the project venv's python is used.
# Requires Git Bash plus cmake, ninja and a C++20 compiler on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."
RT=third_party/saturn-recomp-pal
PY=${PY:-build/venv/Scripts/python.exe}
CXX=${CXX:-g++}
B=build/check
# Git for Windows ships /mingw64/bin/libstdc++-6.dll, which shadows the toolchain that built the
# exe and fails it at load with 0xC0000139; -static keeps the runtime libraries inside the exe.
CMAKE=(-G Ninja -DCMAKE_CXX_COMPILER="$CXX" -DSATURN_NO_SDL=ON -DCMAKE_CXX_FLAGS=-static -DCMAKE_EXE_LINKER_FLAGS=-static)

echo "== Python tests (upstream, pinned $RT)"
# Fail on every failure. Some upstream harness tests may need Windows fixes;
# their failure must remain visible rather than being reported as a green run.
"$PY" tools/prepare_linux_runtime.py
"$PY" -m pytest "$RT/tests" -q
"$PY" -m unittest discover -s validation/tests
"$PY" -m pytest tools/tests -q

echo "== instruction self-test: generate SH-2 program and vectors"
"$PY" -m saturnrecomp.recomp --out "$B/optest" --optest
cmake -S "$B/optest" -B "$B/optest-build" "${CMAKE[@]}"
ninja -C "$B/optest-build" selftest saturn
"$B/optest-build/selftest.exe" "$B/optest/selftest/optest.txt"

echo "== runtime unit tests"
# bup_test.cpp points the save directory at a scratch folder with POSIX setenv, which MinGW has no
# equivalent of; tools/wincompat.h supplies it, plus %APPDATA% for the branch Windows takes.
# The path must be Windows-shaped (pwd -W): a /c/... path reaches g++ unconverted and it fails to open it.
WININC=$(pwd -W)/tools/wincompat.h
TESTCMAKE=(-G Ninja -DCMAKE_CXX_COMPILER="$CXX" -DSATURN_NO_SDL=ON -DCMAKE_EXE_LINKER_FLAGS=-static
           "-DCMAKE_CXX_FLAGS=-static -include $WININC")
cmake -S "$RT/runtime/tests" -B "$B/runtime-tests" "${TESTCMAKE[@]}"
ninja -C "$B/runtime-tests"
"$B/runtime-tests/runtime_tests.exe"

echo "== runtime unit tests, VDP1 by Mednafen's rules (SATURN_VDP1_GPL)"
cmake -S "$RT/runtime/tests" -B "$B/runtime-tests-gpl" "${TESTCMAKE[@]}" -DSATURN_VDP1_GPL=ON
ninja -C "$B/runtime-tests-gpl"
"$B/runtime-tests-gpl/runtime_tests.exe"
