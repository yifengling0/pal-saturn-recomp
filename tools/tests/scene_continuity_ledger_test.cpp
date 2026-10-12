#include "pal_field_input_ledger.h"
#include <cassert>
#include <cstdio>
#include <functional>
#include <map>
#include <vector>
using pal_field_host::Ledger;
using pal_field_host::Read;
constexpr uint16_t Up=0x1000, Down=0x2000, Left=0x4000, Right=0x8000;
constexpr uint64_t K=(uint64_t(1)<<60)|79, P=(uint64_t(2)<<60)|7, T=(uint64_t(3)<<60)|1;
static Ledger field() { Ledger l; l.context(true,false); return l; }
static Read take(Ledger& l, uint16_t direction, bool pending, bool continuation) {
    auto r=l.begin(); assert(r.active); assert(r.direction==direction);
    assert(r.pending==pending); assert(r.scene_held==continuation); assert(l.acknowledge(r)); return r;
}
static void neutral(Ledger& l) { take(l,0,false,false); }
// Minimal model of the real host ownership rules. No SDL / guest / ROM code.
struct Host {
    Ledger l=field(); uint64_t serial=0; bool intercept=true;
    struct Touch { uint64_t source; bool armed; uint16_t raw; };
    std::map<unsigned,Touch> touches;
    void down(unsigned id,uint16_t direction) {
        auto old=touches.find(id); if(old!=touches.end()) l.cancel(old->second.source);
        auto source=(uint64_t(3)<<60)|++serial;
        touches[id]={source,l.active(),direction};
        if(touches[id].armed) l.observe(source,direction,true);
    }
    void motion(unsigned id,uint16_t direction) {
        auto it=touches.find(id); if(it==touches.end()) return;
        auto& t=it->second; t.raw=direction;
        if(!t.armed || !direction) l.cancel(t.source); else l.observe(t.source,direction);
    }
    void up(unsigned id) { auto it=touches.find(id); if(it==touches.end())return; l.release(it->second.source); touches.erase(it); }
    void cancel(unsigned id) { auto it=touches.find(id); if(it==touches.end())return; l.cancel(it->second.source); touches.erase(it); }
    void scene() { intercept=false; l.scene_suspend(); }
    void hard() { intercept=false; l.context(false,true); for(auto& [id,t]:touches)l.cancel(t.source); touches.clear(); }
    bool resume(const std::function<void()>& drain) {
        assert(l.scene_suspended()); const auto epoch=l.epoch();
        // Queued events must be processed while l.active()==false.
        drain();
        // A queued menu/focus/background/resize/rebind event revokes this resume.
        if(l.epoch()!=epoch || !l.scene_suspended()) return false;
        l.context(true,false); intercept=true; return true;
    }
};
int main() {
    unsigned tests=0;
    const auto run=[&](const char* name, const std::function<void()>& f) {f(); ++tests; std::printf("PASS %s\n",name);};
    run("keyboard/controller/touch held-only resume", [] {
        for(auto source:{K,P,T}) {auto l=field(); l.observe(source,Up,true);auto old=take(l,Up,true,false);
            l.scene_suspend(); assert(!l.active()); assert(!l.current(old)); assert(!l.acknowledge(old));
            assert(!l.begin().scene_held); l.observe(source,Up); l.context(true,false);
            auto r=take(l,Up,false,true); assert(r.source==source && r.press_seq==old.press_seq);
            take(l,Up,false,true); l.release(source); neutral(l);}
    });
    run("old pending released tap is discarded", [] {auto l=field(); l.observe(K,Up,true);l.release(K);auto r=l.begin();assert(r.pending); l.scene_suspend();l.context(true,false);neutral(l);assert(!l.acknowledge(r));});
    run("still-held unconsumed tap becomes hold only", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);take(l,Up,false,true);l.release(K);neutral(l);});
    run("release during scene revokes", [] {auto l=field();l.observe(K,Up,true);take(l,Up,true,false);l.scene_suspend();l.release(K);l.context(true,false);neutral(l);});
    run("same source release then press while paused is new", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.release(K);l.observe(K,Up,true);l.context(true,false);neutral(l);});
    run("same source explicit new down revokes without up", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.observe(K,Up,true);l.context(true,false);neutral(l);});
    run("load-time new source is not captured", [] {auto l=field();l.scene_suspend();l.observe(K,Up,true);l.context(true,false);l.observe(K,Up);neutral(l);l.release(K);l.observe(K,Up,true);take(l,Up,true,false);});
    run("new source poll-discovered down is not captured", [] {auto l=field();l.scene_suspend();l.observe(P,Left);l.context(true,false);l.observe(P,Left);neutral(l);});
    run("direction change then back during scene revokes", [] {auto l=field();l.observe(P,Up,true);l.scene_suspend();l.observe(P,Right);l.observe(P,Up);l.context(true,false);neutral(l);});
    run("raw change to same cardinal revokes continuation", [] {auto l=field();l.observe(P,Up,true);take(l,Up,true,false);l.scene_suspend();l.context(true,false);auto r=l.begin();assert(r.scene_held);l.observe(P,Up|Right);assert(!l.acknowledge(r));assert(!l.begin().scene_held);});
    run("release between begin and apply rejects", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);auto r=l.begin();l.release(K);assert(!l.acknowledge(r));neutral(l);});
    run("new same-id contact between begin and apply rejects", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);auto r=l.begin();l.release(K);l.observe(K,Up,true);assert(!l.acknowledge(r));take(l,Up,true,false);});
    run("hard boundary always revokes before/during/after scene", [] {for(int where=0;where<3;++where){auto l=field();l.observe(K,Up,true);if(where==0)l.context(false,true);l.scene_suspend();if(where==1)l.context(false,true);l.context(true,false);if(where==2){l.context(false,true);l.context(true,false);}l.observe(K,Up);neutral(l);}});
    run("initial inactive UI source never promoted by scene", [] {Ledger l;l.observe(K,Up,true);l.scene_suspend();l.scene_suspend();l.context(true,false);neutral(l);});
    run("nested/repeated scene boundary preserves survivor", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();auto e=l.epoch();l.scene_suspend();assert(l.epoch()>e);l.context(false,false);assert(l.scene_suspended());l.context(true,false);take(l,Up,false,true);});
    run("new pending field input after resume loses old token", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);l.observe(K,Up,true);take(l,Up,true,false);});
    run("other held source survives release of newest", [] {auto l=field();l.observe(K,Up,true);l.observe(T,Left,true);l.scene_suspend();l.release(T);l.context(true,false);auto r=take(l,Up,false,true);assert(r.source==K);});
    run("newer inactive source cannot win over survivor", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.observe(P,Left,true);l.context(true,false);auto r=take(l,Up,false,true);assert(r.source==K);});
    run("touch table survives scene and retains source serial", [] {Host h;h.down(7,Up);auto source=h.touches[7].source;take(h.l,Up,true,false);h.scene();assert(h.touches.count(7));assert(h.resume([&]{h.motion(7,Up);}));auto r=take(h.l,Up,false,true);assert(r.source==source);});
    run("touch UP plus same external ID DOWN in load queue", [] {Host h;h.down(7,Up);h.scene();assert(h.resume([&]{h.up(7);h.down(7,Up);}));neutral(h.l);assert(!h.touches[7].armed);});
    run("touch replacement DOWN without UP in load queue", [] {Host h;h.down(7,Up);auto old=h.touches[7].source;h.scene();assert(h.resume([&]{h.down(7,Up);}));assert(h.touches[7].source!=old);neutral(h.l);});
    run("touch center or CANCEL during loading revokes", [] {for(bool center:{false,true}){Host h;h.down(7,Up);h.scene();assert(h.resume([&]{if(center)h.motion(7,0);else h.cancel(7);}));neutral(h.l);}});
    run("queued load DOWN+UP is drained before arming", [] {Host h;h.scene();assert(h.resume([&]{h.l.observe(K,Up,true);h.l.release(K);}));neutral(h.l);});
    run("hard boundary while draining vetoes activation", [] {Host h;h.down(7,Up);h.scene();assert(!h.resume([&]{h.hard();h.down(7,Up);}));assert(!h.l.active());h.l.context(true,false);neutral(h.l);});
    run("touch held in UI and motion after exit never captured", [] {Host h;h.hard();h.down(7,Up);h.scene();assert(h.resume([]{}));h.motion(7,Up);neutral(h.l);h.up(7);h.down(7,Up);take(h.l,Up,true,false);});
    run("ordinary taps and stale epoch semantics preserved", [] {auto l=field();l.observe(K,Up,true);l.release(K);take(l,Up,true,false);neutral(l);l.observe(K,Left,true);auto r=l.begin();l.context(false,true);l.context(true,false);l.release(K);l.observe(K,Down,true);assert(!l.acknowledge(r));take(l,Down,true,false);});
    run("blocked read never grants continuation", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);auto r=l.begin(true);assert(r.blocked && !r.direction && !r.scene_held);assert(!l.acknowledge(r));});
    run("duplicate acknowledgement remains rejected", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);auto r=take(l,Up,false,true);assert(!l.acknowledge(r));});
    run("32768 inactive event sequences never resurrect identity", [] {
        for(unsigned word=0;word<(1u<<15);++word) {
            auto l=field(); l.observe(K,Up,true); l.scene_suspend();
            bool survives=true; unsigned events=word;
            for(unsigned i=0;i<5;++i,events>>=3) switch(events&7u) {
                case 0:l.observe(K,Up);break;
                case 1:l.release(K);survives=false;break;
                case 2:l.observe(K,Up,true);survives=false;break;
                case 3:l.observe(K,Left);survives=false;break;
                case 4:l.cancel(K);survives=false;break;
                case 5:l.observe(P,Right,true);break;
                case 6:l.scene_suspend();break;
                case 7:l.context(false,true);survives=false;break;
            }
            l.context(true,false);auto r=l.begin();
            assert(r.direction==(survives?Up:0));assert(r.scene_held==survives);
            assert(!r.pending);assert(l.acknowledge(r));
        }
    });
    run("strict reveal cannot promote a new active source", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend(true);l.context(true,false);neutral(l);});
    run("strict reveal preserves only old scene-held source", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);l.observe(P,Left,true);l.scene_suspend(true);l.context(true,false);auto r=take(l,Up,false,true);assert(r.source==K);});
    run("strict reveal cannot upgrade a repressed same source", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);l.release(K);l.observe(K,Up,true);l.scene_suspend(true);l.context(true,false);neutral(l);});
    run("strict reveal cannot revive changed then restored direction", [] {auto l=field();l.observe(P,Up,true);l.scene_suspend();l.context(true,false);l.observe(P,Left);l.observe(P,Up);l.scene_suspend(true);l.context(true,false);neutral(l);});
    run("strict reveal cannot revive new press after hard boundary", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(false,true);l.context(true,false);l.release(K);l.observe(K,Up,true);l.scene_suspend(true);l.context(true,false);neutral(l);});
    run("strict reveal discards old pending tap", [] {auto l=field();l.observe(K,Up,true);l.release(K);l.scene_suspend(true);l.context(true,false);neutral(l);});
    run("repeated strict suspension preserves surviving identity", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend();l.context(true,false);l.scene_suspend(true);l.scene_suspend(true);l.context(true,false);take(l,Up,false,true);});
    run("ordinary suspension still promotes valid active hold", [] {auto l=field();l.observe(K,Up,true);l.scene_suspend(false);l.context(true,false);take(l,Up,false,true);});
    std::printf("%u cases passed\n",tests);
}
