#include "pal_ohos_gamepad.h"
#include <SDL3/SDL.h>
#include <cstdio>
#if PAL_OHOS_GAMEPAD_BRIDGE
#include <GameControllerKit/game_device.h>
#include <GameControllerKit/game_pad.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <condition_variable>
#include <cstdlib>
#include <dlfcn.h>
#include <map>
#include <mutex>
#include <string>
#include <vector>

// API 21 functions only. Resolve at runtime: the application's existing minimum
// OS (API 16) predates Game Controller Kit and must still load with touch input.
#define PAL_BUTTON_APIS(X) \
 X(LeftShoulder) X(RightShoulder) X(LeftTrigger) X(RightTrigger) \
 X(ButtonMenu) X(ButtonHome) X(ButtonA) X(ButtonB) X(ButtonX) X(ButtonY) X(ButtonC) \
 X(Dpad_LeftButton) X(Dpad_RightButton) X(Dpad_UpButton) X(Dpad_DownButton) \
 X(LeftThumbstick) X(RightThumbstick)
#define PAL_AXIS_APIS(X) X(LeftThumbstick) X(RightThumbstick) X(Dpad) X(LeftTrigger) X(RightTrigger)
#define PAL_DATA_APIS(X) \
 X(OH_GameDevice_GetAllDeviceInfos) X(OH_GameDevice_RegisterDeviceMonitor) X(OH_GameDevice_UnregisterDeviceMonitor) \
 X(OH_GameDevice_DestroyAllDeviceInfos) X(OH_GameDevice_AllDeviceInfos_GetCount) X(OH_GameDevice_AllDeviceInfos_GetDeviceInfo) \
 X(OH_GameDevice_DeviceEvent_GetChangedType) X(OH_GameDevice_DeviceEvent_GetDeviceInfo) X(OH_GameDevice_DestroyDeviceInfo) \
 X(OH_GameDevice_DeviceInfo_GetDeviceId) X(OH_GameDevice_DeviceInfo_GetName) X(OH_GameDevice_DeviceInfo_GetDeviceType) \
 X(OH_GamePad_ButtonEvent_GetDeviceId) X(OH_GamePad_ButtonEvent_GetButtonAction) X(OH_GamePad_ButtonEvent_GetButtonCode) \
 X(OH_GamePad_AxisEvent_GetDeviceId) X(OH_GamePad_AxisEvent_GetAxisSourceType) \
 X(OH_GamePad_AxisEvent_GetXAxisValue) X(OH_GamePad_AxisEvent_GetYAxisValue) X(OH_GamePad_AxisEvent_GetZAxisValue) \
 X(OH_GamePad_AxisEvent_GetRZAxisValue) X(OH_GamePad_AxisEvent_GetHatXAxisValue) X(OH_GamePad_AxisEvent_GetHatYAxisValue) \
 X(OH_GamePad_AxisEvent_GetBrakeAxisValue) X(OH_GamePad_AxisEvent_GetGasAxisValue)
