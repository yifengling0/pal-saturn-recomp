"""Run the shipped background pause helper against lifecycle and quit events."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def test_background_wait_services_events_and_excludes_pause_from_pacing():
    patch = (ROOT/'patches/0027-ohos-background-production-pause.patch').read_text(encoding='utf8')
    start = patch.index('+static void wait_in_background() {')
    end = patch.index('+#endif', start)
    helper = '\n'.join(line[1:] for line in patch[start:end].splitlines() if line.startswith('+'))
    with tempfile.TemporaryDirectory(prefix='pal-ohos-background-') as folder:
        source = Path(folder)/'pause.cpp'
        source.write_text(r'''
#include <cassert>
#include <chrono>
#include <stdexcept>
struct Clock {
    using time_point=std::chrono::steady_clock::time_point;
    static inline time_point tick{};
    static time_point now(){return tick;}
};
Clock::time_point g_base;
namespace pal_ohos_audio { bool bg; bool backgrounded(){return bg;} }
bool root_stack; int polls,delays,handled; bool quit,throws;
constexpr int SDL_EVENT_QUIT=1, Foreground=2;
struct SDL_Event {int type;};
struct HostCall {explicit HostCall(const char*){assert(root_stack);} };
void tasks_on_thread_stack(void (*fn)(void*),void* arg){
    assert(!root_stack);root_stack=true;fn(arg);root_stack=false;
}
bool SDL_PollEvent(SDL_Event* event){
    assert(root_stack);++polls;
    if(quit){quit=false;event->type=SDL_EVENT_QUIT;return true;}
    if(delays==3){event->type=Foreground;++delays;return true;}
    return false;
}
void on_event(const SDL_Event& event){
    assert(root_stack);++handled;
    if(throws)throw std::runtime_error("lifecycle failure");
    if(event.type==Foreground)pal_ohos_audio::bg=false;
}
void SDL_Delay(int ms){assert(root_stack);++delays;Clock::tick+=std::chrono::milliseconds(ms);}
''' + helper + r'''
void reset(){Clock::tick={};g_base={};root_stack=false;polls=delays=handled=0;
    quit=throws=false;pal_ohos_audio::bg=true;}
int main(){
    reset();wait_in_background();
    assert(!pal_ohos_audio::bg && handled==1 && polls==5);
    assert(g_base.time_since_epoch()==std::chrono::milliseconds(30));
    assert(!root_stack);
    reset();quit=true;wait_in_background();
    assert(handled==1 && delays==0 && pal_ohos_audio::bg && !root_stack);
    reset();pal_ohos_audio::bg=false;wait_in_background();
    assert(polls==0 && delays==0 && g_base==Clock::time_point{});
    reset();quit=throws=true;
    try{wait_in_background();assert(false);}catch(const std::runtime_error&){}
    assert(handled==1 && delays==0);
}
''', encoding='utf8')
        exe = Path(folder)/('pause.exe' if os.name=='nt' else 'pause')
        compile_result = subprocess.run([os.environ.get('CXX','g++'),'-std=c++17',
            '-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],capture_output=True,text=True)
        assert compile_result.returncode == 0, compile_result.stderr
        subprocess.run([str(exe)],check=True,capture_output=True,timeout=5)
