"""Regression for the explicitly seeded PAL default callback, without game assets.

Run from the project root:
    python -m pytest -q tools/tests/test_default_callback_seed.py

Optional environment overrides:
    PAL_SATURN_PROJECT_ROOT: project containing tools/seeds.json
    PAL_SATURN_UPSTREAM: checkout of saturn-recomp (default: third_party/saturn-recomp)
    PAL_SATURN_CXX: one g++/clang++ compatible executable (no shell arguments)

The discovery fixture targets upstream pin 086c372. Its 96 bytes are hand-authored
SH-2 test instructions, not extracted game code. Generated files and executables
use pytest's temporary directory. Missing upstream/compiler skips only dependent
tests, with a reason; a failed available generator/compiler is a real failure.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys

import pytest


PROJECT = Path(os.environ.get("PAL_SATURN_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
TARGET = 0x0605D66C
BASE = 0x06004000
DEFAULT = BASE + 0x0C
DECOY = BASE + 0x30


def test_project_registers_default_callback_exactly_once():
    path = PROJECT / "tools" / "seeds.json"
    assert path.is_file(), "Project seeds not found; set PAL_SATURN_PROJECT_ROOT: " + str(path)
    seeds = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(seeds.get("PROG"), list), "PROG needs an explicit seed list"
    parsed = {module: [int(value, 16) for value in values] for module, values in seeds.items()}
    assert parsed["PROG"].count(TARGET) == 1, "PROG must explicitly seed 0605D66C exactly once"
    assert not any(TARGET in values for module, values in parsed.items() if module != "PROG"), (
        "0605D66C belongs only to PROG, not another overlay"
    )


@pytest.fixture(scope="module")
def upstream():
    path = Path(os.environ.get("PAL_SATURN_UPSTREAM", PROJECT / "third_party" / "saturn-recomp"))
    needed = (
        "src/saturnrecomp/recomp/__main__.py",
        "src/saturnrecomp/recomp/discover.py",
        "runtime/include/saturn/sh2.h",
        "runtime/src/core/core.cpp",
    )
    missing = [name for name in needed if not (path / name).is_file()]
    if missing:
        pytest.skip("Pinned saturn-recomp unavailable; set PAL_SATURN_UPSTREAM: " + ", ".join(missing))
    return path.resolve()


def _run(command, *, env=None, expected=0, timeout=60):
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == expected, (
        "Command: " + repr(command) + "\nexit=" + str(result.returncode)
        + "\nstdout:\n" + result.stdout + "\nstderr:\n" + result.stderr
    )
    return result


def _fixture_bytes():
    blob = bytearray(0x60)

    def instructions(offset, words):
        for index, word in enumerate(words):
            start = offset + index * 2
            blob[start:start + 2] = word.to_bytes(2, "big")

    # Setter: tst r4,r4; bf/s return; mov r4,r0; mova default,r0;
    #         rts; mov.l r0,@(20,gbr). Then default: rts;nop.
    instructions(0x00, [0x2448, 0x8F01, 0x6043, 0xC701, 0x000B, 0xC205, 0x000B, 0x0009])
    # Explicitly seeded non-default callback: mov #7,r8; rts;nop.
    instructions(0x20, [0xE807, 0x000B, 0x0009])
    # Unreferenced rts;nop must NOT be swept into the entry table.
    instructions(0x30, [0x000B, 0x0009])
    # Save PR; load GBR+20; jsr @r0;nop; restore PR; rts;nop.
    instructions(0x40, [0x4F22, 0xC605, 0x400B, 0x0009, 0x4F26, 0x000B, 0x0009])
    return bytes(blob)


@pytest.fixture(scope="module")
def generated(tmp_path_factory, upstream):
    work = tmp_path_factory.mktemp("default-callback")
    image = work / "fixture.bin"
    image.write_bytes(_fixture_bytes())
    env = dict(os.environ)
    env["PYTHONPATH"] = str(upstream / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    outputs = {}
    for label, extra in (("red", []), ("green", [DEFAULT])):
        seeds = extra + [BASE + 0x20, BASE + 0x40]
        out = work / label
        spec = "FIXTURE=" + str(image) + "@06004000+" + ",".join(f"{value:08X}" for value in seeds)
        _run([sys.executable, "-m", "saturnrecomp.recomp", "--out", str(out), spec], env=env)
        outputs[label] = out
    return outputs


def _entries(out):
    table = (out / "p_fixture_table.cpp").read_text(encoding="utf-8")
    return [int(value, 16) for value in re.findall(r"\{0x([0-9A-F]+)u, f_", table)]


def test_single_seed_adds_only_the_default_entry(generated):
    red, green = (_entries(generated[label]) for label in ("red", "green"))
    assert red == [BASE, BASE + 0x20, BASE + 0x40]
    assert green == [BASE, DEFAULT, BASE + 0x20, BASE + 0x40]
    assert DEFAULT not in red and DEFAULT in green
    assert DECOY not in red and DECOY not in green


@pytest.fixture(scope="module")
def compiler():
    requested = os.environ.get("PAL_SATURN_CXX")
    command = shutil.which(requested) if requested else (shutil.which("g++") or shutil.which("clang++"))
    if command is None:
        pytest.skip("C++ compiler unavailable; set PAL_SATURN_CXX to a g++/clang++ compatible executable")
    return command


HARNESS = r'''
#include "p_fixture_funcs.h"
#include <cstdio>
#include <cstring>
#include <stdexcept>
struct Unknown { uint32_t addr, pr; };
// Deliberately strict service boundary: never turn an unknown callback into success.
void sh2_call_unknown(SH2Context& c, uint32_t a) { throw Unknown{a, c.pr}; }
void sh2_program_start(SH2Context&, uint32_t) { throw std::runtime_error("unexpected program start"); }
void sh2_bad_return(SH2Context&, uint32_t) { throw std::runtime_error("bad return"); }
void sh2_poll(SH2Context&) { throw std::runtime_error("unexpected poll"); }
uint32_t sh2_mmio_read(uint32_t, int) { throw std::runtime_error("unexpected MMIO read"); }
void sh2_mmio_write(uint32_t, uint32_t, int) { throw std::runtime_error("unexpected MMIO write"); }
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
int main(int argc, char**) {
    const bool seeded = argc > 1;
    sh2_activate(&p_fixture::module);
    SH2Context c{};
    c.gbr = 0x060FFC00; c.r[15] = 0x060FFA00; c.budget = 10000;
    c.pr = 0x01234560; c.r[4] = 0;
    p_fixture::f_06004000(c);
    check(ld32(c.gbr + 20) == 0x0600400C && c.pc == 0x01234560, "setter or delay slot");
    check(sh2_lookup(0x06004030) == nullptr, "unseeded decoy registered");
    bool trapped = false;
    c.pr = 0x01234560;
    try { p_fixture::f_06004040(c); }
    catch (const Unknown& error) {
        trapped = true;
        check(error.addr == 0x0600400C && error.pr == 0x06004048, "wrong red failure");
    }
    if (!seeded) {
        check(trapped, "baseline should fail");
        std::puts("RED: unknown default callback at 0600400C, PR 06004048");
        return 11;
    }
    check(!trapped && c.pc == 0x01234560, "seeded dispatcher return");
    SH2Context before = c;
    c.pr = 0x060600E8; before.pr = c.pr; before.pc = c.pr;
    uint8_t saved[0x400];
    std::memcpy(saved, g_wram_h + 0xFFC00, sizeof(saved));
    sh2_call(c, 0x0600400C);
    check(std::memcmp(&before, &c, sizeof(c)) == 0, "no-op altered guest state");
    check(std::memcmp(saved, g_wram_h + 0xFFC00, sizeof(saved)) == 0, "no-op altered memory");
    c.r[4] = 0x06004020; c.pr = 0x01234560;
    p_fixture::f_06004000(c);
    check(ld32(c.gbr + 20) == 0x06004020, "non-null callback overwritten");
    c.pr = 0x01234560;
    p_fixture::f_06004040(c);
    check(c.r[8] == 7 && c.pc == 0x01234560, "non-null callback or return failed");
    c.r[4] = 0x06004030; c.pr = 0x01234560;
    p_fixture::f_06004000(c);
    trapped = false;
    try { p_fixture::f_06004040(c); }
    catch (const Unknown& error) {
        trapped = true;
        check(error.addr == 0x06004030, "wrong strict failure");
    }
    check(trapped, "invalid callback should remain strict");
    std::puts("GREEN: default state/return, non-null callback, and strict unknown dispatch passed");
}
'''


@pytest.mark.parametrize("label,expected", [("red", 11), ("green", 0)])
def test_production_dispatcher_red_green(label, expected, generated, upstream, compiler):
    out = generated[label]
    harness = out / "harness.cpp"
    harness.write_text(HARNESS, encoding="utf-8")
    executable = out / ("callback-test.exe" if os.name == "nt" else "callback-test")
    sources = sorted(out.glob("p_fixture_*.cpp")) + [out / "modules.cpp"]
    command = [
        compiler, "-std=c++20", "-O1", "-I" + str(upstream / "runtime" / "include"),
        "-I" + str(out), str(harness), str(upstream / "runtime" / "src" / "core" / "core.cpp"),
        *(str(path) for path in sources), "-o", str(executable),
    ]
    _run(command)
    result = _run([str(executable)] + (["seeded"] if label == "green" else []), expected=expected, timeout=10)
    assert ("RED: unknown default callback" if label == "red" else "GREEN:") in result.stdout
