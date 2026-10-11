// Actual isolated candidate host.cpp tests. No SDL window/device is created.
// OS/audio/game side effects are stubbed; SDL geometry/event handlers under test are real source.
#include HOST_SOURCE
#include <cstdio>
#include <cmath>
#include <cstdarg>
#include <set>
#include <filesystem>
#include <cstdlib>
SaturnConfig g_cfg;
std::atomic<const char*> g_host_call{nullptr};
std::atomic<int> g_host_paused{0};
static float test_scale=1;
static int test_w=1920,test_h=1080,stops=0;
static bool test_pal=false;
static std::string diagnostic;
static int diagnostic_lines=0;
void sat_note(const char* format,...) {char message[1024];va_list a;va_start(a,format);vsnprintf(message,sizeof message,format,a);va_end(a);if(std::string(message).rfind("layoutdiag ",0)==0){diagnostic=message;++diagnostic_lines;}}
void state_stop(const char*) { ++stops; }
uint64_t sat_vblanks() { return 0; }
void write_png(const std::string&,const Frame&) {}
bool bios_pal() { return test_pal; }
extern "C" float SDL_GetWindowDisplayScale(SDL_Window*) { return test_scale; }
extern "C" float SDL_GetWindowPixelDensity(SDL_Window*) { return test_scale; }
extern "C" bool SDL_GetWindowSize(SDL_Window*,int*w,int*h) { *w=test_w/test_scale;*h=test_h/test_scale;return true; }
extern "C" bool SDL_GetWindowSizeInPixels(SDL_Window*,int*w,int*h) { *w=test_w;*h=test_h;return true; }
extern "C" bool SDL_GetCurrentRenderOutputSize(SDL_Renderer*,int*w,int*h) { *w=test_w;*h=test_h;return true; }
void ui_fill_rounded(SDL_FRect,float,SDL_FColor) {}
void ui_fill_circle(float,float,float,SDL_FColor) {}
void ui_text(float,float,float,const std::string&,SDL_FColor,bool,UiAlign) {}
float ui_text_width(float,const std::string&,bool) { return 0; }
static int checks=0,failures=0;
#define CHECK(e) do{++checks;if(!(e)){++failures;std::printf("FAIL %d: %s\n",__LINE__,#e);}}while(0)
static bool near(float a,float b){return std::fabs(a-b)<0.03;}

