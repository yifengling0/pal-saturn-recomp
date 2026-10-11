#!/usr/bin/env bash
# Run only after authorizing the pinned external runtime and its tests.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PIN=086c372c67d9e0f94fcc64cedd6e6b63cc5542b5
CLEAN=$ROOT/third_party/saturn-recomp
PATCHED=$ROOT/third_party/saturn-recomp-pal
mkdir -p third_party build
if [[ ! -d "$CLEAN/.git" ]]; then
  git clone https://github.com/callumjenkins/saturn-recomp "$CLEAN"
  git -C "$CLEAN" checkout "$PIN"
fi
[[ $(git -C "$CLEAN" rev-parse HEAD) == "$PIN" ]]
[[ -z $(git -C "$CLEAN" status --porcelain --untracked-files=no) ]]
python3 tools/prepare_linux_runtime.py
# Leave local runtime modifications as an auditable patch diff, not a false upstream identity.
[[ -x build/venv/bin/python ]] || python3 -m venv build/venv
build/venv/bin/python -m pip install -r tools/requirements-linux.txt
build/venv/bin/python -m pip install --no-build-isolation -e "$PATCHED"
build/venv/bin/python -m pip freeze > build/dependencies.freeze.txt
printf 'Ready: clean parser %s; patched build %s\n' "$CLEAN" "$PATCHED"
