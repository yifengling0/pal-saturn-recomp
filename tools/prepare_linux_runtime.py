"""Prepare an auditable patched checkout; does not import or execute runtime code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

PIN = '086c372c67d9e0f94fcc64cedd6e6b63cc5542b5'
ROOT = Path(__file__).resolve().parents[1]
# 0006 belongs to the options builder, which applies it to its own runtime copy.
NUMBERS = (1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)


def patch_set(numbers=NUMBERS):
    """Resolve one patch per number, or stop.

    Two people numbering the same release each add a 0012 and a 0013, and `next(glob(...))` then
    picks one of the two by filename and builds without ever mentioning the other.
    """
    out = []
    for n in numbers:
        found = sorted((ROOT / 'patches').glob(f'{n:04d}-*.patch'))
        if len(found) > 1:
            raise ValueError(f'{n:04d}-*.patch is ambiguous: ' + ', '.join(p.name for p in found))
        if not found:
            raise ValueError(f'{n:04d}-*.patch is missing')
        out.append(found[0])
    return out


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.STDOUT)


def identity(path, pin):
    if not (path / '.git').is_dir():
        raise ValueError(f'Not an independent checkout: {path}')
    if Path(git(path, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != path.resolve():
        raise ValueError('Wrong checkout root')
    if git(path, 'rev-parse', 'HEAD').decode().strip() != pin:
        raise ValueError('Unexpected upstream commit')


def rename_when_unlocked(scratch: Path, patched: Path, tries: int = 30, pause: float = 2.0):
    """Windows refuses to rename a directory the instant it stops being written to: Defender and the
    indexer hold handles on the loose objects the clone and the ten `git apply` runs just created, and
    the rename lands in that window. Waiting is what clears it, so retry with a backoff."""
    for attempt in range(tries):
        try:
            scratch.rename(patched)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(pause)


def prepare(clean: Path, patched: Path, pin: str, patches: list[Path]):
    identity(clean, pin)
    if git(clean, 'status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Parser checkout must remain clean')
    inputs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in patches}
    marker = patched / '.git/pal-setup-manifest.json'
    if patched.exists():
        identity(patched, pin)
        data = json.loads(marker.read_text())
        diff = git(patched, 'diff', 'HEAD', '--binary')
        if data != {'pin': pin, 'patches': inputs, 'diff_sha256': hashlib.sha256(diff).hexdigest()}:
            raise ValueError('Patched checkout or patch inputs changed; refusing to overwrite')
        return False
    patched.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='.pal-runtime-', dir=patched.parent))
    try:
        subprocess.run(['git', 'clone', '--no-hardlinks', str(clean), str(scratch)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git(scratch, 'checkout', '-b', 'pal-linux', pin)
        for patch in patches:
            # Include newly added helpers in diff HEAD and the repeat identity check.
            git(scratch, 'apply', '--check', '--index', str(patch.resolve()))
            git(scratch, 'apply', '--index', str(patch.resolve()))
        data = {'pin': pin, 'patches': inputs,
                'diff_sha256': hashlib.sha256(git(scratch, 'diff', 'HEAD', '--binary')).hexdigest()}
        (scratch / '.git/pal-setup-manifest.json').write_text(json.dumps(data, indent=2) + '\n')
        rename_when_unlocked(scratch, patched)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)
    return True


def main():
    clean = ROOT / 'third_party/saturn-recomp'
    made = prepare(clean, ROOT / 'third_party/saturn-recomp-pal', PIN, patch_set())
    print('Patched runtime prepared' if made else 'Existing runtime identity verified')


if __name__ == '__main__':
    main()
