"""Windows build and run driver for this game.

Why this file exists — two measured Windows gaps in the pinned upstream (saturn-recomp 086c372):

1. `saturnrecomp.prereqs.check()` appends the hard-coded problem "Windows is not supported yet",
   and `saturnrecomp.build.recompile()` aborts on any problem, so `python -m saturnrecomp.build`
   and `python -m saturnrecomp.learn` refuse to run here at all. Upstream's own release workflow
   does compile windows-x64 (`ilammy/msvc-dev-cmd` + clang), so the platform is capable; what is
   missing is a Windows path through that one label.
2. `build.recompile()` hard-codes `-DCMAKE_CXX_COMPILER=clang++` and no static link. This host has
   no MSVC, and a MinGW-shared exe fails at load with 0xC0000139 because Git for Windows'
   /mingw64/bin/libstdc++-6.dll shadows the DLL of the toolchain that built it.

Neither is a game-hardware change: the recompiler, the runtime and the disc code are used exactly
as upstream wrote them. This driver re-runs the real prerequisite checks (cmake, ninja, a C++20
compiler through CMake, SDL3 presence) and substitutes its measured verdict for the platform label,
then does the CMake/Ninja step with the compiler and link flags this machine needs. Upstream stays
untouched; the patch is monkeypatching inside this process only.

    python tools/winbuild.py check
    python tools/winbuild.py build  [--recompile]
    python tools/winbuild.py learn  -- --cue disc/x.cue --headless --vblanks 600
    python tools/winbuild.py run    -- --cue disc/x.cue --headless --vblanks 600 --trace
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from saturnrecomp import build, config, learn, prereqs
from saturnrecomp.analysis import resume
from saturnrecomp.recomp.__main__ import generate

CXX = os.environ.get("CXX", "g++")
# -static: see gap 2 above. Also what makes the build portable to a plain Windows box (P3).
STATIC = ["-DCMAKE_CXX_FLAGS=-static", "-DCMAKE_EXE_LINKER_FLAGS=-static"]
LOG = []


def log(msg=""):
    print(msg, flush=True)
    LOG.append(str(msg))


def prereq_verdict(cxx=CXX):
    """The checks upstream means, run for real here instead of by platform label."""
    problems, notes = [], []
    for tool in ("cmake", "ninja", cxx):
        if not shutil.which(tool):
            problems.append(f"missing {tool}")
    if not problems:
        failed, sdl = prereqs.probe(cxx)
        if failed:
            problems.append(failed)
        elif not sdl:
            notes.append("SDL3 not found: this build has no window, pads or sound (headless runs only)")
        else:
            notes.append(f"ok: SDL3 {sdl}")
    return problems, notes


def _cmake_args(game):
    return ["-G", "Ninja", f"-DCMAKE_CXX_COMPILER={CXX}", *STATIC,
            *(f"-D{o}" for o in game.cmake)]


def win_recompile(game, log=log):
    """Upstream build.recompile with the two Windows assumptions replaced."""
    missing = [m.file for m in game.modules if not os.path.exists(m.file)]
    if missing:
        raise SystemExit("missing module files (has the disc been prepared?): " + ", ".join(missing))
    problems, notes = prereq_verdict()
    for n in notes:
        log("note: " + n)
    if problems:
        raise SystemExit("this machine cannot build the game yet:\n  " + "\n  ".join(problems))
    made_from = build.inputs(game)
    learned = game.learned_seeds()
    points = resume.for_game(game, log)
    specs = []
    for m in game.modules:
        seeds = set(m.seeds) | set(learned.get(m.name, []))
        if game.tasks and m.name == game.tasks.module:
            seeds |= set(points)
        specs.append((m.name, m.file, m.base, sorted(seeds)))
    tasks = (game.tasks.setjmp, game.tasks.longjmp) if game.tasks else None
    out = os.path.join(game.build, "recomp")
    generate(specs, out, log=log, hooks=game.hooks, tasks=tasks)
    build_dir = os.path.join(game.build, "recomp-build")
    cache = os.path.join(build_dir, "CMakeCache.txt")
    if os.path.exists(cache):
        os.remove(cache)
    _run("configuring the build", ["cmake", "-S", out, "-B", build_dir, *_cmake_args(game)], build_dir)
    win_build(game)
    with open(build._stamp(game), "w") as f:
        json.dump(made_from, f, indent=1, sort_keys=True)
        f.write("\n")


def win_build(game):
    build_dir = os.path.join(game.build, "recomp-build")
    _run("the build", ["ninja", "-C", build_dir], build_dir)


def _run(what, args, build_dir):
    log(f"$ {' '.join(args)}")
    t0 = time.time()
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise SystemExit(f"{what} failed: no {args[0]}")
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-12:])
    log(f"  {what}: exit {r.returncode} in {time.time() - t0:.1f} s")
    if r.returncode:
        os.makedirs(build_dir, exist_ok=True)
        path = os.path.join(build_dir, "build-log.txt")
        open(path, "w", encoding="utf-8").write(r.stdout + r.stderr)
        raise SystemExit(f"{tail}\n\n{what} failed; the whole output is in {path}")


def win_ensure(game, recompile_all=False):
    changed = ["asked to"] if recompile_all else build.stale(game)
    if changed:
        log("recompiling: " + ", ".join(changed))
        win_recompile(game)
    else:
        win_build(game)


def exe(game):
    """game.saturn, with the .exe Windows' CreateProcess would append for us."""
    path = game.saturn
    return path if os.path.exists(path) else path + ".exe"


def run_args(game, args, out=None):
    """One run of the built executable, its whole output kept under evidence/."""
    cmd = [exe(game)] + (["--out", out] if out else []) + args
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:                        # saturn's own flags start at the first bare --
        cut = argv.index("--")
        saturn_args, argv = argv[cut + 1:], argv[:cut]
    else:
        saturn_args = []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=("check", "build", "learn", "run"))
    ap.add_argument("--config", default="game.toml")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--recompile", action="store_true")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    args = saturn_args

    if a.what == "check":
        problems, notes = prereq_verdict()
        for n in notes:
            log("note: " + n)
        for p in problems:
            log("problem: " + p)
        log(f"verdict for {sys.platform}: {'cannot build' if problems else 'can build'}")
        return 1 if problems else 0

    game = config.load(a.config)
    build.recompile = win_recompile          # upstream stays untouched on disk
    build.build = win_build
    if a.what == "build":
        win_ensure(game, recompile_all=a.recompile)
        log("built: " + exe(game))
        return 0
    if a.what == "learn":
        out = a.out or os.path.join(game.build, "learn")
        text = learn.learn(game, args, out, limit=a.limit, log=log)
        log(text[-4000:])
        return 0
    return run_args(game, args, a.out).returncode


if __name__ == "__main__":
    sys.exit(main())
