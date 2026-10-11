#include "../src/pal_game/pal_dump_parse.h"
#include <initializer_list>
#include <cassert>
#include <cstdio>
int main() {
    int r; uint32_t a;
    for (int i=0; i<16; ++i) {
        char s[8]; std::snprintf(s,sizeof s,"r%d",i);
        assert(pal_parse_dump_target(s,r,a) && r==i);
    }
    for (auto s : {"", "r", "rX", "r16", "r-1", "r100000000000", "06000000junk", "100000000", "0x", "-1"})
        assert(!pal_parse_dump_target(s,r,a));
    assert(pal_parse_dump_target("060FFC00",r,a) && r==-1 && a==0x060FFC00);
    assert(pal_parse_dump_target("0xffffffff",r,a) && r==-1 && a==0xffffffff);
    puts("PAL_DUMP parser: 28 checks passed");
}
