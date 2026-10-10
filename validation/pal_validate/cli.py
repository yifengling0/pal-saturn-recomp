from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .core import (DISC_PY_SHA256, PIN, InputError, classify_extracted,
                   describe_file, inventory, new_report, sha256)
from .walking import summarize_csv


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(report: dict, name: str, argv: list[str], out: Path,
            timeout: int, env: dict | None = None) -> None:
    stdout, stderr = out / "logs" / f"{name}.stdout.txt", out / "logs" / f"{name}.stderr.txt"
    start = time.monotonic()
    record = {"stage": name, "argv": argv, "cwd": str(out),
              "stdout": str(stdout), "stderr": str(stderr)}
    report["commands"].append(record)
    try:
        with stdout.open("wb") as so, stderr.open("wb") as se:
            done = subprocess.run(argv, cwd=out, env=env, stdout=so, stderr=se,
                                  timeout=timeout, check=False)
        record["returncode"] = done.returncode
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        if done.returncode:
            raise InputError(f"{name} exited {done.returncode}; see {stderr}")
    except subprocess.TimeoutExpired:
        record["returncode"] = None
        record["timed_out"] = True
        raise InputError(f"{name} exceeded {timeout} seconds; see logs") from None


def verify_toolchain(repo: Path) -> dict:
    if not (repo / "src/saturnrecomp/disc.py").is_file():
        raise InputError("Toolchain checkout does not contain src/saturnrecomp/disc.py")
    git = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo)]
    head = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True, timeout=20).strip()
    if head != PIN:
        raise InputError(f"Toolchain pin mismatch: expected {PIN}, got {head}")
    dirty = subprocess.check_output(git + ["status", "--porcelain", "--untracked-files=no"], text=True, timeout=20)
    if dirty.strip():
        raise InputError("Toolchain has tracked changes; use the verified clean pinned checkout")
    digest = sha256(repo / "src/saturnrecomp/disc.py")
    if digest != DISC_PY_SHA256:
        raise InputError("Upstream disc.py hash does not match the reviewed CLI")
    return {"repository": "https://github.com/callumjenkins/saturn-recomp",
            "commit": head, "checkout": str(repo), "disc_py_sha256": digest,
            "cli": "python -m saturnrecomp.disc IMAGE --info | --list | --extract DIR"}