namespace {
struct Api {
#define FIELD(n) decltype(&::n) n = nullptr;
 PAL_DATA_APIS(FIELD)
#define BUTTON_FIELD(n) FIELD(OH_GamePad_##n##_RegisterButtonInputMonitor) FIELD(OH_GamePad_##n##_UnregisterButtonInputMonitor)
 PAL_BUTTON_APIS(BUTTON_FIELD)
#define AXIS_FIELD(n) FIELD(OH_GamePad_##n##_RegisterAxisInputMonitor) FIELD(OH_GamePad_##n##_UnregisterAxisInputMonitor)
 PAL_AXIS_APIS(AXIS_FIELD)
#undef AXIS_FIELD
#undef BUTTON_FIELD
#undef FIELD
} api;
void* library = nullptr;
std::mutex mutex;
std::condition_variable quiet;
bool accepting = false, active = true, overflow = false;
unsigned in_flight = 0;
uint64_t epoch = 0;
bool started = false, prefer_native = false;
std::vector<GameController_ErrorCode(*)()> unregisters;
struct Command {
 enum Kind { Online, Offline, Button, Axis } kind = Online;
 std::string id, name;
 int code = 0;
 bool down = false;
 double x = 0, y = 0;
};
std::vector<Command> commands;
constexpr size_t kMaxCommands = 2048, kMaxPads = 12;
struct Callback {
 bool valid = false; uint64_t generation = 0;
 Callback() { std::lock_guard<std::mutex> lock(mutex); if (accepting) { valid = true; generation = epoch; ++in_flight; } }
 ~Callback() { if (valid) { std::lock_guard<std::mutex> lock(mutex); if (--in_flight == 0) quiet.notify_all(); } }
};
void enqueue(Command c, const Callback& call) {
 std::lock_guard<std::mutex> lock(mutex);
 if (!accepting) return;
 if ((c.kind == Command::Button || c.kind == Command::Axis) && (!active || call.generation != epoch)) return;
 if (commands.size() >= kMaxCommands) { commands.clear(); overflow = true; ++epoch; return; }
 commands.push_back(std::move(c));
}
bool info(GameDevice_DeviceInfo* p, Command& out) {
 char* id = nullptr; char* name = nullptr; GameDevice_DeviceType type = UNKNOWN;
 bool ok = api.OH_GameDevice_DeviceInfo_GetDeviceType(p, &type) == GAME_CONTROLLER_SUCCESS && type == GAME_PAD &&
           api.OH_GameDevice_DeviceInfo_GetDeviceId(p, &id) == GAME_CONTROLLER_SUCCESS && id && *id;
 if (ok) { out.id = id; if (api.OH_GameDevice_DeviceInfo_GetName(p, &name) == GAME_CONTROLLER_SUCCESS && name) out.name = name; }
 std::free(id); std::free(name); return ok;
}
void device_event(const GameDevice_DeviceEvent* e) {
 Callback call; if (!call.valid) return;
 GameDevice_StatusChangedType type; GameDevice_DeviceInfo* p = nullptr; Command c;
 if (api.OH_GameDevice_DeviceEvent_GetChangedType(e, &type) != GAME_CONTROLLER_SUCCESS ||
     api.OH_GameDevice_DeviceEvent_GetDeviceInfo(e, &p) != GAME_CONTROLLER_SUCCESS) return;
 bool ok = p && info(p, c);
 if (p) api.OH_GameDevice_DestroyDeviceInfo(&p);
 if (ok && (type == ONLINE || type == OFFLINE)) { c.kind = type == ONLINE ? Command::Online : Command::Offline; enqueue(std::move(c), call); }
}
void button_event(const GamePad_ButtonEvent* e) {
 Callback call; if (!call.valid) return;
 Command c; c.kind = Command::Button; char* id = nullptr; int32_t code; GamePad_Button_ActionType action;
 bool ok = api.OH_GamePad_ButtonEvent_GetDeviceId(e, &id) == GAME_CONTROLLER_SUCCESS && id && *id &&
           api.OH_GamePad_ButtonEvent_GetButtonCode(e, &code) == GAME_CONTROLLER_SUCCESS &&
           api.OH_GamePad_ButtonEvent_GetButtonAction(e, &action) == GAME_CONTROLLER_SUCCESS;
 if (ok && (action == DOWN || action == UP)) { c.id = id; c.code = code; c.down = action == DOWN; enqueue(std::move(c), call); }
 std::free(id);
}
void axis_event(const GamePad_AxisEvent* e) {
 Callback call; if (!call.valid) return;
 Command c; c.kind = Command::Axis; char* id = nullptr; GamePad_AxisSourceType source;
 bool ok = api.OH_GamePad_AxisEvent_GetDeviceId(e, &id) == GAME_CONTROLLER_SUCCESS && id && *id &&
           api.OH_GamePad_AxisEvent_GetAxisSourceType(e, &source) == GAME_CONTROLLER_SUCCESS;
 if (ok) {
  c.id = id; c.code = source;
  switch (source) {
  case LEFT_THUMBSTICK: ok = !api.OH_GamePad_AxisEvent_GetXAxisValue(e, &c.x) && !api.OH_GamePad_AxisEvent_GetYAxisValue(e, &c.y); break;
  case RIGHT_THUMBSTICK: ok = !api.OH_GamePad_AxisEvent_GetZAxisValue(e, &c.x) && !api.OH_GamePad_AxisEvent_GetRZAxisValue(e, &c.y); break;
  case DPAD: ok = !api.OH_GamePad_AxisEvent_GetHatXAxisValue(e, &c.x) && !api.OH_GamePad_AxisEvent_GetHatYAxisValue(e, &c.y); break;
  case LEFT_TRIGGER: ok = !api.OH_GamePad_AxisEvent_GetBrakeAxisValue(e, &c.x); break;
  case RIGHT_TRIGGER: ok = !api.OH_GamePad_AxisEvent_GetGasAxisValue(e, &c.x); break;
  default: ok = false; break;
  }
  if (ok) enqueue(std::move(c), call);
 }
 std::free(id);
}
struct Pad {
 std::string name;
 SDL_JoystickID id = 0;
 SDL_Joystick* joystick = nullptr;
 std::map<int, bool> keys;
 std::array<double, SDL_GAMEPAD_AXIS_COUNT> axes{};
 double hat_x = 0, hat_y = 0;
 bool input_seen = false;
};
std::map<std::string, Pad> pads; // OS identity kept only in process; not logged or persisted.
const std::pair<int, SDL_GamepadButton> button_map[] = {
 {2301,SDL_GAMEPAD_BUTTON_SOUTH}, {2302,SDL_GAMEPAD_BUTTON_EAST}, {2304,SDL_GAMEPAD_BUTTON_WEST}, {2305,SDL_GAMEPAD_BUTTON_NORTH},
 {2307,SDL_GAMEPAD_BUTTON_LEFT_SHOULDER}, {2308,SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER}, {2303,SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER},
 {2311,SDL_GAMEPAD_BUTTON_BACK}, {2312,SDL_GAMEPAD_BUTTON_START}, {2314,SDL_GAMEPAD_BUTTON_LEFT_STICK}, {2315,SDL_GAMEPAD_BUTTON_RIGHT_STICK},
 {2012,SDL_GAMEPAD_BUTTON_DPAD_UP}, {2013,SDL_GAMEPAD_BUTTON_DPAD_DOWN}, {2014,SDL_GAMEPAD_BUTTON_DPAD_LEFT}, {2015,SDL_GAMEPAD_BUTTON_DPAD_RIGHT}
};
double finite_clamp(double x, double lo, double hi) { return std::isfinite(x) ? std::clamp(x, lo, hi) : 0; }
Sint16 stick(double x) { x = finite_clamp(x, -1, 1); return (Sint16)std::lround(x * (x < 0 ? 32768 : 32767)); }
Sint16 trigger(double x) { return (Sint16)std::lround(finite_clamp(x, 0, 1) * 65535 - 32768); }
void neutral(Pad& p) { p.keys.clear(); p.axes.fill(0); p.hat_x = p.hat_y = 0; }
void flush(Pad& p) {
 if (!p.joystick) return;
 std::array<bool, SDL_GAMEPAD_BUTTON_COUNT> b{};
 for (auto m : button_map) { auto at = p.keys.find(m.first); if (at != p.keys.end()) b[m.second] = b[m.second] || at->second; }
 b[SDL_GAMEPAD_BUTTON_DPAD_LEFT] = b[SDL_GAMEPAD_BUTTON_DPAD_LEFT] || p.hat_x < -0.5;
 b[SDL_GAMEPAD_BUTTON_DPAD_RIGHT] = b[SDL_GAMEPAD_BUTTON_DPAD_RIGHT] || p.hat_x > 0.5;
 b[SDL_GAMEPAD_BUTTON_DPAD_UP] = b[SDL_GAMEPAD_BUTTON_DPAD_UP] || p.hat_y < -0.5;
 b[SDL_GAMEPAD_BUTTON_DPAD_DOWN] = b[SDL_GAMEPAD_BUTTON_DPAD_DOWN] || p.hat_y > 0.5;
 for (int i = 0; i < SDL_GAMEPAD_BUTTON_COUNT; ++i) SDL_SetJoystickVirtualButton(p.joystick, i, b[i]);
 for (int i = 0; i < SDL_GAMEPAD_AXIS_LEFT_TRIGGER; ++i) SDL_SetJoystickVirtualAxis(p.joystick, i, stick(p.axes[i]));
 for (int i = SDL_GAMEPAD_AXIS_LEFT_TRIGGER; i <= SDL_GAMEPAD_AXIS_RIGHT_TRIGGER; ++i) {
  auto key = p.keys.find(i == SDL_GAMEPAD_AXIS_LEFT_TRIGGER ? 2309 : 2310);
  bool held = key != p.keys.end() && key->second;
  SDL_SetJoystickVirtualAxis(p.joystick, i, trigger(held ? 1.0 : p.axes[i]));
 }
}
void detach(Pad& p) {
 if (p.joystick) { neutral(p); flush(p); SDL_UpdateJoysticks(); SDL_CloseJoystick(p.joystick); p.joystick = nullptr; }
 if (p.id) { SDL_DetachVirtualJoystick(p.id); p.id = 0; }
}
void attach(Pad& p) {
 if (p.id || prefer_native) return;
 SDL_VirtualJoystickDesc desc; SDL_INIT_INTERFACE(&desc);
 std::string name = "PAL Harmony: " + (p.name.empty() ? std::string("Gamepad") : p.name);
 desc.type = SDL_JOYSTICK_TYPE_GAMEPAD; desc.naxes = SDL_GAMEPAD_AXIS_COUNT; desc.nbuttons = SDL_GAMEPAD_BUTTON_COUNT;
 desc.axis_mask = (1u << SDL_GAMEPAD_AXIS_COUNT) - 1; desc.button_mask = (1u << SDL_GAMEPAD_BUTTON_COUNT) - 1; desc.name = name.c_str();
 p.id = SDL_AttachVirtualJoystick(&desc);
 if (p.id) p.joystick = SDL_OpenJoystick(p.id);
 if (!p.joystick) { std::fprintf(stderr, "gamepad OHOS: virtual attach/open failed: %s\n", SDL_GetError()); if (p.id) SDL_DetachVirtualJoystick(p.id); p.id = 0; return; }
 // Virtual joystick triggers rest at -32768, not SDL gamepad's translated zero.
 flush(p); SDL_UpdateJoysticks();
 std::fprintf(stderr, "gamepad OHOS: attached SDL id=%u name=%s\n", (unsigned)p.id, name.c_str());
}
void apply(Command& c) {
 if (c.kind == Command::Online) {
  if (pads.find(c.id) == pads.end()) {
   if (pads.size() >= kMaxPads) { std::fprintf(stderr, "gamepad OHOS: controller limit reached\n"); return; }
   Pad p; p.name = c.name; auto at = pads.emplace(c.id, std::move(p)).first; attach(at->second);
  }
  return;
 }
 auto at = pads.find(c.id); if (at == pads.end()) return;
 Pad& p = at->second;
 if (c.kind == Command::Offline) { detach(p); pads.erase(at); return; }
 if (c.kind == Command::Button) {
  bool known = c.code == 2309 || c.code == 2310;
  for (auto b : button_map) known = known || b.first == c.code;
  if (!known) return;
  p.keys[c.code] = c.down;
 } else if (c.kind == Command::Axis) {
  switch (c.code) {
  case LEFT_THUMBSTICK: p.axes[0] = c.x; p.axes[1] = c.y; break;
  case RIGHT_THUMBSTICK: p.axes[2] = c.x; p.axes[3] = c.y; break;
  case LEFT_TRIGGER: p.axes[4] = c.x; break;
  case RIGHT_TRIGGER: p.axes[5] = c.x; break;
  case DPAD: p.hat_x = finite_clamp(c.x,-1,1); p.hat_y = finite_clamp(c.y,-1,1); break;
  }
 }
 flush(p);
 // Preserve each event transition for SDL menus even if several arrive between
 // polls. Gameplay continues to sample SDL's final held state, like native pads.
 SDL_UpdateJoysticks();
 if (!p.input_seen && p.joystick) { p.input_seen = true; std::fprintf(stderr, "gamepad OHOS: first input reached SDL id=%u\n", (unsigned)p.id); }
}
bool enumerate(std::vector<Command>& out) {
 GameDevice_AllDeviceInfos* all = nullptr;
 auto code = api.OH_GameDevice_GetAllDeviceInfos(&all);
 if (code != GAME_CONTROLLER_SUCCESS || !all) { std::fprintf(stderr, "gamepad OHOS: enumeration failed code=%d\n", (int)code); return false; }
 int32_t count = 0;
 bool ok = api.OH_GameDevice_AllDeviceInfos_GetCount(all, &count) == GAME_CONTROLLER_SUCCESS && count >= 0 && count <= 256;
 if (ok) for (int32_t i=0; i<count; ++i) {
  GameDevice_DeviceInfo* p = nullptr;
  if (api.OH_GameDevice_AllDeviceInfos_GetDeviceInfo(all, i, &p) != GAME_CONTROLLER_SUCCESS || !p) { ok = false; break; }
  Command c; if (info(p,c)) out.push_back(std::move(c));
  api.OH_GameDevice_DestroyDeviceInfo(&p);
 }
 api.OH_GameDevice_DestroyAllDeviceInfos(&all);
 std::fprintf(stderr, "gamepad OHOS: enumerated=%zu status=%s\n", out.size(), ok ? "ok" : "failed");
 return ok;
}
bool has_native_gamepad() {
 int count = 0; SDL_JoystickID* ids = SDL_GetGamepads(&count); bool found = false;
 for (int i=0; ids && i<count; ++i) if (!SDL_IsJoystickVirtual(ids[i])) found = true;
 SDL_free(ids); return found;
}
bool load_api() {
 library = dlopen("libohgame_controller.z.so", RTLD_NOW | RTLD_LOCAL);
 if (!library) { std::fprintf(stderr, "gamepad OHOS: Game Controller Kit unavailable (API 21+ required): %s; touch/keyboard remain available\n", dlerror()); return false; }
#define LOAD(n) api.n = reinterpret_cast<decltype(api.n)>(dlsym(library, #n)); if (!api.n) { std::fprintf(stderr, "gamepad OHOS: missing API %s; bridge unavailable\n", #n); return false; }
 PAL_DATA_APIS(LOAD)
#define BUTTON_LOAD(n) LOAD(OH_GamePad_##n##_RegisterButtonInputMonitor) LOAD(OH_GamePad_##n##_UnregisterButtonInputMonitor)
 PAL_BUTTON_APIS(BUTTON_LOAD)
#define AXIS_LOAD(n) LOAD(OH_GamePad_##n##_RegisterAxisInputMonitor) LOAD(OH_GamePad_##n##_UnregisterAxisInputMonitor)
 PAL_AXIS_APIS(AXIS_LOAD)
#undef AXIS_LOAD
#undef BUTTON_LOAD
#undef LOAD
 return true;
}
} // namespace

