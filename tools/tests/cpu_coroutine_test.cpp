#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <map>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

struct SH2Context { int cpu=0,imask=0,budget=0; uint32_t vbr=0,r[16]{},pc=0,pr=0; };
SH2Context g_master,g_slave;
SH2Context* g_cpu=&g_master;
struct SlaveReset {};
struct TaskUnwind { uint32_t pc; };
struct Finished {};
struct CallFailure {};
struct ChildFailure {};
struct State { bool loading=false; template<class T> void operator()(T&) {} };
using SH2Func=void(*)(SH2Context&);
constexpr int kBudget=256;
void master_script(SH2Context&);
SH2Func sh2_lookup(uint32_t) { return master_script; }
void sh2_hook_add(uint32_t,void(*)(SH2Context&,uint32_t)) {}
bool sat_in_interrupt() { return false; }
void state_point(SH2Context&) {}
[[noreturn]] void state_fail(const char*) { std::abort(); }
[[noreturn]] void sat_fatal(const char*,...) { std::abort(); }
void sat_trace(const char*,...) {}
void sat_note(const char*,...) {}
void tasks_route(SH2Context&,uint32_t);
void tasks_on_thread_stack(void(*)(void*),void*);
uint32_t ld32(uint32_t) { return 0x6020040; }
void onchip_reset(int) {}
void onchip_input_capture(int) {}
void sh2_call(SH2Context&,uint32_t);
#include "minicoro.h"
#include "machine.inc"
#ifndef PAL_SERIAL_SLAVE_COROUTINE
bool slave_on_thread_stack(void(*)(void*),void*) { return false; }
#endif
#include PAL_TASKS_SOURCE

static uint64_t transcript=1469598103934665603ull;
static unsigned command,ack,boots,callbacks,slices,idles,resets;
static bool fail_child;
static void event(uint64_t v) { transcript=(transcript^v)*1099511628211ull; }
static void callback(void*) {
    if(g_cpu!=&g_slave || mco_running()!=nullptr)std::abort();
    ++callbacks;event(0xC0000+command);
    if(command%97==0)throw CallFailure{};
}
void sh2_call(SH2Context& c,uint32_t) {
    if(fail_child)throw ChildFailure{};
    ++boots;event(0xB0000+boots);
    for(;;) {
        // Real idle and slice give() paths, reset exception handled by actual
        // slave_main(), and serial command/ack writes shared by both variants.
        g_slave_idle=true;++idles;to_master();
        if(c.cpu!=1 || g_cpu!=&g_slave)std::abort();
        const unsigned observed=command;
        for(unsigned j=0;j<64+observed%129;++j) {
            event(observed*257+j);
            if(++g_slave_polls>=64) { ++slices;to_master(); }
        }
        try {
#ifdef PAL_SERIAL_SLAVE_COROUTINE
            tasks_on_thread_stack(callback,nullptr);
#else
            // Original slave already runs on its own OS thread stack.
            callback(nullptr);
#endif
        } catch(CallFailure&) { event(0xE0000+observed); }
        ack=observed;
        event(0xA0000+ack);
    }
}
void master_script(SH2Context&) {
    for(unsigned reset=0;reset<40;++reset) {
        slave_on();
        for(unsigned j=0;j<80;++j) {
            ++command;
            slave_kick();
            while(!g_slave_idle)to_slave();
            if(g_cpu!=&g_master || ack!=command)std::abort();
            event(0xD0000+command);
        }
        slave_off();++resets;
    }
    throw Finished{};
}
int main() {
    const auto start=std::chrono::steady_clock::now();
    // Test calls from the thread's own stack and from actual runtime task
    // fibers. Each child host callback must reach the real root thread stack.
    try { master_script(g_master); } catch(Finished&) {}
    try { tasks_run(0x6020040); } catch(Finished&) {}
    const double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    std::printf("trace=%llu commands=%u ack=%u boots=%u callbacks=%u slices=%u idles=%u resets=%u time_ms=%.3f\n",
      (unsigned long long)transcript,command,ack,boots,callbacks,slices,idles,resets,ms);
    std::fflush(stdout);
#ifdef PAL_SERIAL_SLAVE_COROUTINE
    fail_child=true;
    bool caught=false;
    try { slave_on(); } catch(ChildFailure&) { caught=true; }
    if(!caught || g_cpu!=&g_master)std::abort();
#endif
    // Baseline intentionally retains the original detached parked thread.
    std::_Exit(0);
}
