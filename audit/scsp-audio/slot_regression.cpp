#include "saturn.h"
#include "sound.h"
#include "state.h"
#include "test.h"
#include <array>
#include <cstring>

namespace {
void constant(bool sdir, int tl, int direct = 7, int imxl = 0, int ef = 0) {
    scsp_reset();
    std::memset(g_sound_ram, 0, 0x80000);
    for (int i = 0; i < 64; ++i) g_sound_ram[0x4000 + 2*i] = 0x20;
    scsp_write(0x400, 15, 2);
    scsp_write(2, 0x4000, 2);
    scsp_write(6, 32, 2);
    scsp_write(8, 31, 2);
    scsp_write(10, 15 << 10 | 31, 2);
    scsp_write(12, (sdir ? 0x100 : 0) | tl, 2);
    scsp_write(20, (1 << 3) | imxl, 2);
    scsp_write(22, direct << 13 | ef << 5, 2);
    scsp_write(0, 0x1820, 2);
}
std::array<int16_t,2> sample() {
    std::array<int16_t,2> out{};
    scsp_sample(0,0,out.data()); return out;
}
void dsp_passthrough() {
    scsp_write(0x700, 0x7FF8, 2); // 4095/4096 gain
    scsp_write(0x802, 0xA840, 2); // XSEL, YSEL=COEF, IRA=MIXS1
    scsp_write(0x804, 2, 2);      // ZERO
    scsp_write(0x80C, 0x1000, 2); // EWT -> EFREG0
}
}
TEST(sdir_bypasses_tl_in_both_direct_channels) {
    constant(true,0); auto a=sample();
    constant(true,255); auto b=sample();
    CHECK_EQ(a[0],8192); CHECK_EQ(a[1],8192);
    CHECK_EQ(b[0],a[0]); CHECK_EQ(b[1],a[1]);
}
TEST(sdir_bypasses_tl_before_dsp_mixs) {
    constant(true,0,0,7,7); dsp_passthrough(); auto a=sample();
    constant(true,255,0,7,7); dsp_passthrough(); auto b=sample();
    CHECK_EQ(a[0],8190); CHECK_EQ(a[1],8190);
    CHECK_EQ(b[0],a[0]); CHECK_EQ(b[1],a[1]);
}
TEST(normal_slots_still_apply_total_level) {
    constant(false,0); auto a=sample();
    constant(false,255); auto b=sample();
    CHECK_EQ(a[0]>8000,true); CHECK_EQ(b[0],0); CHECK_EQ(b[1],0);
}
TEST(sdir_fm_stack_still_bypasses_total_level) {
    constant(true,255); sample();
    CHECK_EQ(scsp_read(0x600,2),16384);
}
TEST(existing_key_semantics_are_preserved) {
    constant(true,0);
    scsp_write(6,1,2); scsp_write(0,0x1800,2);
    CHECK_EQ(sample()[0],8192); CHECK_EQ(scsp_active_slots(),0);
    scsp_write(0,0x1800,2); CHECK_EQ(sample()[0],0);
    scsp_write(0,0x1000,2); scsp_write(0,0x1800,2);
    CHECK_EQ(sample()[0],8192);
}
TEST(left_and_right_pan_are_not_collapsed) {
    constant(true,0); scsp_write(22,0xEF00,2); auto right=sample();
    CHECK_EQ(right[0],0); CHECK_EQ(right[1],8192);
    scsp_write(22,0xFF00,2); auto left=sample();
    CHECK_EQ(left[0],8192); CHECK_EQ(left[1],0);
}
TEST(pcm8_and_pcm16_have_correct_signed_big_endian_amplitude) {
    constant(true,0); g_sound_ram[0x4000]=0x80;
    CHECK_EQ(sample()[0],-32768);
    constant(true,0); g_sound_ram[0x4000]=0x80; scsp_write(0,0x1830,2);
    CHECK_EQ(sample()[0],-32768);
}
TEST(external_cd_channels_are_not_mixed_together) {
    scsp_reset(); scsp_write(0x400,15,2);
    scsp_write(16*32+22,(7<<5)|31,2); // EXTS0 left only
    scsp_write(17*32+22,(7<<5)|15,2); // EXTS1 right only
    int16_t out[2];scsp_sample(1234,-5678,out);
    CHECK_EQ(out[0],1234);CHECK_EQ(out[1],-5678);
}
TEST(legacy_missing_dsp_part_resets_nonzero_carry) {
    scsp_reset();
    scsp_write(0xC00,0x123400,4);
    scsp_write(0x780,0x100,2);
    scsp_write(0xBFC,0xC000,2); // step127 TABLE+MWT, pending next sample
    scsp_write(0xBFE,0x100,2);  // NOFL
    sample();
    g_sound_ram[0x200]=g_sound_ram[0x201]=0;
    scspdsp_reset();
    // Simulates the absent-part default in state.cpp, after a legacy chip
    // part was restored. No pending write is allowed to leak into it.
    scsp_write(0xBFC,0,2); scsp_write(0xBFE,0,2); sample();
    CHECK_EQ(g_sound_ram[0x200],0);CHECK_EQ(g_sound_ram[0x201],0);
}
