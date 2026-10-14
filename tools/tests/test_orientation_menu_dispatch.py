"""Execute actual patched host orientation dispatch without a window or ROM.

Device, editor and layout endpoints are fixtures; the choice handling, menu
activation/adjustment, pointer path and keyboard/controller branches are copied
verbatim from the runtime that the build driver actually prepares.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index('\n}\n', start) + 3]


def test_orientation_menu_keyboard_controller_and_row_dispatch():
    runtime = Path(os.environ.get('PAL_ORIENTATION_MENU_RUNTIME',
                                  ROOT / 'third_party/saturn-recomp-pal/runtime'))
    host = (runtime / 'src/host/host.cpp').read_text(encoding='utf8')
    declarations = host[host.index('enum MenuId {'):host.index('static bool g_menu_open,')]
    signatures = ['static int choice_count(', 'static int choice_at(', 'static void choose(',
                  'static void menu_activate(', 'static void menu_adjust(',
                  'static void menu_tap(', 'static void on_menu_key(']
    # choice_count is intentionally a one-line production function.
    functions = [host[host.index(signatures[0]):].split('\n', 1)[0]]
    functions += [function(host, signature) for signature in signatures[1:]]
    event = host[host.index('static void on_event(const SDL_Event& e) {'):]
    branches = event[event.index('    case SDL_EVENT_KEY_DOWN: {'):
                     event.index('    case SDL_EVENT_MOUSE_BUTTON_DOWN:')]
    source = r'''
#include "settings.h"
#include "pal_display_layout.h"
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>
struct SDL_FRect { float x,y,w,h; };
using SDL_FingerID=int64_t;
using SDL_Scancode=int;
enum { SDL_EVENT_KEY_DOWN=1, SDL_EVENT_GAMEPAD_BUTTON_DOWN,
       SDL_SCANCODE_F12, SDL_SCANCODE_F11, SDL_SCANCODE_RETURN, SDL_SCANCODE_SPACE,
       SDL_SCANCODE_AC_BACK, SDL_SCANCODE_ESCAPE, SDL_SCANCODE_UP, SDL_SCANCODE_DOWN,
       SDL_SCANCODE_LEFT, SDL_SCANCODE_RIGHT, SDL_KMOD_ALT=256, SDL_WINDOW_FULLSCREEN=512,
       SDL_GAMEPAD_BUTTON_BACK=100, SDL_GAMEPAD_BUTTON_GUIDE, SDL_GAMEPAD_BUTTON_DPAD_UP,
       SDL_GAMEPAD_BUTTON_DPAD_DOWN, SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_BUTTON_START,
       SDL_GAMEPAD_BUTTON_EAST, SDL_GAMEPAD_BUTTON_DPAD_LEFT, SDL_GAMEPAD_BUTTON_DPAD_RIGHT };
struct SDL_Event { int type; struct { int scancode; bool repeat=false; int mod=0; } key{};
                   struct { int button; } gbutton{}; };
''' + declarations + r'''
Settings g_settings;
static bool g_menu_open=true,g_confirm_quit=false,g_confirm_layout=false,g_slider_active=false;
static bool g_layout_edit=false;
static int g_menu_at=0,g_menu_page=0,g_out_w=1600,g_out_h=900;
static MenuId g_slider_id=M_SIZE;
static SDL_FingerID g_slider_finger=0;
static int g_win=0,g_edit_group=0;
static float saves=0,refreshes=0;
struct Position {float x,y;};
static Position g_edit_positions[1]{};
static const char* const kOrientations[]={"landscape","portrait","auto"};
static const char* const kPresent[]={"original","fit","stretch"};
static const char* const kPadModes[]={"auto","on","off"};
static const char* const kStyles[]={"western","japanese"};
static bool host_settings_save(){++saves;return true;}
static void refresh_display_regions(){++refreshes;}
static void setting_change(const char* key,const char* value){g_settings.set("touch",key,value);}
static void menu_close(){g_menu_open=false;}
static void menu_open(){g_menu_open=true;}
static void menu_quit(bool){}
static bool split_controls(){return false;}
static void touch_reset(){}
static void touch_edit_begin(){}
static void touch_edit_finish(bool){}
static const char* slider_section(MenuId){return "touch";}
static const char* slider_key(MenuId){return "size";}
static int slider_max(MenuId){return 200;}
static int slider_min(MenuId){return 50;}
static void slider_set(MenuId,int){}
static void slide(const MenuLayout&,const MenuRow&,float){}
static int pad_layout(){return 0;}
static SDL_FRect touch_group_bounds(int,int){return {0,0,1,1};}
static float display_scale(){return 1;}
static Position position_for_center(int,float x,float y){return {x,y};}
static bool inside(SDL_FRect r,float x,float y){return x>=r.x&&y>=r.y&&x<r.x+r.w&&y<r.y+r.h;}
static MenuLayout menu_layout(){
    MenuLayout l{};l.u=1;l.panel={0,0,500,200};
    l.rows.push_back({M_ORIENTATION,Control::Choice,0,{10,20,400,60}});return l;
}
static SDL_FRect menu_back_rect(const MenuLayout&){return {450,0,40,20};}
static SDL_FRect control_area(const MenuLayout&,const MenuRow&){return {200,20,210,60};}
static SDL_FRect segment(const MenuLayout&,const MenuRow&,int i){return {200.f+70*i,20,70,60};}
static void save_shot(){}
static int SDL_GetWindowFlags(int){return 0;}
static void SDL_SetWindowFullscreen(int,bool){}
static bool escape_is_a_button(){return false;}
''' + '\n'.join(functions) + '\nstatic void dispatch(const SDL_Event& e){switch(e.type){\n' + branches + r'''
}}
static void expect(const char* value){assert(g_settings.get("display","orientation")==value);}
static void key(int code,bool repeat=false){SDL_Event e{};e.type=SDL_EVENT_KEY_DOWN;e.key.scancode=code;e.key.repeat=repeat;dispatch(e);}
static void pad(int button){SDL_Event e{};e.type=SDL_EVENT_GAMEPAD_BUTTON_DOWN;e.gbutton.button=button;dispatch(e);}
int main(){
    expect("landscape");
    key(SDL_SCANCODE_RETURN);expect("portrait");
    key(SDL_SCANCODE_SPACE);expect("auto");
    key(SDL_SCANCODE_RETURN,true);expect("auto");
    key(SDL_SCANCODE_RIGHT);expect("landscape");
    key(SDL_SCANCODE_LEFT);expect("auto");
    pad(SDL_GAMEPAD_BUTTON_SOUTH);expect("landscape");
    pad(SDL_GAMEPAD_BUTTON_START);expect("portrait");
    pad(SDL_GAMEPAD_BUTTON_DPAD_LEFT);expect("landscape");
    pad(SDL_GAMEPAD_BUTTON_DPAD_RIGHT);expect("portrait");
    menu_tap(50,50,1);expect("auto"); // The row label follows activation.
    menu_tap(235,50,1);expect("landscape"); // Direct choice segments still work.
    menu_tap(305,50,1);expect("portrait");
    menu_tap(375,50,1);expect("auto");
    assert(saves==12&&refreshes==12&&g_menu_open);
    pad(SDL_GAMEPAD_BUTTON_EAST);assert(!g_menu_open);
}
'''
    with tempfile.TemporaryDirectory(prefix='pal-orientation-dispatch-') as folder:
        folder = Path(folder)
        cpp = folder / 'menu.cpp'
        cpp.write_text(source, encoding='utf8')
        exe = folder / ('menu.exe' if os.name == 'nt' else 'menu')
        compiled = subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++17',
            '-Wall', '-Wextra', '-Werror', '-I' + str(runtime / 'src/host'),
            '-I' + str(runtime / 'include'), str(cpp),
            str(runtime / 'src/host/settings.cpp'), '-o', str(exe)], capture_output=True, text=True)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
