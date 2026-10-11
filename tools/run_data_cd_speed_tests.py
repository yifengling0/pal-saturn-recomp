"""Build/run real CD-block synthetic tests in a fresh copy; no disc or game data.

Repository placement:
  tools/run_data_cd_speed_tests.py
  tools/pal_data_cd_speed.py
  tools/tests/data_cd_speed_test.cpp

Example (Windows/Linux; choose an unused --out):
  python tools/run_data_cd_speed_tests.py --runtime third_party/saturn-recomp-pal/runtime --out build/data-cd-synthetic-001
CXX / --cxx is one compiler executable or full path, not shell code.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from pal_data_cd_speed import apply_data_cd_speed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cxx', default=os.environ.get('CXX', 'g++' if os.name == 'nt' else 'c++'))
    parser.add_argument('--test-source', type=Path, default=Path(__file__).resolve().parent / 'tests/data_cd_speed_test.cpp')
    args = parser.parse_args()
    source = args.test_source.resolve(strict=True)
    runtime = args.runtime.resolve(strict=True)
    out = args.out.resolve()
    if out.exists():
        parser.error('--out must be a fresh directory; existing results are never overwritten')
    if out == runtime or runtime in out.parents or out in runtime.parents:
        parser.error('--out must not overlap the source runtime')
    out.mkdir(parents=True)
    private = out / 'runtime'
    shutil.copytree(runtime, private)
    identity = apply_data_cd_speed(private)
    exe = out / ('data_cd_speed_test.exe' if os.name == 'nt' else 'data_cd_speed_test')
    cdblock = (private / 'src/machine/cdblock.cpp').as_posix()
    command = [args.cxx, '-std=c++20', '-O2', '-Wall', '-Wextra',
               '-I' + str(private / 'include'),
               '-DSATURN_CD_BLOCK_SOURCE=' + json.dumps(cdblock),
               str(source), '-o', str(exe)]
    # Avoid Git for Windows' unrelated libstdc++ DLL shadowing the compiler's DLL.
    if os.name == 'nt':
        command.append('-static')
    report = {'compile_command': command, 'run_command': [str(exe)],
              'source_runtime': str(runtime), 'private_runtime': str(private),
              'transform': identity, 'game_or_disc_data_used': False,
              'test_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    with (out / 'compile.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    report['compile_exit'] = result.returncode
    if result.returncode == 0:
        with (out / 'test.log').open('w') as log:
            result = subprocess.run([str(exe)], stdout=log, stderr=subprocess.STDOUT, check=False)
        report['test_exit'] = result.returncode
    report['passed'] = report.get('compile_exit') == 0 and report.get('test_exit') == 0
    (out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
