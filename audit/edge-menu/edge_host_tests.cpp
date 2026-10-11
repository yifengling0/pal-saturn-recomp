// Real host.cpp event and menu-loop paths, with SDL devices/rendering/guest stubbed.
#include HOST_SOURCE
#include <cstdio>
#include <cstdarg>
#include <filesystem>
#include <thread>
SaturnConfig g_cfg;
std::atomic<const char*> g_host_call{nullptr};
std::atomic<int> g_host_paused{0};
static int checks=0,failures=0;
#define CHECK(e) do { ++checks; if (!(e)) { ++failures; std::printf("FAIL %d: %s\n",__LINE__,#e); } } while(0)
static int width=1600,height=900,stops=0,pauses=0,resumes=0,polls=0,delays=0;
static float density=1;
static bool physical_held=false,in_loop=false,keyboard[SDL_SCANCODE_COUNT]{};
static uint64_t guest_vblanks=1234;
void sat_note(const char*,...) {}
void state_stop(const char*) { ++stops; }
uint64_t sat_vblanks() { return guest_vblanks; }
void write_png(const std::string&,const Frame&) {}
bool bios_pal() { return true; }
extern "C" float SDL_GetWindowDisplayScale(SDL_Window*) {return density;}
extern "C" float SDL_GetWindowPixelDensity(SDL_Window*) {return density;}
extern "C" bool SDL_GetWindowSize(SDL_Window*,int*w,int*h){*w=width/density;*h=height/density;return true;}
extern "C" bool SDL_GetWindowSizeInPixels(SDL_Window*,int*w,int*h){*w=width;*h=height;return true;}
extern "C" bool SDL_GetCurrentRenderOutputSize(SDL_Renderer*,int*w,int*h){*w=width;*h=height;return true;}
extern "C" const bool* SDL_GetKeyboardState(int*n){if(n)*n=SDL_SCANCODE_COUNT;return keyboard;}
extern "C" SDL_Keymod SDL_GetModState(){return SDL_KMOD_NONE;}
extern "C" bool SDL_GetGamepadButton(SDL_Gamepad*,SDL_GamepadButton b){return physical_held&&b==SDL_GAMEPAD_BUTTON_SOUTH;}
extern "C" Sint16 SDL_GetGamepadAxis(SDL_Gamepad*,SDL_GamepadAxis){return 0;}
extern "C" bool SDL_GamepadConnected(SDL_Gamepad*){return true;}
extern "C" bool SDL_PauseAudioStreamDevice(SDL_AudioStream*){++pauses;CHECK(g_menu_open);return true;}
extern "C" bool SDL_ResumeAudioStreamDevice(SDL_AudioStream*){++resumes;CHECK(!g_menu_open);CHECK(g_host_paused==0);return true;}
extern "C" bool SDL_PollEvent(SDL_Event* e){
 if(!in_loop)return false;
 CHECK(g_host_paused==1);CHECK(guest_vblanks==1234);++polls;
 if(polls==2){*e={};e->type=SDL_EVENT_KEY_DOWN;e->key.scancode=SDL_SCANCODE_AC_BACK;return true;}
 return false;
}
extern "C" void SDL_Delay(Uint32){if(in_loop){++delays;CHECK(g_host_paused==1);CHECK(guest_vblanks==1234);std::this_thread::sleep_for(std::chrono::milliseconds(2));}}
void ui_fill_rounded(SDL_FRect,float,SDL_FColor) {}
void ui_fill_circle(float,float,float,SDL_FColor) {}
void ui_text(float,float,float,const std::string&,SDL_FColor,bool,UiAlign) {}
float ui_text_width(float,const std::string&,bool){return 1;}
static void event(Uint32 type){SDL_Event e{};e.type=type;on_event(e);}
static int serial=100;
static void finger(Uint32 type,int id,float x,float y,uint64_t ms=0,SDL_TouchID device=0){SDL_Event e{};e.type=type;e.tfinger.touchID=device;e.tfinger.fingerID=id;e.tfinger.x=x/width;e.tfinger.y=y/height;e.tfinger.timestamp=1000000000ULL+ms*1000000;on_event(e);}
static void reset(){
 menu_close();g_pads.clear();g_slots=PadSlots(kHostSlots);g_keys.clear();physical_held=false;
 width=g_out_w=1600;height=g_out_h=900;density=1;g_settings=Settings{};g_settings_path.clear();g_settings_text=Settings::default_text();g_cfg.after.clear();g_touchscreen=true;g_quitting=false;g_audio=nullptr;g_last=nullptr;
 event(SDL_EVENT_WINDOW_FOCUS_LOST);event(SDL_EVENT_WINDOW_FOCUS_GAINED);event(SDL_EVENT_DID_ENTER_FOREGROUND);
 g_settings.set("touch","edge_menu","true");g_settings.set("touch","controls","on");g_settings.set("touch","layout_version","2");read_pads();++serial;
}
static void swipe(bool right=false,uint64_t duration=200){int id=++serial;float x=right?width-4.f:4.f,dx=right?-150.f:150.f;finger(SDL_EVENT_FINGER_DOWN,id,x,200);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_MOTION,id,x+dx,200,duration/2);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_UP,id,x+dx,200,duration);}
static bool edge_row(MenuId& result){auto l=menu_layout();for(int p=0;p<l.pages;++p){g_menu_page=p;for(auto&r:menu_layout().rows)if(std::string(menu_label(r.id))=="侧滑菜单"||std::string(menu_label(r.id))=="Edge swipe"){result=r.id;return true;}}return false;}
int main(int argc,char**argv){
 if(argc!=2)return 2;g_win=reinterpret_cast<SDL_Window*>(1);std::filesystem::create_directories(argv[1]);
 // Qualifying swipes confirm on release only, no guest quick-tap backlog.
 for(bool right:{false,true}){reset();swipe(right);CHECK(g_menu_open);CHECK(g_fingers.empty()&&g_unread.empty()&&g_lifted.empty());CHECK(touch_read()==0);CHECK(stops==0);}
 for(bool right:{false,true})for(auto d: {std::pair{0.f,0.f},std::pair{20.f,0.f},std::pair{12.f,25.f},std::pair{-12.f,0.f}}){reset();float x=right?width-20.f:20.f;int id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,x,200);finger(SDL_EVENT_FINGER_MOTION,id,x+(right?-d.first:d.first),200+d.second,100);finger(SDL_EVENT_FINGER_UP,id,x+(right?-d.first:d.first),200+d.second,200);CHECK(!g_menu_open);CHECK(touch_read()==0);}
 reset();swipe(false,600);CHECK(!g_menu_open);CHECK(touch_read()==0);
 // Claimed motion may cross actual buttons but never inject them, even on cancellation.
 reset();auto button=pad_layout().buttons.front();int id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);finger(SDL_EVENT_FINGER_MOTION,id,button.x,button.y,100);CHECK(touch_read()==0);finger(SDL_EVENT_FINGER_UP,id,button.x,button.y,200);CHECK(!g_menu_open&&touch_read()==0);
 // A pressed D-pad sliding through/away from its edge remains a D-pad finger.
 reset();auto l=pad_layout();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,l.dpad_x-l.dpad_r*.6f,l.dpad_y);CHECK(touch_read()&B_LEFT);finger(SDL_EVENT_FINGER_MOTION,id,4,l.dpad_y,100);CHECK(touch_read()&B_LEFT);finger(SDL_EVENT_FINGER_MOTION,id,200,l.dpad_y,150);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_UP,id,200,l.dpad_y,200);touch_read();CHECK(!g_menu_open&&touch_read()==0);
 // Existing gameplay touch plus second edge finger preserves normal controls.
 reset();button=pad_layout().buttons.front();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,button.x,button.y);CHECK(touch_read()==button.bit);int other=++serial;finger(SDL_EVENT_FINGER_DOWN,other,4,200,10);finger(SDL_EVENT_FINGER_UP,other,154,200,200);CHECK(!g_menu_open);CHECK(touch_read()==button.bit);finger(SDL_EVENT_FINGER_UP,id,button.x,button.y,220);touch_read();CHECK(touch_read()==0);
 // Second finger cancels the edge candidate but still drives its ordinary
 // button. The original owner never becomes gameplay input after cancellation.
 for(bool owner_first:{false,true}){reset();id=++serial;other=++serial;button=pad_layout().buttons.front();finger(SDL_EVENT_FINGER_DOWN,id,4,200);finger(SDL_EVENT_FINGER_DOWN,other,button.x,button.y,10);CHECK(touch_read()==button.bit);finger(SDL_EVENT_FINGER_MOTION,id,button.x,button.y,50);CHECK(touch_read()==button.bit);finger(SDL_EVENT_FINGER_UP,owner_first?id:other,154,200,100);CHECK(!g_menu_open&&touch_read()==(owner_first?button.bit:0));finger(SDL_EVENT_FINGER_UP,owner_first?other:id,154,200,200);CHECK(!g_menu_open&&touch_read()==0);swipe();CHECK(g_menu_open);}
 // Regression from the independent reviewer: expired edge -> A -> owner Up ->
 // third A -> keyboard menu -> fresh Resume. No inherited input blockade.
 reset();button=pad_layout().buttons.front();id=++serial;other=++serial;
 finger(SDL_EVENT_FINGER_DOWN,id,4,200);finger(SDL_EVENT_FINGER_MOTION,id,4,200,600);
 finger(SDL_EVENT_FINGER_DOWN,other,button.x,button.y,700);CHECK(touch_read()==button.bit);
 finger(SDL_EVENT_FINGER_UP,id,4,200,800);int third=++serial;finger(SDL_EVENT_FINGER_DOWN,third,button.x,button.y,900);CHECK(touch_read()==button.bit);
 int new_edge=++serial;finger(SDL_EVENT_FINGER_DOWN,new_edge,4,200,910);finger(SDL_EVENT_FINGER_UP,new_edge,154,200,920);CHECK(!g_menu_open);CHECK(touch_read()==button.bit);
 SDL_Event menu_key{};menu_key.type=SDL_EVENT_KEY_DOWN;menu_key.key.scancode=SDL_SCANCODE_AC_BACK;on_event(menu_key);CHECK(g_menu_open);
 auto resume_row=menu_layout().rows.front();CHECK(resume_row.id==M_RESUME);int fresh=++serial;finger(SDL_EVENT_FINGER_DOWN,fresh,resume_row.r.x+resume_row.r.w/2,resume_row.r.y+resume_row.r.h/2,1000);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_UP,fresh,500,400,1100);finger(SDL_EVENT_FINGER_UP,other,button.x,button.y,1200);finger(SDL_EVENT_FINGER_UP,third,button.x,button.y,1200);CHECK(touch_read()==0);
 // Even while the original owner remains held, a new menu touch can Resume;
 // the old owner tail cannot reopen or activate a newly exposed item.
 reset();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);on_event(menu_key);CHECK(g_menu_open);resume_row=menu_layout().rows.front();fresh=++serial;finger(SDL_EVENT_FINGER_DOWN,fresh,resume_row.r.x+resume_row.r.w/2,resume_row.r.y+resume_row.r.h/2,100);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open&&touch_read()==0);finger(SDL_EVENT_FINGER_UP,fresh,500,400,250);
 // Custom menu at the side keeps first priority; existing enlarged button hit areas win.
 reset();g_settings.set("touch","menu_x","0");g_settings.set("touch","menu_y","5000");l=pad_layout();id=++serial;float mx=l.menu_x-(l.menu_hit_r>0?l.menu_hit_r:1.5f*l.menu_r)+1;CHECK(mx<width*.05f);finger(SDL_EVENT_FINGER_DOWN,id,mx,l.menu_y);CHECK(g_menu_open);finger(SDL_EVENT_FINGER_UP,id,mx,l.menu_y,100);
 reset();g_settings.set("touch","face_x","0");g_settings.set("touch","face_y","3000");l=pad_layout();bool found=false;float bx=0,by=0;uint16_t bit=0;for(int y=0;y<height&&!found;++y)for(int x=0;x<=24&&!found;++x){auto held=touch_buttons(l,{{(float)x,(float)y,false}});if(held&&!touch_on_dpad(l,x,y)&&!touch_on_menu(l,x,y)){found=true;bx=x;by=y;bit=held;}}CHECK(found);if(found){id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,bx,by);CHECK(touch_read()==bit);finger(SDL_EVENT_FINGER_MOTION,id,bx+150,by,100);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_UP,id,bx+150,by,200);touch_read();CHECK(!g_menu_open);}
 // Hidden pad and auto-hidden physical controller retain this independent entry.
 reset();g_settings.set("touch","controls","off");CHECK(!touch_shown());swipe();CHECK(g_menu_open);
 reset();g_settings.set("touch","controls","auto");g_slots.connect(77,"mock");g_pads.push_back({reinterpret_cast<SDL_Gamepad*>(1),77,{{{SDL_GAMEPAD_BUTTON_SOUTH,-1,B_A}},16000,16000}});physical_held=true;CHECK(!touch_shown());read_pads();CHECK(g_buttons[0]==B_A);swipe(true);CHECK(g_menu_open);menu_close();read_pads();CHECK(g_buttons[0]==0);physical_held=false;read_pads();physical_held=true;read_pads();CHECK(g_buttons[0]==B_A);
 // Menu/editor gestures never recursively open or alter scene state on release.
 reset();menu_open();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_MOTION,id,154,200,100);finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open);
 reset();menu_open();touch_edit_begin();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,300);finger(SDL_EVENT_FINGER_MOTION,id,154,300,100);finger(SDL_EVENT_FINGER_UP,id,154,300,200);CHECK(g_menu_open&&g_layout_edit);CHECK(touch_read()==0);touch_edit_finish(false);
 // Edge owner released over a Resume row still cannot activate that row.
 reset();menu_open();auto layout=menu_layout();SDL_FRect resume{};for(auto&r:layout.rows)if(r.id==M_RESUME)resume=r.r;menu_close();id=++serial;float y=resume.y+resume.h/2,x=resume.x+resume.w/2;finger(SDL_EVENT_FINGER_DOWN,id,4,y);finger(SDL_EVENT_FINGER_UP,id,x,y,200);CHECK(g_menu_open);finger(SDL_EVENT_FINGER_UP,id,x,y,201);CHECK(g_menu_open);
 // Interruptions require a fresh gesture; late tails never open a menu.
 for(auto type:{SDL_EVENT_WINDOW_FOCUS_LOST,SDL_EVENT_WILL_ENTER_BACKGROUND,SDL_EVENT_DID_ENTER_BACKGROUND,SDL_EVENT_WINDOW_RESIZED,SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED}){reset();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);event(type);event(SDL_EVENT_WINDOW_FOCUS_GAINED);event(SDL_EVENT_DID_ENTER_FOREGROUND);finger(SDL_EVENT_FINGER_MOTION,id,154,200,100);finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open&&touch_read()==0);swipe();CHECK(g_menu_open);}
 reset();event(SDL_EVENT_WINDOW_FOCUS_LOST);swipe();CHECK(!g_menu_open);touch_read();event(SDL_EVENT_WINDOW_FOCUS_GAINED);swipe();CHECK(g_menu_open);
 reset();event(SDL_EVENT_DID_ENTER_BACKGROUND);swipe();CHECK(!g_menu_open);touch_read();event(SDL_EVENT_DID_ENTER_FOREGROUND);swipe();CHECK(g_menu_open);
 reset();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);width=900;height=1600;finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open);
 reset();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);finger(SDL_EVENT_FINGER_CANCELED,id,154,200,100);finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open&&touch_read()==0);swipe();CHECK(g_menu_open);
 // Resize/180-degree orientation does not turn a second live contact into
 // a first finger, even when the normal pad is hidden.
 for(auto type:{SDL_EVENT_WINDOW_RESIZED,SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED,SDL_EVENT_DISPLAY_ORIENTATION,SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED})for(bool claimed:{false,true}){
  reset();g_settings.set("touch","controls","off");id=++serial;other=++serial;
  finger(SDL_EVENT_FINGER_DOWN,id,claimed?4:500,200);event(type);
  finger(SDL_EVENT_FINGER_DOWN,other,4,200,10);finger(SDL_EVENT_FINGER_UP,other,154,200,100);CHECK(!g_menu_open);
  finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open&&touch_read()==0);
  swipe();CHECK(g_menu_open);
 }
 reset();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);event(SDL_EVENT_DISPLAY_ORIENTATION);finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open);
 // WILL-background clears existing normal held input before orphan-tail
 // quarantine begins; no stale button waits for a later DID event.
 reset();button=pad_layout().buttons.front();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,button.x,button.y);CHECK(touch_read()==button.bit);event(SDL_EVENT_WILL_ENTER_BACKGROUND);CHECK(g_fingers.empty()&&g_touch_held==0);finger(SDL_EVENT_FINGER_UP,id,button.x,button.y,100);CHECK(touch_read()==0);event(SDL_EVENT_DID_ENTER_FOREGROUND);swipe();CHECK(g_menu_open);
 // Unknown OS duplicate behavior is not guessed: AC_BACK remains normal Back.
 reset();swipe();CHECK(g_menu_open);SDL_Event back{};back.type=SDL_EVENT_KEY_DOWN;back.key.scancode=SDL_SCANCODE_AC_BACK;on_event(back);CHECK(!g_menu_open);on_event(back);CHECK(g_menu_open);
 // A key opens/closes the menu while a gesture finger is held: its late Up
 // must not reopen settings after the explicit close.
 reset();id=++serial;finger(SDL_EVENT_FINGER_DOWN,id,4,200);on_event(back);CHECK(g_menu_open);on_event(back);CHECK(!g_menu_open);finger(SDL_EVENT_FINGER_UP,id,154,200,200);CHECK(!g_menu_open&&touch_read()==0);
 // Real menu loop pauses/resumes the existing audio path, offsets host time,
 // leaves the guest clock stand-in unchanged, and does not start a machine.
 reset();swipe();CHECK(g_menu_open);g_audio=reinterpret_cast<SDL_AudioStream*>(1);g_audio_jitter=true;g_audio_resets=0;g_audio_pause_errors=g_audio_resume_errors=0;pauses=resumes=polls=delays=0;g_base=Clock::now();const auto before=g_base;in_loop=true;menu_loop();in_loop=false;CHECK(pauses==1&&resumes==1);CHECK(g_audio_resets==2);CHECK(g_audio_pause_errors==0&&g_audio_resume_errors==0);CHECK(g_host_paused==0&&!g_menu_open);CHECK(g_base-before>=std::chrono::milliseconds(2));CHECK(guest_vblanks==1234&&stops==0);CHECK(delays>=1);g_audio=nullptr;
 // Bilingual toggle is reachable, writes the proper key, and reset is touch-only.
 reset();g_settings_path=std::string(argv[1])+"/edge-host.ini";g_settings_text="; keep\n[touch]\nedge_menu = true\n[keyboard]\na = Space\n[gamepad]\na = b\n[controls]\nkeyboard_profile = pc98\n";g_settings.set("keyboard","a","Space");g_settings.set("gamepad","a","b");menu_open();MenuId toggle=M_PAD;CHECK(edge_row(toggle));if(edge_row(toggle)){menu_activate(toggle);CHECK(!g_settings.flag("touch","edge_menu"));bool exists=false;auto saved=settings_load(g_settings_path,exists);CHECK(exists&&saved.find("edge_menu = false")!=std::string::npos);Settings disk;std::vector<std::string> notices;disk.read(saved,notices);CHECK(!disk.flag("touch","edge_menu"));menu_close();swipe();CHECK(!g_menu_open);CHECK(menu_button_shown());menu_open();menu_adjust(toggle,1);CHECK(g_settings.flag("touch","edge_menu"));menu_adjust(toggle,-1);CHECK(!g_settings.flag("touch","edge_menu"));touch_reset();CHECK(g_settings.flag("touch","edge_menu")==Settings{}.flag("touch","edge_menu"));CHECK(g_settings.get("keyboard","a")=="Space"&&g_settings.get("gamepad","a")=="b");saved=settings_load(g_settings_path,exists);CHECK(saved.find("keyboard_profile = pc98")!=std::string::npos&&saved.find("; keep")!=std::string::npos);}
 CHECK(pal_host_ui_feature_version()==13); // UI13 edge identity, not proof of device/publication.
 std::printf("%d actual edge-host checks, %d failures; SDL/guest/audio mocked, no device\n",checks,failures);return failures?1:0;
}
