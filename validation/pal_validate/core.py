"""Local, read-only input inventory and honest evidence classification."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PureWindowsPath

PIN = "086c372c67d9e0f94fcc64cedd6e6b63cc5542b5"
DISC_PY_SHA256 = "3a63f6c444677e5fb44f172de8331b6697def3c17c0f2be13ba5e973de220b6e"
STAGES = (
    "input_inventory", "toolchain_identity", "disc_structure", "disc_info",
    "disc_list", "disc_extract", "extracted_inventory", "sh2_module_entry_proof",
    "game_boot", "map_input", "walking_baseline", "native_ohos",
)


class InputError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe_file(path: Path) -> dict:
    before = path.stat()
    digest = sha256(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ):
        raise InputError(f"Input changed while hashing: {path}")
    return {"path": str(path), "bytes": after.st_size, "sha256": digest}


def cue_references(path: Path) -> list[Path]:
    """Only a FILE path safety scan; track/sector interpretation is upstream's job."""
    if path.stat().st_size > 1024 * 1024:
        raise InputError("CUE is over 1 MiB; refusing an unbounded metadata scan")
    root = path.parent.resolve()
    references = []
    for number, line in enumerate(path.read_text(encoding="latin-1").splitlines(), 1):
        line = line.strip()
        if re.match(r"(?i)^(PREGAP|POSTGAP)(?:\s|$)", line):
            raise InputError("Explicit PREGAP/POSTGAP is not interpreted by this pinned upstream parser; verify/normalize the dump layout separately")
        if not re.match(r"(?i)^FILE(?:\s|$)", line):
            continue
        match = re.fullmatch(r'FILE\s+(?:"([^"\r\n]+)"|(\S+))\s+BINARY', line)
        if not match:
            raise InputError(f"Unsupported CUE FILE syntax/type on line {number}; use BINARY and preserve filenames")
        name = match.group(1) or match.group(2)
        raw = Path(name)
        if raw.is_absolute() or PureWindowsPath(name).drive or "\\" in name:
            raise InputError(f"CUE line {number} must use a relative POSIX path inside its directory")
        if any(c in name for c in "\0\r\n") or any(part in ("..", ".") for part in name.split("/")):
            raise InputError(f"Unsafe CUE path on line {number}")
        resolved = (root / name).resolve()
        if not resolved.is_relative_to(root):
            raise InputError(f"CUE track escapes image directory on line {number}")
        if not resolved.is_file():
            raise InputError(f"Referenced track is missing or not a regular file: {name}")
        if resolved.stat().st_size == 0:
            raise InputError(f"Referenced track is empty: {name}")
        if resolved not in references:
            references.append(resolved)
    if not references:
        raise InputError("CUE has no supported FILE references")
    return references


def inventory(image: str | None, output: Path) -> tuple[list[dict], list[str]]:
    if not image:
        raise InputError("Missing input: supply your lawful Saturn PAL1 CUE plus every referenced BIN track")
    path = Path(image).expanduser().resolve()
    if not path.is_file():
        raise InputError(f"Input image is missing or not a regular file: {path}")
    if path.suffix.lower() not in (".cue", ".bin", ".iso"):
        raise InputError("Use .cue with all BIN tracks, or a verified single .bin/.iso")
    if path.stat().st_size == 0:
        raise InputError("Input image is empty")
    sources = [path] + (cue_references(path) if path.suffix.lower() == ".cue" else [])
    if any(p.is_relative_to(output.resolve()) for p in sources):
        raise InputError("Output directory must not contain input images")
    if output.resolve().is_relative_to(path.parent):
        raise InputError("Output directory must be outside the input image directory")
    warnings = [] if path.suffix.lower() == ".cue" else [
        "A standalone BIN/ISO cannot preserve missing CUE, track boundaries, pregaps or CD-DA; full-disc completeness remains unknown."
    ]
    return [describe_file(p) for p in sources], warnings


def safe_disc_path(name: str) -> str:
    """Check extraction destinations returned by upstream's ISO parser."""
    if not name.startswith("/") or name.startswith("//"):
        raise InputError(f"Invalid ISO path: {name!r}")
    parts = name[1:].split("/")
    if any(not p or p in (".", "..") for p in parts):
        raise InputError(f"Unsafe ISO path: {name!r}")
    if any(ord(c) < 32 or c in "\\:" for c in name):
        raise InputError(f"Unsafe ISO path characters: {name!r}")
    relative = "/".join(parts)
    if relative == "IP.BIN":
        raise InputError("ISO file IP.BIN would overwrite upstream's extracted boot header")
    return relative


def classify_extracted(path: Path, boot_path: str | None) -> list[dict]:
    result = []
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix()
        if relative == "IP.BIN":
            role = "disc_boot_header_not_proven_sh2_module"
        elif boot_path and relative == boot_path.lstrip("/"):
            role = "first_read_payload_candidate_not_proven_sh2_module"
        else:
            role = "opaque_disc_file_not_proven_sh2_module"
        result.append({**describe_file(item), "relative_path": relative,
                       "classification": role, "load_address": None,
                       "entry_address": None, "proof_status": "unknown"})
    return result


def new_report(kind: str, note: str | None) -> dict:
    return {
        "schema_version": 1,
        "purpose": "Linux feasibility evidence; not a completed PAL1 port",
        "input_kind": kind,
        "provenance": {"user_note": note, "note_is_self_declared": True,
                       "copyright_or_ownership_verified": False},
        "pal1_identity_status": "unverified",
        "synthetic_is_game_evidence": False,
        "stages": {stage: {"status": "not_run", "reason": "Prerequisite evidence is missing"} for stage in STAGES},
        "missing_inputs": [], "warnings": [], "commands": [],
        "claims": {"game_ported": False, "game_booted": False,
                   "walking_bug_identified": False, "walking_fix_validated": False,
                   "native_ohos_validated": False},
    }
