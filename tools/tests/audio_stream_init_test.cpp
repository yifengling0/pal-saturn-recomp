#include "pal_audio_stream_init.h"
#include <cassert>
#include <initializer_list>
using pal_audio_stream_init::Pointers;
using pal_audio_stream_init::plan;
int main() {
    Pointers p{0x1234, 0x5678};
    assert(!plan(0, 0x25A00000, 0x25A000A0, p));
    assert(p.table==0x1234 && p.progress==0x5678);
    for (auto n : {0x700u, 0x800u, 4u, 0x7FF5Cu}) {
        assert(plan(n, 0x25A00000, 0x25A000A0, p));
        assert(p.table==0x25A00000+n && p.progress==0x25A000A0+n);
        assert(!plan(n, p.table, p.progress, p)); // Warm / already repaired.
    }
    for (auto n : {1u, 0x701u, 0x7FF60u, 0x80000u, 0xFFFFFFFFu}) {
        p={0x1234,0x5678};assert(!plan(n,0x25A00000,0x25A000A0,p));
        assert(p.table==0x1234 && p.progress==0x5678);
    }
    assert(!plan(0x700,0x25A00100,0x25A001A0,p));
    assert(!plan(0x700,0x25A00000,0x25A000A4,p));
    assert(!plan(0x700,0x05A00000,0x05A000A0,p));
}
