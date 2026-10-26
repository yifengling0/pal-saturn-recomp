#include "pal_obstacle_stop.h"
#include <cstdlib>
#include <cstring>
#include <saturn/sh2.h>

#ifndef PAL_OBSTACLE_HOOK_VERIFIED
#error "The obstacle stop policy requires the verified original-disc hook"
#endif

namespace {
void stop_manual_fallback(SH2Context& c, uint32_t address) {
    if (!pal_obstacle_stop::frame_address(c.r[14])) return;
    // The collision callee has already overwritten c.pr. The original caller
    // is saved at frame+4 by the mover's unmodified prologue.
    if (!pal_obstacle_stop::matches(c.cpu, address, c.r[14],
            ld32(c.r[14] + 4), c.r[1], c.r[3], ld16(c.r[14]),
            ld16(pal_obstacle_stop::Hook))) return;
    // 4 selects the original switch's out-of-range branch to 06033B90.
    // Move count stays zero: preserve its stop animation, party/camera update,
    // facing and stack unwinding. Never roll coordinates back after a move.
    c.r[1] = 4;
}
struct RegisterObstacleStop {
    RegisterObstacleStop() {
        // Explicit original-game comparison mode, independent of input speed.
        const char* value = std::getenv("PAL_OBSTACLE_STOP");
        if (!value || std::strcmp(value, "0"))
            sh2_hook_add(pal_obstacle_stop::Hook, stop_manual_fallback);
    }
} register_obstacle_stop;
} // namespace
