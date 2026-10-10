"""Subprocess helper: reuse upstream parser and validate its extraction paths.

Run only via the explicit --run-upstream workflow. No input files are written.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

# When invoked as a script, use only the selected checkout plus this project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pal_validate.core import InputError, safe_disc_path


def main() -> None:
    repo, image, out = map(Path, sys.argv[1:4])
    sys.path.insert(0, str(repo / "src"))
    from saturnrecomp.disc import Disc
    disc = Disc(str(image))
    paths = set()
    records = []
    # Traverse with the upstream listdir parser, keeping resource/cycle bounds.
    seen_directories = set()
    pending = [(disc.iso.root, 0)]
    while pending:
        directory, depth = pending.pop()
        key = (directory.lba, directory.size)
        if key in seen_directories or depth > 64:
            raise InputError("Repeated/cyclic or excessively deep ISO directory")
        seen_directories.add(key)
        for record in disc.iso.listdir(directory):
            if len(records) >= 100000:
                raise InputError("ISO exceeds the 100000-record safety limit")
            name = safe_disc_path(record.path)
            if name in paths:
                raise InputError(f"Duplicate extraction destination: {name}")
            paths.add(name)
            records.append({"path": record.path, "bytes": record.size,
                            "lba": record.lba, "directory": record.is_dir,
                            "cd_audio": disc.is_cdda(record)})
            if record.is_dir:
                pending.append((record, depth + 1))
    for record in records:
        if not record["directory"]:
            prefix = record["path"].lstrip("/") + "/"
            if any(name.startswith(prefix) for name in paths):
                raise InputError("A file is also used as an extraction directory")
    first = disc.iso.first_file()
    tracks = []
    if disc.tracks[0].is_audio:
        raise InputError("First track must contain Saturn data")
    if len({t.number for t in disc.tracks}) != len(disc.tracks):
        raise InputError("Duplicate track numbers")
    for track in disc.tracks:
        if track.mode not in {"MODE1/2048", "MODE1/2352", "MODE2/2352", "AUDIO"}:
            raise InputError(f"Unsupported upstream track mode: {track.mode}")
        if track.file_offset is None or track.file_offset < 0 or track.frames <= 0 or track.pregap < 0:
            raise InputError("Invalid track offset, length or pregap")
        if Path(track.path).stat().st_size % track.sector_size:
            raise InputError("Track file is not a whole number of sectors")
        tracks.append({"number": track.number, "mode": track.mode, "lba": track.lba,
                       "frames": track.frames, "pregap": track.pregap,
                       "file_offset": track.file_offset, "path": str(Path(track.path).resolve())})
    result = {
        "product": disc.ip.product, "version": disc.ip.version,
        "title": disc.ip.title, "areas": disc.ip.areas,
        "volume_id": disc.iso.volume_id, "records": records, "tracks": tracks,
        "first_read": {"path": first.path, "bytes": first.size,
                       "declared_load_address": f"0x{disc.ip.first_read_addr:08X}",
                       "declared_load_size": disc.ip.first_read_size,
                       "entry_address": None,
                       "proof_status": "header_declaration_only_not_runtime_entry_proof"},
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for file in disc._fh.values():
        file.close()
    print(f"Validated {len(records)} extraction paths; SH-2 entry proof remains unknown")


if __name__ == "__main__":
    main()
