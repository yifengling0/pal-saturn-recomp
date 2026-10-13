#include <SDL3/SDL.h>
#include "pal_keyboard_profile.h"
#include "pal_tap_hold.h"
#include <map>
#include <vector>
#include <string>
#include <algorithm>
#include <cassert>
#include <cstdio>
static SDL_Window* g_win;
static SDL_Renderer* g_ren;
static int g_out_w=320,g_out_h=224;
struct Config {bool headless=false,resume=false;std::string input;};static Config g_cfg;
static bool sat_resuming(){return false;}
static bool g_edge_focus=true,g_edge_foreground=true,g_menu_open=false,g_layout_edit=false,g_quitting=false;
struct TouchFinger{float x,y;bool dpad;};static std::map<SDL_FingerID,TouchFinger>g_fingers;
struct Layout{};
static Layout pad_layout(){return {};}
static bool menu_button_shown(){return false;}
static bool touch_on_menu(Layout,float,float){return false;}
static bool touch_on_dpad(Layout,float x,float){return x<100;}
static bool touch_shown(){return true;}
static uint16_t touch_buttons(Layout,const std::vector<TouchFinger>&f){return !f.empty()&&f[0].x>200?0x400:0;}
struct Input{int button,axis;uint16_t bit;};struct Map{std::vector<Input>inputs;int trigger=16000;};
struct Pad{SDL_JoystickID id;SDL_Gamepad* pad;Map map;};static std::vector<Pad>g_pads;
struct Slots{int slot_of(SDL_JoystickID){return 0;}};static Slots g_slots;
static uint16_t g_held_over[1]{},g_buttons[1]{};
static PalTapHold g_pal_taps[1];
static pal_keyboard::PressLatch g_pc_press;
static std::vector<std::pair<SDL_Scancode,uint16_t>>g_keys{{SDL_SCANCODE_C,0x400}};
static std::vector<SDL_Scancode>g_confirm_keys{SDL_SCANCODE_RETURN,SDL_SCANCODE_SPACE};
static bool semantic_key(SDL_Scancode k){return k==SDL_SCANCODE_RETURN || k==SDL_SCANCODE_SPACE;}
