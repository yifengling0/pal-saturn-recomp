#!/usr/bin/env bash
# Explicit PAL control profiles. All game arguments are forwarded unchanged.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 ]]; then
  echo 'usage: run_pal_profile.sh original|precise|experimental-fast [saturn arguments...]' >&2
  exit 2
fi
profile="$1"; shift
case "$profile" in
  original) input=0; align=0; wake=0 ;;
  precise) input=1; align=0; wake=0 ;;
  experimental-fast) input=1; align=1; wake=1 ;;
  *) echo "unknown control profile: $profile" >&2; exit 2 ;;
esac
exe="${PAL_RESPONSIVE_EXE:-$ROOT/build/linux-responsive-sdl-v4/recomp-build/saturn}"
if [[ ! -x "$exe" ]]; then
  echo 'Missing experimental executable. Build an isolated SDL experiment using tools/prepare_responsive_lab.py, then set PAL_RESPONSIVE_EXE to its saturn executable.' >&2
  exit 3
fi
if [[ "$profile" == experimental-fast ]]; then
  echo 'Experimental fast profile advances some field/NPC/script/RNG iterations; it is not original timing.' >&2
fi
export PAL_RESPONSIVE_INPUT="$input" PAL_RESPONSIVE_ALIGN="$align" PAL_RESPONSIVE_WAKE="$wake"
exec "$exe" "$@"
