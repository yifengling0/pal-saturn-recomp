"""Metrics are per observed game logic tick, independent of presentation FPS."""
from __future__ import annotations
import csv
import math
from pathlib import Path
import statistics

REQUIRED = {"game_tick", "vblank", "world_x", "world_y", "camera_x", "camera_y",
            "animation_frame", "input", "map_id", "render_present_count"}


def finite(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Coordinates must be finite numbers or blank")
    return result


def summarize_csv(path: Path, kind: str) -> dict:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing CSV columns: {sorted(REQUIRED - set(reader.fieldnames or []))}")
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError("At least two samples are needed")
    for row in rows:
        row["game_tick"] = int(row["game_tick"])
        row["vblank"] = int(row["vblank"])
        row["render_present_count"] = int(row["render_present_count"])
        if min(row["game_tick"], row["vblank"], row["render_present_count"]) < 0:
            raise ValueError("Ticks, VBlanks and presentation counters cannot be negative")
        for key in ("world_x", "world_y", "camera_x", "camera_y"):
            row[key] = finite(row[key])
    pairs = list(zip(rows, rows[1:]))
    for a, b in pairs:
        if b["game_tick"] <= a["game_tick"]:
            raise ValueError("game_tick must strictly increase; unwrap/reset and segment captures first")
        if b["vblank"] < a["vblank"] or b["render_present_count"] < a["render_present_count"]:
            raise ValueError("VBlank and presentation counters must not decrease")
    # Never measure travel across map loads, changed input or gaps in capture.
    segments = [(a, b) for a, b in pairs if b["game_tick"] == a["game_tick"] + 1
                and a["map_id"] == b["map_id"] and a["input"] == b["input"]]
    metrics = {}
    for prefix in ("world", "camera"):
        distances = []
        vectors = []
        for a, b in segments:
            values = [r[f"{prefix}_{axis}"] for r in (a, b) for axis in ("x", "y")]
            if None in values:
                continue
            dx, dy = b[f"{prefix}_x"] - a[f"{prefix}_x"], b[f"{prefix}_y"] - a[f"{prefix}_y"]
            vectors.append([dx, dy])
            distances.append(math.hypot(dx, dy))
        metrics[prefix] = {
            "status": "measured" if distances else "unavailable",
            "units": "observed_coordinate_units_per_game_logic_tick",
            "eligible_tick_pairs": len(distances),
            "deltas_xy_per_tick": vectors,
            "median_distance_per_tick": statistics.median(distances) if distances else None,
            "mean_distance_per_tick": statistics.mean(distances) if distances else None,
            "path_length_observed": sum(distances) if distances else None,
            "zero_delta_fraction": sum(d == 0 for d in distances) / len(distances) if distances else None,
        }
    animation = [(a, b) for a, b in segments if a["animation_frame"] and b["animation_frame"]]
    metrics["animation"] = {
        "status": "measured" if animation else "unavailable",
        "eligible_tick_pairs": len(animation),
        "transition_count": sum(a["animation_frame"] != b["animation_frame"] for a, b in animation),
        "transition_fraction_per_tick": (sum(a["animation_frame"] != b["animation_frame"] for a, b in animation) / len(animation)) if animation else None,
    }
    return {
        "schema_version": 1, "input_kind": kind,
        "synthetic_is_game_evidence": False,
        "samples": len(rows), "game_tick_span": rows[-1]["game_tick"] - rows[0]["game_tick"],
        "excluded_tick_pairs": len(pairs) - len(segments),
        "exclusion_policy": "Exclude nonconsecutive game ticks, map transitions, and changed input",
        "metrics": metrics,
        "presentation_only": {"vblank_span": rows[-1]["vblank"] - rows[0]["vblank"],
                              "render_present_span": rows[-1]["render_present_count"] - rows[0]["render_present_count"]},
        "limits": ["CSV origin and memory-coordinate meaning must be verified separately",
                   "A zero world delta can be normal collision, idle or a low-rate update; it is not a diagnosis",
                   "Animation labels are opaque; a transition count alone does not establish cycle length",
                   "No root cause, correct speed, baseline match or fix is inferred"],
        "walking_bug_identified": False, "walking_fix_validated": False,
    }
