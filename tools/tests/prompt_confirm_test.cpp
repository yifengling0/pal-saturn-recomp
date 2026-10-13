#include "pal_keyboard_profile.h"
#include <cassert>
#include <cstdio>
using namespace pal_prompt;
static bool valid=true;
static unsigned consumed=0;
static bool begin(){return valid;}
static bool alive(){return valid;}
static void consume(){++consumed;}
int main(){
    const Source a{1,0,40},b{1,0,44},t{3,10,20},pad{2,4,0};
    host_begin=begin;host_valid=alive;host_consume=consume;
    // Opening press, duplicate non-repeat DOWN and a held key cannot skip.
    ledger.press(a,true);
    {Scope scope(true);assert(scope.enabled);assert(!scope.accept());
     ledger.press(a,true);assert(!scope.accept());ledger.release(a);
     ledger.press(a,true);assert(scope.accept());assert(!scope.accept());}
    assert(consumed==1);
    // Holding through a new box is inert. Fresh UP/DOWN is required.
    {Scope scope(true);ledger.press(a,true);assert(!scope.accept());
     ledger.release(a);ledger.press(a,true);assert(scope.accept());}
    ledger.release(a);
    // Down/up in one event pump survives until consumed; no held quarantine.
    {Scope scope(true);ledger.press(t,true);ledger.release(t);
     assert(ledger.held()==0);assert(scope.accept());assert(!scope.accept());}
    // Multiple simultaneous sources still dismiss exactly one box.
    {Scope scope(true);ledger.press(a,true);ledger.press(b,true);ledger.press(pad,true,0x0200);
     assert(ledger.held()==0x0600);assert(scope.accept());assert(!scope.accept());}
    ledger.release(a);ledger.release(b);ledger.release(pad);
    // Touch cancellation removes its owed edge but not another source.
    {Scope scope(true);ledger.press(t,true);ledger.release(t,true);assert(!scope.accept());
     ledger.press(t,true);ledger.press(b,true);ledger.release(t,true);assert(scope.accept());}
    ledger.release(b);
    // Prior queued timestamp / blocked keys are tracked as held, never accepted.
    {Scope scope(true);ledger.press(a,false);ledger.press(a,true);assert(!scope.accept());}
    ledger.release(a);
    // Focus loss cannot carry an edge into the next box or revive old token.
    {Scope scope(true);ledger.press(a,true);valid=false;assert(!scope.accept());
     valid=true;ledger.press(a,true);assert(!scope.accept());
     ledger.press(b,true);assert(scope.accept());}
    ledger.release(a);ledger.release(b);
    {Scope scope(true);assert(!scope.accept());}
    // Timeout destroys pending intent, and unknown/recursive calls cannot claim it.
    {Scope scope(true);ledger.press(t,true);{Scope nested(true);assert(!nested.enabled);}}
    ledger.release(t);
    {Scope scope(true);assert(!scope.accept());}
    {Scope scope(false);assert(!scope.enabled);}
    valid=false;{Scope scope(true);assert(!scope.enabled);} valid=true;
    host_begin=nullptr;{Scope scope(true);assert(!scope.enabled);}
    // One physical input may legally map to direction/Start and both A/C.
    { Ledger l; l.press(a,false,0x1000); l.press(a,false,0x0400); l.press(a,false,0x0200);
      assert(l.held()==0x0600);auto token=l.begin();l.press(a,true,0x0400);
      assert(!l.consume(token));l.release(a);l.press(a,true,0x0400);assert(l.consume(token)); }
    // Cross every source and repeated begin/release sequence.
    for(unsigned i=0;i<10000;++i){Ledger l;Source source{(i%3)+1,0,i};
      l.press(source,true);auto token=l.begin();assert(!l.consume(token));
      l.release(source);l.press(source,true);l.release(source);
      assert(l.consume(token));assert(!l.consume(token));l.end(token);
      assert(!l.consume(l.begin()));}
    std::puts("PASS: prompt opening, quick tap, hold, cancellation, source and scope ledger");
}
