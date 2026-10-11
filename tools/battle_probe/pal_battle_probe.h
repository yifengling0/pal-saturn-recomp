#pragma once
// Observation only: no ld/st MMIO, no SH2_POLL, no writes to SH2Context/guest RAM.
#include <saturn/sh2.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <cstdint>
extern uint64_t sat_vblanks() __attribute__((weak));
extern uint64_t sat_now() __attribute__((weak));
namespace pal_battle_probe {
inline uint8_t raw8(uint32_t a) noexcept {
    const uint32_t p = a & 0x1fffffffu;
    if (p >= 0x06000000u && p < 0x08000000u) return g_wram_h[p & 0xfffffu];
    if (p >= 0x00200000u && p < 0x00300000u) return g_wram_l[p & 0xfffffu];
    return 0;  // Never cause an MMIO read to observe hardware.
}
inline uint16_t raw16(uint32_t a) noexcept { return uint16_t(raw8(a)) << 8 | raw8(a+1); }
inline uint32_t raw32(uint32_t a) noexcept { return uint32_t(raw16(a)) << 16 | raw16(a+2); }
inline uint64_t vb() noexcept { return sat_vblanks ? sat_vblanks() : 0; }
inline uint64_t guest() noexcept { return sat_now ? sat_now() : 0; }
inline uint64_t wall() noexcept {
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
inline bool enabled() noexcept {
    static const bool v = [] { const char* p=std::getenv("PAL_BATTLE_PROBE"); return p && p[0]=='1' && !p[1]; }();
    return v;
}
inline thread_local unsigned depth = 0;
inline thread_local uint64_t sequence = 0;
inline thread_local uint64_t printed = 0;
inline bool permit() noexcept {
    if (printed < 20000) { ++printed; return true; }
    if (printed == 20000) {
        ++printed;
        std::fputs("PAL_BATTLE event=LIMIT incomplete=1 max_records=20000\n", stderr);
    }
    return false;
}
inline void state(const SH2Context& c) noexcept {
    std::fprintf(stderr,
        " scene=%u reqscene=%u held=%04X pressed=%04X released=%04X driver=%04X menuedge=%04X"
        " tick=%u effect_frame=%u effect_count=%u sprites=%u sprite_bytes=%u interval=%u countdown=%d gbr=%08X",
        unsigned(raw16(0x060768ee)), unsigned(raw16(0x060768e0)),
        unsigned(raw16(0x0607682a)), unsigned(raw16(0x0607682c)), unsigned(raw16(0x0607682e)),
        unsigned(raw16(0x0605d1da)), unsigned(raw16(0x06076830)),
        unsigned(raw16(0x06076990)), unsigned(raw16(0x060769c8)), unsigned(raw16(0x060769da)),
        unsigned(raw16(0x060769b2)), unsigned(raw32(0x060769b4)),
        unsigned(raw8(c.gbr+18)), int(int8_t(raw8(c.gbr+19))), c.gbr);
}
struct Scope {
    SH2Context& c;
    uint32_t pc, pr, args[4]{};
    uint64_t id=0, start_vb=0, start_guest=0, start_wall=0;
    uint32_t start_pixels=0;
    bool root=false, active=false;
    int exception_count=0;
    Scope(SH2Context& context, uint32_t address) noexcept : c(context), pc(address), pr(c.pr) {
        if (!enabled() || c.cpu != 0) return;
        root = pc == 0x060422b8u;
        if (root) ++depth;
        active = depth != 0;
        if (!active) return;
        id=++sequence;
        for (int i=0;i<4;++i) args[i]=c.r[4+i];
        start_pixels=raw32(0x060769b4);
        exception_count=std::uncaught_exceptions();
        // Timestamps before printing allow a bounded accounting of probe overhead.
        start_vb=vb(); start_guest=guest(); start_wall=wall();
        if (!permit()) return;
        std::fprintf(stderr,
            "PAL_BATTLE event=B id=%llu pc=%08X pr=%08X vb=%llu guest_ns=%llu wall_ns=%llu"
            " r4=%08X r5=%08X r6=%08X r7=%08X",
            (unsigned long long)id, pc, pr, (unsigned long long)start_vb,
            (unsigned long long)start_guest, (unsigned long long)start_wall,
            args[0], args[1], args[2], args[3]);
        if (pc == 0x06020094u) {
            char name[41]{};
            for (unsigned i=0;i<40;++i) {
                uint8_t ch=raw8(args[0]+i); if (!ch) break;
                name[i]=(ch>=33 && ch<=126 && ch!='"' && ch!='\\') ? char(ch) : '_';
            }
            std::fprintf(stderr," name=%s sector=%u bytes_req=%u whole_file=%u dest=%08X",
                name, args[1]&0xffffu, args[3], unsigned(args[3]==0), args[2]);
        }
        if (root) std::fprintf(stderr," battle_group=%u",unsigned(raw16(args[0])));
        state(c); std::fputc('\n',stderr);
    }
    ~Scope() noexcept {
        if (!active) return;
        const auto end_vb=vb(), end_guest=guest(), end_wall=wall();
        if (permit()) {
            std::fprintf(stderr,
                "PAL_BATTLE event=E id=%llu pc=%08X pr=%08X vb=%llu guest_ns=%llu wall_ns=%llu"
                " dvb=%llu dguest_ns=%llu dwall_ns=%llu result=%08X unwind=%u",
                (unsigned long long)id, pc, pr, (unsigned long long)end_vb,
                (unsigned long long)end_guest, (unsigned long long)end_wall,
                (unsigned long long)(end_vb-start_vb), (unsigned long long)(end_guest-start_guest),
                (unsigned long long)(end_wall-start_wall), c.r[0],
                unsigned(std::uncaught_exceptions()!=exception_count));
            if (pc == 0x0602f590u)
                std::fprintf(stderr," upload_bytes=%u",raw32(0x060769b4)-start_pixels);
            state(c); std::fputc('\n',stderr);
        }
        if (root) --depth;
    }
    Scope(const Scope&)=delete;
    Scope& operator=(const Scope&)=delete;
};
inline void mark(const SH2Context& c,uint32_t pc,const char* phase) noexcept {
    if (!enabled() || c.cpu!=0 || !depth || !permit()) return;
    std::fprintf(stderr,"PAL_BATTLE event=M pc=%08X phase=%s vb=%llu guest_ns=%llu wall_ns=%llu",
        pc,phase,(unsigned long long)vb(),(unsigned long long)guest(),(unsigned long long)wall());
    state(c); std::fputc('\n',stderr);
}
} // namespace pal_battle_probe
