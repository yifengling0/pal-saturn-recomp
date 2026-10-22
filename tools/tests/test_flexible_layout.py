"""Compile real geometry/settings and extracted host editor code, without a ROM.

The fixtures replace OS/rendering/file-I/O endpoints only. No device execution
or subjective mobile usability is implied by these native C++ regressions.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'third_party/saturn-recomp-pal/runtime'


def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    pos = opening + 1
    while depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    return text[start:pos] + '\n'


def compile_run(source, mobile=False):
    with tempfile.TemporaryDirectory(prefix='pal-flex-layout-') as tmp:
        tmp = Path(tmp)
        cpp, exe = tmp / 'test.cpp', tmp / 'test'
        cpp.write_text(source, encoding='utf8')
        command = [os.environ.get('CXX', 'g++'), '-std=c++17', '-O1',
                   '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                   '-I' + str(RUNTIME / 'src/host'), '-I' + str(RUNTIME / 'include'),
                   '-I' + str(RUNTIME / 'src/video'), '-I' + str(RUNTIME / 'src/machine'),
                   str(cpp), str(RUNTIME / 'src/host/settings.cpp'), '-o', str(exe)]
        if mobile:
            command += ['-DPAL_OHOS_DEFAULTS', '-DPAL_OHOS_DISPLAY']
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr


COMMON = r'''
#include "pal_display_layout.h"
#include "touch_positions.h"
#include "touch_split_pad.h"
#include "settings.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <map>
#include <vector>
static bool near(float a,float b){return std::fabs(a-b)<.05f;}
'''


def test_profiles_inherit_snapshot_roundtrip_and_geometry():
    source = COMMON + r'''
int main(){
    Settings s; std::vector<std::string> errors;
    const std::string old="; personal configuration\n[display]\nlayout = below\ngame_percent = 70\n"
        "orientation = auto\n[touch]\nsize = 150\ndpad_x = 1234\nsplit_face_y = 8765\n"
        "[keyboard]\na = Return\n";
    s.read(old,errors);assert(errors.empty());
    assert(!s.has_section("display landscape")&&!s.has_section("touch portrait"));
    assert(s.get("display landscape","layout")=="below");
    assert(s.number("touch portrait","size")==150);
    assert(s.number("touch landscape","split_face_y")==8765);
    // First change snapshots all legacy values, not just the changed property.
    s.set("display landscape","split_axis","below");
    s.set("touch landscape","dpad_x","9000");
    assert(s.number("touch landscape","size")==150);
    assert(s.number("touch portrait","dpad_x")==1234);
    s.set("touch","size","110");
    assert(s.number("touch landscape","size")==150);
    assert(s.number("touch portrait","size")==110);
    s.set("display portrait","picture_scale","80");
    s.set("touch portrait","split_face_y","2000");
    const auto saved=s.write_over(old);
    assert(saved.find("; personal configuration")!=std::string::npos);
    assert(saved.find("[display landscape]")!=std::string::npos);
    Settings restored;restored.read(saved,errors);assert(errors.empty());
    for(auto section:{"display","display landscape","display portrait","touch","touch landscape","touch portrait","keyboard"})
        for(auto key:s.keys(section))assert(restored.get(section,key)==s.get(section,key));
    assert(restored.write_over(saved)==saved);
    // Malformed profile values do not leak into either profile or the baseline.
    Settings invalid;invalid.read("[display portrait]\npicture_scale = 0\npicture_x = 101\nsplit_axis = bad\n"
        "[touch landscape]\nsize = 999\ndpad_x = -2\n",errors);
    assert(errors.size()==5);
    assert(invalid.number("display portrait","picture_scale")==100);
    assert(invalid.number("touch landscape","dpad_x")==-1);
    using namespace pal_display;
    for(auto size:std::vector<std::pair<int,int>>{{1920,1080},{1080,1920},{1280,480},{480,1280},{640,360},{360,640},{320,120},{120,320},{512,512}}){
        const auto [w,h]=size;
        assert(std::string(profile(w,h))==(h>w?"portrait":"landscape"));
        // Legacy manual choice still follows current window with no new axis setting.
        const auto legacy=regions(w,h,"below",60,{});
        assert(h>w?near(legacy.game.h,std::floor(h*.6f)):near(legacy.game.w,std::floor(w*.6f)));
        for(auto axis:{"auto","below","right"})for(int percent:{30,60,70}){
            const auto region=regions(w,h,"right",percent,{},axis);
            assert(region.split);
            const bool below=std::string(axis)=="below"||(std::string(axis)=="auto"&&h>w);
            assert(below?region.controls.y>0:region.controls.x>0);
            for(float aspect:{1.f,4.f/3.f,320.f/224})for(int scale:{-1,40,70,100,1000})for(int x:{-1,0,50,100,1000})for(int y:{0,50,100}){
                auto fitted=touch_game_viewport((int)region.game.w,(int)region.game.h,aspect,false);
                auto placed=place_picture(fitted,region.game,scale,x,y);
                assert(near(placed.w/placed.h,aspect));
                assert(placed.x>=region.game.x-.05f&&placed.y>=region.game.y-.05f);
                assert(placed.x+placed.w<=region.game.x+region.game.w+.05f);
                assert(placed.y+placed.h<=region.game.y+region.game.h+.05f);
                if(x==0)assert(near(placed.x,region.game.x));
                if(y==100)assert(near(placed.y+placed.h,region.game.y+region.game.h));
            }
        }
        auto overlay=regions(w,h,"overlay",60,{},"below");assert(!overlay.split&&overlay.game.w==w&&overlay.game.h==h);
    }
    // Explicit split axis must not defeat fold-crease avoidance in automatic mode.
    Fold fold{true,1,{Rect{0,.49f,1,.02f}}};
    auto automatic=regions(1200,800,"auto",60,fold,"right");
    assert(automatic.game.y+automatic.game.h<=392.01f&&automatic.controls.y>=407.99f);
    std::cout<<"profiles, migration, geometry and fold precedence passed\n";
}
'''
    compile_run(source)
    compile_run(source, mobile=True)


def test_real_host_editor_transactions_and_resize_profile_boundaries():
    host = (RUNTIME / 'src/host/host.cpp').read_text(encoding='utf8')
    signatures = ['static std::string layout_section(', 'static std::string display_section() {',
                  'static std::string touch_section() {', 'static bool split_controls()',
                  'static std::string position_key(', 'static void refresh_display_regions()',
                  'static TouchPositions saved_touch_positions()', 'static TouchEditToolbar touch_edit_toolbar()',
                  'static void touch_edit_begin()', 'static void touch_edit_finish(',
                  'static void touch_edit_pointer(']
    functions = [function(host, name) for name in signatures]
    source = COMMON + r'''
using Uint32=unsigned;using SDL_FingerID=long long;
struct SDL_FRect {float x=0,y=0,w=0,h=0;};
enum {SDL_EVENT_FINGER_DOWN=1,SDL_EVENT_FINGER_UP,SDL_EVENT_FINGER_CANCELED,SDL_EVENT_FINGER_MOTION};
Settings g_settings;
static bool g_layout_edit=false,g_edit_dragging=false,g_picture_edit=false,g_confirm_layout=false,g_slider_active=false;
static int g_edit_picture_x=50,g_edit_picture_y=50,g_edit_picture_scale=100;
static TouchPositions g_edit_positions;
static TouchGroup g_edit_group=TouchGroup::Dpad;
static SDL_FingerID g_edit_finger=0;
static float g_edit_offset_x=0,g_edit_offset_y=0;
static int g_out_w=1200,g_out_h=600,g_menu_page=0,g_menu_at=0;
static SDL_FRect g_dst;
static pal_display::Regions g_regions;
static std::string g_region_profile;
static std::map<int,int> g_fingers,g_lifted,g_unread;
static int g_touch_held=0,boundaries=0,saves=0;
static bool save_ok=true;
static std::string disk;
static void field_boundary(){++boundaries;}
template<class... T> static void sat_note(const char*,T...){}
static bool host_settings_save(){++saves;if(save_ok)disk=g_settings.write_over(disk);return save_ok;}
namespace pal_ohos_display {
static void request_orientation(int){}
static pal_display::Fold snapshot(){return {};}
}
struct TouchEditToolbar {SDL_FRect cancel,reset,done;};
static float display_scale(){return 1;}
static bool inside(SDL_FRect r,float x,float y){return x>=r.x&&y>=r.y&&x<r.x+r.w&&y<r.y+r.h;}
static TouchLayout pad_layout(){return touch_mobile_layout(g_out_w,g_out_h,1,100,100);}
static TouchPosition position_for_center(TouchGroup group,float x,float y){return touch_position_for_center(pad_layout(),group,g_out_w,g_out_h,1,x,y);}
''' + '\n'.join(functions) + r'''
int main(){
    std::vector<std::string> problems;
    g_settings.read("[display]\nlayout = below\n[touch]\ndpad_x = 3000\n",problems);
    assert(problems.empty());
    refresh_display_regions();
#ifdef PAL_OHOS_DEFAULTS
    assert(display_section()=="display landscape"&&touch_section()=="touch landscape");
#else
    assert(display_section()=="display"&&touch_section()=="touch");
    assert(!g_regions.split);
#endif
    disk=g_settings.write_over("");const auto original=disk;
    touch_edit_begin();assert(g_layout_edit&&!g_picture_edit);
    g_edit_positions[0]={8000,9000};touch_edit_finish(false);
    assert(!g_layout_edit&&disk==original&&saves==0);
    touch_edit_begin();g_edit_positions[0]={8000,9000};save_ok=false;
    touch_edit_finish(true);assert(g_layout_edit&&disk==original&&saves==1);
    assert(g_settings.number(touch_section(),position_key(0,false))!=8000);
    save_ok=true;touch_edit_finish(true);assert(!g_layout_edit&&saves==2);
    assert(g_settings.number(touch_section(),position_key(0,false))==8000);
    Settings reloaded;reloaded.read(disk,problems);assert(problems.empty());
    assert(reloaded.number(touch_section(),position_key(0,false))==8000);
    // Picture editing never saves the touched layout merely by opening/closing.
    const auto touch_before=g_settings.get(touch_section(),position_key(0,false));
    touch_edit_begin();g_picture_edit=true;g_edit_picture_x=0;g_edit_picture_y=100;g_edit_picture_scale=60;
    auto prior=disk;save_ok=false;touch_edit_finish(true);
    assert(g_layout_edit&&disk==prior&&g_settings.number(display_section(),"picture_scale")==100);
    save_ok=true;touch_edit_finish(true);
    assert(g_settings.number(display_section(),"picture_x")==0&&g_settings.number(display_section(),"picture_y")==100);
    assert(g_settings.get(touch_section(),position_key(0,false))==touch_before);
    // Same-profile resize cancels capture but may preserve its normalized draft.
    touch_edit_begin();g_edit_dragging=true;g_fingers[1]=1;g_touch_held=1;
    g_out_w=1000;refresh_display_regions();assert(g_layout_edit&&!g_edit_dragging&&g_fingers.empty()&&g_touch_held==0);
    // Rotation cannot commit the old orientation's draft into the new section.
    g_edit_positions[0]={1111,2222};g_edit_dragging=true;
    g_out_w=600;g_out_h=1000;refresh_display_regions();
#ifdef PAL_OHOS_DEFAULTS
    assert(!g_layout_edit&&!g_edit_dragging&&touch_section()=="touch portrait");
    assert(g_settings.number("touch portrait","split_dpad_x")!=1111);
#else
    assert(g_layout_edit&&!g_edit_dragging&&touch_section()=="touch");
#endif
    // A second finger cannot steal the picture drag; cancel only releases owner.
    touch_edit_begin();g_picture_edit=true;g_dst={100,100,200,200};
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,7,150,150);assert(g_edit_dragging&&g_edit_finger==7);
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,8,300,300);assert(g_edit_finger==7);
    touch_edit_pointer(SDL_EVENT_FINGER_CANCELED,8,0,0);assert(g_edit_dragging);
    touch_edit_pointer(SDL_EVENT_FINGER_MOTION,7,9999,9999);
    assert(g_edit_picture_x==100&&g_edit_picture_y==100);
    touch_edit_pointer(SDL_EVENT_FINGER_MOTION,7,-9999,-9999);
    assert(g_edit_picture_x==0&&g_edit_picture_y==0);
    touch_edit_pointer(SDL_EVENT_FINGER_CANCELED,7,0,0);assert(!g_edit_dragging);
    prior=disk;touch_edit_finish(false);assert(disk==prior);
    // Actual toolbar Reset changes only the open editor draft until Done.
    const std::string other_display=display_section()=="display landscape"?"display portrait":"display landscape";
    const std::string other_touch=touch_section()=="touch landscape"?"touch portrait":"touch landscape";
    g_settings.set(other_display,"picture_x","23");
    g_settings.set(other_touch,"split_dpad_x","5999");
    disk=g_settings.write_over("");prior=disk;
    const auto picture_before=g_settings.number(display_section(),"picture_x");
    touch_edit_begin();g_edit_positions[0]={8888,7777};
    auto toolbar=touch_edit_toolbar();
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,1,toolbar.reset.x+1,toolbar.reset.y+1);
    for(const auto& pos:g_edit_positions)assert(pos.x==-1&&pos.y==-1);
    assert(disk==prior&&g_settings.number(display_section(),"picture_x")==picture_before);
    touch_edit_finish(false);assert(disk==prior);
    touch_edit_begin();
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,1,toolbar.reset.x+1,toolbar.reset.y+1);
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,1,toolbar.done.x+1,toolbar.done.y+1);
    assert(!g_layout_edit&&g_settings.number(touch_section(),position_key(0,false))==-1);
    assert(g_settings.number(display_section(),"picture_x")==picture_before);
    assert(g_settings.number(other_display,"picture_x")==23&&g_settings.number(other_touch,"split_dpad_x")==5999);
    prior=disk;
    touch_edit_begin();g_picture_edit=true;g_edit_picture_x=7;g_edit_picture_y=8;g_edit_picture_scale=40;
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,1,toolbar.reset.x+1,toolbar.reset.y+1);
    assert(g_edit_picture_x==50&&g_edit_picture_y==50&&g_edit_picture_scale==100);
    assert(disk==prior);
    touch_edit_finish(false);assert(disk==prior);
    touch_edit_begin();g_picture_edit=true;
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,1,toolbar.reset.x+1,toolbar.reset.y+1);
    touch_edit_pointer(SDL_EVENT_FINGER_DOWN,1,toolbar.done.x+1,toolbar.done.y+1);
    assert(!g_layout_edit&&g_settings.number(display_section(),"picture_x")==50);
    assert(g_settings.number(display_section(),"picture_y")==50&&g_settings.number(display_section(),"picture_scale")==100);
    assert(g_settings.number(touch_section(),position_key(0,false))==-1);
    assert(g_settings.number(other_display,"picture_x")==23&&g_settings.number(other_touch,"split_dpad_x")==5999);
    assert(boundaries>=3);
    std::cout<<"actual host editor save/cancel/failure and profile boundaries passed\n";
}
'''
    compile_run(source)
    compile_run(source, mobile=True)


def test_actual_host_interruption_branch_clears_drag_slider_and_pending_taps():
    host = (RUNTIME / 'src/host/host.cpp').read_text(encoding='utf8')
    event = function(host, 'static void on_event(const SDL_Event& e)')
    branch = event[event.index('    case SDL_EVENT_WINDOW_FOCUS_LOST:'):
                   event.index('    case SDL_EVENT_QUIT:')]
    source = COMMON + r'''
enum {SDL_EVENT_WINDOW_FOCUS_LOST=1,SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED,
    SDL_EVENT_WINDOW_RESIZED,SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED,
    SDL_EVENT_WILL_ENTER_BACKGROUND,SDL_EVENT_DID_ENTER_BACKGROUND,SDL_EVENT_DISPLAY_ORIENTATION};
static std::map<int,int> g_fingers,g_lifted,g_unread;
static int g_touch_held=0,g_slider_finger=0;
static bool g_slider_active=false,g_edit_dragging=false;
struct Taps {unsigned pending=0;void forget(unsigned mask){pending&=~mask;}};
static std::array<Taps,2> g_pal_taps;
static void actual_interruption(int event){switch(event){
''' + branch + r'''
default:break;}}
int main(){
    for(int event:{SDL_EVENT_WINDOW_FOCUS_LOST,SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED,
            SDL_EVENT_WINDOW_RESIZED,SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED,
            SDL_EVENT_WILL_ENTER_BACKGROUND,SDL_EVENT_DID_ENTER_BACKGROUND,SDL_EVENT_DISPLAY_ORIENTATION}){
        g_fingers[1]=1;g_lifted[1]=1;g_unread[1]=1;
        g_touch_held=0xffff;g_slider_finger=19;g_slider_active=true;g_edit_dragging=true;
        for(auto& taps:g_pal_taps)taps.pending=0xffff;
        actual_interruption(event);
        assert(g_fingers.empty()&&g_lifted.empty()&&g_unread.empty());
        assert(!g_touch_held&&!g_slider_finger&&!g_slider_active&&!g_edit_dragging);
        for(auto& taps:g_pal_taps)assert(taps.pending==0);
    }
}
'''
    compile_run(source)
