#include "saturn.h"
#include "video.h"
bool movie_on(){return false;}
std::string movie_wav(){return g_cfg.wav;}
void movie_frame(const Frame&){if(!g_cfg.video.empty())sat_fatal("MP4 export is not supported on Switch; use WAV/screenshots instead");}
void movie_finish(){}
