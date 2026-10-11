#!/usr/bin/env python3
"""Original, asset-free SH-2 arithmetic and synthetic-disc integration checks.

This does not run PAL, a game ROM, or a BIOS. Expected arithmetic comes from
Python integer mathematics, never saturnrecomp.sh2emu or its vector generator.
Every invocation creates a separate run beneath build/synthetic by default.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import shlex
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
MASK = 0xFFFFFFFF
RETURN = 0xFFFFFFF0
ARITH_BASE = 0x06020000
BOOT_BASE = 0x06004000
BAD_BASE = 0x06008000
UNKNOWN = 0x060F0000
MARKER_ADDRESS = 0x06030000
MARKER_VALUE = 0x53594E54  # ASCII SYNT, created by this test.
COLOUR = 0x46A9
EDGE = [0, 1, 2, 0x7F, 0x80, 0xFF, 0x7FFF, 0x8000, 0xFFFF,
        0x10000, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFE, MASK]


def signed(x):
    return x if x < 0x80000000 else x - 0x100000000


def arithmetic_cases():
    # SH-2 instruction words written here directly, not by the tested encoder.
    # Ordinary bodies: mov r4,r0; operation; rts; nop.
    ops = [('add', 0x305C), ('sub', 0x3058), ('xor', 0x205A),
           ('and', 0x2059), ('or', 0x205B), ('addc', 0x305E),
           ('subc', 0x305A), ('shll', 0x4000), ('shlr', 0x4001),
           ('rotl', 0x4004), ('rotr', 0x4005), ('addv', 0x305F),
           ('subv', 0x305B)]
    cases = [(name, [0x6043, word, 0x000B, 0x0009]) for name, word in ops]
    cases += [('signed_lt', [0x3547, 0x0029, 0x000B, 0x0009]),
              ('unsigned_lt', [0x3546, 0x0029, 0x000B, 0x0009]),
              ('mul_low', [0x0547, 0x001A, 0x000B, 0x0009])]
    return cases


def mathematical_result(name, state):
    """Independent mathematical oracle, including unchanged registers and flags."""
    out = state.copy()
    a, b, t = state[4], state[5], state[16] & 1
    new_t = None
    if name == 'add': value = a + b
    elif name == 'sub': value = a - b
    elif name == 'xor': value = a ^ b
    elif name == 'and': value = a & b
    elif name == 'or': value = a | b
    elif name == 'addc':
        value = a + b + t
        new_t = int(value > MASK)
    elif name == 'subc':
        value = a - b - t
        new_t = int(value < 0)
    elif name == 'shll': value, new_t = a << 1, a >> 31
    elif name == 'shlr': value, new_t = a >> 1, a & 1
    elif name == 'rotl': value, new_t = (a << 1) | (a >> 31), a >> 31
    elif name == 'rotr': value, new_t = (a >> 1) | ((a & 1) << 31), a & 1
    elif name in ('addv', 'subv'):
        value = signed(a) + signed(b) if name == 'addv' else signed(a) - signed(b)
        new_t = int(not -(1 << 31) <= value < (1 << 31))
    elif name == 'signed_lt': value = new_t = int(signed(a) < signed(b))
    elif name == 'unsigned_lt': value = new_t = int(a < b)
    elif name == 'mul_low':
        value = a * b
        out[20] = value & MASK  # MACL
    else: raise ValueError(name)
    out[0] = value & MASK
    if new_t is not None:
        out[16] = (out[16] & ~1) | new_t
    out[21] = RETURN
    return out


class Program:
    """Tiny original assembler for only the literal loads needed by boot tests."""
    def __init__(self, base):
        self.base, self.words, self.literals = base, [], []

    def literal(self, reg, value):
        self.literals.append((len(self.words), reg, value))
        self.words.append(0)

    def store(self, addr, value, size):
        self.literal(1, addr)
        self.literal(0, value)
        self.words.append({2: 0x2101, 4: 0x2102}[size])  # mov.w/l r0,@r1

    def finish(self):
        if len(self.words) % 2: self.words.append(0x0009)
        for index, reg, value in self.literals:
            here = self.base + index * 2
            target = self.base + len(self.words) * 2
            disp = (target - ((here + 4) & ~3)) // 4
            assert 0 <= disp <= 255
            self.words[index] = 0xD000 | reg << 8 | disp
            self.words.extend([value >> 16, value & 0xFFFF])
        return struct.pack('>' + 'H' * len(self.words), *self.words)


def boot_program():
    p = Program(BOOT_BASE)
    p.store(MARKER_ADDRESS, MARKER_VALUE, 4)
    p.store(0x25E40000, COLOUR, 2)  # Original single-colour back-screen data.
    p.store(0x25F800AC, 2, 2)       # BKTAU: word address 0x20000.
    p.store(0x25F800AE, 0, 2)       # BKTAL.
    p.store(0x25F80000, 0x8000, 2)  # TVMD: enable 320 x 224 display.
    p.words += [0xAFFE, 0x0009]    # bra to itself; nop. Polls reach VBlank limit.
    return p.finish()


def bad_program():
    p = Program(BAD_BASE)
    p.literal(4, UNKNOWN)
    p.words += [0x442B, 0x0009]    # jmp @r4; nop, to an uncompiled address.
    return p.finish()


def both16(n): return struct.pack('<H', n) + struct.pack('>H', n)
def both32(n): return struct.pack('<I', n) + struct.pack('>I', n)


def directory_record(name, lba, size, directory=False):
    date = bytes([126, 10, 10, 0, 0, 0, 0])
    body = (b'\0' + both32(lba) + both32(size) + date
            + bytes([2 if directory else 0, 0, 0]) + both16(1)
            + bytes([len(name)]) + name + (b'\0' if len(name) % 2 == 0 else b''))
    return bytes([len(body) + 1]) + body


def synthetic_disc(directory, body, base):
    """Create a tiny, original MODE1/2048 fixture with a genuine ISO9660 layout.

    Only format identifiers/header constants are used; there is no Sega BIOS,
    security bootstrap, original game executable, audio, or game artwork.
    """
    directory.mkdir()
    sectors = 21 + (len(body) + 2047) // 2048
    image = bytearray(sectors * 2048)
    image[:16] = b'SEGA SEGASATURN '
    image[0x10:0x20] = b'ORIGINAL TEST'.ljust(16)
    image[0x20:0x2A] = b'SYNTH-0001'
    image[0x2A:0x30] = b'V1.000'
    image[0x30:0x38] = b'20261010'
    image[0x38:0x40] = b'CD-1/1  '
    image[0x40:0x50] = b'J'.ljust(16)
    image[0x50:0x60] = b'J'.ljust(16)
    image[0x60:0xD0] = b'ORIGINAL SYNTHETIC TEST - NOT A GAME'.ljust(0x70)
    image[0xE0:0xF8] = struct.pack('>6I', 0x100, 0, 0x06001000, 0x06000800, base, len(body))
    root = directory_record(b'\0', 20, 2048, True)
    pvd = bytearray(2048)
    pvd[:7] = b'\x01CD001\x01'
    pvd[8:40] = b'ORIGINAL SYNTHETIC'.ljust(32)
    pvd[40:72] = b'NO GAME OR BIOS DATA'.ljust(32)
    pvd[80:88] = both32(sectors)
    pvd[120:124] = both16(1)
    pvd[124:128] = both16(1)
    pvd[128:132] = both16(2048)
    pvd[132:140] = both32(10)
    pvd[140:144] = struct.pack('<I', 18)
    pvd[148:152] = struct.pack('>I', 19)
    pvd[156:190] = root
    pvd[881] = 1
    image[16 * 2048:17 * 2048] = pvd
    image[17 * 2048:17 * 2048 + 7] = b'\xFFCD001\x01'
    image[18 * 2048:18 * 2048 + 10] = b'\x01\x00' + struct.pack('<IH', 20, 1) + b'\x00\x00'
    image[19 * 2048:19 * 2048 + 10] = b'\x01\x00' + struct.pack('>IH', 20, 1) + b'\x00\x00'
    records = root + directory_record(b'\1', 20, 2048, True) + directory_record(b'SYNTH.BIN;1', 21, len(body))
    image[20 * 2048:20 * 2048 + len(records)] = records
    image[21 * 2048:21 * 2048 + len(body)] = body
    (directory / 'synthetic.iso').write_bytes(image)
    cue = directory / 'synthetic.cue'
    cue.write_text('FILE "synthetic.iso" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n')
    return cue


def png_pixels(path):
    """Read the runtime's filter-0 RGB PNG without an image library dependency."""
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'missing PNG signature'
    at, compressed, dimensions = 8, bytearray(), None
    while at < len(data):
        length = struct.unpack_from('>I', data, at)[0]
        kind, payload = data[at + 4:at + 8], data[at + 8:at + 8 + length]
        crc = struct.unpack_from('>I', data, at + 8 + length)[0]
        assert zlib.crc32(kind + payload) == crc, 'PNG chunk checksum mismatch'
        if kind == b'IHDR':
            width, height, depth, colour, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            assert (depth, colour, compression, filtering, interlace) == (8, 2, 0, 0, 0)
            dimensions = (width, height)
        elif kind == b'IDAT': compressed += payload
        at += 12 + length
    assert dimensions is not None
    width, height = dimensions
    raw = zlib.decompress(compressed)
    assert len(raw) == height * (1 + width * 3)
    rows = []
    for row in range(height):
        start = row * (1 + width * 3)
        assert raw[start] == 0, 'unexpected PNG filter'
        rows.append(raw[start + 1:start + 1 + width * 3])
    return dimensions, b''.join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='new, nonexistent run directory')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    if args.jobs < 1: parser.error('--jobs must be positive')
    if sys.flags.optimize:
        parser.error('assertion checks must be enabled; do not use python -O or PYTHONOPTIMIZE')
    runtime = ROOT / 'third_party/saturn-recomp-pal'
    installed = importlib.util.find_spec('saturnrecomp')
    if installed is None or not Path(installed.origin).resolve().is_relative_to(runtime):
        parser.error('install the authorized, patched saturn-recomp-pal checkout editable in this Python environment first')
    out = (args.out or ROOT / 'build/synthetic' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    if not out.is_relative_to(ROOT / 'build/synthetic'):
        parser.error('--out must be beneath this repository\'s build/synthetic directory')
    out.mkdir(parents=True, exist_ok=False)
    inputs, logs = out / 'inputs', out / 'logs'
    inputs.mkdir(); logs.mkdir()
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment['PATH'] = str(Path(sys.executable).parent) + os.pathsep + environment['PATH']
    environment['HOME'] = str(out / 'home')
    environment['XDG_DATA_HOME'] = str(out / 'home/data')
    environment['XDG_CONFIG_HOME'] = str(out / 'home/config')
    (out / 'home').mkdir()
    records = []
    provenance = {'python': sys.version, 'platform': platform.platform(),
                  'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'runtime_checkout': str(runtime), 'runtime_import': str(installed.origin),
                  'runtime_commit': subprocess.check_output(['git', '-C', str(runtime), 'rev-parse', 'HEAD'], text=True).strip(),
                  'runtime_diff_sha256': hashlib.sha256(subprocess.check_output(['git', '-C', str(runtime), 'diff', 'HEAD'])).hexdigest(),
                  'patch_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted((ROOT / 'patches').glob('000[1-4]-*.patch'))}}
    if not provenance['runtime_commit'].startswith('086c372'):
        raise RuntimeError('the synthetic acceptance test expects the reviewed 086c372 runtime revision')
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')

    def run(label, command, expected=0, require=(), env=None, timeout=180):
        print('$ ' + shlex.join(map(str, command)), flush=True)
        path = logs / (label + '.log')
        with path.open('w') as log:
            log.write('$ ' + shlex.join(map(str, command)) + '\n')
            log.flush()
            try:
                result = subprocess.run(list(map(str, command)), cwd=out, env=env or environment,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            except subprocess.TimeoutExpired:
                log.write('\nFAIL: command timed out\n')
                raise
            except OSError as error:
                log.write(f'\nFAIL: command could not start: {error}\n')
                raise
            log.write(f'\nEXIT_CODE={result.returncode}\n')
        output = path.read_text()
        print(f'{label}: exit {result.returncode}; log {path}', flush=True)
        if result.returncode != expected:
            raise AssertionError(f'{label}: expected exit {expected}, got {result.returncode}\n{output[-5000:]}')
        for phrase in require:
            assert phrase in output, f'{label}: missing expected evidence {phrase!r}\n{output[-5000:]}'
        records.append({'stage': label, 'command': list(map(str, command)), 'exit_code': result.returncode,
                        'expected_exit_code': expected, 'log': str(path.relative_to(out))})
        return output

    cases = arithmetic_cases()
    arithmetic = b''.join(struct.pack('>8H', *words, *([0x0009] * (8 - len(words)))) for _, words in cases)
    arith = inputs / 'arithmetic.bin'; arith.write_bytes(arithmetic)
    boot = inputs / 'boot.bin'; boot.write_bytes(boot_program())
    bad = inputs / 'bad-entry.bin'; bad.write_bytes(bad_program())
    entries = [ARITH_BASE + index * 16 for index in range(len(cases))]
    vectors = [f'image {ARITH_BASE:08X} {arith}', 'module ARITH']
    rng = random.Random(0x53594E54)
    count = 0
    low, high = bytearray(0x100000), bytearray(0x100000)
    high[ARITH_BASE - 0x06000000:ARITH_BASE - 0x06000000 + len(arithmetic)] = arithmetic
    crc_line = f'mem {zlib.crc32(low):08X} {zlib.crc32(high):08X}'
    for index, (name, _) in enumerate(cases):
        vectors.append(f'func {entries[index]:08X} independent_{name}')
        operands = [(a, b, t) for a in EDGE for b in EDGE for t in (0, 1)]
        operands += [(rng.getrandbits(32), rng.getrandbits(32), rng.randrange(2)) for _ in range(256)]
        for a, b, t in operands:
            state = [rng.getrandbits(32) for _ in range(22)]
            state[4], state[5] = a, b
            state[16] = (state[16] & 0x3F2) | t
            state[21] = RETURN
            result = mathematical_result(name, state)
            vectors.append('v ' + ' '.join(f'{x:08X}' for x in state + result))
            count += 1
        vectors.append(crc_line)
    vector_file = inputs / 'independent-math.txt'
    vector_file.write_text('\n'.join(vectors) + '\n')
    first = next(line for line in vectors if line.startswith('v '))
    mutated = first.split()
    mutated[23] = f'{int(mutated[23], 16) ^ 1:08X}'
    wrong_file = inputs / 'deliberately-wrong-expected.txt'
    wrong_file.write_text('\n'.join(vectors[:3] + [' '.join(mutated)]) + '\n')
    unknown_file = inputs / 'unknown-entry.txt'
    unknown_file.write_text('\n'.join(vectors[:2] + [f'func {UNKNOWN:08X} deliberate_nonentry', first]) + '\n')
    cue = synthetic_disc(inputs / 'disc-good', boot.read_bytes(), BOOT_BASE)
    bad_cue = synthetic_disc(inputs / 'disc-unknown-entry', bad.read_bytes(), BAD_BASE)
    mismatch_cue = synthetic_disc(inputs / 'disc-mismatch', boot.read_bytes() + b'\0\0', BOOT_BASE)
    # Change code within the checked image, not just bytes after it.
    mismatch = mismatch_cue.parent / 'synthetic.iso'
    mismatch_bytes = bytearray(mismatch.read_bytes())
    mismatch_bytes[21 * 2048] ^= 1
    mismatch.write_bytes(mismatch_bytes)
    input_hashes = {str(p.relative_to(inputs)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(inputs.rglob('*')) if p.is_file()}
    # The clean checkout validates the hand-built disc independently of the patched import path.
    clean_environment = dict(environment, PYTHONPATH=str(ROOT / 'third_party/saturn-recomp/src'))
    run('disc-info', [sys.executable, '-m', 'saturnrecomp.disc', cue, '--info'],
        require=('SYNTH-0001',), env=clean_environment)
    run('disc-list', [sys.executable, '-m', 'saturnrecomp.disc', cue, '--list'],
        require=('SYNTH.BIN',), env=clean_environment)
    specs = [f'ARITH={arith}@{ARITH_BASE:08X}+' + ','.join(f'{x:08X}' for x in entries),
             f'BOOT={boot}@{BOOT_BASE:08X}', f'BAD={bad}@{BAD_BASE:08X}']
    run('generate', [sys.executable, '-m', 'saturnrecomp.recomp', '--out', out / 'generated', *specs])
    run('configure', ['cmake', '-S', out / 'generated', '-B', out / 'native', '-G', 'Ninja',
                     '-DCMAKE_CXX_COMPILER=' + os.environ.get('CXX', 'g++'), '-DSATURN_NO_SDL=ON'])
    run('build', ['cmake', '--build', out / 'native', '--parallel', args.jobs], timeout=600)
    selftest, saturn = out / 'native/selftest', out / 'native/saturn'
    run('independent-arithmetic', [selftest, vector_file], require=(f'{len(cases)} functions, {count} vectors, 0 failures',))
    run('reject-wrong-expectation', [selftest, wrong_file], expected=1, require=('1 vectors, 1 failures',))
    run('reject-unknown-selftest-entry', [selftest, unknown_file], expected=1, require=('call to a non-entry 060F0000',))
    expected_rgb = bytes(((COLOUR & 31) * 8, ((COLOUR >> 5) & 31) * 8, ((COLOUR >> 10) & 31) * 8))
    frame_hashes = []
    for repeat in (1, 2):
        run_dir = out / f'headless-{repeat}'; run_dir.mkdir()
        run(f'headless-{repeat}', [saturn, '--cue', cue, '--headless', '--save', '-', '--out', run_dir,
                                 '--vblanks', '10', '--shot', '2,10', '--peek', f'{MARKER_ADDRESS:08X}:1',
                                 '--coverage', run_dir / 'coverage.txt'],
            require=('boot: BOOT at 06004000', 'stopped (VBlank limit) after 10 VBlanks', '53594E54'))
        for frame in (2, 10):
            png = run_dir / f'shot-{frame}.png'
            dimensions, pixels = png_pixels(png)
            assert dimensions == (320, 224), dimensions
            assert pixels == expected_rgb * (320 * 224), 'rendered pixels differ from original constant-colour expectation'
            frame_hashes.append(hashlib.sha256(png.read_bytes()).hexdigest())
        assert 'BOOT' in (run_dir / 'coverage.txt').read_text()
    assert len(set(frame_hashes)) == 1, 'frames are not deterministic across isolated runs'
    bad_out = out / 'headless-unknown'; bad_out.mkdir()
    run('reject-unknown-runtime-entry', [saturn, '--cue', bad_cue, '--headless', '--save', '-', '--out', bad_out,
                                       '--vblanks', '10'], expected=1,
        require=('boot: BAD at 06008000', 'call to 060F0000, not an entry of an active module'))
    mismatch_out = out / 'headless-mismatch'; mismatch_out.mkdir()
    run('reject-mismatched-disc', [saturn, '--cue', mismatch_cue, '--headless', '--save', '-', '--out', mismatch_out,
                                 '--vblanks', '10'], expected=2,
        require=('no module matches the 1st read file at 06004000',))
    after_hashes = {str(p.relative_to(inputs)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(inputs.rglob('*')) if p.is_file()}
    assert after_hashes == input_hashes, 'a supposedly read-only input changed'
    assert not list((out / 'home').rglob('backup.bin')), 'an isolated test unexpectedly saved backup RAM'
    summary = {'status': 'passed', 'scope': 'original synthetic data only; not PAL/game/BIOS validation',
               'provenance': provenance,
               'arithmetic': {'functions': len(cases), 'vectors': count, 'failures': 0,
                              'oracle': 'Python integer mathematics; no interpreter-derived expected results'},
               'headless': {'runs': 2, 'vblanks_per_run': 10, 'verified_pngs': 4,
                            'dimensions': [320, 224], 'expected_rgb': list(expected_rgb),
                            'sha256': frame_hashes[0], 'marker': f'{MARKER_VALUE:08X}'},
               'negative_tests': 4, 'inputs_unchanged': True, 'no_persistent_save': True,
               'input_sha256': input_hashes, 'stages': records}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'PASS: {len(cases)} arithmetic functions / {count} independent vectors; '
          '4 expected-failure tests; 2 headless boots / 4 verified frames.', flush=True)
    print(f'Summary: {out / "summary.json"}', flush=True)


if __name__ == '__main__':
    main()
