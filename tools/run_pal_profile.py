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
    parser.add_argument('--data-cd-speed', choices=('1', '2', '4'), default='1', help='Multiplier of original 300-sector/s data delivery; CD-DA unchanged')
    parser.add_argument('--effect-animation-speed', choices=('1', '1.25', '1.5', '2'), default='1', help='Tested battle effect frame cadence; preparation remains a separate option')
    parser.add_argument('--paired-frames', action='store_true', help='Default-off completed RGB queue, requires precise profile')
    args = parser.parse_args(own)
    if args.paired_frames and args.profile != 'precise':
        parser.error('--paired-frames requires precise profile (without experimental timing wake/align)')
    exe = args.exe.resolve()
    if not exe.is_file():
        print(f'Missing executable: {exe}', file=sys.stderr)
        return 3
    required = (['input_v4'] if args.profile != 'original' else []) + (['effect_wait_v3'] if args.quick_spell else [])
    if args.data_cd_speed != '1':
        required.append('data_cd_speed')
    if args.effect_animation_speed != '1':
        required.append('effect_cadence_v4_manual_pair')
    if args.paired_frames:
        required.append('paired_frame_queue_v3')
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
    env['SATURN_DATA_CD_SPEED'] = args.data_cd_speed
    env['PAL_COMPLETED_FRAME_PREVIEW'] = '0'
    env['PAL_EFFECT_ANIMATION_SPEED'] = args.effect_animation_speed
    env['PAL_PAIRED_FRAME_QUEUE'] = '1' if args.paired_frames else '0'
    if args.profile == 'experimental-fast':
        print('Experimental fast input changes field/NPC/script/RNG opportunities.', file=sys.stderr)
    if args.quick_spell:
        print('Quick spell preparation changes battle tick/RNG opportunities; animation frames are retained in tested cases.', file=sys.stderr)
    if args.data_cd_speed != '1':
        print('Faster data delivery changes guest waiting/RNG timing; CD-DA and CPU clocks stay unchanged.', file=sys.stderr)
    if args.effect_animation_speed != '1':
        print('Faster tested battle effects retain decoded frames and logical ticks; random/idle timing may differ.', file=sys.stderr)
    print(f'PAL profile={args.profile} quick_spell={args.quick_spell} data_cd_speed={args.data_cd_speed} effect_animation_speed={args.effect_animation_speed} paired_frames={args.paired_frames} exe_sha256={sha256(exe)}', flush=True)
    try:
        return subprocess.run([str(exe), *forwarded], env=env).returncode
    except OSError as error:
        print(f'Unable to start PAL: {error}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
