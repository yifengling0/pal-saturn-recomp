#include "touch_positions.h"
#include <cstdio>
#include <utility>
static int checks=0,failures=0;
#define CHECK(expr) do{++checks;if(!(expr)){++failures;printf("FAIL %d: %s\n",__LINE__,#expr);}}while(0)
static bool near(float a,float b,float tolerance=.08f){return std::fabs(a-b)<=tolerance;}
int main(){
 for(auto wh:{std::pair{320,240},std::pair{360,800},std::pair{800,360},std::pair{1280,800},std::pair{800,1280},std::pair{2048,1276}})
 for(float d:{1.f,2.f,3.f})for(int size:{50,100,200})for(int gap:{50,100,200}) {
  int w=wh.first*d,h=wh.second*d;auto base=touch_mobile_layout(w,h,d,size,gap);float margin=touch_position_margin(w,h,d);
  for(int normalized:{-1,0,1250,5000,10000}) {
   TouchPositions p;for(auto& value:p)value={normalized,normalized};auto l=touch_positioned(base,w,h,d,p);auto repeated=touch_positioned(l,w,h,d,p);
   for(int i=0;i<kTouchGroups;++i){auto b=touch_group_bounds(l,(TouchGroup)i),r=touch_group_bounds(repeated,(TouchGroup)i);
    CHECK(b.x>=margin-.1f&&b.y>=margin-.1f);CHECK(b.x+b.w<=w-margin+.1f&&b.y+b.h<=h-margin+.1f);CHECK(near(b.x,r.x)&&near(b.y,r.y));
    if(normalized>=0){auto got=touch_position_for_center(l,(TouchGroup)i,w,h,d,b.x+b.w/2,b.y+b.h/2);CHECK(std::abs(got.x-normalized)<=1);CHECK(std::abs(got.y-normalized)<=1);}
    auto low=touch_position_for_center(l,(TouchGroup)i,w,h,d,-1e6f,-1e6f);auto high=touch_position_for_center(l,(TouchGroup)i,w,h,d,1e6f,1e6f);CHECK(low.x==0&&low.y==0&&high.x==10000&&high.y==10000);
   }
  }
 }
 // Same stored percentages survive rotate/resize and different density/Size.
 TouchPositions custom;custom[(int)TouchGroup::Dpad]={1700,8100};custom[(int)TouchGroup::Face]={8400,7200};custom[(int)TouchGroup::Menu]={10000,0};
 for(auto wh:{std::pair{320,240},std::pair{1080,2400},std::pair{2560,1600}})for(float d:{1.f,2.f,3.f}){auto l=touch_positioned(touch_mobile_layout(wh.first,wh.second,d,140,120),wh.first,wh.second,d,custom);for(auto g:{TouchGroup::Dpad,TouchGroup::Face,TouchGroup::Menu}){auto b=touch_group_bounds(l,g);auto p=touch_position_for_center(l,g,wh.first,wh.second,d,b.x+b.w/2,b.y+b.h/2);CHECK(std::abs(p.x-custom[(int)g].x)<=1);CHECK(std::abs(p.y-custom[(int)g].y)<=1);}}
 // Defaults place Menu beside Start at the lower edge on a wide landscape screen.
 auto l=touch_mobile_layout(1920,1080,3,100,100);auto start=touch_group_bounds(l,TouchGroup::Start);CHECK(std::fabs(l.menu_y-(start.y+start.h/2))<.1f);CHECK(l.menu_y>1080*.7f);
 printf("%d normalized-position checks, %d failures\n",checks,failures);return failures?1:0;
}
