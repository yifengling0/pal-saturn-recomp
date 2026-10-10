import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pal_validate.cli import main, verify_toolchain
from pal_validate.core import InputError, classify_extracted, cue_references, inventory, new_report, safe_disc_path
from pal_validate.walking import REQUIRED, summarize_csv


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        self.out = self.root / "output"

    def tearDown(self):
        self.temp.cleanup()

    def cue(self, name="track 01.bin", file_type="BINARY"):
        path = self.inputs / "test.cue"
        path.write_text(f'FILE "{name}" {file_type}\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n')
        return path

    def silent_main(self, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(args)


class InputTests(TemporaryCase):
    def test_missing_image_has_machine_report(self):
        self.assertEqual(2, self.silent_main(["prepare", "--out", str(self.out)]))
        result = json.loads((self.out / "report.json").read_text())
        self.assertEqual("blocked", result["stages"]["input_inventory"]["status"])
        self.assertFalse(result["claims"]["game_ported"])
        self.assertTrue(result["missing_inputs"])

    def test_missing_referenced_bin(self):
        with self.assertRaisesRegex(InputError, "missing"):
            cue_references(self.cue())

    def test_good_cue_with_spaces_and_stable_hash(self):
        track = self.inputs / "track 01.bin"
        track.write_bytes(b"synthetic fixture only")
        files, warnings = inventory(str(self.cue()), self.out)
        self.assertEqual(2, len(files))
        self.assertEqual(64, len(files[1]["sha256"]))
        self.assertEqual([], warnings)

    def test_cue_traversal_rejected(self):
        (self.root / "outside.bin").write_bytes(b"not an image")
        with self.assertRaises(InputError):
            cue_references(self.cue("../outside.bin"))

    def test_cue_absolute_path_rejected(self):
        with self.assertRaises(InputError):
            cue_references(self.cue("/tmp/outside.bin"))

    def test_cue_windows_drive_rejected(self):
        with self.assertRaises(InputError):
            cue_references(self.cue("C:\\dump.bin"))

    def test_cue_symlink_escape_rejected(self):
        outside = self.root / "outside.bin"
        outside.write_bytes(b"not an image")
        (self.inputs / "link.bin").symlink_to(outside)
        with self.assertRaisesRegex(InputError, "escapes"):
            cue_references(self.cue("link.bin"))

    def test_unsupported_file_type_rejected(self):
        with self.assertRaisesRegex(InputError, "syntax/type"):
            cue_references(self.cue(file_type="WAVE"))

    def test_explicit_pregap_not_silently_lost(self):
        (self.inputs / "track 01.bin").write_bytes(b"fixture")
        path = self.cue()
        path.write_text(path.read_text() + "    PREGAP 00:02:00\n")
        with self.assertRaisesRegex(InputError, "PREGAP"):
            cue_references(path)

    def test_empty_bin_rejected(self):
        (self.inputs / "track 01.bin").touch()
        with self.assertRaisesRegex(InputError, "empty"):
            cue_references(self.cue())

    def test_inventory_only_does_not_execute_upstream(self):
        image = self.inputs / "bare.bin"
        image.write_bytes(b"synthetic arbitrary bytes not SH2")
        with patch("pal_validate.cli.command") as run:
            self.assertEqual(0, self.silent_main(["prepare", "--image", str(image), "--out", str(self.out), "--input-kind", "synthetic"]))
        run.assert_not_called()
        result = json.loads((self.out / "report.json").read_text())
        self.assertTrue(result["input_hashes_unchanged"])
        self.assertEqual("unverified", result["pal1_identity_status"])
        self.assertEqual("not_run", result["stages"]["disc_extract"]["status"])
        self.assertFalse(result["synthetic_is_game_evidence"])

    def test_refuse_reuse_output_directory(self):
        self.out.mkdir()
        self.assertEqual(2, self.silent_main(["prepare", "--out", str(self.out)]))

    def test_output_inside_inputs_rejected(self):
        image = self.inputs / "bare.bin"
        image.write_bytes(b"fixture")
        with self.assertRaisesRegex(InputError, "outside"):
            inventory(str(image), self.inputs / "build")

    def test_bin_is_not_a_proven_module(self):
        self.out.mkdir()
        (self.out / "CODE.BIN").write_bytes(b"name is not proof")
        records = classify_extracted(self.out, "/CODE.BIN")
        self.assertEqual("unknown", records[0]["proof_status"])
        self.assertIsNone(records[0]["entry_address"])

    def test_path_safety(self):
        self.assertEqual("FOLDER/DATA.BIN", safe_disc_path("/FOLDER/DATA.BIN"))
        for bad in ("../bad", "/../bad", "/A//B", "//absolute", "/A/./B", "/C:/B", "/IP.BIN", "/bad\nname"):
            with self.subTest(path=bad), self.assertRaises(InputError):
                safe_disc_path(bad)

    def test_initial_report_never_claims_port(self):
        for kind in ("synthetic", "user_provided"):
            report = new_report(kind, "self declaration")
            self.assertFalse(any(report["claims"].values()))
            self.assertEqual("not_run", report["stages"]["sh2_module_entry_proof"]["status"])

    def test_upstream_requires_explicit_checkout(self):
        image = self.inputs / "bare.bin"
        image.write_bytes(b"fixture")
        self.assertEqual(3, self.silent_main(["prepare", "--image", str(image), "--out", str(self.out), "--run-upstream"]))
        result = json.loads((self.out / "report.json").read_text())
        self.assertEqual("failed", result["stages"]["toolchain_identity"]["status"])

    def test_missing_toolchain_is_error(self):
        with self.assertRaises(InputError):
            verify_toolchain(self.root / "absent")

    def test_source_mutation_cannot_return_success(self):
        image = self.inputs / "bare.bin"
        image.write_bytes(b"fixture")
        with patch("pal_validate.cli.describe_file", return_value={"changed": True}):
            self.assertEqual(3, self.silent_main(["prepare", "--image", str(image), "--out", str(self.out)]))


class WalkingTests(TemporaryCase):
    def capture(self, presents=(0, 1, 2, 3), missing=False, ticks=(0, 1, 2, 3), maps=None):
        rows = []
        for i, tick in enumerate(ticks):
            rows.append({"game_tick": tick, "vblank": i * 2, "world_x": "" if missing else i * 2,
                         "world_y": "" if missing else 0, "camera_x": i, "camera_y": 0,
                         "animation_frame": i // 2, "input": "RIGHT", "map_id": (maps or ["fixture"] * 4)[i],
                         "render_present_count": presents[i]})
        path = self.root / (str(presents[-1]) + str(missing) + ".csv")
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_fps_independence(self):
        slow = summarize_csv(self.capture((0, 1, 2, 3)), "synthetic")
        fast = summarize_csv(self.capture((0, 4, 8, 12)), "synthetic")
        self.assertEqual(slow["metrics"], fast["metrics"])
        self.assertNotEqual(slow["presentation_only"], fast["presentation_only"])
        self.assertEqual(2, slow["metrics"]["world"]["median_distance_per_tick"])
        self.assertFalse(slow["walking_bug_identified"])

    def test_unknown_world_position_stays_unavailable(self):
        result = summarize_csv(self.capture(missing=True), "synthetic")
        self.assertEqual("unavailable", result["metrics"]["world"]["status"])
        self.assertIsNone(result["metrics"]["world"]["median_distance_per_tick"])

    def test_logic_tick_reset_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increase"):
            summarize_csv(self.capture(ticks=(0, 1, 0, 1)), "synthetic")

    def test_capture_gaps_are_excluded(self):
        result = summarize_csv(self.capture(ticks=(0, 1, 4, 5)), "synthetic")
        self.assertEqual(1, result["excluded_tick_pairs"])
        self.assertEqual(2, result["metrics"]["world"]["eligible_tick_pairs"])

    def test_map_transition_is_excluded(self):
        result = summarize_csv(self.capture(maps=["a", "a", "b", "b"]), "synthetic")
        self.assertEqual(1, result["excluded_tick_pairs"])

    def test_nonfinite_coordinates_rejected(self):
        path = self.capture()
        # Explicitly write a nonfinite world coordinate independent of column order.
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["world_x"] = "nan"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED))
            writer.writeheader(); writer.writerows(rows)
        with self.assertRaisesRegex(ValueError, "finite"):
            summarize_csv(path, "synthetic")

    def test_missing_columns(self):
        path = self.root / "bad.csv"
        path.write_text("game_tick\n1\n2\n")
        with self.assertRaisesRegex(ValueError, "Missing CSV"):
            summarize_csv(path, "synthetic")


if __name__ == "__main__":
    unittest.main()
