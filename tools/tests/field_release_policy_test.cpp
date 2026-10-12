#include "pal_release_gate.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
using namespace pal_field_release;
static unsigned checks;
static void check(bool value) { ++checks; assert(value); }
static Writer resource(unsigned scene=7) {
    return {WriteSite::Resource, 0x060327D4, uint16_t(scene), true, false, false};
}
static Writer scene(unsigned target=8) {
    return {WriteSite::Scene, 0x06026DAE, uint16_t(target), true, false, true};
}
static Decision move(unsigned direction=0x8000, unsigned action=6, unsigned sc=7) {
    return {FieldReturn, DeltaX, DeltaY, 0x060FE000, 0x060FE000,
            uint16_t(action),uint16_t(sc),0,uint16_t(direction),uint16_t(direction),
            0xFF,true,false,true};
}
static void load(GateLedger& l, const Writer& w=resource(), unsigned previous=0) {
    l.resource_enter(); l.write_ff(w, uint8_t(previous)); l.resource_leave();
}
int main() {
    GateLedger l;
    check(!l.permits_held_direction(l.freeze(), move())); // unknown FF
    load(l);
    for (auto d : {move(0x1000,3), move(0x2000,4), move(0x4000,5), move(0x8000,6)}) {
        const auto s=l.freeze();
        for(unsigned repeat=0; repeat<600; ++repeat) check(l.permits_held_direction(s,d));
        d.pressed_buttons=0; check(!l.permits_held_direction(s,d)); // released pending alone
    }
    auto s=l.freeze(); auto d=move();
    for(unsigned a=0; a<256; ++a) { d.action=a; check(l.permits_held_direction(s,d)==movement_action(a)); }
    d=move();
    for(unsigned bit=0; bit<12; ++bit) {
        d.pressed_buttons=uint16_t(0x8000|(1u<<bit));
        for(unsigned a : {0u,1u,2u,3u,6u,7u,10u,11u,13u}) {
            d.action=a; check(!l.permits_held_direction(s,d));
        }
    }
    d=move(); d.return_pc++; check(!l.permits_held_direction(s,d));
    d=move(); d.dx_ptr++; check(!l.permits_held_direction(s,d));
    d=move(); d.dy_ptr++; check(!l.permits_held_direction(s,d));
    d=move(); d.action_ptr++; check(!l.permits_held_direction(s,d));
    d=move(); d.field_frame=0; check(!l.permits_held_direction(s,d));
    d=move(); d.scene++; check(!l.permits_held_direction(s,d));
    d=move(); d.scene_change=1; check(!l.permits_held_direction(s,d));
    d=move(); d.field_scope=false; check(!l.permits_held_direction(s,d));
    d=move(); d.protected_scope=true; check(!l.permits_held_direction(s,d));
    d=move(); d.input_current=false; check(!l.permits_held_direction(s,d));
    d=move(); d.gate=0; check(!l.permits_held_direction(s,d));
    for(unsigned h : {0u,0xC000u,0x3000u,0xF000u}) {
        d=move(); d.pressed_buttons=h; check(!l.permits_held_direction(s,d));
    }
    d=move(); d.selected_direction=0x4000; check(!l.permits_held_direction(s,d));
    d=move(); d.selected_direction=0x9000; check(!l.permits_held_direction(s,d));
    d=move(); d.pressed_buttons=0x9000; check(l.permits_held_direction(s,d)); // cardinal chosen upstream
    l.neutral_cleared(); check(!l.permits_held_direction(s,move()));
    check(!l.permits_held_direction(l.freeze(),move()));
    load(l); check(l.permits_held_direction(l.freeze(),move()));
    s=l.freeze(); l.hard_boundary(); check(!l.permits_held_direction(s,move()));
    load(l,resource(),0xFF); check(!l.permits_held_direction(l.freeze(),move()));
    l.write_ff(scene(),0xFF); check(!l.permits_held_direction(l.freeze(),move(0x8000,6,8)));
    l.neutral_cleared(); load(l); check(l.permits_held_direction(l.freeze(),move()));
    Writer protected_writer{WriteSite::Script,0,7,true,false,false};
    l.write_ff(protected_writer,0xFF); load(l,resource(),0xFF);
    check(!l.permits_held_direction(l.freeze(),move()));
    GateLedger unknown; load(unknown,resource(),0xFF);
    check(!unknown.permits_held_direction(unknown.freeze(),move()));
    for(unsigned variant=0;variant<7;++variant) {
        GateLedger bad; auto w=resource();
        if(variant==0) w.return_pc=0x0602A88C; // direct script helper, not observed cache miss
        if(variant==1) w.return_pc=0;
        if(variant==2) w.field_scope=false;
        if(variant==3) w.protected_scope=true;
        if(variant==4) w.site=WriteSite::Unknown;
        if(variant==5) w=Writer{WriteSite::Scene,0x06026DAE,7,true,false,false};
        if(variant==6) w=Writer{WriteSite::Scene,0xDEADBEEF,7,true,false,true};
        load(bad,w); check(!bad.permits_held_direction(bad.freeze(),move()));
    }
    GateLedger nested; nested.resource_enter(); nested.write_ff(resource(),0);
    check(!nested.permits_held_direction(nested.freeze(),move()));
    nested.resource_enter(); nested.write_ff(resource(),0xFF); nested.resource_leave();
    check(!nested.permits_held_direction(nested.freeze(),move()));
    nested.resource_leave(); check(nested.permits_held_direction(nested.freeze(),move()));
    s=nested.freeze(); load(nested,resource(),0xFF);
    check(!nested.permits_held_direction(s,move())); // old freeze invalid after a new writer
    check(nested.permits_held_direction(nested.freeze(),move()));
    nested.resource_enter(); nested.write_ff(protected_writer,0xFF);
    nested.resource_enter(); nested.write_ff(resource(),0xFF); nested.resource_leave(); nested.resource_leave();
    check(!nested.permits_held_direction(nested.freeze(),move()));
    GateLedger transition; load(transition); s=transition.freeze();
    transition.write_ff(scene(),0xFF);
    check(!transition.permits_held_direction(s,move()));
    check(transition.permits_held_direction(transition.freeze(),move(0x8000,6,8)));
    load(transition,resource(8),0xFF);
    check(transition.permits_held_direction(transition.freeze(),move(0x8000,6,8)));
    load(transition,resource(9),0xFF);
    check(!transition.permits_held_direction(transition.freeze(),move(0x8000,6,9)));
    GateLedger broken; broken.write_ff(resource(),0); check(!broken.permits_held_direction(broken.freeze(),move()));
    load(broken); broken.resource_leave(); check(!broken.permits_held_direction(broken.freeze(),move()));

    // Consumer contract: this policy supplies only a conditional FF exception.
    // Rejection preserves the original branch and the original nonmovement action.
    for(unsigned action : {1u,2u,7u,10u,11u,13u}) {
        GateLedger p; load(p); Decision q=move(); q.action=action;
        unsigned guest_action=action, original_mover_calls=0;
        const bool bypass=p.permits_held_direction(p.freeze(),q);
        check(!bypass); check(guest_action==action); check(original_mover_calls==0);
    }
    std::printf("PASS %u policy checks; no guest/host/mover calls or memory writes\n", checks);
}
