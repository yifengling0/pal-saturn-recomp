// 仙剑土星版的游戏层诊断通道（不动上游：通过 recomp 的 [[hook]] 与 sh2_hook_add 挂进重编译码）。
//
// 为什么需要它：土星的 CD Block 寄存器窗口（0x25800400..）不在 --watch 覆盖的 Work RAM 里，
// 而本作装载 PROG.BIN 时目标区一次写入都没有，只凭 FATAL 无法判断装载器在哪一步放弃。
// 这里在指定指令之后打印上下文寄存器与栈上的装载请求块，把"游戏自己认为发生了什么"记进日志。
//
//   PAL_HOOKS=06004330,06004360     逗号分隔的地址（16 进制，与 game.toml 的 [[hook]] 对应）
//   PAL_DUMP=r14:24 或 060FFC00:24   每次命中额外打印若干字节：寄存器起（装载请求块）或绝对地址起
//   PAL_LIMIT=60                    每个 hook 最多打印多少次（之后只计数）
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "pal_dump_parse.h"

#include <saturn/sh2.h>
#include "saturn.h"          // sat_note / sat_vblanks，运行时内部头（saturn 目标已带该包含路径）

namespace {

constexpr int kMaxHooks = 32;

struct Hook {
    uint32_t addr;
    int hits;
};

Hook g_hooks[kMaxHooks];
int g_nhooks;
uint32_t g_dump_addr;
int g_dump_reg = -1;
int g_dump_bytes;
int g_limit = 60;

uint32_t parse_hex(const char* s) {
    return static_cast<uint32_t>(std::strtoul(s, nullptr, 16));
}

void read_env() {
    if (const char* h = std::getenv("PAL_HOOKS")) {
        char buf[1024];
        std::snprintf(buf, sizeof buf, "%s", h);
        for (char* tok = std::strtok(buf, ","); tok && g_nhooks < kMaxHooks; tok = std::strtok(nullptr, ",")) {
            g_hooks[g_nhooks++] = {parse_hex(tok), 0};
        }
    }
    if (const char* d = std::getenv("PAL_DUMP")) {
        const char* colon = std::strchr(d, ':');
        if (colon) {
            char head[32];
            int n = static_cast<int>(colon - d);
            if (n > 0 && n < static_cast<int>(sizeof head)) {
                std::memcpy(head, d, n);
                head[n] = 0;
                if (pal_parse_dump_target(head, g_dump_reg, g_dump_addr))
                    g_dump_bytes = std::atoi(colon + 1);
                if (g_dump_bytes > 256) g_dump_bytes = 256;
            }
        }
    }
    if (const char* l = std::getenv("PAL_LIMIT")) g_limit = std::atoi(l);
}

void report(SH2Context& c, uint32_t addr) {
    for (int i = 0; i < g_nhooks; ++i) {
        if (g_hooks[i].addr != addr) continue;
        if (++g_hooks[i].hits > g_limit) return;
        std::uint64_t vb = sat_vblanks();
        sat_note("PALDIAG %08X vb=%llu pc=%08X pr=%08X gbr=%08X  r0..r7=%08X %08X %08X %08X %08X %08X %08X %08X",
                 addr, static_cast<unsigned long long>(vb), c.pc, c.pr, c.gbr,
                 c.r[0], c.r[1], c.r[2], c.r[3], c.r[4], c.r[5], c.r[6], c.r[7]);
        sat_note("        r8..r15=%08X %08X %08X %08X %08X %08X %08X %08X",
                 c.r[8], c.r[9], c.r[10], c.r[11], c.r[12], c.r[13], c.r[14], c.r[15]);
        uint32_t from = g_dump_reg >= 0 ? c.r[g_dump_reg] : g_dump_addr;
        if (g_dump_bytes && from) {
            char line[1200];
            int used = std::snprintf(line, sizeof line, "        [%08X]", from);
            for (int o = 0; o + 4 <= g_dump_bytes && used < static_cast<int>(sizeof line) - 12; o += 4) {
                uint32_t v = ld32(from + o);
                used += std::snprintf(line + used, sizeof line - used, " +%02X=%08X", o, v);
            }
            sat_note("%s", line);
        }
        return;
    }
}

struct Register {
    Register() {
        read_env();
        for (int i = 0; i < g_nhooks; ++i) sh2_hook_add(g_hooks[i].addr, report);
        if (g_nhooks) sat_note("PALDIAG armed %d hook(s) from PAL_HOOKS", g_nhooks);
    }
} g_register;

}  // namespace
