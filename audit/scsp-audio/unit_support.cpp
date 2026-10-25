#include "state.h"
#include <cstdlib>
#include <cstdio>
void sound_irq_changed() {}
void sound_main_irq() {}
void sat_trace(const char*, ...) {}
[[noreturn]] void state_fail(const char* what) { std::fprintf(stderr, "%s\n", what); std::abort(); }
#ifdef LEGACY_SCSP
// No carry part exists in the baseline. This adapter only allows linking the
// SAME tests; it does not simulate the new DSP and cannot make its tests pass.
void scspdsp_state(State&) {}
void scspdsp_reset() {}
#endif
