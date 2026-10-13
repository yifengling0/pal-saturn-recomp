"""Asset-free compiled regressions for the five narrow render-return guards.

Run: python -m pytest -q tools/tests/test_render_return_guards.py
Only pytest temporary files are generated. No ROM, game, save, or GUI is used.
PAL_SATURN_CXX may select one g++/clang++ compatible compiler executable.
"""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pal_render_returns_under_test", ROOT / "tools" / "pal_render_returns.py"
)
PLANNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLANNER)

# Module, caller, instruction, continuation, helper, record-advance bytes.
CASES = (
    ("PROG", "0605E398", "0605E39C", "0605E3A0", "06060870", 0),
    ("PROG", "06065E26", "06065E28", "06065E2C", "06065DC8", 20),
    ("PROG", "06065E8C", "06065E8E", "06065E92", "06065DC8", 28),
    ("TRUE", "06038F72", "06038F74", "06038F78", "06038F14", 20),
    ("TRUE", "06038FD8", "06038FDA", "06038FDE", "06038F14", 28),
)


def _signature(helper, advance):
    if advance == 0:
        return f"x == 0x{helper}u && c.r[0] == 0"
    return (f"c.t && c.r[2] == {advance} && "
            f"c.r[4] == pal_return_r4 + {advance}u")


def _line(pc, expected, helper, advance):
    if advance == 0:
        return (
            "    { const uint32_t x = c.r[0]; "
            f"c.pr = 0x{expected}u; c.r[2] = ld32(c.r[4] + 8); "
            f"SH2_POLL(c); if (x == 0x{helper}u) f_{helper}(c); "
            f"else sh2_call(c, x); SH2_RET(c, 0x{expected}u); }}"
            f"  // {pc} jsr @r0 ; mov.l @(8,r4),r2\n"
        )
    return (
        f"    c.pr = 0x{expected}u; c.r[2] = 0x{advance:X}u; "
        f"SH2_POLL(c); f_{helper}(c); SH2_RET(c, 0x{expected}u);"
        f"  // {pc} bsr 0x{helper} ; mov #{advance},r2\n"
    )


def test_allowlist_contains_exactly_the_five_audited_edges():
    # The planner may prefix an edge with its module; the call metadata is the
    # final five fields in either representation.
    actual = {tuple(edge[-5:]) for edge in PLANNER.EDGES}
    expected = {
        (caller, pc, ret, helper, _signature(helper, advance))
        for _, caller, pc, ret, helper, advance in CASES
    }
    assert actual == expected
    assert len(PLANNER.EDGES) == len(expected)


@pytest.mark.parametrize("case", CASES, ids=[row[2] for row in CASES])
def test_lowering_preserves_original_instructions_poll_and_strict_check(case):
    _, _, pc, ret, helper, advance = case
    original = _line(pc, ret, helper, advance)
    changed = PLANNER.lower_call(original, ret, _signature(helper, advance))
    assert changed.count("SH2_POLL(c);") == 1
    assert changed.count(f"SH2_RET(c, 0x{ret}u);") == 1
    assert changed.count(f"f_{helper}(c);") == 1
    assert changed.split("  // ", 1)[1] == original.split("  // ", 1)[1]
    assert changed.index("const uint32_t pal_return_pr") < changed.index(f"c.pr = 0x{ret}u")
    assert changed.index("if (c.pc == pal_return_pr") < changed.index("SH2_RET(c,")
    assert "c.pc !=" not in changed


def test_lowering_rejects_a_missing_or_duplicate_return_anchor():
    _, _, pc, ret, helper, advance = CASES[0]
    line = _line(pc, ret, helper, advance)
    anchor = f"SH2_RET(c, 0x{ret}u);"
    for bad in (line.replace(anchor, ""), line.replace(anchor, anchor + anchor)):
        with pytest.raises(ValueError, match="anchor changed"):
            PLANNER.lower_call(bad, ret, _signature(helper, advance))