bool pal_ohos_gamepad_start() {
 if (started) return true;
 if (!load_api()) { if (library) dlclose(library); library = nullptr; api = {}; return false; }
 { std::lock_guard<std::mutex> lock(mutex); accepting = true; active = true; overflow = false; ++epoch; commands.clear(); }
 auto code = api.OH_GameDevice_RegisterDeviceMonitor(device_event);
 if (code == GAME_CONTROLLER_SUCCESS) unregisters.push_back(api.OH_GameDevice_UnregisterDeviceMonitor);
 else { std::fprintf(stderr, "gamepad OHOS: device monitor failed code=%d\n",(int)code); pal_ohos_gamepad_stop(); return false; }
#define REGISTER_BUTTON(n) code = api.OH_GamePad_##n##_RegisterButtonInputMonitor(button_event); if (code == GAME_CONTROLLER_SUCCESS) unregisters.push_back(api.OH_GamePad_##n##_UnregisterButtonInputMonitor); else { std::fprintf(stderr,"gamepad OHOS: button registration failed %s code=%d\n",#n,(int)code); pal_ohos_gamepad_stop(); return false; }
 PAL_BUTTON_APIS(REGISTER_BUTTON)
#undef REGISTER_BUTTON
#define REGISTER_AXIS(n) code = api.OH_GamePad_##n##_RegisterAxisInputMonitor(axis_event); if (code == GAME_CONTROLLER_SUCCESS) unregisters.push_back(api.OH_GamePad_##n##_UnregisterAxisInputMonitor); else { std::fprintf(stderr,"gamepad OHOS: axis registration failed %s code=%d\n",#n,(int)code); pal_ohos_gamepad_stop(); return false; }
 PAL_AXIS_APIS(REGISTER_AXIS)
#undef REGISTER_AXIS
 // Register first, then enumerate. Apply the snapshot before callbacks queued
 // during enumeration so an offline callback cannot be overwritten by the scan.
 prefer_native = has_native_gamepad();
 std::vector<Command> initial;
 if (!enumerate(initial)) { pal_ohos_gamepad_stop(); return false; }
 for (auto& c : initial) apply(c);
 started = true;
 std::fprintf(stderr, "gamepad OHOS: API 21 callbacks registered, SDL native preference=%d\n", (int)prefer_native);
 pal_ohos_gamepad_pump(); return true;
}
void pal_ohos_gamepad_pump() {
 if (!started) return;
 bool native = has_native_gamepad();
 if (native != prefer_native) {
  prefer_native = native;
  std::fprintf(stderr, "gamepad OHOS: SDL physical backend %s; %s bridge pads to prevent duplicates\n",native?"detected":"gone",native?"suspending":"restoring");
  for (auto& item:pads) { neutral(item.second); if (native) detach(item.second); else attach(item.second); }
 }
 std::vector<Command> pending; bool over;
 { std::lock_guard<std::mutex> lock(mutex); pending.swap(commands); over=overflow; overflow=false; }
 if (over) {
  std::fprintf(stderr, "gamepad OHOS: callback queue overflow; neutralizing and rescanning\n");
  for (auto& item:pads) detach(item.second);
 pads.clear();
  std::vector<Command> initial; if (enumerate(initial)) for (auto& c:initial) apply(c);
  return;
 }
 for (auto& c:pending) apply(c);
}
void pal_ohos_gamepad_set_active(bool value) {
 { std::lock_guard<std::mutex> lock(mutex); if (active == value) return; active=value; ++epoch;
   commands.erase(std::remove_if(commands.begin(),commands.end(),[](const Command& c){return c.kind==Command::Button||c.kind==Command::Axis;}),commands.end()); }
 for (auto& item:pads) { neutral(item.second); flush(item.second); }
 SDL_UpdateJoysticks();
}
void pal_ohos_gamepad_stop() {
 { std::lock_guard<std::mutex> lock(mutex); accepting=false; ++epoch; commands.clear(); }
 for (auto i=unregisters.rbegin();i!=unregisters.rend();++i) {
  auto code=(*i)(); if(code!=GAME_CONTROLLER_SUCCESS) std::fprintf(stderr,"gamepad OHOS: unregister failed code=%d\n",(int)code);
 }
 unregisters.clear();
 { std::unique_lock<std::mutex> lock(mutex); quiet.wait(lock,[]{return in_flight==0;}); }
 for (auto& item:pads) detach(item.second);
 pads.clear();
 started=false; prefer_native=false;
 if(library) dlclose(library);
 library=nullptr; api={};
}
#else
bool pal_ohos_gamepad_start() { std::fprintf(stderr,"gamepad OHOS: bridge disabled at build time; physical controllers require an SDL native backend\n"); return false; }
void pal_ohos_gamepad_pump() {}
void pal_ohos_gamepad_set_active(bool) {}
void pal_ohos_gamepad_stop() {}
#endif
