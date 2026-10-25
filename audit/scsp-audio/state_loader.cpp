// Exercise the REAL state.cpp kParts loader with synthetic empty other devices.
// No game/disc state is fabricated; only SCSP and its carry are meaningful here.
#include "saturn.h"
#include "sound.h"
#include "state.h"
#include <cassert>
#include <cstdarg>
#include <filesystem>
#include <fstream>
#include <stdexcept>

SaturnConfig g_cfg;SH2Context g_master{},g_slave{};SH2Context* g_cpu=&g_master;
uint8_t g_wram_h[0x100000]{},g_wram_l[0x100000]{};
int sh2_active_slots(){return 0;}
const SH2Module* sh2_active_slot(int){return nullptr;}
void sh2_set_active_slot(int,const SH2Module*){}
uint64_t sat_vblanks(){return 0;}
void sat_trace(const char*,...){}
void sat_note(const char*,...){}
[[noreturn]] void sat_fatal(const char* fmt,...){
    char b[1024];va_list a;va_start(a,fmt);std::vsnprintf(b,sizeof b,fmt,a);va_end(a);throw std::runtime_error(b);
}
// These scheduler seams are not exercised by state_load. Define them explicitly
// instead of relying on ELF section garbage collection (PE retains the callers).
[[noreturn]] void sat_stop(const char* why){throw std::runtime_error(why);}
bool sat_in_interrupt(){return false;}
bool state_slave_busy(){return false;}
void sound_irq_changed(){}void sound_main_irq(){}
#define EMPTY(name) void name(State&){}
EMPTY(machine_state) EMPTY(video_state) EMPTY(mmio_state) EMPTY(bios_state)
EMPTY(scu_state) EMPTY(scudsp_state) EMPTY(onchip_state) EMPTY(smpc_state)
EMPTY(cdblock_state) EMPTY(vdp1_state) EMPTY(vdp2_state) EMPTY(sound_state) EMPTY(tasks_state)

void write_state(const std::filesystem::path& path,int mode){
    std::ofstream f(path,std::ios::binary);f.write("SATSTATE",8);uint32_t version=1;f.write((char*)&version,4);
    const struct{const char*name;void(*fn)(State&);} parts[]={
        {"machine",machine_state},{"video",video_state},{"core",core_state},{"mmio",mmio_state},
        {"bios",bios_state},{"scu",scu_state},{"scudsp",scudsp_state},{"onchip",onchip_state},
        {"smpc",smpc_state},{"cdblock",cdblock_state},{"vdp1",vdp1_state},{"vdp2",vdp2_state},
        {"sound",sound_state},{"scsp",scsp_state},{"tasks",tasks_state},{"scspdsp",scspdsp_state}};
    for(auto&p:parts){
        if(mode==0 && std::string(p.name)=="scspdsp")continue;
        if(mode==3 && std::string(p.name)=="scsp")continue;
        State s;p.fn(s);
        if(mode==2 && std::string(p.name)=="scspdsp")s.data.clear();
        uint8_t n=std::strlen(p.name);uint64_t size=s.data.size();
        f.write((char*)&n,1);f.write(p.name,n);f.write((char*)&size,8);f.write((char*)s.data.data(),size);
    }
}
void arm(){
    scsp_reset();scsp_write(0xC00,0x123400,4);scsp_write(0x780,0x100,2);
    scsp_write(0xBFC,0xC000,2);scsp_write(0xBFE,0x100,2);
    int16_t out[2];scsp_sample(0,0,out);
}
void finish(){scsp_write(0xBFC,0,2);scsp_write(0xBFE,0,2);int16_t out[2];scsp_sample(0,0,out);}
int main(int argc,char**argv){
    assert(argc==2);std::filesystem::path dir(argv[1]);std::filesystem::create_directories(dir);
    scsp_reset();write_state(dir/"legacy.state",0);
    arm(); // nonzero carry BEFORE loading missing optional part
    state_load((dir/"legacy.state").string());finish();assert(g_sound_ram[0x200]==0 && g_sound_ram[0x201]==0);
    arm();write_state(dir/"new.state",1);scsp_reset();state_load((dir/"new.state").string());finish();
    assert(g_sound_ram[0x200]==0x12 && g_sound_ram[0x201]==0x34);
    for(int mode:{2,3}){
        write_state(dir/"bad.state",mode);bool rejected=false;
        try{state_load((dir/"bad.state").string());}catch(const std::runtime_error& e){rejected=true;std::printf("expected rejection: %s\n",e.what());}
        assert(rejected);
    }
    std::puts("state loader: legacy default, carry roundtrip, empty-present rejection, required-part rejection passed");
}
