"""Measure how the guest acknowledges a title-screen press: minimum hold and response lag.

The recorded boot-load script holds every press for 12 VBlanks. Re-running it with shorter holds
answers whether the message/menu code only notices the pad on its own poll, and dense shots after a
cursor move answer how many frames the game takes to show the result. Both use throwaway save
copies; the private checkpoint stays read-only.
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXE = ROOT / 'build/windows-pal-options/recomp-build/saturn.exe'
SOURCE_SAVE = ROOT / 'build/cp11/pal-private-checkpoints-v11/saves/hidden-dragon-exit-rescue-complete.bup'
OUT = ROOT / 'build/run/ack'
TITLE, MENU, VILLAGE = '9abeb31b0a367f03931d34556464bcd0bbcda3acfbc28868ddfee1bf67c60a18', \
    'e3c5907156f05e88cc155d355deb1c371ed19c4b3ce7f97cd73b7293118a7089', \
    '7f410a40b8ee582a9a9db9514d801ee03ad09f9f4cbc1ab25a1e53565598ff10'
PRESSES = [(1500, 'START'), (2500, 'DOWN'), (2600, 'START'), (2750, 'START'), (2900, 'START')]


def run(name, script, shots, vblanks=3401):
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'input.txt').write_text(script, encoding='utf-8')
    save = folder / 'wc.bup'
    save.write_bytes(SOURCE_SAVE.read_bytes())
    cmd = [str(EXE), '--cue', 'disc/pal_t37401h_13tr.cue', '--headless', '--vblanks', str(vblanks),
           '--save', str(save), '--settings', '-', '--clock', '1998-11-01T12:00:00',
           '--input', '@' + str(folder / 'input.txt'), '--shot', ','.join(map(str, shots)),
           '--out', str(folder)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        print(name, 'exit', result.returncode, result.stdout[-400:], result.stderr[-400:])
        return {}
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:8] for p in sorted(folder.glob('shot-*.png'))}


def held(hold):
    steps = []
    for vblank, button in PRESSES:
        steps.append(f'{vblank}:{button}')
        steps.append(f'{vblank + hold}:')
    return ','.join(steps)


def main():
    control = held(12)
    print('== minimum hold (control is the recorded 12 VBlanks) ==')
    for hold in (12, 8, 6, 4, 3, 2, 1):
        shots = run(f'hold{hold}', held(hold), [2000, 2700, 3401])
        ok = shots.get('shot-3401.png') == VILLAGE[:8]
        print(f'hold={hold:2d} title={shots.get("shot-2000.png")} menu={shots.get("shot-2700.png")} '
              f'end={shots.get("shot-3401.png")} full-path={"YES" if ok else "no"}')
    print('== response lag after the 2500:DOWN cursor move ==')
    shots = run('lag', control, list(range(2496, 2560, 2)) + [3401])
    seen = []
    for v in range(2496, 2560, 2):
        key = f'shot-{v}.png'
        if key in shots:
            seen.append((v, shots[key]))
    first = seen[0][1]
    for v, h in seen:
        if h != first:
            print(f'first picture change at VB{v} (press was published at VB2500, {v - 2500} frames after)')
            break
    else:
        print('no change seen in 2496..2558:', seen)
    print('end control:', shots.get('shot-3401.png'))


if __name__ == '__main__':
    sys.exit(main())
