#include "pal_field_input_ledger.h"
#include <cassert>
#include <cstdio>
using pal_field_host::Ledger;
constexpr uint16_t Up=0x1000, Left=0x4000;
constexpr uint64_t Key=(uint64_t(1)<<60)|79, Pad=(uint64_t(2)<<60)|1, Touch=(uint64_t(3)<<60)|1;
static Ledger field() { Ledger l; l.context(true,false); return l; }
static void resume(Ledger& l) { l.context(true,false); assert(l.resume_held()); }
static void held(Ledger& l, uint16_t direction) {
    const auto r=l.begin(); assert(r.active && r.direction==direction && !r.pending);
    assert(!direction || (r.held & direction)); assert(l.acknowledge(r));
}
int main() {
    for (auto source : {Key, Pad, Touch}) {
        auto l=field(); l.observe(source,Up,true); const auto old=l.begin(); assert(l.acknowledge(old));
        l.guest_suspend(); assert(!l.begin().direction); resume(l);
        assert(!l.acknowledge(old)); held(l,Up); l.release(source); held(l,0);
        std::puts("PASS held keyboard/gamepad/touch survives guest return only while down");
    }
    {
        auto l=field(); l.guest_suspend(); l.observe(Key,Up,true); resume(l); held(l,Up);
        std::puts("PASS direction first pressed inside dialogue is a current level on return");
    }
    {
        auto l=field(); l.guest_suspend(); l.observe(Key,Up,true); l.release(Key); resume(l); held(l,0);
        l.guest_suspend(); l.observe(Touch,Up,true); l.cancel(Touch); resume(l); held(l,0);
        std::puts("PASS released tap and canceled touch never become a field step");
    }
    {
        auto l=field(); l.observe(Key,Up,true); l.guest_suspend(); l.observe(Key,Left);
        l.guest_suspend(); resume(l); held(l,Left);
        auto old=l.begin(); l.observe(Key,Up|0x8000); assert(!l.acknowledge(old));
        std::puts("PASS latest held direction wins and changed snapshots are rejected");
    }
    {
        auto l=field(); l.observe(Key,Up,true); l.guest_suspend(); l.context(false,true);
        assert(!l.return_pending()); l.guest_suspend(); resume(l); held(l,0);
        l.release(Key); l.observe(Key,Up,true); const auto r=l.begin();
        assert(r.pending && r.direction==Up && l.acknowledge(r));
        std::puts("PASS host boundary remains sticky until a fresh physical press");
    }
    {
        auto l=field(); l.guest_suspend(); assert(!l.resume_held());
        l.observe(Key,Up,true); l.release(Key); l.observe(Pad,Left,true); resume(l); held(l,Left);
        std::puts("PASS resume requires field activation and coalesces only current levels");
    }
}
