#include "pal_keyboard_profile.h"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
using SDL_Scancode = int;
constexpr int SDL_SCANCODE_UNKNOWN=0, SDL_SCANCODE_A=4, SDL_SCANCODE_RETURN=40,
    SDL_SCANCODE_ESCAPE=41, SDL_SCANCODE_F10=67, SDL_SCANCODE_F11=68,
    SDL_SCANCODE_F12=69, SDL_SCANCODE_AC_BACK=270;
constexpr int SDL_EVENT_KEY_DOWN=1, SDL_EVENT_KEY_UP=2, SDL_EVENT_WINDOW_FOCUS_LOST=3,
    SDL_EVENT_WILL_ENTER_BACKGROUND=4, SDL_EVENT_DID_ENTER_BACKGROUND=5, SDL_KMOD_ALT=1;
struct SDL_Event { int type; struct { unsigned windowID; int scancode; bool repeat; int mod; } key{};
    struct { unsigned windowID; } window{}; };
static int window_object;
static int* g_win=&window_object;
static bool focused=true, g_menu_open=false, alt=false;
static bool k[512]{};
static uint16_t real_pad_bits=0;
constexpr uint16_t B_LEFT=0x2000, B_RIGHT=0x8000;
static int* SDL_GetKeyboardFocus() { return focused ? g_win : nullptr; }
static unsigned SDL_GetWindowID(int*) { return 1; }
static uint64_t sat_vblanks() { return 0; }
static int SDL_GetScancodeFromName(const char* raw) {
    const std::string n(raw);
    if (n.size()==1 && n[0]>='A' && n[0]<='Z') return n[0]-'A'+4;
    if (n=="Enter") return SDL_SCANCODE_RETURN;
    if (n=="Escape") return SDL_SCANCODE_ESCAPE;
    if (n=="F10") return SDL_SCANCODE_F10;
    if (n=="F11") return SDL_SCANCODE_F11;
    if (n=="F12") return SDL_SCANCODE_F12;
    return SDL_SCANCODE_UNKNOWN;
}
struct Settings {
    std::map<std::pair<std::string,std::string>,std::string> values;
    std::string get(const std::string& s,const std::string& n) const {
        const auto it=values.find({s,n}); return it==values.end() ? "" : it->second;
    }
    void set(const std::string& s,const std::string& n,const std::string& v) { values[{s,n}]=v; }
} g_settings;
struct Button { const char* name; uint16_t bit; };
static const Button kSaturn[]={{"a",0x400},{"r",0x80},{"left",0x2000}};
static auto ignored=[](const std::string& n) {return SDL_GetScancodeFromName(n.c_str());};
template<class Parse> std::vector<int> names(const Settings& s,const std::string& section,const std::string& name,Parse parse) {
    std::vector<int> out; std::stringstream stream(s.get(section,name)); std::string part;
    while (std::getline(stream,part,',')) {
        const auto first=part.find_first_not_of(' '); if(first==std::string::npos) continue;
        part=part.substr(first,part.find_last_not_of(' ')-first+1);
        const int key=parse(part); if(key>0) out.push_back(key);
    } return out;
}
static void existing_close_hook() { g_menu_open=false; }
static void existing_open_hook() { g_menu_open=true; }
