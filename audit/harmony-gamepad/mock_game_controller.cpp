// Mock OS service using genuine API declarations, not replacement API headers.
#include <GameControllerKit/game_device.h>
#include <GameControllerKit/game_pad.h>
#include "mock_game_controller.h"
#include <map>
#include <mutex>
#include <string>
#include <vector>
#include <cstdlib>
#include <cstring>
#include <atomic>
#include <thread>
struct GameDevice_DeviceInfo { std::string id,name; };
struct GameDevice_AllDeviceInfos { std::vector<GameDevice_DeviceInfo> items; };
struct GameDevice_DeviceEvent { GameDevice_StatusChangedType type; GameDevice_DeviceInfo info; };
struct GamePad_ButtonEvent { std::string id; int code; bool down; };
struct GamePad_AxisEvent { std::string id; int source; double x,y; };
static std::mutex mx;
static std::map<std::string,GameDevice_DeviceInfo> devices;
static GameDevice_DeviceMonitorCallback device_cb=nullptr;
static std::map<int,GamePad_ButtonInputMonitorCallback> button_cb;
static std::map<int,GamePad_AxisInputMonitorCallback> axis_cb;
static std::string enum_remove,enum_add;
static GamePad_ButtonInputMonitorCallback late_button=nullptr;
static int reg_n=0,fail_reg=-1;
static bool fail_enum=false;
static std::atomic<int> allocations{0};
static std::atomic<bool> block_getter{false},getter_waiting{false};
static GameController_ErrorCode str(const std::string& s,char** out){*out=strdup(s.c_str());return *out?GAME_CONTROLLER_SUCCESS:GAME_CONTROLLER_NO_MEMORY;}
extern "C" {
void mock_reset(){std::lock_guard<std::mutex> l(mx);devices.clear();device_cb=nullptr;button_cb.clear();axis_cb.clear();enum_remove.clear();enum_add.clear();reg_n=0;fail_reg=-1;fail_enum=false;}
void mock_online(const char* id,const char* name){GameDevice_DeviceEvent e{ONLINE,{id,name}};GameDevice_DeviceMonitorCallback cb;{std::lock_guard<std::mutex> l(mx);devices[id]=e.info;cb=device_cb;}if(cb)cb(&e);}
void mock_offline(const char* id){GameDevice_DeviceEvent e{OFFLINE,{id,""}};GameDevice_DeviceMonitorCallback cb;{std::lock_guard<std::mutex> l(mx);devices.erase(id);cb=device_cb;}if(cb)cb(&e);}
void mock_button(const char* id,int code,bool down){GamePad_ButtonInputMonitorCallback cb=nullptr;{std::lock_guard<std::mutex> l(mx);auto i=button_cb.find(code);if(i!=button_cb.end())cb=i->second;}GamePad_ButtonEvent e{id,code,down};if(cb)cb(&e);}
void mock_axis(const char* id,int source,double x,double y){GamePad_AxisInputMonitorCallback cb=nullptr;{std::lock_guard<std::mutex> l(mx);auto i=axis_cb.find(source);if(i!=axis_cb.end())cb=i->second;}GamePad_AxisEvent e{id,source,x,y};if(cb)cb(&e);}
void mock_enum_race(const char* id){enum_remove=id;}
void mock_enum_connect(const char* id){enum_add=id;}
void mock_late_button(const char*id,int code,bool down){GamePad_ButtonEvent e{id,code,down};if(late_button)late_button(&e);}
void mock_fail_registration(int nth){fail_reg=nth;}
void mock_fail_enumeration(bool f){fail_enum=f;}
int mock_registrations(){std::lock_guard<std::mutex> l(mx);return (device_cb?1:0)+button_cb.size()+axis_cb.size();}
int mock_allocations(){return allocations;}
void mock_block_getter(bool b){block_getter=b;}
bool mock_getter_waiting(){return getter_waiting;}
GameController_ErrorCode OH_GameDevice_RegisterDeviceMonitor(GameDevice_DeviceMonitorCallback cb){std::lock_guard<std::mutex>l(mx);if(++reg_n==fail_reg)return GAME_CONTROLLER_MULTIMODAL_INPUT_ERROR;device_cb=cb;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_UnregisterDeviceMonitor(){std::lock_guard<std::mutex>l(mx);device_cb=nullptr;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_GetAllDeviceInfos(GameDevice_AllDeviceInfos**p){if(fail_enum)return GAME_CONTROLLER_MULTIMODAL_INPUT_ERROR;*p=new GameDevice_AllDeviceInfos; ++allocations;{std::lock_guard<std::mutex>l(mx);for(auto&d:devices)(*p)->items.push_back(d.second);}if(!enum_remove.empty()){auto id=enum_remove;enum_remove.clear();mock_offline(id.c_str());}if(!enum_add.empty()){auto id=enum_add;enum_add.clear();mock_online(id.c_str(),"Scan-race new pad");}return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_DestroyAllDeviceInfos(GameDevice_AllDeviceInfos**p){delete *p;*p=nullptr;--allocations;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_AllDeviceInfos_GetCount(const GameDevice_AllDeviceInfos*p,int32_t*n){*n=p->items.size();return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_AllDeviceInfos_GetDeviceInfo(const GameDevice_AllDeviceInfos*p,int32_t i,GameDevice_DeviceInfo**o){*o=new GameDevice_DeviceInfo(p->items.at(i));++allocations;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_DeviceEvent_GetChangedType(const GameDevice_DeviceEvent*p,GameDevice_StatusChangedType*t){*t=p->type;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_DeviceEvent_GetDeviceInfo(const GameDevice_DeviceEvent*p,GameDevice_DeviceInfo**o){*o=new GameDevice_DeviceInfo(p->info);++allocations;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_DestroyDeviceInfo(GameDevice_DeviceInfo**p){delete *p;*p=nullptr;--allocations;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetDeviceId(const GameDevice_DeviceInfo*p,char**o){return str(p->id,o);}
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetName(const GameDevice_DeviceInfo*p,char**o){return str(p->name,o);}
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetDeviceType(const GameDevice_DeviceInfo*,GameDevice_DeviceType*t){*t=GAME_PAD;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GamePad_ButtonEvent_GetDeviceId(const GamePad_ButtonEvent*p,char**o){getter_waiting=true;while(block_getter)std::this_thread::yield();getter_waiting=false;return str(p->id,o);}
GameController_ErrorCode OH_GamePad_ButtonEvent_GetButtonAction(const GamePad_ButtonEvent*p,GamePad_Button_ActionType*o){*o=p->down?DOWN:UP;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GamePad_ButtonEvent_GetButtonCode(const GamePad_ButtonEvent*p,int32_t*o){*o=p->code;return GAME_CONTROLLER_SUCCESS;}
GameController_ErrorCode OH_GamePad_AxisEvent_GetDeviceId(const GamePad_AxisEvent*p,char**o){return str(p->id,o);}
GameController_ErrorCode OH_GamePad_AxisEvent_GetAxisSourceType(const GamePad_AxisEvent*p,GamePad_AxisSourceType*o){*o=(GamePad_AxisSourceType)p->source;return GAME_CONTROLLER_SUCCESS;}
#define GET_AXIS(n,f) GameController_ErrorCode OH_GamePad_AxisEvent_Get##n##AxisValue(const GamePad_AxisEvent*p,double*o){*o=p->f;return GAME_CONTROLLER_SUCCESS;}
GET_AXIS(X,x) GET_AXIS(Y,y) GET_AXIS(Z,x) GET_AXIS(RZ,y) GET_AXIS(HatX,x) GET_AXIS(HatY,y) GET_AXIS(Brake,x) GET_AXIS(Gas,x)
#define BUTTON(n,c) GameController_ErrorCode OH_GamePad_##n##_RegisterButtonInputMonitor(GamePad_ButtonInputMonitorCallback cb){std::lock_guard<std::mutex>l(mx);if(++reg_n==fail_reg)return GAME_CONTROLLER_PARAM_ERROR;button_cb[c]=cb;late_button=cb;return GAME_CONTROLLER_SUCCESS;} GameController_ErrorCode OH_GamePad_##n##_UnregisterButtonInputMonitor(){std::lock_guard<std::mutex>l(mx);button_cb.erase(c);return GAME_CONTROLLER_SUCCESS;}
BUTTON(LeftShoulder,2307) BUTTON(RightShoulder,2308) BUTTON(LeftTrigger,2309) BUTTON(RightTrigger,2310) BUTTON(ButtonMenu,2312) BUTTON(ButtonHome,2311) BUTTON(ButtonA,2301) BUTTON(ButtonB,2302) BUTTON(ButtonX,2304) BUTTON(ButtonY,2305) BUTTON(ButtonC,2303) BUTTON(Dpad_LeftButton,2014) BUTTON(Dpad_RightButton,2015) BUTTON(Dpad_UpButton,2012) BUTTON(Dpad_DownButton,2013) BUTTON(LeftThumbstick,2314) BUTTON(RightThumbstick,2315)
#define AXIS(n,c) GameController_ErrorCode OH_GamePad_##n##_RegisterAxisInputMonitor(GamePad_AxisInputMonitorCallback cb){std::lock_guard<std::mutex>l(mx);if(++reg_n==fail_reg)return GAME_CONTROLLER_PARAM_ERROR;axis_cb[c]=cb;return GAME_CONTROLLER_SUCCESS;} GameController_ErrorCode OH_GamePad_##n##_UnregisterAxisInputMonitor(){std::lock_guard<std::mutex>l(mx);axis_cb.erase(c);return GAME_CONTROLLER_SUCCESS;}
AXIS(LeftThumbstick,1) AXIS(RightThumbstick,2) AXIS(Dpad,0) AXIS(LeftTrigger,3) AXIS(RightTrigger,4)
}
