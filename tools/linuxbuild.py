"""Linux headless build entry. Keeps the Windows config and parser checkout unchanged.

Run with build/venv/bin/python tools/linuxbuild.py check|build [--recompile].
Input files must already be validated/extracted; this driver never obtains game assets.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    print('$ ' + ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, cwd=ROOT)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['check', 'build'])
    p.add_argument('--config', default='game.toml')
    p.add_argument('--recompile', action='store_true')
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--probe-resources', action='store_true', help='Observe selected PROG resource-loader entries')
    p.add_argument('--probe-literals', action='store_true', help='Observe folded loads against raw RAM, keeping their original values')
    p.add_argument('--sdl-prefix', type=Path, help='Verified local SDL3 install prefix; uses separate windowed build')
    a = p.parse_args()
    os.chdir(ROOT)
    os.environ['PATH'] = str(ROOT / 'build/venv/bin') + os.pathsep + os.environ['PATH']
    cxx = os.environ.get('CXX', 'g++')
    if a.sdl_prefix:
        a.sdl_prefix = a.sdl_prefix.resolve()
        if not a.sdl_prefix.is_dir():
            raise SystemExit('Missing SDL install prefix: ' + str(a.sdl_prefix))
        os.environ['CMAKE_PREFIX_PATH'] = str(a.sdl_prefix)
    for tool in ('cmake', 'ninja', cxx):
        if not shutil.which(tool):
            raise SystemExit('Missing build tool: ' + tool)
    if a.probe_literals:
        import literal_probe
        literal_probe.install()
    # Imports deliberately occur only when this runtime has execution authorization.
    from saturnrecomp import config, build, prereqs
    from saturnrecomp.analysis import resume
    from saturnrecomp.recomp.__main__ import generate
    failed, sdl = prereqs.probe(cxx)
    if failed:
        raise SystemExit(failed)
    if a.sdl_prefix and not sdl:
        raise SystemExit('Requested SDL3 prefix did not pass the real CMake probe')
    mode = 'SDL3' if a.sdl_prefix else 'headless'
    print(f'C++20 compiler verified: {cxx}; requested host={mode}; SDL3 detected={bool(sdl)}')
    if a.action == 'check':
        return
    game = config.load(a.config)
    # Preserve proven modules, hooks and seeds. Only host paths/options change.
    game.build = str(ROOT / ('build/linux-game-resources' if a.probe_resources else 'build/linux-game-probe' if a.probe_literals else 'build/linux-game-sdl' if a.sdl_prefix else 'build/linux-game'))
    game.cmake = [f'SATURN_NO_SDL={"OFF" if a.sdl_prefix else "ON"}', f'SATURN_EXTRA={ROOT / "src/pal_game/pal_game.cmake"}']
    if a.sdl_prefix:
        game.cmake.append(f'CMAKE_PREFIX_PATH={a.sdl_prefix}')
    missing = [m.file for m in game.modules if not Path(m.file).is_file()]
    if missing:
        raise SystemExit('blocked-input: verified/extracted game modules required: ' + ', '.join(missing))
    out = Path(game.build) / 'recomp'
    binary = Path(game.build) / 'recomp-build'
    changed = a.recompile or build.stale(game)
    if changed:
        learned = game.learned_seeds()
        points = resume.for_game(game, print)
        specs = []
        for m in game.modules:
            seeds = set(m.seeds) | set(learned.get(m.name, []))
            if game.tasks and m.name == game.tasks.module:
                seeds |= set(points)
            specs.append((m.name, m.file, m.base, sorted(seeds)))
        tasks = (game.tasks.setjmp, game.tasks.longjmp) if game.tasks else None
        generate(specs, str(out), hooks=game.hooks, tasks=tasks)
        if a.probe_literals:
            literal_probe.add_headers(out, ROOT)
        if a.probe_resources:
            import resource_probe
            resource_probe.add_headers(out, ROOT)
    # --fresh avoids stale Windows/GPL/SDL flags while preserving generated inputs.
    run('cmake', '--fresh', '-S', out, '-B', binary, '-G', 'Ninja',
        f'-DCMAKE_CXX_COMPILER={cxx}', *('-D' + opt for opt in game.cmake))
    run('cmake', '--build', binary, '--parallel', a.jobs)
    if changed:
        Path(build._stamp(game)).write_text(json.dumps(build.inputs(game), indent=2) + '\n')
    print('Built:', binary / 'saturn')
    print('Use --save - and a fresh --out directory for every game run.')


if __name__ == '__main__':
    main()
