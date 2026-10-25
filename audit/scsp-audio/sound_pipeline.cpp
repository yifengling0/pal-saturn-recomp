// Synthetic (no game assets) SH2 sound-RAM commands -> REAL Musashi 68000 ->
// REAL SCSP -> REAL sound.cpp batching/WAV, with a recording host-device seam.
// The seam does not synthesize/alter audio. No physical sound-card claim.
#include "saturn.h"
#include "sound.h"
#include "state.h"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <vector>

SaturnConfig g_cfg;
static uint64_t now_ns;
static std::vector<int16_t> delivered;
static unsigned pushes, largest_push;
static FILE* trace_file;
uint64_t sat_now() {return now_ns;}
bool movie_on(){return false;}
std::string movie_wav(){return {};}
void cd_audio_sample(int16_t* s){s[0]=s[1]=0;}
void scu_raise(int){}
bool host_audio_open(){return true;}
void host_audio_push(const int16_t* lr,int frames){
    assert(frames>0);++pushes;largest_push=std::max(largest_push,(unsigned)frames);
    delivered.insert(delivered.end(),lr,lr+2*frames);
}
void host_audio_report(){}
void sat_trace(const char* fmt,...){
    if(!trace_file)return;
    std::fprintf(trace_file,"%llu ",(unsigned long long)now_ns);
    va_list a;va_start(a,fmt);std::vfprintf(trace_file,fmt,a);va_end(a);std::fputc('\n',trace_file);
}
[[noreturn]] void sat_fatal(const char* fmt,...){
    va_list a;va_start(a,fmt);std::vfprintf(stderr,fmt,a);va_end(a);std::abort();
}
[[noreturn]] void state_fail(const char* why){sat_fatal("state: %s",why);}

static uint32_t pc;
void emit(uint16_t w){sound_write(0x05A00000u+pc,w,2);pc+=2;}
void move_imm(uint16_t v,uint32_t address){emit(0x33FC);emit(v);emit(address>>16);emit(address);}
void driver(bool muted_sdir){
    sound_write(0x05A00000,0x0007F000,4);
    sound_write(0x05A00004,0x00000100,4);
    pc=0x100;
    emit(0x46FC);emit(0x2700); // MOVE #$2700,SR; no timer interrupts in this fixture
    move_imm(15,0x100400);
    move_imm(4096,0x100006); // 4096 PCM16 samples per one-shot
    move_imm(31,0x100008);
    move_imm((15<<10)|31,0x10000A);
    move_imm(muted_sdir?0x1FF:0x100,0x10000C);
    move_imm(0xE000,0x100016);
    const uint32_t loop=pc;
    emit(0x3039);emit(0);emit(0x800); // MOVE.W command.l,D0
    emit(0x67F8); // BEQ loop
    move_imm(0x1000,0x100000); // explicitly execute KEY_OFF
    emit(0x33C0);emit(0x0010);emit(0x0002); // MOVE.W D0,SA.l
    move_imm(0x1800,0x100000); // execute KEY_ON
    move_imm(0,0x800);         // acknowledge command in shared RAM
    emit(0x6000);emit(static_cast<uint16_t>(loop-pc)); // BRA.W, base is extension word address
}
void waves(){
    uint32_t rng=1;
    for(int i=0;i<4096;++i){
        const int16_t sine=static_cast<int16_t>(12000*std::sin(2*3.14159265358979323846*441*i/44100));
        const int16_t square=(i%50<25)?10000:-10000;
        rng=rng*1664525u+1013904223u;
        const int16_t noise=static_cast<int16_t>(rng>>16)/2;
        sound_write(0x05A01000+2*i,(uint16_t)sine,2);
        sound_write(0x05A03000+2*i,(uint16_t)square,2);
        sound_write(0x05A05000+2*i,(uint16_t)noise,2);
    }
}
int main(int argc,char**argv){
    assert(argc==4);std::filesystem::path out(argv[1]);std::filesystem::create_directories(out);
    const unsigned batch=std::stoul(argv[2]);assert(batch>=1 && batch<=10000);
    const bool muted=std::string(argv[3])=="sdir-tl255";
    g_cfg.wav=(out/"pipeline.wav").string();trace_file=std::fopen((out/"trace.log").string().c_str(),"wb");assert(trace_file);
    sound_init();driver(muted);waves();sound_power(true);
    uint64_t samples=0;
    auto advance=[&](uint64_t until){
        while(samples<until){samples=std::min<uint64_t>(samples+batch,until);now_ns=(samples*1000000000ull+44099)/44100;sound_tick();}
        assert(delivered.size()==samples*2);
    };
    advance(2205);
    std::ofstream commands(out/"commands.csv");commands<<"sample,sa,ack,pcm_start,pcm_end\n";
    for(uint32_t sa:{0x1000u,0x3000u,0x5000u,0x1000u}){
        const uint64_t start=samples;
        sound_write(0x05A00800,sa,2);advance(start+11025);
        const uint32_t ack=sound_read(0x05A00800,2);assert(ack==0);
        commands<<start<<','<<sa<<','<<ack<<','<<start<<','<<samples<<'\n';
    }
    advance(48510);sound_close();std::fclose(trace_file);
    std::ofstream raw(out/"host-sink.s16le",std::ios::binary);
    for(int16_t s:delivered){const char b[2]={(char)(s&255),(char)((uint16_t)s>>8)};raw.write(b,2);}raw.close();
    std::printf("samples=%zu host_pushes=%u largest_batch=%u mode=%s\n",delivered.size()/2,pushes,largest_push,argv[3]);
}
