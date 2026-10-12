#include <cstdlib>
#include <cstring>
#include "pal_field_input_api.h"
// Test-only substitute for window/thread/headless/script capability. Production
// links the reviewed host.cpp implementation; this is never shipped with it.
#ifndef TEST_LIVE_HOST
#define TEST_LIVE_HOST 1
#endif
bool test_host_available=TEST_LIVE_HOST!=0;
namespace pal_field_host {
bool available() {
    const char* field=std::getenv("PAL_FIELD_INPUT");
    return test_host_available && (!field || !std::strcmp(field,"1"));
}
}