HARNESS = r'''
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
struct SH2Context { uint32_t r[16]{}, t{}, pc{}, pr{}; };
struct BadReturn { uint32_t actual, expected; };
enum Mode { Normal, Unwind, BadPc, BadPr, NoPop, DoublePop,
            BadZero, BadT, BadSize, BadAdvance, WrongTarget };
static Mode mode;
static uint32_t saved_pr, expected, input_sp, input_r4, advance;
static unsigned polls, calls, checks, continued, reads, total;
static SH2Context after_helper;
static void require(bool ok, const char* why) {
    if (!ok) throw std::runtime_error(why);
}
static uint32_t ld32(uint32_t address) {
    ++reads;
    if (address == input_sp) return saved_pr;
    require(address == input_r4 + 8u, "unexpected guard/delay-slot read");
    return 0xA1u;
}
static void poll(SH2Context& c) {
    ++polls;
    require(c.pr == expected, "PR must be set before original poll");
    require(c.r[2] == (advance ? advance : 0xA1u), "delay slot must precede poll");
}
#define SH2_POLL(c) poll(c)
#define SH2_RET(c, a) do { ++checks; if ((c).pc != (a)) throw BadReturn{(c).pc, (a)}; } while (0)
static void helper(SH2Context& c) {
    ++calls;
    require(polls == 1, "exactly one original poll before helper");
    if (mode == Normal) {
        c.pc = c.pr;
        c.r[0] = 42;
    } else {
        c.pc = c.pr = saved_pr;
        c.r[15] += 4;
        c.r[0] = 0;
        c.t = 1;
        if (advance) c.r[4] += c.r[2];
        if (mode == BadPc) c.pc = saved_pr + 2;
        if (mode == BadPr) c.pr = saved_pr + 2;
        if (mode == NoPop) c.r[15] -= 4;
        if (mode == DoublePop) c.r[15] += 4;
        if (mode == BadZero) c.r[0] = 1;
        if (mode == BadT) c.t = 0;
        if (mode == BadSize) ++c.r[2];
        if (mode == BadAdvance) ++c.r[4];
    }
    after_helper = c;
}
static void f_06060870(SH2Context& c) { helper(c); }
static void f_06065DC8(SH2Context& c) { helper(c); }
static void f_06038F14(SH2Context& c) { helper(c); }
static void sh2_call(SH2Context& c, uint32_t target) {
    require(target == 0x06001234u, "unexpected indirect target");
    helper(c);
}
@WRAPPERS@
using Fn = void (*)(SH2Context&);
struct Edge { Fn fixed, original; uint32_t ret, helper, advance; };
static const Edge edges[] = {
@EDGES@
};
static void run(const Edge& e, Mode selected, bool collision, bool baseline = false,
                bool wrap_r4 = false) {
    mode = selected; expected = e.ret; advance = e.advance;
    input_sp = 0x060FF000u;
    input_r4 = wrap_r4 ? 0xFFFFFFF0u : 0x060AA000u;
    saved_pr = collision ? expected : 0x060343B8u;
    polls = calls = checks = continued = reads = 0;
    SH2Context c{};
    c.r[15] = input_sp; c.r[4] = input_r4; c.pr = saved_pr;
    c.r[0] = selected == WrongTarget ? 0x06001234u : e.helper;
    c.r[8] = 0xABCDEF01u;
    bool trapped = false;
    try { (baseline ? e.original : e.fixed)(c); }
    catch (const BadReturn& error) {
        trapped = true;
        require(error.expected == expected && error.actual == c.pc, "wrong strict failure");
    }
    const bool should_trap = baseline || (selected != Normal && selected != Unwind);
    require(trapped == should_trap, "guard admitted unexpected return or rejected legal return");
    require(polls == 1 && calls == 1, "original call/poll count changed");
    require(continued == (selected == Normal ? 1u : 0u), "incorrect caller continuation");
    require(checks == (selected == Unwind && !baseline ? 0u : 1u), "strict checker bypassed");
    for (unsigned i = 0; i < 16; ++i) require(c.r[i] == after_helper.r[i], "guard mutated guest register");
    require(c.pr == after_helper.pr && c.pc == after_helper.pc && c.t == after_helper.t,
            "guard mutated guest status");
    require(c.r[8] == 0xABCDEF01u, "unrelated guest register changed");
    require(reads == (baseline ? 0u : 1u) + (advance ? 0u : 1u), "extra memory read");
    if (!trapped && selected == Unwind) {
        require(c.r[15] == input_sp + 4u, "one-frame unwind lost");
        SH2_RET(c, saved_pr); // The grandparent's ordinary strict check still succeeds.
    }
    ++total;
}
int main() {
    try {
        for (const auto& e : edges) {
            run(e, Normal, false);
            run(e, Normal, true);
            run(e, Unwind, false);
            run(e, Unwind, true); // Same PC does not mean the saved frame still exists.
            run(e, Unwind, false, true); // The unmodified lowering must reproduce failure.
            run(e, BadPc, false);
            run(e, BadPr, false);
            run(e, NoPop, false);
            run(e, DoublePop, false);
            if (e.advance) {
                run(e, BadT, false);
                run(e, BadSize, false);
                run(e, BadAdvance, false);
                run(e, Unwind, false, false, true); // SH-2 32-bit add wraps.
            } else {
                run(e, BadZero, false);
                run(e, WrongTarget, false); // Matching state from an unrelated target is rejected.
            }
        }
        std::printf("PASS: %u synthetic return-boundary cases across 5 edges\n", total);
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "FAIL edge=%08X mode=%d: %s\n", expected, int(mode), e.what());
        return 1;
    } catch (...) {
        std::fprintf(stderr, "FAIL: unexpected exception\n");
        return 2;
    }
}
'''


def test_compiled_guards_preserve_legal_returns_and_reject_mismatches(tmp_path):
    requested = os.environ.get("PAL_SATURN_CXX")
    compiler = shutil.which(requested) if requested else (shutil.which("g++") or shutil.which("clang++"))
    if compiler is None:
        pytest.skip("C++ compiler unavailable; set PAL_SATURN_CXX")
    wrappers, edges = [], []
    for index, (_, _, pc, ret, helper, advance) in enumerate(CASES):
        original = _line(pc, ret, helper, advance)
        lowered = PLANNER.lower_call(original, ret, _signature(helper, advance))
        wrappers.append(f"static void fixed_{index}(SH2Context& c) {{\n{lowered}    ++continued;\n}}\n")
        wrappers.append(f"static void original_{index}(SH2Context& c) {{\n{original}    ++continued;\n}}\n")
        edges.append(f"    {{fixed_{index}, original_{index}, 0x{ret}u, 0x{helper}u, {advance}u}},")
    source = tmp_path / "render_return_guards.cpp"
    binary = tmp_path / ("render_return_guards.exe" if os.name == "nt" else "render_return_guards")
    source.write_text(HARNESS.replace("@WRAPPERS@", "\n".join(wrappers)).replace("@EDGES@", "\n".join(edges)), encoding="utf-8")
    command = [compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", str(source), "-o", str(binary)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, repr(command) + "\n" + built.stdout + built.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: 63 synthetic return-boundary cases across 5 edges" in result.stdout
