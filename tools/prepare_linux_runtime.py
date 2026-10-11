"""Prepare an auditable patched checkout; does not import or execute runtime code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

PIN = '086c372c67d9e0f94fcc64cedd6e6b63cc5542b5'
ROOT = Path(__file__).resolve().parents[1]


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.STDOUT)


def identity(path, pin):
    if not (path / '.git').is_dir():
        raise ValueError(f'Not an independent checkout: {path}')
    if Path(git(path, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != path.resolve():
        raise ValueError('Wrong checkout root')
    if git(path, 'rev-parse', 'HEAD').decode().strip() != pin:
        raise ValueError('Unexpected upstream commit')


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
            git(scratch, 'apply', '--check', str(patch.resolve()))
            git(scratch, 'apply', str(patch.resolve()))
        data = {'pin': pin, 'patches': inputs,
                'diff_sha256': hashlib.sha256(git(scratch, 'diff', 'HEAD', '--binary')).hexdigest()}
        (scratch / '.git/pal-setup-manifest.json').write_text(json.dumps(data, indent=2) + '\n')
        scratch.rename(patched)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
    return True


def main():
    clean = ROOT / 'third_party/saturn-recomp'
    # 0006 belongs to the options builder, which applies it to its own runtime copy.
    patches = [next((ROOT / 'patches').glob(f'{n:04d}-*.patch')) for n in (1, 2, 3, 4, 5, 7, 8, 9, 10)]
    made = prepare(clean, ROOT / 'third_party/saturn-recomp-pal', PIN, patches)
    print('Patched runtime prepared' if made else 'Existing runtime identity verified')


if __name__ == '__main__':
    main()
