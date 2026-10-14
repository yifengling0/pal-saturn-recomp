#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <thread>
#include <vector>
namespace runtime {
#include PAL_CPU_HANDOFF
}
int main() {
    using namespace runtime;
    unsigned command=0,ack=0;
    std::vector<unsigned> work;
    std::atomic<bool> done{false};
    std::thread slave([&] {
        {
            std::unique_lock<std::mutex> lock(g_mu);
#ifdef PAL_DIRECTED_CV
            g_cv[1].wait(lock,[] {return g_turn==1;});
#else
            g_cv.wait(lock,[] {return g_turn==1;});
#endif
        }
        for(unsigned i=1;i<=30000;++i) {
            if(command!=i)std::abort();
            work.push_back(i);ack=command^0x31415926;
            give(0);
        }
        done=true;
        // Return the final shutdown handshake without parking again.
        std::lock_guard<std::mutex> lock(g_mu);g_turn=0;
#ifdef PAL_DIRECTED_CV
        g_cv[0].notify_one();
#else
        g_cv.notify_all();
#endif
    });
    const auto begin=std::chrono::steady_clock::now();
    for(unsigned i=1;i<=30000;++i) {
        command=i;give(1);
        if(ack!=(i^0x31415926)||work.size()!=i)std::abort();
    }
    command=0;give(1);slave.join();
    if(!done||work.size()!=30000)std::abort();
    for(unsigned i=0;i<work.size();++i)if(work[i]!=i+1)std::abort();
    std::printf("30000 exact serial handoffs passed in %.3f ms\n",
        std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count());
}
