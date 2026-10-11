// Compile the real detached CD block against a deterministic synthetic disc/clock.
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef SATURN_CD_BLOCK_SOURCE
#define SATURN_CD_BLOCK_SOURCE "snapshot/runtime/src/machine/cdblock.cpp"
#endif
#include SATURN_CD_BLOCK_SOURCE
static uint64_t clock_ns;
static uint32_t fail_fad = 0;
static std::vector<uint32_t> reads;
uint64_t sat_now() { return clock_ns; }
void sat_note(const char*, ...) {}
void sat_trace(const char*, ...) {}
[[noreturn]] void sat_fatal(const char* fmt, ...) { char b[1024]; va_list a;va_start(a,fmt);vsnprintf(b,sizeof b,fmt,a);va_end(a);throw std::runtime_error(b); }
[[noreturn]] void state_fail(const char* what) { throw std::runtime_error(what); }
bool cdrom_is_audio(uint32_t fad) { return fad>=10000; }
uint32_t cdrom_leadout() { return 20000; }
int cdrom_tracks(CdTrack* t,int n) { if(n>0)t[0]={150,0x41};if(n>1)t[1]={10000,1};return n>1?2:1; }
bool cdrom_read(uint32_t fad,uint8_t* raw) {
 if(fad==fail_fad)return false;
 reads.push_back(fad);
 for(int i=0;i<2352;++i)raw[i]=uint8_t(fad+i);
 raw[15]=1;return true;
}
static void env(const char* s) {
#ifdef _WIN32
 _putenv_s("SATURN_DATA_CD_SPEED",s?s:"");
#else
 if(s)setenv("SATURN_DATA_CD_SPEED",s,1);else unsetenv("SATURN_DATA_CD_SPEED");
#endif
}
static void init(unsigned speed) {
 env(std::to_string(speed).c_str()); clock_ns=0;reads.clear();fail_fad=0;
 g_next_peri=0;g_cmd_busy=false;g_cdda.clear();g_getlen=2048;g_xcount=0;g_xblocks.clear();g_dir.clear();
 cd_init();g_hirq=0;
}
static void command4(uint16_t a,uint16_t b=0,uint16_t c=0,uint16_t d=0) {
 cd_write(0x90018,a,2);cd_write(0x9001c,b,2);cd_write(0x90020,c,2);cd_write(0x90024,d,2);
}
static uint64_t boundary(uint64_t n,unsigned speed) { auto r=300ull*speed;return (n*1000000000ull+r-1)/r; }
static void tick(uint64_t ns) {clock_ns=ns;cd_tick();}
static void play(uint32_t fad,uint32_t count,int repeat=0) {start_play(0x800000|fad,0x800000|count,repeat);}
static void data_cases(unsigned speed) {
 // Periodic status remains ~60Hz and never scales with data delivery.
 init(speed);tick(0);assert(g_hirq&SCDQ);cd_write(0x90008,~SCDQ,2);
 tick(16666666);assert(!(g_hirq&SCDQ));tick(16666667);assert(g_hirq&SCDQ);
 assert(clock_ns==16666667); // CD block never advances the CPU/guest clock.
 init(speed);play(150,3);
 tick(boundary(1,speed)-1);assert(g_part[0].empty());assert(!(g_hirq&CSCT));
 tick(boundary(1,speed));assert(g_part[0].size()==1&&g_fad==151&&(g_hirq&CSCT));
 cd_write(0x90008,~CSCT,2);assert(!(cd_read(0x90008,2)&CSCT));
 tick(boundary(3,speed));assert(g_part[0].size()==3&&g_fad==153&&g_status==ST_PLAY);assert(!(g_hirq&PEND));
 tick(boundary(4,speed));assert(g_status==ST_PAUSE&&(g_hirq&PEND));
 assert((reads==std::vector<uint32_t>{150,151,152}));
 command4(0x5100);assert(cd_read(0x90024,2)==3);assert(g_hirq&CMOK);
 command4(0x6300,0,0,3);assert((g_hirq&(CMOK|DRDY))==(CMOK|DRDY));
 for(uint32_t f=150;f<153;++f)for(unsigned i=16;i<2064;i+=2){ auto got=cd_read(0x18000,2);assert(got==unsigned((uint8_t(f+i)<<8)|uint8_t(f+i+1)));}
 command4(0x0600);assert(g_out[1]==3*1024&&g_part[0].empty()&&g_free.size()==200&&(g_hirq&EHST));
 // Full buffer stalls rather than skipping or overwriting, recovery preserves sector order.
 init(speed);play(150,250);tick(boundary(250,speed));assert(g_part[0].size()==200&&g_fad==350&&(g_hirq&BFUL));
 command4(0x6200,0,0,100);assert(g_free.size()==100);uint64_t resumed=clock_ns;
 tick(resumed);assert(g_fad==350);tick(resumed+boundary(50,speed)+2);assert(g_fad==400&&g_part[0].size()==150);
 for(size_t i=0;i<reads.size();++i)assert(reads[i]==150+i);
 // Rejected filter sectors still advance and signal CSCT, but never allocate blocks.
 init(speed);g_filter[0].mode=0x40;g_filter[0].fad=999;g_filter[0].range=1;play(150,2);
 tick(boundary(2,speed));assert(g_part[0].empty()&&g_free.size()==200&&g_fad==152&&(g_hirq&CSCT));
 // Read failure has existing retry behavior, no ghost sector or duplicate data.
 init(speed);fail_fad=151;play(150,3);tick(boundary(3,speed));assert(g_fad==151&&g_part[0].size()==1);
 fail_fad=0;tick(clock_ns+boundary(2,speed)+2);assert(g_fad==153&&g_part[0].size()==3);
 // Finite repeat starts a fresh timed period, retains order and final PEND.
 init(speed);play(150,2,1);tick(boundary(3,speed));assert(g_fad==150&&g_repeat_left==0&&g_status==ST_PLAY);
 tick(clock_ns+boundary(3,speed));assert(g_status==ST_PAUSE&&(reads==std::vector<uint32_t>{150,151,150,151}));
 // Pause cancels delivery; a later play starts with a new epoch.
 init(speed);play(150,9);tick(boundary(1,speed));command4(0x11ff,0xffff);tick(1000000000);assert(reads.size()==1&&g_status==ST_PAUSE);
 play(500,2);tick(clock_ns+boundary(2,speed));assert(reads.size()==3&&reads[1]==500&&reads[2]==501);
 // File command sector rounding (2049 bytes -> 2) and partial file offset.
 init(speed);g_dir.push_back({700,2049,0,0,"synthetic"});command4(0x7400,0,0,0);tick(boundary(3,speed));assert((reads==std::vector<uint32_t>{700,701}));
 init(speed);g_dir.push_back({700,4096,0,0,"synthetic"});command4(0x7400,1,0,0);tick(boundary(2,speed));assert((reads==std::vector<uint32_t>{701}));
 // Raw runtime state roundtrip in the same configured speed preserves pending delivery.
 init(speed);play(150,20);tick(boundary(7,speed));State saved;cdblock_state(saved);auto t=clock_ns;
 tick(boundary(12,speed));State expected;cdblock_state(expected);
 saved.loading=true;saved.pos=0;cdblock_state(saved);clock_ns=t;tick(boundary(12,speed));State got;cdblock_state(got);assert(got.data==expected.data);
}
static std::vector<int16_t> audio_case(unsigned speed) {
 init(speed);play(10000,8);std::vector<int16_t> pcm;
 for(unsigned sample=1;sample<=588*6;++sample){tick((uint64_t(sample)*1000000000ull+44099)/44100);int16_t lr[2];cd_audio_sample(lr);pcm.push_back(lr[0]);pcm.push_back(lr[1]);}
 assert(g_fad==10006&&reads.size()==6&&g_part[0].empty());
 // Explicit switch into and out of audio keeps data speed from affecting the audio epoch.
 play(200,2);tick(clock_ns+boundary(2,speed));assert(g_fad==202&&g_part[0].size()==2);
 play(10010,2);auto start=clock_ns;tick(start+13333333);assert(g_fad==10010);tick(start+13333334);assert(g_fad==10011);
 return pcm;
}
int main() {
 env(nullptr);assert(data_cd_speed_from_environment()==1);
 for(const char* bad:{"0","3","8","-1","01","1 "," 2","2x","4.0","999999999999999999999"}) {env(bad);bool failed=false;try{(void)data_cd_speed_from_environment();}catch(const std::runtime_error& e){failed=std::string(e.what()).find("must be 1, 2, or 4")!=std::string::npos;}assert(failed);}
 #ifndef _WIN32
 env("");bool empty_failed=false;try{(void)data_cd_speed_from_environment();}catch(const std::runtime_error&){empty_failed=true;}assert(empty_failed);
#endif
 std::vector<int16_t> baseline;
 for(unsigned speed:{1,2,4}){data_cases(speed);auto pcm=audio_case(speed);if(speed==1)baseline=pcm;else assert(pcm==baseline);std::printf("PASS speed=%u: sector deadlines/order, flags, xfer counts/data, full/recovery, filter, failure, repeat, pause, file, state, CDDA PCM\n",speed);}
 puts("PASS default unset and strict invalid environment parsing");
}
