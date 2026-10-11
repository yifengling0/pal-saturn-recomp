#include HOST_SOURCE
#include "pal_ohos_gamepad.h"
#include "mock_game_controller.h"
#include <cmath>
#include <cstdarg>
#include <cstdlib>
#include <limits>
#include <thread>
#include <dlfcn.h>
static SDL_JoystickID simulated_native=0;
extern "C" bool SDL_IsJoystickVirtual(SDL_JoystickID id){
 if(id==simulated_native)return false;
 static auto real=reinterpret_cast<bool(*)(SDL_JoystickID)>(dlsym(RTLD_NEXT,"SDL_IsJoystickVirtual"));
 return real(id);
}
SaturnConfig g_cfg;
std::atomic<const char*> g_host_call{nullptr};
std::atomic<int> g_host_paused{0};
void sat_note(const char*fmt,...){va_list ap;va_start(ap,fmt);vfprintf(stderr,fmt,ap);fputc('\n',stderr);va_end(ap);}
std::string sat_data_dir(){return "";}
void state_stop(const char*){}
uint64_t sat_vblanks(){return 0;}
void write_png(const std::string&,const Frame&){}
bool bios_pal(){return false;}
void ui_open(SDL_Renderer*){}
void ui_fill_rounded(SDL_FRect,float,SDL_FColor){}
void ui_fill_circle(float,float,float,SDL_FColor){}
void ui_text(float,float,float,const std::string&,SDL_FColor,bool,UiAlign){}
float ui_text_width(float,const std::string&,bool){return 0;}
static int checks=0,failures=0;
#define CHECK(e) do{++checks;if(!(e)){++failures;fprintf(stderr,"FAIL %d: %s\n",__LINE__,#e);}}while(0)
static void tick(){host_pump_input();SDL_Event e;while(SDL_PollEvent(&e))on_event(e);read_pads();}
static void focus(bool yes){SDL_Event e{};e.type=yes?SDL_EVENT_WINDOW_FOCUS_GAINED:SDL_EVENT_WINDOW_FOCUS_LOST;e.window.windowID=SDL_GetWindowID(g_win);on_event(e);read_pads();}
static void button(const char*id,int code,bool down){mock_button(id,code,down);tick();}
static int count(){int n=0;SDL_free(SDL_GetGamepads(&n));return n;}
static void axis(int source,double x,double y=0){mock_axis("one",source,x,y);tick();}
int main(){
 SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS,"1");
 mock_reset();mock_online("one","Test Controller");g_cfg.settings="-";g_cfg.scale=3;
 CHECK(host_window(g_cfg));focus(true);tick();
 CHECK((SDL_WasInit(SDL_INIT_GAMEPAD|SDL_INIT_JOYSTICK)&(SDL_INIT_GAMEPAD|SDL_INIT_JOYSTICK))==(SDL_INIT_GAMEPAD|SDL_INIT_JOYSTICK));
 CHECK(mock_registrations()==23);CHECK(mock_allocations()==0);CHECK(g_pads.size()==1);CHECK(g_slots.slot_of(g_pads[0].id)==0);CHECK(host_pad(0)==0);
 auto first=g_pads[0].id;SDL_Event added{};added.type=SDL_EVENT_GAMEPAD_ADDED;added.gdevice.which=first;
 for(int i=0;i<4;++i)host_pad_event(added);CHECK(g_pads.size()==1);CHECK(!g_slots.taken(1));
 g_touchscreen=true;g_settings.set("touch","controls","auto");CHECK(!touch_shown());
 std::thread producer([]{mock_button("one",2301,true);});producer.join();CHECK(host_pad(0)==0);CHECK(!SDL_GetGamepadButton(g_pads[0].pad,SDL_GAMEPAD_BUTTON_SOUTH));tick();CHECK(host_pad(0)==B_A);
 button("one",2301,false);CHECK(host_pad(0)==0);
 for(auto m:{std::pair{2301,B_A},std::pair{2302,B_B},std::pair{2304,B_X},std::pair{2305,B_Y},std::pair{2307,B_Z},std::pair{2308,B_C},std::pair{2303,B_C},std::pair{2312,B_START},std::pair{2012,B_UP},std::pair{2013,B_DOWN},std::pair{2014,B_LEFT},std::pair{2015,B_RIGHT},std::pair{2309,B_L},std::pair{2310,B_R}}){button("one",m.first,true);CHECK(host_pad(0)==m.second);button("one",m.first,false);CHECK(host_pad(0)==0);}
 // Aliased native C and right shoulder cannot release each other.
 button("one",2308,true);button("one",2303,true);button("one",2303,false);CHECK(host_pad(0)==B_C);button("one",2308,false);CHECK(host_pad(0)==0);
 axis(1,0.1,0.1);CHECK(host_pad(0)==0);axis(1,1,-1);CHECK(host_pad(0)==(B_RIGHT|B_UP));axis(1,-1,1);CHECK(host_pad(0)==(B_LEFT|B_DOWN));axis(1,0,0);CHECK(host_pad(0)==0);
 axis(1,999,-999);CHECK(host_pad(0)==(B_RIGHT|B_UP));axis(1,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity());CHECK(host_pad(0)==0);
 axis(0,-1,1);CHECK(host_pad(0)==(B_LEFT|B_DOWN));button("one",2014,true);axis(0,0,0);CHECK(host_pad(0)==B_LEFT);button("one",2014,false);CHECK(host_pad(0)==0);
 axis(3,0);CHECK(host_pad(0)==0);axis(3,1);CHECK(host_pad(0)==B_L);button("one",2309,true);axis(3,0);CHECK(host_pad(0)==B_L);button("one",2309,false);CHECK(host_pad(0)==0);
 axis(4,1);CHECK(host_pad(0)==B_R);axis(4,0);CHECK(host_pad(0)==0);
 button("one",2301,true);CHECK(host_pad(0)==B_A);focus(false);CHECK(host_pad(0)==0);mock_button("one",2301,true);tick();CHECK(host_pad(0)==0);focus(true);tick();CHECK(host_pad(0)==0);button("one",2301,false);button("one",2301,true);CHECK(host_pad(0)==B_A);button("one",2301,false);
 // Pending press cannot leak through a focus boundary.
 mock_button("one",2302,true);focus(false);focus(true);tick();CHECK(host_pad(0)==0);button("one",2302,false);
 // Host menu still uses SDL BACK, not translated keyboard semantics.
 button("one",2311,true);CHECK(g_menu_open);button("one",2311,false);button("one",2311,true);CHECK(!g_menu_open);button("one",2311,false);CHECK(host_pad(0)==0);
 mock_online("two","Other Controller");tick();CHECK(g_pads.size()==2);button("two",2301,true);CHECK(host_pad(1)==B_A);CHECK(host_pad(0)==0);
 mock_offline("one");tick();CHECK(g_pads.size()==1);CHECK(host_pad(0)==0);CHECK(host_pad(1)==B_A);
 mock_online("one","Test Controller");tick();CHECK(g_pads.size()==2);button("one",2302,true);CHECK(host_pad(0)==B_B);CHECK(host_pad(1)==B_A);
 mock_offline("one");mock_offline("two");tick();CHECK(g_pads.empty());CHECK(touch_shown());CHECK(host_pad(0)==0&&host_pad(1)==0);
 host_shutdown_input();CHECK(mock_registrations()==0);CHECK(mock_allocations()==0);CHECK(count()==0);
 // Startup snapshot includes a pad whose unplug callback arrives during scan.
 mock_reset();mock_online("gone","Race Controller");mock_enum_race("gone");CHECK(pal_ohos_gamepad_start());tick();CHECK(g_pads.empty());CHECK(count()==0);host_shutdown_input();CHECK(mock_registrations()==0);
 mock_late_button("gone",2301,true);CHECK(count()==0);CHECK(mock_allocations()==0);
 mock_reset();mock_enum_connect("new");CHECK(pal_ohos_gamepad_start());tick();CHECK(g_pads.size()==1);button("new",2301,true);CHECK(host_pad(0)==B_A);host_shutdown_input();CHECK(mock_registrations()==0);
 // Partial subscription failure unwinds every successful registration.
 for(int nth:{1,7,20,23}){mock_reset();mock_fail_registration(nth);CHECK(!pal_ohos_gamepad_start());CHECK(mock_registrations()==0);CHECK(count()==0);CHECK(mock_allocations()==0);}
 mock_reset();mock_fail_enumeration(true);CHECK(!pal_ohos_gamepad_start());CHECK(mock_registrations()==0);CHECK(count()==0);
 // Overflow cannot leave a held control latched; recovered topology is neutral.
 mock_reset();mock_online("one","Test Controller");CHECK(pal_ohos_gamepad_start());tick();button("one",2301,true);CHECK(host_pad(0)==B_A);
 for(int i=0;i<2200;++i)mock_button("one",2302,(i%2)==0);tick();CHECK(host_pad(0)==0);CHECK(g_pads.size()==1);CHECK(mock_allocations()==0);
 button("one",2301,false);button("one",2301,true);CHECK(host_pad(0)==B_A);button("one",2301,false);
 // Emulate a future physical SDL backend by reporting one real SDL virtual test
 // device as non-virtual at the API boundary. All polling/state remains real SDL.
 SDL_VirtualJoystickDesc d;SDL_INIT_INTERFACE(&d);d.type=SDL_JOYSTICK_TYPE_GAMEPAD;d.naxes=SDL_GAMEPAD_AXIS_COUNT;d.nbuttons=SDL_GAMEPAD_BUTTON_COUNT;d.name="Future native SDL backend";
 simulated_native=SDL_AttachVirtualJoystick(&d);CHECK(simulated_native!=0);tick();CHECK(g_pads.size()==1);CHECK(g_pads[0].id==simulated_native);CHECK(g_slots.slot_of(simulated_native)==0);CHECK(count()==1);
 SDL_DetachVirtualJoystick(simulated_native);simulated_native=0;tick();CHECK(g_pads.size()==1);CHECK(g_slots.slot_of(g_pads[0].id)==0);CHECK(host_pad(0)==0);button("one",2301,true);CHECK(host_pad(0)==B_A);button("one",2301,false);
 // Topology callbacks continue while focus is absent.
 focus(false);mock_offline("one");tick();CHECK(g_pads.empty());mock_online("two","Other Controller");tick();CHECK(g_pads.size()==1);focus(true);button("two",2301,true);CHECK(host_pad(0)==B_A);button("two",2301,false);
 host_shutdown_input();CHECK(mock_registrations()==0);CHECK(mock_allocations()==0);CHECK(count()==0);
 // Deinit waits for callbacks already converting an OS payload; late callbacks
 // after unregistration return before touching unloaded API pointers.
 mock_reset();mock_online("one","Test Controller");CHECK(pal_ohos_gamepad_start());tick();
 mock_block_getter(true);std::thread blocked([]{mock_button("one",2301,true);});
 for(int i=0;i<100000&&!mock_getter_waiting();++i)std::this_thread::yield();CHECK(mock_getter_waiting());
 std::thread release([]{std::this_thread::sleep_for(std::chrono::milliseconds(15));mock_block_getter(false);});
 host_shutdown_input();blocked.join();release.join();CHECK(mock_registrations()==0);CHECK(mock_allocations()==0);CHECK(count()==0);
 std::thread late([]{mock_late_button("one",2301,true);});late.join();CHECK(count()==0);
 // SDL raw joysticks are diagnosed, never guessed into a gamepad mapping.
 SDL_VirtualJoystickDesc raw;SDL_INIT_INTERFACE(&raw);raw.type=SDL_JOYSTICK_TYPE_FLIGHT_STICK;raw.naxes=2;raw.nbuttons=2;raw.name="Unmapped raw joystick";
 auto rawid=SDL_AttachVirtualJoystick(&raw);CHECK(rawid!=0);CHECK(!SDL_IsGamepad(rawid));tick();CHECK(g_pads.empty());SDL_DetachVirtualJoystick(rawid);tick();
 // Startup enumeration recovers a mapped controller even if its ADDED event
 // was consumed earlier. The later duplicate event cannot allocate another slot.
 SDL_VirtualJoystickDesc pre;SDL_INIT_INTERFACE(&pre);pre.type=SDL_JOYSTICK_TYPE_GAMEPAD;pre.naxes=SDL_GAMEPAD_AXIS_COUNT;pre.nbuttons=SDL_GAMEPAD_BUTTON_COUNT;pre.name="Preconnected event-loss test";
 auto preid=SDL_AttachVirtualJoystick(&pre);CHECK(preid!=0);SDL_FlushEvents(SDL_EVENT_FIRST,SDL_EVENT_LAST);enumerate_pads();CHECK(g_pads.size()==1);CHECK(g_slots.slot_of(preid)==0);added.gdevice.which=preid;host_pad_event(added);CHECK(g_pads.size()==1);host_shutdown_input();SDL_DetachVirtualJoystick(preid);tick();
 SDL_DestroyRenderer(g_ren);SDL_DestroyWindow(g_win);g_ren=nullptr;g_win=nullptr;SDL_Quit();
 printf("%d actual-host/real-SDL/mock-OH checks, %d failures (no OHOS device tested)\n",checks,failures);return failures?1:0;
}
