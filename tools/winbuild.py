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
import hashlib
from pathlib import Path
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
STATIC = ["-DCMAKE_CXX_FLAGS=-static", "-DCMAKE_EXE_LINKER_FLAGS=-static"] if sys.platform == "win32" else []
LOG = []
OPTIONS = False
JOBS = 2
REQUIRE_SDL = False
PATCHED_RUNTIME = Path(ROOT) / "third_party/saturn-recomp-pal/runtime"


def win_stale(game):
    """Upstream game.saturn omits .exe; test the actual Windows binary."""
    if not os.path.isfile(exe(game)):
        return ["no build yet"]
    try:
        before = json.loads(Path(build._stamp(game)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["no record of the last recompile's inputs"]
    now = build.inputs(game)
    return [key for key in sorted(set(before) | set(now)) if before.get(key) != now.get(key)]


def verify_options_runtime():
    # This helper is platform-neutral despite its historical filename. It
    # preserves a clean parser checkout and verifies the exact five-patch diff.
    from prepare_linux_runtime import prepare, PIN
    expected = PATCHED_RUNTIME.parent / "src/saturnrecomp/build.py"
    if Path(build.__file__).resolve() != expected.resolve():
        raise SystemExit("Wrong imported generator: install with python -m pip install -e third_party/saturn-recomp-pal")
    clean = Path(ROOT) / "third_party/saturn-recomp"
    patches = [next((Path(ROOT) / "patches").glob(f"{n:04d}-*.patch")) for n in range(1, 6)]
    prepare(clean, PATCHED_RUNTIME.parent, PIN, patches)


def option_build_manifest(game):
    """Only a successful linked executable receives its launch capability proof."""
    from pal_options import VERSION, MANIFEST
    if not OPTIONS:
        from pal_keyboard_profile import VERSION, MANIFEST
    binary = Path(exe(game))
    injected = Path(game.build) / "recomp" / MANIFEST
    data = {"schema": 1, "version": VERSION,
            "exe_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "instrumentation_manifest_sha256": hashlib.sha256(injected.read_bytes()).hexdigest(),
            "features": ["input_v4", "effect_wait_v3", "data_cd_speed", "effect_cadence_v4_manual_pair", "paired_frame_queue_v3", "keyboard_profile_v1"] if OPTIONS else ["keyboard_profile_v1"]}
    (binary.parent / "pal-options-build.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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
            (problems if REQUIRE_SDL else notes).append(
                "SDL3 not found: no window, pads or sound; supply --sdl-dir or explicitly use --headless")
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
    if OPTIONS:
        proof = Path(game.build) / "recomp-build/pal-options-build.json"
        if proof.exists():
            proof.unlink()
        # Recreate only these dedicated, reproducible build inputs. Never mutate
        # the clean parser or patched source runtime, nor the baseline build.
        for directory in (Path(out), Path(game.build) / "runtime"):
            if directory.exists():
                shutil.rmtree(directory)
        shutil.copytree(PATCHED_RUNTIME, Path(game.build) / "runtime")
        from pal_data_cd_speed import apply_data_cd_speed
        apply_data_cd_speed(Path(game.build) / "runtime")
    else:
        # Mapping-only builds own a distinct runtime copy; never patch upstream.
        directory = Path(game.build) / "pal-keyboard-runtime"
        owner = directory / ".pal-keyboard-owner.json"
        owner_data = {"schema": 1, "kind": "pal-keyboard-generated-runtime"}
        if directory.exists():
            try:
                owned = json.loads(owner.read_text()) == owner_data
            except (OSError, ValueError):
                owned = False
            if not owned:
                raise SystemExit("Refusing to replace unowned keyboard runtime: " + str(directory))
            shutil.rmtree(directory)
        shutil.copytree(PATCHED_RUNTIME, directory)
        owner.write_text(json.dumps(owner_data) + "\n")
        manifest = Path(out) / "pal-keyboard-manifest.json"
        if manifest.exists():
            manifest.unlink()
    generate(specs, out, log=log, hooks=game.hooks, tasks=tasks)
    if OPTIONS:
        from pal_options import prepare_options
        prepare_options(Path(out), Path(game.build) / "runtime", Path(ROOT))
    else:
        from pal_keyboard_profile import prepare_keyboard
        prepare_keyboard(Path(out), Path(game.build) / "pal-keyboard-runtime", Path(ROOT))
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
    proof = Path(build_dir) / "pal-options-build.json"
    if proof.exists():
        proof.unlink()  # Validation and compilation failures must invalidate prior proof.
    if OPTIONS:
        from pal_options import prepare_options
        from pal_data_cd_speed import apply_data_cd_speed
        apply_data_cd_speed(Path(game.build) / "runtime")
        prepare_options(Path(game.build) / "recomp", Path(game.build) / "runtime", Path(ROOT))
    else:
        from pal_keyboard_profile import prepare_keyboard
        prepare_keyboard(Path(game.build) / "recomp", Path(game.build) / "pal-keyboard-runtime", Path(ROOT))
    _run("the build", ["cmake", "--build", build_dir, "--target", "saturn", "--parallel", str(JOBS)], build_dir)
    option_build_manifest(game)


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
    changed = ["asked to"] if recompile_all else win_stale(game)
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
    global OPTIONS, JOBS, REQUIRE_SDL
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
    ap.add_argument("--pal-options", action="store_true", help="Build both default-off PAL options in an isolated executable")
    ap.add_argument("--build-dir", type=Path, help="Dedicated output under this repository's build directory")
    ap.add_argument("--sdl-dir", type=Path, help="Directory containing SDL3Config.cmake")
    ap.add_argument("--headless", action="store_true", help="Explicitly compile without window/audio support")
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args(argv)
    OPTIONS, JOBS = a.pal_options, a.jobs
    REQUIRE_SDL = (OPTIONS or a.sdl_dir is not None) and not a.headless
    if a.jobs < 1:
        ap.error("--jobs must be positive")
    if a.sdl_dir and a.headless:
        ap.error("--sdl-dir and --headless are mutually exclusive")
    # Venv executables are siblings of this Python on both Windows and Linux.
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    if a.sdl_dir:
        a.sdl_dir = a.sdl_dir.resolve()
        if not (a.sdl_dir / "SDL3Config.cmake").is_file():
            ap.error("--sdl-dir must contain SDL3Config.cmake")
        os.environ["SDL3_DIR"] = a.sdl_dir.as_posix()
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
    # Machine paths do not belong in game.toml. Preserve unrelated game flags.
    game.cmake = [x for x in game.cmake if not x.startswith(("SATURN_EXTRA=", "SDL3_DIR=", "SATURN_RUNTIME=", "SATURN_NO_SDL="))]
    game.cmake.append("SATURN_EXTRA=" + (Path(ROOT) / "src/pal_game/pal_game.cmake").as_posix())
    if a.sdl_dir:
        game.cmake.append("SDL3_DIR=" + a.sdl_dir.as_posix())
    game.cmake.append("SATURN_NO_SDL=" + ("ON" if a.headless else "OFF"))
    if OPTIONS:
        output = (a.build_dir or Path(ROOT) / "build/windows-pal-options").resolve()
        if output == Path(ROOT) / "build" or not output.is_relative_to(Path(ROOT) / "build"):
            ap.error("Option output must be a dedicated directory under ROOT/build")
        owner = output / "pal-options-root.json"
        owner_data = {"schema": 1, "kind": "pal-windows-options-generated-build"}
        if output.exists() and any(output.iterdir()):
            try:
                owned = json.loads(owner.read_text(encoding="utf-8")) == owner_data
            except (OSError, ValueError):
                owned = False
            if not owned:
                ap.error("Refusing to replace an existing unowned build directory; choose a new --build-dir")
        game.build = str(output)
        game.cmake.append("SATURN_RUNTIME=" + (output / "runtime").as_posix())
        if a.what != "run":
            verify_options_runtime()
            output.mkdir(parents=True, exist_ok=True)
            owner.write_text(json.dumps(owner_data) + "\n", encoding="utf-8")
        original_inputs = build.inputs
        def option_inputs(game):
            data = original_inputs(game)
            for path in [Path(ROOT) / "tools/winbuild.py", Path(ROOT) / "tools/pal_options.py", Path(ROOT) / "tools/pal_data_cd_speed.py", Path(ROOT) / "tools/pal_paired_frame_queue.py", Path(ROOT) / "tools/pal_keyboard_profile.py", *sorted((Path(ROOT) / "src/pal_game").glob("pal_*.cpp")), *sorted((Path(ROOT) / "src/pal_game").glob("pal_*.h")), *sorted((Path(ROOT) / "patches").glob("*.patch"))]:
                data["PAL " + path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            return data
        build.inputs = option_inputs
    else:
        if a.build_dir:
            ap.error("--build-dir requires --pal-options")
        output = Path(game.build).resolve()
        if not output.is_relative_to(Path(ROOT) / "build"):
            ap.error("Keyboard build output must be under ROOT/build")
        game.cmake.append("SATURN_RUNTIME=" + (output / "pal-keyboard-runtime").as_posix())
        if a.what != "run":
            verify_options_runtime()
        original_inputs = build.inputs
        def keyboard_inputs(game):
            data = original_inputs(game)
            for path in [Path(ROOT)/"tools/winbuild.py", Path(ROOT)/"tools/pal_keyboard_profile.py", *sorted((Path(ROOT)/"src/pal_game").glob("pal_*.cpp")), *sorted((Path(ROOT)/"src/pal_game").glob("pal_*.h")), *sorted((Path(ROOT)/"patches").glob("*.patch"))]:
                data["PAL " + path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            return data
        build.inputs = keyboard_inputs
    build.stale = win_stale
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
