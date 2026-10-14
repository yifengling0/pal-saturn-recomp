#pragma once
#include "pal_display_layout.h"

// ArkTS publishes normalized surface coordinates; SDL consumes a coherent copy.
namespace pal_ohos_display {
pal_display::Fold snapshot();
// 0 landscape, 1 portrait, 2 automatic. Changes are delivered to the ArkTS window thread.
void request_orientation(int orientation);
}
