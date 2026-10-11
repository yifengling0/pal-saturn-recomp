#!/usr/bin/env python3
"""Compile read-only runtime audio tests; never generate or patch runtime files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, default=os.environ.get('PAL_RUNTIME'),
                        help='Runtime root containing src/host; or set PAL_RUNTIME')
    parser.add_argument('--sdl-prefix', type=Path, default=os.environ.get('SDL3_PREFIX'),
                        help='Installed native SDL3 prefix with include/SDL3 and lib; or set SDL3_PREFIX')
    parser.add_argument('--policy-only', action='store_true',
                        help='Run only the pure C++ helper checks; no SDL required')
    parser.add_argument('--cxx', default=os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++'),
                        help='Installed GCC/Clang-compatible C++ compiler executable')
    parser.add_argument('--build-dir', type=Path, default=Path.cwd() / 'build/audio-tests',
                        help='Only binaries/logs/results are written here')
    parser.add_argument('--no-sanitizer', action='store_true',
                        help='Omit UBSan when unavailable in the selected native toolchain')
    args = parser.parse_args()
    if args.runtime is None:
        parser.error('--runtime or PAL_RUNTIME is required')
    if not args.cxx or not shutil.which(args.cxx):
        parser.error('No existing C++ compiler found; supply --cxx (nothing will be installed)')
    runtime = args.runtime.expanduser().resolve()
    build = args.build_dir.expanduser().resolve()
    required = [runtime / 'src/host/pal_audio_jitter_policy.h',
                runtime / 'src/host/pal_audio_queue_policy.h']
    if not args.policy_only:
        required += [runtime / 'src/host/host.cpp', runtime / 'src/host/settings.cpp']
        if args.sdl_prefix is None:
            parser.error('--sdl-prefix or SDL3_PREFIX is required unless --policy-only is used')
        sdl = args.sdl_prefix.expanduser().resolve()
        required += [sdl / 'include/SDL3/SDL.h']
        libdir = sdl / 'lib'
        if not libdir.is_dir() and (sdl / 'lib64').is_dir():
            libdir = sdl / 'lib64'
        if not libdir.is_dir():
            parser.error('SDL prefix must contain a native lib or lib64 directory')
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        parser.error('Missing input files: ' + ', '.join(missing))
    build.mkdir(parents=True, exist_ok=True)
    inputs = [path for path in required if runtime in path.parents]
    before = {str(path.relative_to(runtime)): digest(path) for path in inputs}
    result = {'runtime': str(runtime), 'policy_only': args.policy_only,
              'sanitizer': None if args.no_sanitizer else 'undefined',
              'source_sha256_before': before, 'steps': [], 'passed': False,
              'scope': 'pure policy and actual host.cpp with mocked SDL audio endpoints; no device'}
    env = os.environ.copy()
    # A developer's optional adaptation setting must not change the baseline cases.
    env.pop('PAL_AUDIO_ADAPTIVE_LEAD', None)
    if not args.policy_only:
        env['PATH'] = str(sdl / 'bin') + os.pathsep + env.get('PATH', '')
        for name in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'):
            env[name] = str(libdir) + os.pathsep + env.get(name, '')

    def run(name: str, command: list[str]) -> None:
        completed = subprocess.run(command, cwd=build, env=env, capture_output=True, text=True)
        (build / (name + '.log')).write_text(completed.stdout + completed.stderr, encoding='utf-8')
        result['steps'].append({'name': name, 'command': command, 'exit_code': completed.returncode})
        if completed.returncode:
            raise RuntimeError(f'{name} failed ({completed.returncode}); see {build / (name + ".log")}')
        if name.endswith('-run'):
            print(completed.stdout.strip())

    compiler = [args.cxx, '-std=c++17', '-O2']
    if not args.no_sanitizer:
        compiler += ['-fsanitize=undefined', '-fno-sanitize-recover=undefined']
    suffix = '.exe' if os.name == 'nt' else ''
    try:
        binary = build / ('audio-jitter-policy-tests' + suffix)
        run('policy-build', compiler + ['-Wall', '-Wextra', '-Werror',
            '-I' + str(runtime / 'src/host'), str(HERE / 'test_audio_jitter_policy.cpp'), '-o', str(binary)])
        run('policy-run', [str(binary)])
        if not args.policy_only:
            host = runtime / 'src/host/host.cpp'
            # Forward slashes avoid C string escaping problems in HOST_SOURCE on Windows.
            flags = ['-ffunction-sections', '-fdata-sections', f'-DHOST_SOURCE="{host.as_posix()}"',
                     '-I' + str(runtime / 'include'), '-I' + str(sdl / 'include')]
            flags += ['-I' + str(runtime / 'src' / part) for part in ('host', 'machine', 'sound', 'video')]
            link = ['-Wl,-dead_strip' if sys.platform == 'darwin' else '-Wl,--gc-sections',
                    '-L' + str(libdir), '-lSDL3', '-pthread']
            if os.name != 'nt':
                link += ['-Wl,-rpath,' + str(libdir)]
            binary = build / ('audio-host-lifecycle-tests' + suffix)
            run('host-build', compiler + flags + [str(HERE / 'test_audio_host_lifecycle.cpp'),
                str(runtime / 'src/host/settings.cpp')] + link + ['-o', str(binary)])
            run('host-run', [str(binary)])
        result['passed'] = True
    except (OSError, RuntimeError) as error:
        result['error'] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        after = {str(path.relative_to(runtime)): digest(path) for path in inputs}
        result['source_sha256_after'] = after
        result['source_unchanged'] = before == after
        result['passed'] = result['passed'] and result['source_unchanged']
        (build / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(f'Source unchanged: {result["source_unchanged"]}; results: {build / "results.json"}')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
