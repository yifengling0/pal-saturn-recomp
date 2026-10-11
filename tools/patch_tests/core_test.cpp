#include "saturn/sh2.h"
#include <cassert>
#include <cstdio>
static int starts, unknown, watched;
static uint32_t watched_a, watched_v;
uint32_t sh2_mmio_read(uint32_t, int) { return 0; }
void sh2_mmio_write(uint32_t, uint32_t, int) {}
void sh2_program_start(SH2Context&, uint32_t) { ++starts; }
void sh2_call_unknown(SH2Context&, uint32_t) { ++unknown; }
static void first(SH2Context& c) { c.r[0] += 7; c.pc = c.pr; }
static void second(SH2Context& c) { c.r[0] += 11; c.pc = c.pr; }
static SH2FuncEntry funcs_a[] = {{0x06004000, first}};
static SH2FuncEntry funcs_b[] = {{0x06004000, second}};
static SH2Module a = {"a", 0x06004000, 4, 0, funcs_a, 1, nullptr, nullptr};
static SH2Module b = {"b", 0x06004000, 4, 0, funcs_b, 1, nullptr, nullptr};
extern const SH2Module* const g_sh2_modules[] = {&a, &b};
extern const int g_sh2_nmodules = 2;
extern void (*g_sh2_watch_report)(uint32_t, uint32_t, int, const void*);
static void watch(uint32_t addr, uint32_t v, int, const void*) { ++watched; watched_a=addr; watched_v=v; }
int main() {
    const uint8_t aa[]={1,2,3,4}, bb[]={5,6,7,8};
    a.crc=sh2_crc32(aa,4); b.crc=sh2_crc32(bb,4);
    SH2Context c{}; c.pr=0x06009900;
    assert(sh2_mem_write(a.base,aa,4)); sh2_call(c,a.base);
    assert(c.r[0]==7 && starts==0 && c.pc==c.pr);
    assert(sh2_mem_write(b.base,bb,4)); sh2_call(c,b.base);
    assert(c.r[0]==18 && starts==0 && c.pc==c.pr);
    sh2_call(c,b.base|0x20000000);
    assert(c.r[0]==29 && starts==0);
    const uint8_t bad[]={0,0,0,0}; sh2_mem_write(a.base,bad,4); sh2_call(c,a.base);
    assert(starts==1); sh2_call(c,0x06005555); assert(unknown==1);
    g_sh2_watch_lo=0x06000120; g_sh2_watch_len=4; g_sh2_watch_report=watch;
    st32(0x06100120,0x11223344); assert(watched==1 && watched_a==0x06100120 && watched_v==0x11223344);
    st32(0x26100120,0x55667788); assert(watched==2 && ld32(0x06000120)==0x55667788);
    st32(0x06000124,0); assert(watched==2);
    puts("patch0002+0003: 10 assertions passed; exact module swap, call return, alias, fallback, watch mirrors");
}
