#include "pal_keyboard_profile.h"
#include <cstdlib>
#include <iostream>
using namespace pal_keyboard;
static int checks;
static void check(bool v,const char* s){++checks;if(!v){std::cerr<<"FAIL "<<s<<'\n';std::exit(1);}}
static AllAttackIntent at_other(){AllAttackIntent a;a.request(true,0,1,7,10);check(a.pad(11)==0x2000,"native Down wakes blocking guest");a.main_event(4,0,1,7,12);check(a.pad(12)==0,"Down acknowledged and released");a.main_ready(3,0,1,7,13);check(a.pad(18)==0,"seven VB neutral before confirm");check(a.pad(19)==Confirm,"native main confirm");a.main_event(1,0,1,7,20);a.main_return(3,0,1,7,20);return a;}
int main(){
 for(unsigned cursor=0;cursor<4;++cursor){AllAttackIntent a;a.request(true,0,1,9,100);a.main_ready(cursor,0,1,9,100);check(a.pad(100)==0x2000,"all old cursors select Down");a.main_event(4,0,1,9,101);a.main_ready(3,0,1,9,102);check(a.pad(107)==0,"neutral");check(a.pad(108)==Confirm,"main confirm");a.main_event(1,0,1,9,109);a.main_return(3,0,1,9,109);check(a.other_enter(true,0x060F0000,0,1,110),"exact Other entry");check(a.pad(116)==0,"Other not yet drawn");a.other_wait(0x060F0000,0,0,1,116);check(a.pad(116)==Confirm,"visible Other confirms via original pad");a.other_event(1,0x060F0000,117);check(a.pad(117)==0,"only once");}
 for(unsigned event=1;event<=11;++event){if(event==4)continue;AllAttackIntent a;a.request(true,0,1,7,10);a.main_event(event,0,1,7,11);check(a.stage==AllAttackIntent::Idle,"unexpected real input cancels");}
 for(int result=-11;result<=3;++result){if(result==3)continue;auto a=at_other();a.stage=AllAttackIntent::AwaitMainReturn;a.main_return(result,0,1,7,21);check(a.stage==AllAttackIntent::Idle,"unexpected main result retires");}
 for(int scenario=0;scenario<6;++scenario){auto a=at_other();bool allowed=a.other_enter(scenario!=0,scenario==1?0x060F0001:0x060F0000,scenario==2?1:0,scenario==3?2:1,scenario==4?250:9);check(!allowed,"Other invalid context denied");}
 for(int scenario=0;scenario<4;++scenario){auto a=at_other();check(a.other_enter(true,0x060F0000,0,1,21),"valid Other");a.other_wait(scenario==0?0x060F0010:0x060F0000,scenario==1?1:0,scenario==2?1:0,scenario==3?2:1,28);check(a.pad(28)==0,"wrong Other identity/cursor cannot confirm");}
 AllAttackIntent a;a.request(false,0,1,7,10);check(a.stage==AllAttackIntent::Idle,"outside main ignored");
 a.request(true,0,1,7,10);a.main_ready(3,1,1,7,11);check(a.pad(11)==0,"actor change ignored");
 a.request(true,0,1,7,10);a.main_ready(3,0,1,8,11);check(a.pad(11)==0,"new menu ignored");
 a.request(true,0,1,7,10);a.main_ready(3,0,2,7,11);check(a.pad(11)==0,"member change ignored");
 a.request(true,0,1,7,10);a.stop();check(a.pad(11)==0,"focus/menu explicit cancel");
 {BattleCommandsScope scope(true,0,1);all_attack.request(true,0,1,battle_boundary,10);}check(all_attack.pad(11)==0,"unacknowledged scope exit clears");
 a.request(true,0,1,7,10);a.main_event(4,0,1,7,12);a.main_ready(3,0,1,7,13);check(a.pad(11)==0,"VB rollback after start clears, no unsigned underflow");
 check(Defend==0x40 && Throw==0x20 && Strongest==8,"distinct native keys");
 std::cout<<"PASS: "<<checks<<" battle pad/menu checks; synthetic only\n";
}
