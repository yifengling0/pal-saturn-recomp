"""Exercise the real CMake gate using temporary copies of private disc assets.

No game data is embedded here. These integration tests explicitly skip when
the locally extracted original assets or CMake are unavailable.
"""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
ASSET_NAMES = ("PROG.BIN", "CM.NOR", "CM.IDX")
HOOK = (
    "    c.r[8] = 0x0604F210u; sh2_hook(c, 0x06028700u);  // 06028700 mov.l 0x06028720,r8\n"
    "    { const uint32_t x = c.r[8]; c.pr = 0x06028706u;"
)
STALE_CALL = HOOK.replace(" sh2_hook(c, 0x06028700u);", "")


def generated_source(hook=HOOK, copies=1):
    header = (
        "#include <cstdint>\n"
        "struct SH2Context { uint32_t r[16]; uint32_t pr; };\n"
        "void sh2_hook(SH2Context&, uint32_t);\n"
    )
    return header + "\n".join(
        f"void generated_call_{index}(SH2Context& c) {{\n" + hook
        + "\n        (void)x;\n    }\n}\n"
        for index in range(copies)
    )


class MedicineChestIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmake = shutil.which(os.environ.get("CMAKE", "cmake"))
        if not cls.cmake:
            raise unittest.SkipTest("CMake is unavailable; private-asset identity integration tests skipped")
        cls.originals = ROOT / "build/disc-extract"
        missing = [name for name in ASSET_NAMES if not (cls.originals / name).is_file()]
        if missing:
            raise unittest.SkipTest(
                "Locally extracted private PAL assets unavailable: " + ", ".join(missing)
            )

    def fixture(self, folder, sources=None, target="saturn", absolute_sources=False,
                have_recomp=True, decoy=False):
        root = Path(folder)
        layer = root / "src/pal_game"
        layer.mkdir(parents=True)
        shutil.copyfile(ROOT / "src/pal_game/pal_disc_identity.cmake",
                        layer / "pal_disc_identity.cmake")
        assets = root / "build/disc-extract"
        assets.mkdir(parents=True)
        for name in ASSET_NAMES:
            shutil.copyfile(self.originals / name, assets / name)

        selected = root / "selected-generation"
        selected.mkdir()
        if sources is None:
            sources = {"p_prog_000.cpp": generated_source()}
        for name, content in sources.items():
            (selected / name).write_text(content)
        selected_names = [
            (selected / name).as_posix() if absolute_sources else name
            for name in sources
        ]
        # CMake reads its own files as UTF-8; with absolute sources the fixture path lands inside
        # this file, and a cp936 write turns the 空格 directory name into a path that cannot open.
        (selected / "CMakeLists.txt").write_text(
            "add_library(recomp STATIC "
            + " ".join('"' + name + '"' for name in selected_names)
            + ")\n", encoding="utf-8"
        )
        # A matching generated source elsewhere must not validate the actual
        # linked generation, whether or not an unrelated target compiles it.
        if decoy:
            other = root / "build/recomp"
            other.mkdir()
            (other / "p_prog_999.cpp").write_text(generated_source())

        (root / "dummy.cpp").write_text("int main() { return 0; }\n")
        cmake = (
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(medicine_identity_fixture LANGUAGES CXX)\n"
            + ("add_subdirectory(selected-generation)\n" if have_recomp else "")
            + ("add_executable(saturn dummy.cpp)\n" if target == "saturn"
               else "add_library(main SHARED dummy.cpp)\n")
            + (f"target_link_libraries({target} PRIVATE recomp)\n" if have_recomp else "")
            + ("add_library(unlinked_decoy STATIC build/recomp/p_prog_999.cpp)\n" if decoy else "")
            + f"set(PAL_GAME_TARGET {target})\n"
            + "include(src/pal_game/pal_disc_identity.cmake)\n"
            + f"get_target_property(definitions {target} COMPILE_DEFINITIONS)\n"
            + 'file(WRITE "${CMAKE_BINARY_DIR}/definitions.txt" "${definitions}")\n'
        )
        (root / "CMakeLists.txt").write_text(cmake, encoding="utf-8")
        return root

    def configure(self, root):
        return subprocess.run(
            [self.cmake, "-S", str(root), "-B", str(root / "out")],
            # A Chinese Windows console hands cmake/ninja diagnostics back in cp936; a strict
            # UTF-8 reader thread then dies and the whole stream arrives as None.
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
        )

    def build(self, root):
        return subprocess.run(
            [self.cmake, "--build", str(root / "out")],
            # A Chinese Windows console hands cmake/ninja diagnostics back in cp936; a strict
            # UTF-8 reader thread then dies and the whole stream arrives as None.
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
        )

    def assert_initial_build_succeeds(self, root):
        configured = self.configure(root)
        self.assertEqual(configured.returncode, 0, configured.stdout + configured.stderr)
        built = self.build(root)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)

    def assert_build_rejected(self, root, diagnostic):
        # Deliberately do not configure again: the generated build system must
        # discover the changed identity dependency and rerun the real gate.
        result = self.build(root)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(diagnostic, output)

    def assert_rejected(self, root, diagnostic):
        result = self.configure(root)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(diagnostic, output)
        self.assertFalse((root / "out/definitions.txt").exists())

    def test_missing_each_original_asset(self):
        for name in ASSET_NAMES:
            with self.subTest(asset=name), tempfile.TemporaryDirectory(prefix="PAL missing asset 空格 ") as folder:
                root = self.fixture(folder)
                (root / "build/disc-extract" / name).unlink()
                self.assert_rejected(root, "requires original extracted asset")

    def test_corrupt_each_original_asset(self):
        for name in ASSET_NAMES:
            with self.subTest(asset=name), tempfile.TemporaryDirectory(prefix="PAL wrong asset 空格 ") as folder:
                root = self.fixture(folder)
                asset = root / "build/disc-extract" / name
                content = bytearray(asset.read_bytes())
                content[len(content) // 2] ^= 1
                asset.write_bytes(content)
                self.assert_rejected(root, f"identity mismatch: {name}")

    def test_missing_actual_recomp_target(self):
        with tempfile.TemporaryDirectory(prefix="PAL no recomp 空格 ") as folder:
            root = self.fixture(folder, have_recomp=False)
            self.assert_rejected(root, "requires the actual recomp target")

    def test_stale_linked_generation_without_hook(self):
        with tempfile.TemporaryDirectory(prefix="PAL stale generation 空格 ") as folder:
            root = self.fixture(folder, sources={"p_prog_000.cpp": generated_source(STALE_CALL)})
            self.assert_rejected(root, "hook missing or duplicated in actual recomp target")

    def test_unlinked_decoy_hook_does_not_validate_linked_generation(self):
        with tempfile.TemporaryDirectory(prefix="PAL decoy generation 空格 ") as folder:
            root = self.fixture(
                folder, sources={"p_prog_000.cpp": generated_source(STALE_CALL)}, decoy=True,
            )
            self.assert_rejected(root, "hook missing or duplicated in actual recomp target")

    def test_duplicate_hook_in_separate_linked_sources(self):
        with tempfile.TemporaryDirectory(prefix="PAL duplicated sources 空格 ") as folder:
            root = self.fixture(folder, sources={
                "p_prog_000.cpp": generated_source(),
                "p_prog_001.cpp": generated_source(),
            })
            self.assert_rejected(root, "hook missing or duplicated in actual recomp target")

    def test_duplicate_hook_in_one_linked_source(self):
        with tempfile.TemporaryDirectory(prefix="PAL duplicated source 空格 ") as folder:
            root = self.fixture(folder, sources={
                "p_prog_000.cpp": generated_source(copies=2),
            })
            self.assert_rejected(root, "hook missing or duplicated in actual recomp target")

    def test_one_hook_on_actual_desktop_and_harmony_targets(self):
        for target, absolute_sources in (("saturn", False), ("main", True)):
            with self.subTest(target=target), tempfile.TemporaryDirectory(prefix="PAL verified gate 空格 ") as folder:
                root = self.fixture(folder, target=target, absolute_sources=absolute_sources, decoy=True)
                result = self.configure(root)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(
                    (root / "out/definitions.txt").read_text(),
                    "PAL_MEDICINE_ASSETS_VERIFIED=1",
                )

    def test_build_rechecks_asset_changed_after_successful_configure(self):
        with tempfile.TemporaryDirectory(prefix="PAL changed asset rebuild 空格 ") as folder:
            root = self.fixture(folder)
            self.assert_initial_build_succeeds(root)
            asset = root / "build/disc-extract/CM.NOR"
            content = bytearray(asset.read_bytes())
            content[len(content) // 2] ^= 1
            asset.write_bytes(content)
            self.assert_build_rejected(root, "identity mismatch: CM.NOR")

    def test_build_rechecks_hook_removed_after_successful_configure(self):
        with tempfile.TemporaryDirectory(prefix="PAL changed hook rebuild 空格 ") as folder:
            root = self.fixture(folder)
            self.assert_initial_build_succeeds(root)
            (root / "selected-generation/p_prog_000.cpp").write_text(generated_source(STALE_CALL))
            self.assert_build_rejected(root, "hook missing or duplicated in actual recomp target")


if __name__ == "__main__":
    unittest.main()
