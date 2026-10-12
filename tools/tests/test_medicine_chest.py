"""Asset-free exact-scope and purity regression tests for the PAL medicine chest."""

from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def test_medicine_chest_exact_snapshot_guard():
    with tempfile.TemporaryDirectory(prefix="PAL medicine chest 空格 ") as folder:
        exe = Path(folder) / ("medicine-chest.exe" if os.name == "nt" else "medicine-chest")
        subprocess.run(
            [
                os.environ.get("CXX", "g++"),
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I" + str(ROOT / "src/pal_game"),
                str(ROOT / "tools/tests/medicine_chest_test.cpp"),
                "-o",
                str(exe),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run([str(exe)], check=True, capture_output=True)


def test_registered_medicine_chest_callback():
    with tempfile.TemporaryDirectory(prefix="PAL medicine callback 空格 ") as folder:
        folder = Path(folder)
        (folder / "saturn.h").write_text("#pragma once\nvoid sat_note(const char*, ...);\n")
        exe = folder / ("medicine-callback.exe" if os.name == "nt" else "medicine-callback")
        subprocess.run(
            [
                os.environ.get("CXX", "g++"),
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Werror",
                # This standalone test uses only a synthetic memory fixture.
                "-DPAL_MEDICINE_ASSETS_VERIFIED=1",
                "-I" + str(folder),
                "-I" + str(ROOT / "src/pal_game"),
                "-I" + str(ROOT / "third_party/saturn-recomp-pal/runtime/include"),
                str(ROOT / "tools/tests/medicine_chest_runtime_test.cpp"),
                str(ROOT / "src/pal_game/pal_medicine_chest.cpp"),
                "-o",
                str(exe),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run([str(exe)], check=True, capture_output=True)
