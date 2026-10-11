// Actual Inter + OFL Chinese font metrics on an SDL software-renderer surface.
// Measures text bounds; it does not verify rendered glyph pixels or a device.
#include HOST_SOURCE
#include <cstdarg>
#include <cstdio>
SaturnConfig g_cfg;
std::atomic<const char*> g_host_call{nullptr};
std::atomic<int> g_host_paused{0};
static float density=1;
static int width=2048,height=1276;
void sat_note(const char* f,...) { va_list a;va_start(a,f);vfprintf(stderr,f,a);fputc('\n',stderr);va_end(a); }
void state_stop(const char*) {}
uint64_t sat_vblanks() {return 0;}
void write_png(const std::string&,const Frame&) {}
bool bios_pal(){return true;}
extern "C" float SDL_GetWindowDisplayScale(SDL_Window*) {return density;}
extern "C" float SDL_GetWindowPixelDensity(SDL_Window*) {return density;}
extern "C" bool SDL_GetWindowSize(SDL_Window*,int*w,int*h){*w=width/density;*h=height/density;return true;}
extern "C" bool SDL_GetWindowSizeInPixels(SDL_Window*,int*w,int*h){*w=width;*h=height;return true;}

#include <cassert>
#include <cmath>
#include <set>
static int checks=0, failures=0;
#define CHECK(e) do { ++checks; if (!(e)) {++failures; fprintf(stderr,"FAIL %dx%d density %.1f, page %d, quit %d line %d: %s\n",width,height,density,g_menu_page,(int)g_confirm_quit,__LINE__,#e);} } while(0)
// The renderer returns zero on atlas initialization failure. A maximum-width
// assertion alone would silently pass that failure, so every measurement must
// also be finite and positive (all inputs in this suite are nonempty strings).
static float checked_width(float size,const std::string& text,bool bold=false) {
 const float measured=ui_text_width(size,text,bold);
 CHECK(std::isfinite(measured)&&measured>0);
 return measured;
}
int main() {
 auto* surface=SDL_CreateSurface(1200,1000,SDL_PIXELFORMAT_RGBA32);
 g_ren=SDL_CreateSoftwareRenderer(surface);assert(surface&&g_ren);ui_open(g_ren);
 g_win=reinterpret_cast<SDL_Window*>(1);g_touchscreen=true;
 for(auto logical:{std::pair{320,120},std::pair{320,180},std::pair{360,800},std::pair{800,360},std::pair{426,240},std::pair{960,540},std::pair{2048,1276}})
 for(float scale:{1.f,2.f,3.f})for(bool saves:{false,true})for(bool quit:{false,true}) {
  density=scale;width=g_out_w=(int)(logical.first*scale);height=g_out_h=(int)(logical.second*scale);
  g_settings=Settings{};g_cfg.after=saves?"not-written":"";g_quitting=false;menu_close();menu_open();
  if(quit)menu_activate(M_QUIT);
  auto first=menu_layout();
  for(int page=0;page<first.pages;++page) {
   g_menu_page=page;auto l=menu_layout();const float u=l.u;
   const float header_space=l.panel.w-128*u;
   if(quit) {
    CHECK(checked_width(16*u,hm::text(hm::Text::QuitTitle),true)<=header_space);
    CHECK(checked_width(10*u,hm::text(hm::Text::QuitWarningLine1))<=header_space);
    CHECK(checked_width(10*u,hm::text(hm::Text::QuitWarningLine2))<=header_space);
   } else if(l.paged) {
    auto title=std::string(hm::text(hm::Text::Settings))+" "+std::to_string(page+1)+"/"+std::to_string(l.pages);
    CHECK(checked_width(18*u,title,true)<=header_space);
   }
   for(auto& r:l.rows) {
    auto a=control_area(l,r);
    float right=r.r.x+16*u+checked_width(16*u,menu_label(r.id),true);
    if(r.control==Control::Slider)right+=10*u+checked_width(14*u,"200%");
    CHECK(right<=(r.control==Control::Action?r.r.x+r.r.w-16*u:a.x-6*u));
    if(r.control==Control::Choice)for(int choice=0;choice<choice_count(r.id);++choice)for(bool bold:{false,true}) {
      auto box=segment(l,r,choice);
      CHECK(checked_width(14*u,choice_name(r.id,choice),bold)<=box.w-12*u);
    }
   }
  }
 }
 // The editor strings use the same font metrics as actual draw_touch_editor.
 for(auto logical:{std::pair{320,240},std::pair{360,800},std::pair{640,360},std::pair{800,360},std::pair{2048,1276}})
 for(float scale:{1.f,2.f,3.f})for(int size:{50,100,200}) {
  density=scale;width=g_out_w=(int)(logical.first*scale);height=g_out_h=(int)(logical.second*scale);
  g_settings=Settings{};g_settings.set("touch","size",std::to_string(size));g_quitting=false;menu_close();menu_open();touch_edit_begin();
  auto toolbar=touch_edit_toolbar();
  CHECK(checked_width(14*scale,hm::text(hm::Text::Cancel),true)<=toolbar.cancel.w-8*scale);
  CHECK(checked_width(14*scale,hm::text(hm::Text::ResetPosition),true)<=toolbar.reset.w-8*scale);
  CHECK(checked_width(14*scale,hm::text(hm::Text::Done),true)<=toolbar.done.w-8*scale);
  CHECK(checked_width(12*scale,hm::text(hm::Text::DragGroups))<=width-16*scale);
  auto layout=pad_layout();
  const auto names={hm::Text::Dpad,hm::Text::FaceButtons,hm::Text::LeftShoulder,hm::Text::RightShoulder,hm::Text::Start,hm::Text::Menu};
  int i=0;
  for(auto name:names){auto box=touch_group_bounds(layout,static_cast<TouchGroup>(i++));
    // A selection outline is not a text clip rect. In English, "Menu" may
    // overhang a small circle slightly while remaining fully on-screen.
    float text_width=checked_width(12*scale,hm::text(name),true);
    CHECK(box.x+box.w/2-text_width/2>=0);
    CHECK(box.x+box.w/2+text_width/2<=width);
  }
 }
#if PAL_HOST_MENU_CHINESE
 CHECK(std::string(menu_label(M_PRESENT))=="画面");
 CHECK(std::string(hm::text(hm::Text::QuitWarningLine1))+hm::text(hm::Text::QuitWarningLine2)=="退出不会自动保存游戏进度，请先在游戏内存盘");
#else
 CHECK(std::string(menu_label(M_PRESENT))=="Picture");
 CHECK(std::string(menu_label(M_RESUME))=="Resume");
 CHECK(std::string(hm::text(hm::Text::QuitWarningLine1))=="Quitting does not save game progress.");
#endif
 printf("%d actual-host text bounds checks, %d failures; SDL font measurement across 168 menu geometry combinations plus 45 editor dimension/density/size combinations.\n",checks,failures);
 return failures?1:0;
}
