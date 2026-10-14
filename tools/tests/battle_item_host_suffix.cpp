static int checks=0;
static void check(bool value,const char* name) {
    ++checks; if(!value) {std::cerr << "FAIL: " << name << '\n'; std::exit(1);}
}
static int code(const char* key) {return SDL_GetScancodeFromName(key);}
static void key_event(const char* key,bool down=true,bool repeat=false,int mods=0,unsigned window=1) {
    SDL_Event e{}; e.type=down ? SDL_EVENT_KEY_DOWN : SDL_EVENT_KEY_UP;
    e.key={window,code(key),repeat,mods}; on_event(e);
}
static void defaults() {
    g_settings.values.clear(); g_settings.set("controls","keyboard_profile","pc98");
    for (auto pair : {std::pair{"confirm","Enter"},{"menu_cancel","Escape"},{"item","E"},
                     {"spell","F"},{"strongest","F"},{"repeat","R"},{"all_attack","A"},
                     {"defend","D"},{"throw","W"},{"equip","W"},{"status","S"},{"system","Q"}})
        g_settings.set("keyboard pc98",pair.first,pair.second);
    g_pc_press.reset(); g_battle_press.presses.reset(); g_all_attack_press.reset();
    focused=true; g_menu_open=false; real_pad_bits=0; std::fill(std::begin(k),std::end(k),false);
    pal_keyboard::clear(); pal_keyboard::ui(); bindings();
}
int main() {
    using namespace pal_keyboard;
    defaults();
    field();key_event("Escape");
    check(read_bits()==Menu,"Escape delivers the native game menu command");
    check(!requests_host_menu(code("Escape")),"gameplay Escape does not open the host menu");
    key_event("Escape",false);ui();key_event("Escape");
    check(read_bits()==Cancel,"Escape delivers native UI cancellation");
    check(requests_host_menu(code("F10")),"F10 opens host settings");
#ifdef _WIN32
    defaults();g_settings.set("controls","keyboard_profile","saturn");
    g_settings.set("keyboard","r","F10");bindings();k[code("F10")]=true;
    check(requests_host_menu(code("F10")),"Windows reserves F10 with legacy/custom mappings");
    check(read_bits()==0,"Windows F10 does not leak to the guest pad");
    check(!requests_host_menu(code("Escape")),"unbound legacy Escape does not open Windows host settings");
    g_menu_open=true;check(requests_host_menu(code("Escape")),"Escape may close an already open host panel");
#endif
    defaults();
    field(); key_event("E"); check(read_bits()==Items,"field E retains native items");
    clear(); ui();
    {
        BattleCommandsScope main(true,0,0);
        check(read_bits()==0,"held field E cannot enter battle");
        key_event("E",true,true); key_event("E"); check(read_bits()==0,"repeat/duplicate cannot cross context");
        key_event("E",false); key_event("E"); check(read_bits()==Items,"fresh battle E emits native R");
        check(g_pc_press.read(code("E"))==0,"battle E does not activate field latch");
    }
    check(read_bits()==0,"leaving main retires E in list/target");
    clear(); field(); key_event("E",true,true); key_event("E");
    check(read_bits()==0,"held battle E cannot activate field");
    key_event("E",false); key_event("E"); check(read_bits()==Items,"fresh E works after return to field");
    defaults(); g_settings.set("keyboard pc98","item","T"); bindings();
    {BattleCommandsScope main(true,2,5); key_event("E"); check(read_bits()==0,"old item key removed");
     key_event("T"); check(read_bits()==Items,"custom item key works"); key_event("T",false); check(read_bits()==Items,"custom tap survives keyup until ack");
     battle_event_consumed(); check(read_bits()==0,"custom ack clears");}
    for (auto pair : {std::pair{"W",Throw},{"D",Defend},{"F",Strongest},{"R",Repeat}}) {
        defaults(); g_settings.set("keyboard pc98","item",pair.first); bindings();
        check(g_battle_item_keys.empty(),"existing battle binding wins duplicate item key");
        BattleCommandsScope main(true,1,3); key_event(pair.first);
        check(read_bits()==pair.second,"custom duplicate emits only prior battle command");
    }
    defaults(); g_settings.set("keyboard pc98","item","A"); bindings();
    check(g_battle_item_keys.empty() && in_keys(g_all_attack_keys,code("A")),"all attack retains A conflict");
    for (const char* key : {"Enter","Escape","F10","F11","F12"}) {
        defaults(); g_settings.set("keyboard pc98","item",key); bindings();
        check(g_item_keys.empty() && g_battle_item_keys.empty(),"ordinary/host key wins in both contexts");
    }
    defaults(); g_settings.set("keyboard pc98","a","E"); bindings();
    check(g_item_keys.empty() && g_battle_item_keys.empty(),"native binding wins item conflict");
    {BattleCommandsScope main(true); k[code("E")]=true; key_event("E"); check(read_bits()==Confirm,"native ordinary key remains active");}
    defaults(); g_settings.set("controls","keyboard_profile","saturn"); g_settings.set("keyboard","r","E"); bindings();
    check(g_battle_item_keys.empty() && g_item_keys.empty(),"Saturn gets no semantic item mappings");
    k[code("E")]=true; check(read_bits()==Items,"Saturn native binding stays unchanged");
    defaults();
    {BattleCommandsScope main(true); key_event("E"); menu_open(); check(read_bits()==0,"overlay retires item");
     menu_close(); key_event("E"); check(read_bits()==0,"overlay close cannot revive held key");
     key_event("E",false); key_event("E"); check(read_bits()==Items,"release restores after overlay");
     SDL_Event lost{}; lost.type=SDL_EVENT_WINDOW_FOCUS_LOST; lost.window.windowID=1; on_event(lost);
     check(read_bits()==0,"focus event retires item"); key_event("E",false);
     key_event("E",true,false,SDL_KMOD_ALT); check(read_bits()==0,"Alt blocks item"); key_event("E",false);
     key_event("E",true,false,0,2); check(read_bits()==0,"other window cannot activate item");
     focused=false; key_event("E"); focused=true; check(read_bits()==0,"unfocused press remains blocked after regain");}
    for (auto pair : {std::pair{"E",Items},{"W",Throw},{"D",Defend},{"F",Strongest},{"R",Repeat}}) {
        defaults();
        BattleCommandsScope main(true,2,4);
        key_event(pair.first); key_event(pair.first,false);
        check(read_bits()==pair.second,"same-pump tap reaches original native command");
        check(read_bits()==pair.second,"tap remains until original reader acknowledges");
        battle_event_consumed(); check(read_bits()==0,"ack removes all tap tail");
        key_event(pair.first); check(read_bits()==pair.second,"fresh held press after ack works");
        battle_event_consumed(); check(read_bits()==0,"ack retires held command");
        key_event(pair.first,true,true); key_event(pair.first);
        check(read_bits()==0,"repeat or duplicate held DOWN cannot resurrect acked command");
        key_event(pair.first,false); key_event(pair.first);
        check(read_bits()==pair.second,"release then fresh DOWN reactivates command");
    }
    const std::pair<const char*,uint16_t> commands[]={{"E",Items},{"W",Throw},{"D",Defend},{"F",Strongest},{"R",Repeat}};
    for (const auto& first : commands) for (const auto& loser : commands) {
        if (first.second==loser.second) continue;
        defaults(); BattleCommandsScope main(true);
        key_event(first.first); key_event(first.first,false); key_event(loser.first);
        const auto bits=read_bits();
        check(bits==first.second && (bits & (bits-1))==0,"first eligible edge wins exactly one native bit");
        check(read_bits()==first.second,"losing command cannot replace pending winner");
        battle_event_consumed(); check(read_bits()==0,"one native ack retires winner and losing shortcut");
        key_event(loser.first,true,true); key_event(loser.first);
        check(read_bits()==0,"losing hold cannot replay after ack");
        key_event(loser.first,false); key_event(loser.first);
        check(read_bits()==loser.second,"loser requires release and fresh eligible edge");
    }
    defaults();
    {BattleCommandsScope main(true);
     key_event("E",true,false,SDL_KMOD_ALT); key_event("W"); key_event("W",false);
     check(read_bits()==Throw,"invalid Alt E does not capture first eligible W");
     key_event("E",false); key_event("E",true,false,SDL_KMOD_ALT);
     check(read_bits()==Throw,"invalid Alt E cannot cancel valid pending W");
     battle_event_consumed(); check(read_bits()==0,"ack clears valid W without queuing invalid E");}
    for (uint16_t real : {uint16_t(Confirm),uint16_t(Items),uint16_t(B_LEFT)}) {
        defaults(); BattleCommandsScope main(true);
        key_event("E"); key_event("E",false); real_pad_bits=real;
        check(read_bits()==real,"real controller/touch/carry source wins pending shortcut");
        real_pad_bits=0; check(read_bits()==0,"real source permanently retires pending shortcut");
    }
    defaults();
    {BattleCommandsScope main(true); key_event("E"); key_event("E",false); key_event("Enter");
     check(read_bits()==Confirm,"real keyboard confirm wins pending shortcut");
     key_event("Enter",false); check(read_bits()==0,"confirm retirement leaves no pending shortcut");}
    std::cout << "PASS: " << checks << " generated host checks\n";
}
