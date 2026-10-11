#pragma once
#include <cstdlib>
#include <cstring>
#include "pal_input_intent.h"
#include "pal_input_wait.h"
#include <saturn/sh2.h>

uint16_t pal_input_peek();
uint16_t pal_input_edges();
uint64_t sat_vblanks();
void sat_note(const char*, ...);
inline bool pal_responsive_enabled() {
    static bool enabled = [] {const char* v=std::getenv("PAL_RESPONSIVE_INPUT"); return v && !std::strcmp(v,"1");}();
    return enabled;
}
inline bool pal_input_option(const char* name) {const char* v=std::getenv(name);return v && !std::strcmp(v,"1");}
inline PalInputIntent pal_intent;
inline bool pal_in_sync_wait=false, pal_last_step=false;
inline bool pal_field_wait = false;
inline uint16_t pal_input_scene = 0xFFFF;
inline uint64_t pal_script_started = 0;
inline void pal_input_clear() {
    if (!pal_responsive_enabled()) return;
    pal_field_wait=false; pal_in_sync_wait=false; pal_input_edges(); pal_intent.clear(pal_input_peek());
}
inline void pal_input_tick() {
    if (!pal_responsive_enabled()) return;
    const uint16_t bits=pal_input_peek();
    const uint16_t scene=ld16(0x060768EE);
    if(scene!=pal_input_scene) {pal_input_scene=scene;pal_field_wait=false;pal_intent.clear(bits);}
    const bool active=pal_field_wait && ld16(0x060768DC)==0;
    pal_intent.sample(bits,sat_vblanks(),active);
    pal_intent.edge(pal_input_edges(),sat_vblanks(),active);
    if(pal_input_option("PAL_RESPONSIVE_WAKE")) {
        const int old=(int8_t)ld8(0x060FFC13);
        const int next=pal_input_wake_target(old,ld8(0x060FFC12),active && ld8(0x06076A09)!=0xFF && pal_in_sync_wait,
                         pal_intent.pending!=0,ld8(0x060FFCA8)!=0,(ld8(0x060FFCBC)&4)!=0);
        if(next!=old) {st8(0x060FFC13,next);sat_note("PALINPUT wake vb=%llu count=%d->%d",(unsigned long long)sat_vblanks(),old,next);}
    }
}
inline void pal_input_script_before() { if(pal_responsive_enabled()) {pal_field_wait=false;pal_script_started=sat_vblanks();} }
inline void pal_input_script_after() { if(pal_responsive_enabled() && sat_vblanks()!=pal_script_started) pal_input_clear(); }
inline bool pal_movement_action(uint16_t action) { return action==0 || (action>=3 && action<=6); }
inline void pal_input_apply(SH2Context& c) {
    if(!pal_responsive_enabled()) return;
    pal_field_wait=false; pal_last_step=false;
    // The original converter owns actions, including menus and interaction.
    if(!pal_movement_action(ld16(c.r[14])) || ld16(0x060768DC)) {
        pal_input_clear(); st16(0x060768E8,0);st16(0x060768EA,0); c.r[0]=c.r[1]=0; return;
    }
    // The guest release-inhibit can lag a newly released host pad. Keep a new
    // field intent queued, but do not consume it or move before guest readiness.
    if(ld8(0x06076A09)==0xFF) {
        st16(0x060768E8,0);st16(0x060768EA,0);c.r[0]=c.r[1]=0;return;
    }
    // A fresh release cancels held-repeat, without cancelling an unconsumed tap.
    pal_intent.sample(pal_input_peek(),sat_vblanks(),true);
    const uint16_t dir=pal_intent.take(sat_vblanks());
    pal_last_step=dir!=0;
    int dx=0,dy=0,facing=0;
    switch(dir) {
      case 0x8000:dx=1;dy=1;facing=3;break;
      case 0x4000:dx=-1;dy=-1;facing=1;break;
      case 0x2000:dx=-1;dy=1;facing=0;break;
      case 0x1000:dx=1;dy=-1;facing=2;break;
    }
    st16(0x060768E8,dx);st16(0x060768EA,dy);
    // Opt-in behaviour: turning and stepping are one action. Collision still
    // runs in the original f06033654, and no position is directly modified.
    if(dir) st8(0x06076970,facing);
    st16(c.r[14],dir ? (dir==0x1000 ? 3 : dir==0x2000 ? 4 : dir==0x4000 ? 5 : 6) : 0);
    c.r[0]=c.r[1]=(dir || pal_intent.held) ? 1 : 0;
    if(dir) sat_note("PALINPUT step vb=%llu dir=%04X",(unsigned long long)sat_vblanks(),dir);
}
inline void pal_input_wait_begin(SH2Context& c) {
    if(pal_responsive_enabled()) pal_field_wait=pal_movement_action(ld16(c.r[14])) && ld16(0x060768DC)==0;
}
inline void pal_input_wait_end() { if(pal_responsive_enabled()) pal_field_wait=false; }

inline void pal_input_sync_enter(SH2Context& c) {
    if(pal_responsive_enabled()) pal_in_sync_wait=pal_field_wait && ((c.gbr&0x1FFFFFFF)==0x060FFC00);
}
inline void pal_input_sync_leave() {if(pal_responsive_enabled())pal_in_sync_wait=false;}
inline void pal_input_align() {
    if(!pal_responsive_enabled() || !pal_input_option("PAL_RESPONSIVE_ALIGN"))return;
    const int old=(int8_t)ld8(0x060FFC13);
    const int next=pal_input_align_target(old,pal_last_step);
    if(next!=old) {st8(0x060FFC13,next);sat_note("PALINPUT align vb=%llu count=%d->%d",(unsigned long long)sat_vblanks(),old,next);}
}
