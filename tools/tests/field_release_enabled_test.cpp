#include <cstdio>
#include <cstdlib>
#include "pal_release_runtime.h"
extern bool test_host_available;
int main() {
    const char* c=std::getenv("PAL_FIELD_CONTINUITY");
    const char* f=std::getenv("PAL_FIELD_INPUT");
    const bool expected=(!c || std::strcmp(c,"0")) && (!f || !std::strcmp(f,"1"));
    test_host_available=true;
    const bool first=pal_release_runtime::enabled();
    test_host_available=false;
    const bool unavailable=pal_release_runtime::enabled();
    test_host_available=true;
    const bool restored=pal_release_runtime::enabled();
    if(first!=expected || unavailable || restored!=expected) {
        std::fprintf(stderr,"FAIL enabled expected=%d actual=%d unavailable=%d restored=%d\n",
            expected,first,unavailable,restored);return 1;
    }
    std::puts("PASS dynamic host availability"); return 0;
}
