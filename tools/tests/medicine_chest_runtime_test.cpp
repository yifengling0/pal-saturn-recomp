#include <saturn/sh2.h>

#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#include <vector>

uint8_t g_wram_h[1 << 20]{}, g_wram_l[1 << 20]{};
uint32_t g_sh2_watch_lo = 0, g_sh2_watch_len = 0xFFFFFFFFu;

namespace {
constexpr std::uint32_t kCall = 0x06028700u;
SH2HookFn callback = nullptr;
unsigned registrations = 0, logs = 0, stores = 0, io_reads = 0, io_writes = 0;
} // namespace

void sh2_hook_add(uint32_t address, SH2HookFn function) {
    assert(address == kCall);
    assert(function != nullptr);
    callback = function;
    ++registrations;
}

void sh2_watch_store(uint32_t, uint32_t, int) { ++stores; }
uint32_t sh2_io_read(uint32_t, int) { ++io_reads; return 0; }
void sh2_io_write(uint32_t, uint32_t, int) { ++io_writes; }
void sat_note(const char*, ...) { ++logs; }

namespace {

SH2Context setup() {
    std::memset(g_wram_h, 0xA5, sizeof g_wram_h);
    std::memset(g_wram_l, 0x5A, sizeof g_wram_l);
    st16(0x060768EEu, 93u);
    st16(0x060769EAu, 1454u);
    st16(0x0609EE84u, 206u);
    st32(0x0609EE78u, 0x060A008Au);
    st16(0x060A008Au, 36788u);
    st16(0x0609C4C0u, 31u);
    st16(0x0609C4C2u, 0u);
    st16(0x0609C4C4u, 0u);
    st16(0x0609C4C6u, 0u);
    st16(kCall, 0xD807u);
    st16(kCall + 2u, 0x480Bu);
    st16(kCall + 4u, 0x0009u);
    st32(0x06028720u, 0x0604F210u);
    SH2Context context;
    // Nonzero sentinels catch incidental clobbers of registers/SR/budget.
    std::memset(&context, 0xA5, sizeof context);
    context.cpu = 0;
    context.r[4] = 0;
    context.r[5] = 1;
    logs = stores = io_reads = io_writes = 0;
    return context;
}

void check_callback(SH2Context& context, uint32_t address, bool repair) {
    std::vector<uint8_t> high_before(g_wram_h, g_wram_h + sizeof g_wram_h);
    std::vector<uint8_t> low_before(g_wram_l, g_wram_l + sizeof g_wram_l);
    SH2Context expected;
    std::memcpy(&expected, &context, sizeof context);
    if (repair) expected.r[4] = 103u;
    const unsigned logs_before = logs;
    stores = io_reads = io_writes = 0;
    callback(context, address);
    assert(std::memcmp(&context, &expected, sizeof context) == 0);
    assert(std::memcmp(g_wram_h, high_before.data(), sizeof g_wram_h) == 0);
    assert(std::memcmp(g_wram_l, low_before.data(), sizeof g_wram_l) == 0);
    assert(stores == 0 && io_reads == 0 && io_writes == 0);
    assert(logs == logs_before + (repair ? 1u : 0u));
}

void test_wrong_guest_words() {
    const std::array<uint32_t, 11> addresses{
        0x060768EEu, 0x060769EAu, 0x0609EE84u, 0x060A008Au,
        0x0609C4C0u, 0x0609C4C2u, 0x0609C4C4u, 0x0609C4C6u,
        kCall, kCall + 2u, kCall + 4u,
    };
    for (const uint32_t address : addresses) {
        for (const uint32_t mask : {1u, 0x8000u, 0xFFFFu}) {
            SH2Context context = setup();
            st16(address, ld16(address) ^ mask);
            check_callback(context, kCall, false);
        }
    }
    for (const uint32_t target : {0u, 0x0604F20Eu, 0x0604F212u,
                                   0x2604F210u, 0xFFFFF210u, 0xFFFFFFFFu}) {
        SH2Context context = setup();
        st32(0x06028720u, target);
        check_callback(context, kCall, false);
    }
}

void test_early_register_guards() {
    for (const uint32_t pc : {0u, kCall - 2u, kCall + 2u,
                               kCall | 0x20000000u, 0xFFFFFFFFu}) {
        SH2Context context = setup();
        check_callback(context, pc, false);
    }
    for (const int cpu : {-1, 1, 2, 0x10000}) {
        SH2Context context = setup();
        context.cpu = cpu;
        check_callback(context, kCall, false);
    }
    for (const uint32_t object : {1u, 103u, 0x100u, 0x10000u,
                                   0x80000000u, 0xFFFFFFFFu}) {
        SH2Context context = setup();
        context.r[4] = object;
        check_callback(context, kCall, false);
    }
    for (const uint32_t count : {0u, 2u, 0x101u, 0x10001u,
                                  0x80000001u, 0xFFFFFFFFu}) {
        SH2Context context = setup();
        context.r[5] = count;
        check_callback(context, kCall, false);
    }
}

void test_bad_script_pointers() {
    for (const uint32_t pointer : {0u, 1u, 0x060A0088u, 0x060A008Cu,
                                    0x060FFFFFu, 0x260A008Au,
                                    0x25A00000u, 0xDEADBEEFu, 0xFFFFFFFFu}) {
        SH2Context context = setup();
        st32(0x0609EE78u, pointer);
        // Invalid non-WRAM pointers would hit the counted IO stub if read.
        // The final WRAM byte is additionally an ASan boundary-read regression.
        check_callback(context, kCall, false);
    }
}

} // namespace

int main() {
    assert(registrations == 1 && callback != nullptr);
    test_wrong_guest_words();
    test_early_register_guards();
    test_bad_script_pointers();

    SH2Context context = setup();
    check_callback(context, kCall, true);
    check_callback(context, kCall, false); // Already repaired: no second log.

    context = setup(); // No hidden one-shot flag may suppress a fresh fixture.
    check_callback(context, kCall, true);
}