static unsigned finger_serial=1000;
static void finger(Uint32 type,Uint64 id,float x,float y){SDL_Event e{};e.type=type;e.tfinger.fingerID=id;e.tfinger.x=x/g_out_w;e.tfinger.y=y/g_out_h;on_event(e);}
static void tap(float x,float y){unsigned id=++finger_serial;finger(SDL_EVENT_FINGER_DOWN,id,x,y);finger(SDL_EVENT_FINGER_UP,id,x,y);}
static void tap_rect(SDL_FRect r){tap(r.x+r.w/2,r.y+r.h/2);}
static void next_page(){auto l=menu_layout();if(!l.paged||l.pages<2){std::fprintf(stderr,"Requested next page when unavailable\n");std::exit(3);}tap_rect(l.next);}
static std::pair<MenuLayout,MenuRow> locate(MenuId id){
  auto first=menu_layout();
  for(int i=0;i<first.pages;++i){auto l=menu_layout();for(auto& r:l.rows)if(r.id==id)return {l,r};if(l.paged&&l.pages>1)next_page();}
  std::fprintf(stderr,"Required MenuId %d is unreachable, not substituting another row\n",(int)id);std::exit(3);
}
static bool contained(SDL_FRect a,SDL_FRect b){return a.x+.02f>=b.x&&a.y+.02f>=b.y&&a.x+a.w<=b.x+b.w+.02f&&a.y+a.h<=b.y+b.h+.02f;}
int main(int argc,char**argv){
 if(argc!=2){std::fprintf(stderr,"usage: actual-host-tests OWNED_TEST_OUTPUT_DIR\n");return 2;}
 g_win=reinterpret_cast<SDL_Window*>(1);
 for(auto wh:{std::pair{2520,1080},std::pair{1080,2520},std::pair{2560,1600},std::pair{1600,2560},std::pair{1280,720},std::pair{1280,648}})
 for(float scale:{1.f,2.f,3.f})for(bool saves:{false,true}) {
  g_out_w=test_w=wh.first;g_out_h=test_h=wh.second;test_scale=scale;g_cfg.after=saves?"not-written":"";g_settings=Settings{};g_touchscreen=true;g_quitting=false;menu_close();menu_open();
  auto first=menu_layout();CHECK(g_menu_page==0);std::set<MenuId> seen;
  for(int page=0;page<first.pages;++page){auto l=menu_layout();CHECK(!l.rows.empty());CHECK(contained(l.panel,{0,0,(float)g_out_w,(float)g_out_h}));auto back=menu_back_rect(l);CHECK(back.w/scale+0.02>=48&&back.h/scale+0.02>=48);
   for(auto& r:l.rows){CHECK(seen.insert(r.id).second);CHECK(contained(r.r,l.panel));CHECK(r.r.h/scale+0.02>=48);if(r.control!=Control::Action){auto a=control_area(l,r);CHECK(a.h/scale+0.02>=48);if(r.control==Control::Choice)for(int i=0;i<choice_count(r.id);++i)CHECK(segment(l,r,i).w/scale+0.02>=48);}}
   if(l.paged&&l.pages>1){int before=g_menu_page;next_page();CHECK(g_menu_page==(before+1)%l.pages);CHECK(!g_slider_active);}
  }
  CHECK(seen.size()==(saves?11:10));CHECK(g_menu_page==0);for(auto id:{M_RESUME,M_PRESENT,M_QUIT,M_PAD,M_SIZE,M_OPACITY,M_STYLE,M_SPACING,M_RESET_TOUCH,M_EDIT_LAYOUT})CHECK(seen.count(id)==1);CHECK(seen.count(M_SAVES)==(saves?1:0));
  auto op=locate(M_OPACITY);auto a=control_area(op.first,op.second);g_settings.set("touch","opacity","55");
  // Red regression: lower-edge minus must subtract, never activate/cycle the row.
  tap(a.x+a.h/2,a.y+a.h-test_scale);CHECK(g_settings.number("touch","opacity")==45);
  auto t=slider_track(op.first,op.second);finger(SDL_EVENT_FINGER_DOWN,11,t.x+t.w/2,t.y+t.h/2);CHECK(g_settings.number("touch","opacity")==60);CHECK(g_slider_active&&g_slider_id==M_OPACITY);
  finger(SDL_EVENT_FINGER_UP,99,0,0);CHECK(g_slider_active);finger(SDL_EVENT_FINGER_MOTION,11,t.x+t.w,t.y+t.h/2);CHECK(g_settings.number("touch","opacity")==100);CHECK(g_settings.number("touch","size")==100);finger(SDL_EVENT_FINGER_UP,11,t.x+t.w,t.y+t.h/2);CHECK(!g_slider_active);
  auto pi=locate(M_PRESENT);for(int i=0;i<3;++i){auto s=segment(pi.first,pi.second,i);tap(s.x+s.w/2,s.y+s.h-test_scale);CHECK(g_settings.get("display","presentation")==kPresent[i]);CHECK(g_menu_open);}
  // All pages expose a real close; keyboard return closes from the last page too.
  if(first.paged&&first.pages>1){while(g_menu_page!=first.pages-1)next_page();CHECK(menu_layout().rows.size()<=first.rows.size());g_menu_at=(int)menu_layout().rows.size()-1;on_menu_key(1,false,false,0);CHECK(g_menu_page==0&&g_menu_at==0);on_menu_key(-1,false,false,0);CHECK(g_menu_page==first.pages-1);}
  tap_rect(menu_back_rect(menu_layout()));CHECK(!g_menu_open&&stops==0);menu_open();CHECK(g_menu_page==0);
  auto re=locate(M_RESUME);tap_rect(re.second.r);CHECK(!g_menu_open&&stops==0);menu_open();tap(0,0);CHECK(!g_menu_open);menu_open();if(menu_layout().paged&&menu_layout().pages>1)next_page();SDL_Event key{};key.type=SDL_EVENT_KEY_DOWN;key.key.scancode=SDL_SCANCODE_AC_BACK;on_event(key);CHECK(!g_menu_open);
 }
 // Compact slider zero-ID stress, page transition cancellation, and live resize.
 g_out_w=test_w=1280;g_out_h=test_h=720;test_scale=3;g_cfg.after="";g_settings=Settings{};g_settings.set("touch","controls","on");menu_open();auto op=locate(M_OPACITY);auto t=slider_track(op.first,op.second);
 finger(SDL_EVENT_FINGER_DOWN,0,t.x+t.w/2,t.y+t.h/2);CHECK(g_slider_active&&g_slider_finger==0);finger(SDL_EVENT_FINGER_CANCELED,99,0,0);CHECK(g_slider_active);finger(SDL_EVENT_FINGER_MOTION,0,t.x+t.w,t.y+t.h/2);CHECK(g_settings.number("touch","opacity")==100);next_page();CHECK(!g_slider_active);finger(SDL_EVENT_FINGER_MOTION,0,t.x,t.y);CHECK(g_settings.number("touch","opacity")==100);
 op=locate(M_OPACITY);t=slider_track(op.first,op.second);finger(SDL_EVENT_FINGER_DOWN,21,t.x+t.w/2,t.y+t.h/2);CHECK(g_slider_active);SDL_Event resize{};resize.type=SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED;test_w=1080;test_h=2520;on_event(resize);CHECK(!g_slider_active&&g_fingers.empty());g_out_w=test_w;g_out_h=test_h;auto rotated=menu_layout();CHECK(rotated.rows.size()>0&&g_menu_page<rotated.pages);auto re=locate(M_RESUME);tap_rect(re.second.r);CHECK(!g_menu_open);
 // Production touch state, same-key multiple fingers, and one-read quick tap semantics.
 auto l=pad_layout();auto a=l.buttons.front();finger(SDL_EVENT_FINGER_DOWN,30,a.x,a.y);finger(SDL_EVENT_FINGER_DOWN,31,a.x,a.y);CHECK(touch_read()==a.bit);finger(SDL_EVENT_FINGER_UP,30,a.x,a.y);CHECK(touch_read()==a.bit);finger(SDL_EVENT_FINGER_UP,31,a.x,a.y);CHECK(touch_read()==0);
 finger(SDL_EVENT_FINGER_DOWN,32,a.x,a.y);finger(SDL_EVENT_FINGER_UP,32,a.x,a.y);CHECK(touch_read()==a.bit);CHECK(touch_read()==0);finger(SDL_EVENT_FINGER_DOWN,33,a.x,a.y);finger(SDL_EVENT_FINGER_CANCELED,33,a.x,a.y);CHECK(touch_read()==0);
 finger(SDL_EVENT_FINGER_DOWN,34,a.x,a.y);CHECK(touch_read()==a.bit);SDL_Event lost{};lost.type=SDL_EVENT_WINDOW_FOCUS_LOST;on_event(lost);CHECK(g_touch_held==0&&g_fingers.empty()&&g_lifted.empty()&&g_unread.empty());finger(SDL_EVENT_FINGER_MOTION,34,a.x,a.y);CHECK(touch_read()==0);
 finger(SDL_EVENT_FINGER_DOWN,35,a.x,a.y);resize.type=SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED;on_event(resize);CHECK(touch_read()==0);finger(SDL_EVENT_FINGER_DOWN,36,a.x,a.y);lost.type=SDL_EVENT_DID_ENTER_BACKGROUND;on_event(lost);CHECK(touch_read()==0);
 // Original integer border and maximum fit retain the same active-picture aspect.
 g_touchscreen=false;g_settings.set("touch","controls","off");menu_close();g_tex_h=224;
 for(auto wh:{std::pair{1920,1080},std::pair{1080,1920},std::pair{1280,800}})for(bool pal:{false,true}){test_w=wh.first;test_h=wh.second;test_pal=pal;g_settings.set("display","presentation","fit");draw();CHECK(near(g_dst.w/g_dst.h,(4.f/3.f)*(pal?256.f/224.f:1.f)));CHECK(near(g_dst.w,test_w)||near(g_dst.h,test_h));auto fit=g_dst;g_settings.set("display","presentation","original");draw();CHECK(near(g_dst.w/g_dst.h,fit.w/fit.h));CHECK(fit.w+.03>=g_dst.w&&fit.h+.03>=g_dst.h);g_settings.set("display","presentation","stretch");draw();CHECK(g_dst.x==0&&g_dst.y==0&&near(g_dst.w,test_w)&&near(g_dst.h,test_h));}
 // New settings are actually reachable and use the right field, including reset isolation.
 g_out_w=test_w=1280;g_out_h=test_h=720;test_scale=3;g_settings=Settings{};g_touchscreen=true;g_quitting=false;menu_close();menu_open();
 g_settings.set("display","presentation","stretch");g_settings.set("keyboard","a","Space");g_settings.set("gamepad","a","b");
 auto sp=locate(M_SPACING);auto track=slider_track(sp.first,sp.second);slide(sp.first,sp.second,track.x+track.w);CHECK(g_settings.number("touch","spacing")==200);CHECK(g_settings.number("touch","size")==100);
 menu_adjust(M_SPACING,-1);CHECK(g_settings.number("touch","spacing")==190);g_settings.set("touch","size","150");g_settings.set("touch","opacity","80");
 auto reset=locate(M_RESET_TOUCH);tap_rect(reset.second.r);CHECK(g_settings.number("touch","size")==100);CHECK(g_settings.number("touch","spacing")==100);CHECK(g_settings.number("touch","opacity")==55);CHECK(g_settings.number("touch","layout_version")==2);CHECK(g_settings.get("display","presentation")=="stretch");CHECK(g_settings.get("keyboard","a")=="Space");CHECK(g_settings.get("gamepad","a")=="b");CHECK(g_menu_open);
 // Every visual key centre and inner edge reaches that Saturn key, never Menu/Dpad.
 for(auto wh:{std::pair{320,240},std::pair{360,800},std::pair{800,360},std::pair{2048,1276}})for(float ds:{1.f,2.f,3.f}) {
  g_out_w=test_w=(int)(wh.first*ds);g_out_h=test_h=(int)(wh.second*ds);test_scale=ds;menu_close();g_settings.set("touch","controls","on");auto layout=pad_layout();
  for(auto& b:layout.buttons)for(float dx:{-.45f,0.f,.45f})for(float dy:{-.45f,0.f,.45f}) {
   float x=b.x+dx*(b.shape==TouchButton::Round?b.w:b.w/2),y=b.y+dy*(b.shape==TouchButton::Round?b.w:b.h/2);
   finger(SDL_EVENT_FINGER_DOWN,701,x,y);CHECK(!g_menu_open);CHECK(touch_read()==b.bit);finger(SDL_EVENT_FINGER_UP,701,x,y);touch_read();
  }
 }
 // Touch-only users cannot lose the independent menu entry after hiding the pad.
 g_settings=Settings{};g_settings.set("touch","controls","off");g_settings.set("touch","menu_button","false");g_touchscreen=true;CHECK(menu_button_shown());auto entry=pad_layout();tap(entry.menu_x,entry.menu_y);CHECK(g_menu_open);auto all=menu_layout();std::set<MenuId> available;for(int page=0;page<all.pages;++page){for(auto& r:menu_layout().rows)available.insert(r.id);if(all.paged&&all.pages>1)next_page();}CHECK(!available.count(M_MENU_BUTTON));
 // Quit requires a distinct confirmation tap. Cancel, close and AC_BACK never stop.
 auto quit=locate(M_QUIT);tap_rect(quit.second.r);CHECK(g_confirm_quit&&g_menu_open&&stops==0);auto cancel=locate(M_CANCEL_QUIT);tap_rect(cancel.second.r);CHECK(!g_confirm_quit&&g_menu_open&&stops==0);
 menu_activate(M_QUIT);tap_rect(menu_back_rect(menu_layout()));CHECK(!g_menu_open&&!g_confirm_quit&&stops==0);menu_open();menu_activate(M_QUIT);SDL_Event back{};back.type=SDL_EVENT_KEY_DOWN;back.key.scancode=SDL_SCANCODE_AC_BACK;on_event(back);CHECK(!g_menu_open&&!g_confirm_quit&&stops==0);
 menu_open();menu_activate(M_QUIT);auto confirm=locate(M_CONFIRM_QUIT);tap_rect(confirm.second.r);CHECK(stops==1&&g_quitting&&!g_menu_open);stops=0;g_quitting=false;menu_open();
 // At the supported 120-logical-pixel menu height, confirmation has visible Next
 // and both actions remain reachable through the actual page-navigation handler.
 for(int logical_height:{120,176,240}) {
  test_w=g_out_w=960;test_h=g_out_h=logical_height*3;test_scale=3;menu_close();menu_open();menu_activate(M_QUIT);auto c=menu_layout();CHECK(c.paged);if(logical_height==120)CHECK(c.pages==2);auto no=locate(M_CANCEL_QUIT);CHECK(no.second.r.h==144);auto yes=locate(M_CONFIRM_QUIT);CHECK(yes.second.r.h==144);tap_rect(menu_back_rect(menu_layout()));CHECK(!g_menu_open&&!g_confirm_quit&&stops==0);
 }
 menu_open();
 // Editor is paused UI: working copy, stable pointer ownership, no injected pad bits.
 test_w=g_out_w=1920;test_h=g_out_h=1080;test_scale=3;menu_close();g_settings=Settings{};g_settings.set("touch","controls","on");menu_open();auto move=locate(M_EDIT_LAYOUT);tap_rect(move.second.r);CHECK(g_layout_edit&&g_menu_open);
 auto base_layout=pad_layout();auto target=touch_group_bounds(base_layout,TouchGroup::Face);float cx=target.x+target.w/2,cy=target.y+target.h/2;
 finger(SDL_EVENT_FINGER_DOWN,800,cx,cy);CHECK(g_edit_dragging&&g_edit_group==TouchGroup::Face);finger(SDL_EVENT_FINGER_MOTION,801,100,100);CHECK(g_edit_positions[(int)TouchGroup::Face].x==-1);finger(SDL_EVENT_FINGER_UP,801,100,100);CHECK(g_edit_dragging);
 finger(SDL_EVENT_FINGER_MOTION,800,-100,5000);CHECK(g_edit_positions[(int)TouchGroup::Face].x==0&&g_edit_positions[(int)TouchGroup::Face].y==10000);CHECK(g_fingers.empty()&&touch_read()==0);CHECK(g_settings.number("touch","face_x")==-1);finger(SDL_EVENT_FINGER_CANCELED,800,0,0);CHECK(!g_edit_dragging);tap_rect(touch_edit_toolbar().cancel);CHECK(!g_layout_edit&&g_menu_open);CHECK(g_settings.number("touch","face_x")==-1);
 // Done via gamepad A, Cancel via gamepad B; stored coordinates survive size/orientation changes.
 touch_edit_begin();g_edit_positions[(int)TouchGroup::Dpad]={1500,8000};SDL_Event gp{};gp.type=SDL_EVENT_GAMEPAD_BUTTON_DOWN;gp.gbutton.button=SDL_GAMEPAD_BUTTON_SOUTH;on_event(gp);CHECK(!g_layout_edit&&g_settings.number("touch","dpad_x")==1500);touch_edit_begin();g_edit_positions[(int)TouchGroup::Dpad]={9000,0};gp.gbutton.button=SDL_GAMEPAD_BUTTON_EAST;on_event(gp);CHECK(!g_layout_edit&&g_settings.number("touch","dpad_x")==1500);
 touch_edit_begin();tap_rect(touch_edit_toolbar().reset);for(auto position:g_edit_positions)CHECK(position.x==-1&&position.y==-1);CHECK(g_settings.number("touch","dpad_x")==1500);tap_rect(touch_edit_toolbar().done);CHECK(!g_layout_edit&&g_settings.number("touch","dpad_x")==-1);
 // OS focus/resize cancel tracking, never leave stale drags able to mutate a position.
 touch_edit_begin();target=touch_group_bounds(pad_layout(),TouchGroup::Dpad);finger(SDL_EVENT_FINGER_DOWN,802,target.x+target.w/2,target.y+target.h/2);CHECK(g_edit_dragging);SDL_Event lost_edit{};lost_edit.type=SDL_EVENT_WINDOW_FOCUS_LOST;on_event(lost_edit);CHECK(!g_edit_dragging);finger(SDL_EVENT_FINGER_MOTION,802,0,0);CHECK(g_edit_positions[(int)TouchGroup::Dpad].x==-1);touch_edit_finish(false);
 // Toolbar controls remain at least 48 logical units and do not overlap. A
 // deliberately overlapping custom Menu still opens settings before game hit tests.
 for(auto wh:{std::pair{960,720},std::pair{1080,2400},std::pair{1920,1080}}){test_w=g_out_w=wh.first;test_h=g_out_h=wh.second;test_scale=3;auto toolbar=touch_edit_toolbar();CHECK(toolbar.cancel.h==144&&toolbar.done.h==144&&toolbar.reset.h==144);CHECK(toolbar.cancel.x+toolbar.cancel.w<=toolbar.reset.x);CHECK(toolbar.reset.x+toolbar.reset.w<=toolbar.done.x);}
 g_settings.set("touch","menu_x","0");g_settings.set("touch","menu_y","10000");g_settings.set("touch","dpad_x","0");g_settings.set("touch","dpad_y","10000");menu_close();auto custom_entry=pad_layout();tap(custom_entry.menu_x,custom_entry.menu_y);CHECK(g_menu_open);CHECK(g_fingers.empty());
 // Actual persistence entry point, in this audit's owned output directory.
 if(argc!=2){std::fprintf(stderr,"Need owned output directory\n");return 2;}
 std::filesystem::create_directories(argv[1]);g_settings_path=std::string(argv[1])+"/actual-host.ini";
 g_settings_text="; retained comment\n[display]\npresentation = original\n[keyboard]\na = Space\n[gamepad]\na = b\n[controls]\nkeyboard_profile = pc98\n[touch]\nsize = 140\nopacity = 75\n";
 g_settings=Settings{};std::vector<std::string> problems;g_settings.read(g_settings_text,problems);
 // A Cancel must leave the actual settings file byte-identical; Done saves just positions.
 host_settings_save();bool file_exists=false;auto before_edit=settings_load(g_settings_path,file_exists);CHECK(file_exists);touch_edit_begin();g_edit_positions[(int)TouchGroup::Menu]={10000,0};touch_edit_finish(false);CHECK(settings_load(g_settings_path,file_exists)==before_edit);
 touch_edit_begin();g_edit_positions[(int)TouchGroup::Menu]={10000,0};touch_edit_finish(true);auto with_position=settings_load(g_settings_path,file_exists);CHECK(with_position.find("menu_x = 10000")!=std::string::npos);CHECK(with_position.find("menu_y = 0")!=std::string::npos);CHECK(with_position.find("size = 140")!=std::string::npos);CHECK(with_position.find("opacity = 75")!=std::string::npos);
 slider_set(M_SPACING,160);bool found=false;auto saved=settings_load(g_settings_path,found);CHECK(found);CHECK(saved.find("spacing = 160")!=std::string::npos);CHECK(saved.find("layout_version = 2")!=std::string::npos);CHECK(saved.find("size = 140")!=std::string::npos);CHECK(saved.find("opacity = 75")!=std::string::npos);
 touch_reset();saved=settings_load(g_settings_path,found);Settings disk;disk.read(saved,problems);CHECK(disk.number("touch","spacing")==100);CHECK(disk.number("touch","size")==100);CHECK(disk.number("touch","opacity")==55);CHECK(disk.get("display","presentation")=="original");CHECK(disk.get("keyboard","a")=="Space");CHECK(disk.get("gamepad","a")=="b");CHECK(saved.find("keyboard_profile = pc98")!=std::string::npos);CHECK(saved.find("; retained comment")!=std::string::npos);
 g_settings_path.clear();g_tex_h=224;g_settings.set("display","presentation","fit");draw();CHECK(diagnostic.find("ohos=1")!=std::string::npos);CHECK(diagnostic.find("logical=")!=std::string::npos);CHECK(diagnostic.find("mode=fit")!=std::string::npos);int count=diagnostic_lines;draw();CHECK(diagnostic_lines==count);g_settings.set("display","presentation","stretch");draw();CHECK(diagnostic_lines==count+1);CHECK(diagnostic.find("mode=stretch")!=std::string::npos);CHECK(g_dst.x==0&&g_dst.y==0&&g_dst.w==test_w&&g_dst.h==test_h);
 // Explicit unsupported boundary: candidate still falls back, so do not assert 48 here.
 test_w=g_out_w=719;test_h=g_out_h=720;test_scale=3;auto unsupported=menu_layout();CHECK(!unsupported.paged);CHECK(menu_back_rect(unsupported).h/test_scale<48);
 std::printf("%d actual-paged-host checks, %d failures; no GUI/device created\n",checks,failures);return failures?1:0;
}
