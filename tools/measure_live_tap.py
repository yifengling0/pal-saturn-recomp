"""Drive the live input path with SDL virtual gamepads to see what a tap shorter than a frame does.

--input writes straight into the pads the SMPC reads, so it cannot show how a press reaches the game
through the host. --virtual-input presses SDL virtual gamepads instead, and those go through
events() -> read_pads() -> the VBlank latch, the same chain a finger or a key takes. The same five
presses as the recorded boot-load script, held for fewer samples each, say when the guest stops
noticing them; the run is graded on the known load-regression frame hashes.

Only read this on an otherwise idle machine. The window has to be visible and the host has to run one
VBlank per frame: with anything else competing for the machine, several VBlanks share one poll and
even a 12-VBlank press disappears between two polls -- --record-input then shows a run that pressed
nothing, which says nothing about the game. tools/tests/test_tap_hold.py is the deterministic test.
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXE = ROOT / 'build/windows-pal-options/recomp-build/saturn.exe'
SOURCE_SAVE = ROOT / 'build/cp11/pal-private-checkpoints-v11/saves/hidden-dragon-exit-rescue-complete.bup'
OUT = ROOT / 'build/run/live-tap'
MENU, VILLAGE = 'e3c59071', '7f410a40'
PRESSES = [(1500, 'START'), (2500, 'DOWN'), (2600, 'START'), (2750, 'START'), (2900, 'START')]


def script(hold):
    steps = []
    for vblank, button in PRESSES:
        steps.append(f'{vblank}:{button}')
        steps.append(f'{vblank + hold}:')
    return ','.join(steps)


def run(hold):
    folder = OUT / f'live{hold}'
    folder.mkdir(parents=True, exist_ok=True)
    # @FILE is resolved by the runtime against its own working directory, so hand it the same
    # relative path every other input script uses; an absolute one is not what the gate runs do.
    input_file = folder / 'input.txt'
    input_file.write_text(script(hold), encoding='utf-8')
    save = folder / 'wc.bup'
    save.write_bytes(SOURCE_SAVE.read_bytes())
    recorded = folder / 'recorded.txt'
    cmd = [str(EXE), '--cue', 'disc/pal_t37401h_13tr.cue', '--vblanks', '3401',
           '--save', str(save), '--settings', '-', '--clock', '1998-11-01T12:00:00',
           '--virtual-input', '@' + input_file.relative_to(ROOT).as_posix(),
           '--record-input', str(recorded),
           '--shot', '2000,2700,3401', '--out', str(folder)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    got = {}
    for p in sorted(folder.glob('shot-*.png')):
        got[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
    pressed = recorded.read_text(encoding='utf-8') if recorded.is_file() else ''
    virtual = [line for line in (result.stdout + result.stderr).splitlines()
               if 'virtual pad' in line or 'gamepad: SDL' in line]
    print(f'hold={hold:2d} exit={result.returncode} menu={got.get("shot-2700.png")} '
          f'end={got.get("shot-3401.png")} '
          f'{"ACKNOWLEDGED" if got.get("shot-3401.png") == VILLAGE else "not acknowledged"}', flush=True)
    print(f'    host published: {pressed}')
    for line in virtual:
        print(f'    {line.strip()}')
    return got


def main():
    holds = [int(a) for a in sys.argv[1:]] or [1, 2, 12]
    for hold in holds:
        run(hold)


if __name__ == '__main__':
    main()
