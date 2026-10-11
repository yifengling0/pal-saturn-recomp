// Pure gesture policy tests. No SDL, window, device or host/menu implementation.
#ifndef EDGE_SOURCE
#define EDGE_SOURCE "touch_edge_swipe.h"
#endif
#include EDGE_SOURCE
#include <cstdio>
#include <limits>

using Edge = TouchEdgeSwipe;
using E = Edge::Event;
using R = Edge::Result;
static int checks = 0, failures = 0;
#define CHECK(e) do { ++checks; if (!(e)) { ++failures; std::printf("FAIL %d: %s\n",__LINE__,#e); } } while(0)
static constexpr uint64_t t0 = 1000000000;
struct Harness {
    Edge edge;
    int w=1000,h=700;
    float s=1;
    bool eligible=true,blocked=false;
    R send(E event,float x,float y,uint64_t ms=0,int64_t finger=0,int64_t device=0) {
        return edge.event(event,{device,finger},x,y,w,h,s,t0+ms*1000000,eligible,blocked);
    }
};

int main() {
    // Both edges over dimension/density combinations. Threshold reached during
    // motion must not open anything; only the release confirms, once.
    for (int width : {320,360,800,1280}) for (int height : {240,700,1080})
    for (float density : {1.f,2.f,3.f}) for (bool right : {false,true}) {
        Harness h; h.w=width*density;h.h=height*density;h.s=density;
        const float x=right ? h.w-4*density : 4*density;
        const float direction=right ? -1.f : 1.f;
        const float distance=std::max(48.f*density,std::min(h.w,h.h)*.08f)+1;
        CHECK(h.send(E::Down,x,h.h*.4f)==R::Consume);
        CHECK(h.send(E::Move,x+direction*distance,h.h*.4f,100)==R::Consume);
        CHECK(h.send(E::Up,x+direction*distance,h.h*.4f,200)==R::OpenMenu);
        CHECK(h.send(E::Up,x+direction*distance,h.h*.4f,201)==R::Pass);
    }
    // A short tap or an insufficient swipe stays consumed with no ghost replay.
    for (float distance : {0.f,3.f,15.f,40.f}) {
        Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);
        CHECK(h.send(E::Move,4+distance,200,100)==R::Consume);
        CHECK(h.send(E::Up,4+distance,200,200)==R::Consume);
        CHECK(h.send(E::Down,4,200,300)==R::Consume);
        CHECK(h.send(E::Up,104,200,400)==R::OpenMenu);
    }
    // Outward, predominantly vertical, excessive vertical travel and timeout
    // each cancel irreversibly, even after returning to a qualifying endpoint.
    for (auto bad : {std::pair{-10.f,0.f},std::pair{10.f,9.f},
                     std::pair{100.f,33.f},std::pair{0.f,-9.f}}) {
        Harness h;CHECK(h.send(E::Down,20,200)==R::Consume);
        CHECK(h.send(E::Move,20+bad.first,200+bad.second,100)==R::Consume);
        CHECK(h.send(E::Up,120,200,200)==R::Consume);
    }
    for (uint64_t ms : {451,500,5000}) {
        Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);
        CHECK(h.send(E::Move,104,200,ms)==R::Consume);
        CHECK(h.send(E::Up,104,200,ms+1)==R::Consume);
    }
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);CHECK(h.send(E::Up,104,200,450)==R::OpenMenu); }
    // At least 2:1 horizontal/vertical; the vertical bound is independent.
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);CHECK(h.send(E::Up,60,228,100)==R::OpenMenu); }
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);CHECK(h.send(E::Up,60,229,100)==R::Consume); }
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);CHECK(h.send(E::Up,60,231,100)==R::Consume); }
    // Non-edge starts, visible-control hits (including D-pad hit expansion),
    // disabled setting, and UI scenes pass through without becoming gestures.
    for(int mode=0;mode<4;++mode) {
        Harness h;h.blocked=mode==1;h.eligible=mode<2;
        float x=mode==0 ? 30.f : 4.f;
        CHECK(h.send(E::Down,x,200)==R::Pass);
        h.eligible=true;h.blocked=false;
        CHECK(h.send(E::Move,4,200,100)==R::Pass);
        CHECK(h.send(E::Up,104,200,200)==R::Pass);
    }
    // A pre-existing contact prevents stealing a new edge finger. Device ID
    // participates in identity; zero and equal finger IDs are valid.
    { Harness h;
      CHECK(h.send(E::Down,500,200,0,7,1)==R::Pass);
      CHECK(h.send(E::Down,4,200,10,7,2)==R::Pass);
      CHECK(h.send(E::Up,104,200,100,7,2)==R::Pass);
      CHECK(h.send(E::Up,500,200,120,7,1)==R::Pass);
      CHECK(h.send(E::Down,4,200,200,7,2)==R::Consume);
      CHECK(h.send(E::Up,104,200,300,7,2)==R::OpenMenu); }
    // Additional fingers cancel recognition but remain ordinary input. Only
    // the originally claimed finger stays isolated until its own Up.
    for(bool owner_first : {false,true}) {
        Harness h;
        CHECK(h.send(E::Down,4,200)==R::Consume);
        CHECK(h.send(E::Down,600,600,10,1)==R::Pass);
        CHECK(h.send(E::Up,104,200,100,owner_first?0:1)==(owner_first?R::Consume:R::Pass));
        CHECK(h.send(E::Down,4,200,110,2)==R::Pass);
        CHECK(h.send(E::Up,104,200,120,owner_first?1:0)==(owner_first?R::Pass:R::Consume));
        CHECK(h.send(E::Up,104,200,130,2)==R::Pass);
        CHECK(h.send(E::Down,4,200,200)==R::Consume);
        CHECK(h.send(E::Up,104,200,300)==R::OpenMenu);
    }
    // Long-held/expired edge owners cannot swallow later gameplay or menu
    // Downs, and ownership cannot be relayed after the original owner lifts.
    { Harness h;
      CHECK(h.send(E::Down,4,200,0,1)==R::Consume);
      CHECK(h.send(E::Move,4,200,600,1)==R::Consume);
      CHECK(h.send(E::Down,500,200,700,2)==R::Pass);
      CHECK(h.send(E::Up,4,200,800,1)==R::Consume);
      CHECK(h.send(E::Down,500,200,900,3)==R::Pass);
      h.eligible=false;
      CHECK(h.send(E::Down,500,200,1000,4)==R::Pass);
      CHECK(h.send(E::Up,500,200,1100,4)==R::Pass);
      h.eligible=true;
      CHECK(h.send(E::Down,4,200,1200,5)==R::Pass);
      CHECK(h.send(E::Up,104,200,1300,5)==R::Pass);
      CHECK(h.send(E::Up,500,200,1400,2)==R::Pass);
      CHECK(h.send(E::Up,500,200,1500,3)==R::Pass);
    }
    // Lifecycle interrupt, CANCELED and duplicate Down never confirm a menu.
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);h.edge.interrupt();
      CHECK(h.send(E::Move,104,200,100)==R::Consume);CHECK(h.send(E::Up,104,200,200)==R::Consume);
      CHECK(h.send(E::Down,4,200,300)==R::Consume);CHECK(h.send(E::Up,104,200,400)==R::OpenMenu); }
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);h.edge.interrupt();
      CHECK(h.send(E::Down,4,200,100)==R::Consume);CHECK(h.send(E::Up,104,200,200)==R::OpenMenu); }
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);CHECK(h.send(E::Cancel,104,200,100)==R::Consume);
      CHECK(h.send(E::Up,104,200,200)==R::Pass); }
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);CHECK(h.send(E::Down,4,200,100)==R::Consume);
      CHECK(h.send(E::Up,104,200,200)==R::Consume); }
    // A scene/eligibility transition cancels but does not release ownership.
    { Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);h.eligible=false;
      CHECK(h.send(E::Move,104,200,100)==R::Consume);h.eligible=true;
      CHECK(h.send(E::Up,104,200,200)==R::Consume); }
    for(int mode=0;mode<3;++mode) {
        Harness h;CHECK(h.send(E::Down,4,200)==R::Consume);
        if(mode==0)h.w=900;else if(mode==1)h.h=600;else h.s=2;
        CHECK(h.send(E::Up,104,200,100)==R::Consume);
    }
    // Non-finite/out-of-bounds points and timestamps preceding Down cancel.
    for(float invalid : {-1.f,1001.f,std::numeric_limits<float>::infinity(),
                          std::numeric_limits<float>::quiet_NaN()}) {
        Harness h;CHECK(h.send(E::Down,invalid,200)==R::Pass);
        CHECK(h.send(E::Up,104,200,100)==R::Pass);
        CHECK(h.send(E::Down,4,200,200)==R::Consume);
        CHECK(h.send(E::Up,invalid,200,300)==R::Consume);
    }
    { Harness h;CHECK(h.send(E::Down,4,200,200)==R::Consume);CHECK(h.send(E::Up,104,200,100)==R::Consume); }
    // After many lifecycle epochs with missing Ups, old and unknown tails are
    // rejected with bounded state; current-epoch normal contacts still pass.
    { Harness h;
      for(int id=0;id<100;++id){CHECK(h.send(E::Down,4,200,0,id)==R::Consume);h.edge.interrupt();}
      CHECK(h.send(E::Move,100,200,100,0)==R::Consume);
      CHECK(h.send(E::Up,100,200,200,99)==R::Consume);
      CHECK(h.send(E::Cancel,100,200,200,900)==R::Consume);
      CHECK(h.send(E::Down,500,200,300,100)==R::Pass);
      CHECK(h.send(E::Move,550,200,350,100)==R::Pass);
      CHECK(h.send(E::Up,550,200,400,100)==R::Pass);
    }
    std::printf("%d pure edge checks, %d failures; no SDL/device/host run\n",checks,failures);
    return failures ? 1 : 0;
}
