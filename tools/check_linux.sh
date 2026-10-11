#!/usr/bin/env bash
# No commercial assets. Fail on ANY failed stage; logs kept separately from historical evidence.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PY=$ROOT/build/venv/bin/python
export PATH="$ROOT/build/venv/bin:$PATH"
export PYTHONPATH="$ROOT/validation${PYTHONPATH:+:$PYTHONPATH}"
RT=$ROOT/third_party/saturn-recomp-pal
B=$ROOT/build/linux-check
JOBS=${JOBS:-2}
CXX=${CXX:-g++}
mkdir -p "$B/logs"
run() { local name=$1; shift; printf '\n== %s\n' "$name"; "$@" 2>&1 | tee "$B/logs/$name.log"; }
CMAKE=(-G Ninja "-DCMAKE_CXX_COMPILER=$CXX" -DSATURN_NO_SDL=ON)
run local-tool-tests "$PY" -m unittest discover -s tools/tests -v
run dump-parser-build "$CXX" -std=c++20 -Wall -Wextra -Werror tools/test_pal_dump_parse.cpp -o "$B/test-pal-dump"
run dump-parser "$B/test-pal-dump"
run wrapper-tests "$PY" -m unittest discover -s validation/tests -v
run python-tests "$PY" -m pytest "$RT/tests" -q
run optest-generate "$PY" -m saturnrecomp.recomp --out "$B/optest" --optest
run optest-configure cmake -S "$B/optest" -B "$B/optest-build" "${CMAKE[@]}" "-DSATURN_EXTRA=$ROOT/src/pal_game/pal_game.cmake"
run optest-build cmake --build "$B/optest-build" --parallel "$JOBS" --target selftest saturn
run optest "$B/optest-build/selftest" "$B/optest/selftest/optest.txt"
for variant in runtime runtime-gpl; do
  extra=(); [[ $variant != runtime-gpl ]] || extra=(-DSATURN_VDP1_GPL=ON)
  run "$variant-configure" cmake -S "$RT/runtime/tests" -B "$B/$variant" "${CMAKE[@]}" "${extra[@]}"
  run "$variant-build" cmake --build "$B/$variant" --parallel "$JOBS"
  run "$variant-tests" "$B/$variant/runtime_tests"
done
run patch-configure cmake -S tools/patch_tests -B "$B/patch-tests" "${CMAKE[@]}"
run patch-build cmake --build "$B/patch-tests" --parallel "$JOBS"
run patch-core "$B/patch-tests/patch_core"
run patch-dma "$B/patch-tests/patch_dma"
run patch-hardware "$B/patch-tests/patch_hardware" "$B/patch-tests/fixtures"
printf '\nAll invoked checks passed. This does not establish PAL game boot.\n'
