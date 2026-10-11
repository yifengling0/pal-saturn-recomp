#include "touch_mobile_layout.h"
#include "touch_ui_policy.h"
#include <cstdio>
#include <utility>
static int checks=0,failures=0;
#define CHECK(x) do { ++checks; if(!(x)){++failures;std::printf("FAIL %d %s w=%d h=%d d=%g size=%d gap=%d\n",__LINE__,#x,w,h,d,size,gap);} } while(0)
int main() {
 for(auto wh:{std::pair{320,240},std::pair{360,240},std::pair{640,360},std::pair{360,640},std::pair{800,1280},std::pair{1280,800},std::pair{2048,1276}})
 for(float d:{1.f,2.f,3.f}) for(int size:{50,100,150,200}) for(int gap:{50,100,200}) {
  int w=wh.first*d,h=wh.second*d;auto l=touch_mobile_layout(w,h,d,size,gap);CHECK(l.buttons.size()==9);CHECK(l.menu_r*2/d>=48-.01f);
  const TouchButton *left=nullptr,*right=nullptr;float first=0;
  for(auto& b:l.buttons){float bw=b.shape==TouchButton::Round?2*b.w:b.w,bh=b.shape==TouchButton::Round?2*b.w:b.h;
   CHECK(b.x-bw/2>=-.01f&&b.x+bw/2<=w+.01f);CHECK(b.y-bh/2>=-.01f&&b.y+bh/2<=h+.01f);CHECK(!touch_on_menu(l,b.x,b.y));CHECK(!touch_on_dpad(l,b.x,b.y));
   CHECK(touch_buttons(l,{{b.x,b.y,false}})==b.bit);
   if(b.shape==TouchButton::Round){if(first)CHECK(std::fabs(first-b.w)<.01f);first=b.w;if(size==100&&gap==100)CHECK(bw/d>=48-.01f);}else {CHECK(bh/d>=48-.01f);if(size==100&&gap==100)CHECK(bw/d>=48-.01f);}
   if(b.bit==B_L)left=&b;if(b.bit==B_R)right=&b;
  }
  if(size==100&&gap==100){CHECK(l.dpad_x-l.dpad_r>=24*d-.01f);CHECK(l.dpad_y+l.dpad_r<=h-24*d+.01f);}
  CHECK(left&&right&&std::fabs(left->y-right->y)<.01f);
  CHECK(touch_buttons(l,{{l.dpad_x-l.dpad_r/2,l.dpad_y,true},{l.buttons[0].x,l.buttons[0].y,false}})==(B_LEFT|B_A));
 }
 auto old=touch_layout(2048,1276,touch_pad_unit(1276,1,100));auto now=touch_mobile_layout(2048,1276,1,100,100);
 std::printf("2048x1276 scale1: old A diameter %.1f, X %.1f; v2 A/X %.1f; old Start %.1f v2 %.1f\n",2*old.buttons[0].w,2*old.buttons[1].w,2*now.buttons[0].w,old.buttons[6].h,now.buttons[8].h);
 std::printf("%d geometry checks, %d failures; synthetic dimensions only\n",checks,failures);return failures?1:0;
}
