static void queue(Uint32 type,SDL_Scancode key=SDL_SCANCODE_RETURN,uint64_t timestamp=0){SDL_Event e{};e.type=type;e.key.windowID=SDL_GetWindowID(g_win);e.key.scancode=key;e.key.timestamp=timestamp;assert(SDL_PushEvent(&e));}
static void pump(){SDL_Event e;while(SDL_PollEvent(&e)){
 if(e.type==SDL_EVENT_KEY_DOWN && semantic_key(e.key.scancode))g_pc_press.down(e.key.scancode,0x400,e.key.repeat,true,false);
 if(e.type==SDL_EVENT_KEY_UP)g_pc_press.up(e.key.scancode);
 prompt_event(e);
}}
int main(){SDL_SetHint(SDL_HINT_VIDEO_DRIVER,"dummy");assert(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMEPAD));g_win=SDL_CreateWindow("private prompt event test",320,224,0);g_ren=SDL_CreateRenderer(g_win,nullptr);assert(g_win&&g_ren);pump();
 // Verify SDL gives timestamp=0 pushed events a real monotonic timestamp.
 auto before=SDL_GetTicksNS();queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);pump();assert(before>0);
 {pal_prompt::Scope wait(true);assert(wait.enabled);queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);pump();assert(g_pc_press.read(SDL_SCANCODE_RETURN)==0);assert(wait.accept());assert(!wait.accept());assert(g_held_over[0]==0);}
 {pal_prompt::Scope wait(true);queue(SDL_EVENT_KEY_DOWN,SDL_SCANCODE_SPACE);queue(SDL_EVENT_KEY_UP,SDL_SCANCODE_SPACE);pump();assert(wait.accept());}
 // A pre-entry queued DOWN/UP is rejected even when processed after begin.
 queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);
 {pal_prompt::Scope wait(true);pump();assert(!wait.accept());queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);pump();assert(wait.accept());}
 // Non-repeat duplicate DOWN is not fresh. Release enables next physical press.
 {pal_prompt::Scope wait(true);queue(SDL_EVENT_KEY_DOWN,SDL_SCANCODE_C,1);pump();assert(!wait.accept());queue(SDL_EVENT_KEY_DOWN,SDL_SCANCODE_C);pump();assert(!wait.accept());queue(SDL_EVENT_KEY_UP,SDL_SCANCODE_C);queue(SDL_EVENT_KEY_DOWN,SDL_SCANCODE_C);pump();assert(wait.accept());assert(g_held_over[0]&0x400);queue(SDL_EVENT_KEY_UP,SDL_SCANCODE_C);pump();}
 g_held_over[0]=0;
 // Real SDL touch events, down/up before one guest read.
 {pal_prompt::Scope wait(true);SDL_Event e{};e.type=SDL_EVENT_FINGER_DOWN;e.tfinger.touchID=7;e.tfinger.fingerID=9;e.tfinger.x=.8f;e.tfinger.y=.5f;assert(SDL_PushEvent(&e));e.type=SDL_EVENT_FINGER_UP;e.common.timestamp=0;assert(SDL_PushEvent(&e));pump();assert(wait.accept());assert(g_held_over[0]==0);}
 // Focus loss clears owed keys; restoration accepts a new event in same wait.
 {pal_prompt::Scope wait(true);queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);queue(SDL_EVENT_WINDOW_FOCUS_LOST);pump();assert(!wait.accept());queue(SDL_EVENT_WINDOW_FOCUS_GAINED);queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);pump();assert(wait.accept());}

 // A release missed while unfocused is reconciled from SDL's current up state.
 {pal_prompt::Scope wait(true);queue(SDL_EVENT_KEY_DOWN,SDL_SCANCODE_RETURN,1);pump();
  queue(SDL_EVENT_WINDOW_FOCUS_LOST);pump();assert(!wait.accept());
  queue(SDL_EVENT_WINDOW_FOCUS_GAINED);queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);pump();assert(wait.accept());}
 // Host menu interruptions clear old intent but leave the exact wait recoverable.
 {pal_prompt::Scope wait(true);queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);pump();
  g_menu_open=true;pal_prompt::ledger.cancel();assert(!wait.accept());
  g_menu_open=false;pal_prompt::ledger.cancel();queue(SDL_EVENT_KEY_DOWN);queue(SDL_EVENT_KEY_UP);pump();assert(wait.accept());}
 // SDL virtual gamepad generates real button/axis events and physical state.
 SDL_VirtualJoystickDesc desc;SDL_INIT_INTERFACE(&desc);
 desc.type=SDL_JOYSTICK_TYPE_GAMEPAD;desc.naxes=SDL_GAMEPAD_AXIS_COUNT;desc.nbuttons=SDL_GAMEPAD_BUTTON_COUNT;
 auto id=SDL_AttachVirtualJoystick(&desc);assert(id);
 auto*j=SDL_OpenJoystick(id);assert(j);auto*pad=SDL_OpenGamepad(id);assert(pad);
 g_pads.push_back({id,pad,{{{SDL_GAMEPAD_BUTTON_SOUTH,-1,0x400},{-1,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,0x400}},16000}});
 assert(SDL_SetJoystickVirtualAxis(j,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MIN));SDL_UpdateJoysticks();pump();
 {pal_prompt::Scope wait(true);assert(SDL_SetJoystickVirtualButton(j,SDL_GAMEPAD_BUTTON_SOUTH,true));SDL_UpdateJoysticks();pump();
  assert(wait.accept());assert(g_held_over[0]&0x400);}
 {pal_prompt::Scope wait(true);SDL_UpdateJoysticks();pump();assert(!wait.accept());
  assert(SDL_SetJoystickVirtualButton(j,SDL_GAMEPAD_BUTTON_SOUTH,false));SDL_UpdateJoysticks();pump();
  assert(SDL_SetJoystickVirtualButton(j,SDL_GAMEPAD_BUTTON_SOUTH,true));SDL_UpdateJoysticks();pump();assert(wait.accept());}
 SDL_SetJoystickVirtualButton(j,SDL_GAMEPAD_BUTTON_SOUTH,false);SDL_UpdateJoysticks();pump();
 {pal_prompt::Scope wait(true);SDL_SetJoystickVirtualAxis(j,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MAX);SDL_UpdateJoysticks();pump();assert(wait.accept());}
 {pal_prompt::Scope wait(true);SDL_UpdateJoysticks();pump();assert(!wait.accept());
  SDL_SetJoystickVirtualAxis(j,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MAX-100);SDL_UpdateJoysticks();pump();assert(!wait.accept());
  SDL_SetJoystickVirtualAxis(j,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MIN);SDL_UpdateJoysticks();pump();
  SDL_SetJoystickVirtualAxis(j,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MAX);SDL_UpdateJoysticks();pump();assert(wait.accept());}
 g_pads.clear();SDL_CloseGamepad(pad);SDL_CloseJoystick(j);assert(SDL_DetachVirtualJoystick(id));pump();
 g_cfg.headless=true;{pal_prompt::Scope wait(true);assert(!wait.enabled);}g_cfg.headless=false;
 g_cfg.input="script";{pal_prompt::Scope wait(true);assert(!wait.enabled);}g_cfg.input.clear();
 SDL_DestroyRenderer(g_ren);SDL_DestroyWindow(g_win);g_win=nullptr;SDL_Quit();std::puts("PASS real SDL dummy-window event queue: Return/Space short taps, stale opening, duplicate down, touch, focus/missed-up/menu recovery, virtual button/trigger, nonlive guards");}
