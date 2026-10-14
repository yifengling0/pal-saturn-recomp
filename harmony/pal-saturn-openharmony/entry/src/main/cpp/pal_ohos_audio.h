#pragma once
#include <cstdint>

namespace pal_ohos_audio {
bool open(float volume);
bool active();
void push(const int16_t* pcm, int frames);
void flush();
void pause();
void resume();
void background(bool paused); // event watch: atomics only
bool backgrounded();
void rebase(uint64_t lost_ns);
void report();
void close();
} // namespace pal_ohos_audio
