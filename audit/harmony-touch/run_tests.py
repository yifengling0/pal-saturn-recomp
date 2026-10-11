#!/usr/bin/env python3
"""Portable Linux C++17 host tests; no window, audio device or OHOS hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", metavar="PATH",
                        help="Alternative positional form: RUNTIME SDL_PREFIX")
    parser.add_argument("--runtime", type=Path, help="Patched runtime root")
    parser.add_argument("--sdl-prefix", type=Path,
                        help="Native SDL3 prefix with include/SDL3 and lib")
    parser.add_argument("--build-dir", type=Path,
                        help="All binaries, logs and test INI files go here; default: new temporary directory")
    parser.add_argument("--fonts-dir", type=Path,
                        help="Also run Chinese/English actual-font bounds tests; directory containing generated inter_regular.h and inter_semibold.h")
    parser.add_argument("--cxx", default=os.environ.get("CXX", "c++"),
                        help="C++17 compiler command (default: CXX or c++)")
    args = parser.parse_args()
    if args.paths:
        if len(args.paths) != 2 or args.runtime is not None or args.sdl_prefix is not None:
            parser.error("use either --runtime/--sdl-prefix or exactly two positional paths")
        args.runtime, args.sdl_prefix = map(Path, args.paths)
    if args.runtime is None or args.sdl_prefix is None:
        parser.error("--runtime and --sdl-prefix are required (or supply both positional paths)")
    runtime, prefix = args.runtime.resolve(), args.sdl_prefix.resolve()
    fonts = args.fonts_dir.resolve() if args.fonts_dir else None
    required = [runtime / "src/host/host.cpp", runtime / "src/host/settings.cpp",
                runtime / "src/host/touch_mobile_layout.h", runtime / "src/host/touch_positions.h",
                prefix / "include/SDL3/SDL.h"]
    if fonts:
        required += [fonts / "inter_regular.h", fonts / "inter_semibold.h",
                     runtime / "src/host/ui.cpp", runtime / "third_party/stb/stb_truetype.h",
                     runtime / "third_party/pal-menu-cjk/glyphs.h"]
    for path in required:
        if not path.is_file():
            parser.error(f"missing required source/header: {path}")
    if not (prefix / "lib").is_dir():
        parser.error(f"missing SDL library directory: {prefix / 'lib'}")
    out = args.build_dir.resolve() if args.build_dir else Path(tempfile.mkdtemp(prefix="harmony-touch-"))
    if out == here or here in out.parents or out == runtime or runtime in out.parents:
        parser.error("choose a build directory outside both the test source tree and the runtime")
    out.mkdir(parents=True, exist_ok=True)
    # Reusing an owned build directory must never leave a stale passing manifest
    # after a failed or interrupted new run. No output directory is deleted.
    manifest_path = out / "tested-manifest.json"
    manifest_path.write_text(json.dumps({"status": "running"}) + "\n")
    (out / "commands.json").write_text("[]\n")
    print(f"Build/test output: {out}", flush=True)
    cxx = shlex.split(args.cxx)
    if not cxx:
        parser.error("empty compiler command")
    flags = ["-std=c++17", "-O2", "-pthread"]
    includes = [runtime / p for p in ["include", "src/host", "src/machine", "src/video", "src/sound"]]
    includes += [prefix / "include"]
    include_flags = ["-I" + str(path) for path in includes]
    # Resolve host.cpp through the explicit runtime include directory, never a bundled copy.
    host_flags = ['-DHOST_SOURCE="host.cpp"', "-ffunction-sections", "-fdata-sections"]
    link = ["-Wl,--gc-sections", "-L" + str(prefix / "lib"),
            "-Wl,-rpath," + str(prefix / "lib"), "-lSDL3"]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(prefix / "lib") + (
        os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    commands = []

    def run(command, name):
        commands.append({"name": name, "argv": list(map(str, command))})
        print(f"[{name}]", flush=True)
        try:
            result = subprocess.run(command, cwd=out, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as error:
            manifest_path.write_text(json.dumps({"status": "failed", "stage": name,
                                                "error": str(error)}) + "\n")
            raise SystemExit(f"{name}: {error}") from error
        (out / (name + ".log")).write_text(result.stdout)
        (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        print(result.stdout, end="", flush=True)
        if result.returncode:
            manifest_path.write_text(json.dumps({"status": "failed", "stage": name,
                                                "returncode": result.returncode}) + "\n")
            raise SystemExit(f"{name} failed ({result.returncode}); see {out / (name + '.log')}")

    for stem in ["geometry", "position"]:
        binary = out / (stem + "-tests")
        run(cxx + flags + include_flags + [str(here / (stem + "_tests.cpp")), "-o", str(binary)], "build-" + stem)
        run([str(binary)], stem)
    binary = out / "actual-host-tests"
    run(cxx + flags + ["-DPAL_OHOS_DEFAULTS=1"] + host_flags + include_flags +
        [str(here / "actual_host_tests.cpp"), str(runtime / "src/host/settings.cpp")] +
        link + ["-o", str(binary)], "build-actual-host")
    run([str(binary), str(out / "tmp/host")], "actual-host")
    binary = out / "discovery-desktop"
    run(cxx + flags + ["-DPAL_TEST_DISCOVERY_ONLY=1"] + host_flags + include_flags +
        [str(here / "actual_host_tests.cpp"), str(runtime / "src/host/settings.cpp")] +
        link + ["-o", str(binary)], "build-discovery-desktop")
    run([str(binary), str(out / "tmp/desktop-host")], "discovery-desktop")
    for mode, default in [("desktop", "original"), ("ohos", "fit")]:
        defs = ["-DPAL_OHOS_DEFAULTS=1"] if mode == "ohos" else []
        binary = out / ("settings-" + mode)
        run(cxx + flags + defs + include_flags + [str(here / "settings_tests.cpp"),
            str(runtime / "src/host/settings.cpp"), "-o", str(binary)], "build-settings-" + mode)
        run([str(binary), str(out / "tmp" / mode), "presentation", default, "55"], "settings-" + mode)
    if fonts:
        for mode in ["chinese", "desktop"]:
            defs = ["-DPAL_OHOS_DEFAULTS=1"] if mode == "chinese" else []
            binary = out / ("text-" + mode)
            run(cxx + flags + defs + host_flags + include_flags +
                ["-I" + str(fonts), "-I" + str(runtime / "third_party/stb"),
                 str(here / "host_text_bounds_v3.cpp"), str(runtime / "src/host/settings.cpp"),
                 str(runtime / "src/host/ui.cpp")] + link + ["-o", str(binary)], "build-text-" + mode)
            run([str(binary)], "text-" + mode)
    else:
        print("Actual-font bounds tests NOT RUN (enable with --fonts-dir).")
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"status": "passed", "audit_sources": {p.name: sha(p) for p in sorted(here.iterdir()) if p.is_file()},
                "runtime_host_sources": {str(p.relative_to(runtime)): sha(p)
                    for p in sorted((runtime / "src/host").iterdir()) if p.suffix in (".h", ".cpp")},
                "font_tests": bool(fonts)}
    if fonts:
        manifest["font_inputs"] = {p.name: sha(p) for p in [fonts / "inter_regular.h", fonts / "inter_semibold.h"]}
        manifest["cjk_inputs"] = {p.name: sha(p) for p in sorted((runtime / "third_party/pal-menu-cjk").glob("*.h"))}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS: 4 core source suites (settings compiled for desktop and OHOS defaults).")
    print("No OHOS SDK/HAP, native view, real density/safe-area or device input/audio claim.")
    print(f"Tested host.cpp SHA256: {sha(runtime / 'src/host/host.cpp')}")


if __name__ == "__main__":
    main()
