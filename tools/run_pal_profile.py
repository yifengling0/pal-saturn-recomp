"""Portable PAL runtime profiles for an explicitly identified options build."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PROFILES = {'original': ('0', '0', '0'), 'precise': ('1', '0', '0'),
            'experimental-fast': ('1', '1', '1')}
MANIFEST = 'pal-options-build.json'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_options(exe, required):
    if not required:
        return
    path = exe.parent / MANIFEST
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'Missing or invalid {path}; rebuild with winbuild.py --pal-options') from error
    if data.get('schema') != 1 or data.get('exe_sha256') != sha256(exe):
        raise ValueError('PAL options manifest does not identify this executable; rebuild, do not copy a stale manifest')
    if not set(required).issubset(data.get('features', [])):
        raise ValueError('Executable does not contain the requested PAL options')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--' in argv:
        split = argv.index('--')
        own, forwarded = argv[:split], argv[split + 1:]
    else:
        own, forwarded = argv, []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=PROFILES)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--quick-spell', action='store_true')
    args = parser.parse_args(own)
    exe = args.exe.resolve()
    if not exe.is_file():
        print(f'Missing executable: {exe}', file=sys.stderr)
        return 3
    required = (['input_v4'] if args.profile != 'original' else []) + (['effect_wait_v3'] if args.quick_spell else [])
    try:
        verify_options(exe, required)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 3
    env = os.environ.copy()
    for key, value in zip(('PAL_RESPONSIVE_INPUT', 'PAL_RESPONSIVE_ALIGN', 'PAL_RESPONSIVE_WAKE'), PROFILES[args.profile]):
        env[key] = value
    env['PAL_SHORT_EFFECT_PREP'] = '1' if args.quick_spell else '0'
    # A profile is explicit: do not accidentally inherit an unrelated timing experiment.
    env['SATURN_DATA_CD_SPEED'] = '1'
    env['PAL_COMPLETED_FRAME_PREVIEW'] = '0'
    if args.profile == 'experimental-fast':
        print('Experimental fast input changes field/NPC/script/RNG opportunities.', file=sys.stderr)
    if args.quick_spell:
        print('Quick spell preparation changes battle tick/RNG opportunities; animation frames are retained in tested cases.', file=sys.stderr)
    print(f'PAL profile={args.profile} quick_spell={args.quick_spell} exe_sha256={sha256(exe)}', flush=True)
    try:
        return subprocess.run([str(exe), *forwarded], env=env).returncode
    except OSError as error:
        print(f'Unable to start PAL: {error}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