def prepare(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser().resolve()
    if out.exists():
        print("Refusing to reuse an output directory; choose a new run directory", file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    (out / "logs").mkdir()
    report = new_report(args.input_kind, args.provenance_note)
    report["created_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["output_directory"] = str(out)
    active = "input_inventory"
    files = []
    exit_code = 0
    try:
        files, warnings = inventory(args.image, out)
        report["input_files"] = files
        report["warnings"].extend(warnings)
        report["stages"][active] = {"status": "passed", "reason": "Input files readable; SHA-256 recorded"}
        if args.input_kind == "synthetic":
            report["warnings"].append("SYNTHETIC INPUT: no stage establishes PAL1 game compatibility")
        elif not args.provenance_note:
            report["warnings"].append("No provenance note supplied; ownership and PAL1 identity remain unverified")
        report["missing_inputs"] = [
            "Independent confirmation of this image's PAL1 edition/product identity and provenance",
            "Evidence-backed SH-2 module boundaries, load addresses and entry points",
            "Actual PAL1 boot, playable map and input replay evidence",
            "Reference and recompiled walking captures aligned by verified game logic ticks",
        ]
        if not args.run_upstream:
            report["stages"]["toolchain_identity"] = {"status": "not_run", "reason": "Pass --run-upstream with --toolchain to run the reviewed pinned source"}
        else:
            active = "toolchain_identity"
            if not args.toolchain:
                raise InputError("--run-upstream requires --toolchain CHECKOUT")
            repo = Path(args.toolchain).expanduser().resolve()
            report["toolchain"] = verify_toolchain(repo)
            report["stages"][active] = {"status": "passed", "reason": "Clean pinned checkout and reviewed disc.py hash verified"}
            env = dict(os.environ, PYTHONPATH=str(repo / "src"), PYTHONNOUSERSITE="1",
                       PYTHONDONTWRITEBYTECODE="1")
            image = files[0]["path"]
            active = "disc_structure"
            command(report, active, [sys.executable, "-S", str(Path(__file__).with_name("upstream_probe.py")),
                                    str(repo), image, str(out / "disc_structure.json")], out, args.timeout, env)
            structure = json.loads((out / "disc_structure.json").read_text())
            report["disc_identity_observed"] = {k: structure[k] for k in ("product", "version", "title", "areas", "volume_id")}
            report["first_read_declaration"] = structure["first_read"]
            report["stages"][active] = {"status": "passed", "reason": "Upstream parser validated disc and safe extraction paths; identity not independently verified"}
            for active, extra in (("disc_info", ["--info"]), ("disc_list", ["--list"]),
                                  ("disc_extract", ["--extract", str(out / "extract")])):
                command(report, active, [sys.executable, "-S", "-m", "saturnrecomp.disc", image, *extra], out, args.timeout, env)
                report["stages"][active] = {"status": "passed", "reason": "Verified upstream CLI completed; see command log"}
            active = "extracted_inventory"
            for record in structure["records"]:
                if not record["directory"] and not record["cd_audio"]:
                    extracted_path = out / "extract" / record["path"].lstrip("/")
                    if extracted_path.stat().st_size != record["bytes"]:
                        raise InputError(f"Extracted size mismatch (possibly truncated input): {record['path']}")
            extracted = classify_extracted(out / "extract", structure["first_read"]["path"])
            write_json(out / "extracted_inventory.json", extracted)
            report["stages"][active] = {"status": "passed", "reason": f"{len(extracted)} files hashed; every SH-2 module/entry remains unproven"}
            report["stages"]["sh2_module_entry_proof"] = {"status": "blocked", "reason": "Extracted data and IP load declarations alone cannot prove executable entry or module boundaries"}
    except (InputError, OSError, ValueError, subprocess.SubprocessError) as exc:
        report["stages"][active] = {"status": "blocked" if active == "input_inventory" else "failed", "reason": str(exc)}
        if active == "input_inventory":
            report["missing_inputs"].append(str(exc))
        exit_code = 2 if active == "input_inventory" else 3
    finally:
        if files:
            try:
                unchanged = all(describe_file(Path(f["path"])) == f for f in files)
                report["input_hashes_unchanged"] = unchanged
                if not unchanged:
                    report["warnings"].append("INPUTS CHANGED: do not rely on this run; recapture from stable read-only inputs")
                    exit_code = 3
            except (OSError, InputError) as exc:
                report["input_hashes_unchanged"] = False
                report["warnings"].append(f"Input recheck failed: {exc}")
                exit_code = 3
        write_json(out / "report.json", report)
        print(f"Evidence report: {out / 'report.json'}")
        print("PAL1 game port, boot and walking fix: NOT VALIDATED")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-first Linux Saturn PAL1 feasibility harness")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Inventory lawful user inputs, optionally run pinned upstream disc tools")
    prep.add_argument("--image", help="CUE with all referenced BIN files, or standalone BIN/ISO")
    prep.add_argument("--out", required=True, help="New isolated output directory outside the image directory")
    prep.add_argument("--input-kind", choices=("user_provided", "synthetic"), default="user_provided")
    prep.add_argument("--provenance-note", help="Local record of image edition/dump origin; no upload occurs")
    prep.add_argument("--run-upstream", action="store_true", help="Execute the reviewed, pinned upstream source")
    prep.add_argument("--toolchain", help="Path to the clean pinned saturn-recomp checkout")
    prep.add_argument("--timeout", type=int, default=180, help="Seconds per upstream command (default 180)")
    walk = sub.add_parser("walking", help="Summarize already captured logical-tick observations; never infer a bug/fix")
    walk.add_argument("--csv", required=True)
    walk.add_argument("--out", required=True, help="New JSON report; must not already exist")
    walk.add_argument("--input-kind", required=True, choices=("synthetic", "reference_capture", "recompiled_capture"))
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.timeout <= 0:
            parser.error("--timeout must be positive")
        return prepare(args)
    target = Path(args.out).expanduser().resolve()
    if target.exists():
        parser.error("Walking output already exists; select a new file")
    try:
        result = summarize_csv(Path(args.csv), args.input_kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target, result)
    except (OSError, ValueError) as exc:
        print(f"Walking input error: {exc}", file=sys.stderr)
        return 2
    print(f"Walking measurement report: {target}; no root cause or fix is inferred")
    return 0
