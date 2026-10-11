#pragma once
// All entry points run on SDL's application thread. OS callbacks only enqueue copies.
bool pal_ohos_gamepad_start();
void pal_ohos_gamepad_pump();
void pal_ohos_gamepad_set_active(bool active);
void pal_ohos_gamepad_stop();
