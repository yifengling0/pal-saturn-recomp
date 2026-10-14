#include "pal_display_layout.h"
#include "pal_pcm_batch.h"
#include "touch_positions.h"
#include "touch_split_pad.h"
#include "settings.h"
#include <cassert>
#include <iostream>
#include <limits>
static bool near(float a,float b) {return std::fabs(a-b)<.03f;}
int main() {
    using namespace pal_display;
    for(auto size:std::array<std::pair<int,int>,8>{{{2560,1600},{1600,2560},{1920,1080},{1080,1920},{2208,1840},{640,480},{3440,1440},{512,512}}}) {
        const auto [w,h]=size;
        for(float aspect:{320.f/224,320.f/240,320.f/256,640.f/448}) {
            auto fit=touch_game_viewport(w,h,aspect,false);
            assert(near(fit.w/fit.h,aspect));assert(near(fit.w,w)||near(fit.h,h));
            assert(fit.x>=0&&fit.y>=0&&fit.x+fit.w<=w+.03f&&fit.y+fit.h<=h+.03f);
            auto stretch=touch_game_viewport(w,h,aspect,true);
            assert(stretch.x==0&&stretch.y==0&&stretch.w==w&&stretch.h==h);
        }
        for(bool horizontal:{false,true}) {
            Fold fold{true,1,{}};fold.creases[0]=horizontal?Rect{0,.49f,1,.02f}:Rect{.49f,0,.02f,1};
            auto split=regions(w,h,"auto",60,fold);assert(split.split);
            if(horizontal) {assert(split.game.y+split.game.h<=.49f*h+.01f);assert(split.controls.y>=.51f*h-.01f);}
            else {assert(split.game.x+split.game.w<=.49f*w+.01f);assert(split.controls.x>=.51f*w-.01f);}
            fold.half=false;assert(!regions(w,h,"auto",60,fold).split);
            fold.half=true;assert(!regions(w,h,"overlay",60,fold).split);
            fold.count=0;assert(!regions(w,h,"auto",60,fold).split);
        }
        for(const char* mode:{"below","right"})for(int percent:{30,60,70}) {
            auto split=regions(w,h,mode,percent,{});assert(split.split);
            // Both legacy directions represent manual separation, following a rotated surface.
            if(h>w) {assert(split.game.w==w&&near(split.game.h,std::floor(h*percent/100.f)));assert(split.controls.y==split.game.h);}
            else {assert(split.game.h==h&&near(split.game.w,std::floor(w*percent/100.f)));assert(split.controls.x==split.game.w);}
            assert(std::string(layout_choice(w,h,2))==(h>w?"below":"right"));
            assert(layout_index(mode)==2);
            for(int scale:{50,100,200}) {
                const int cw=(int)split.controls.w,ch=(int)split.controls.h;
                auto layout=touch_positioned(touch_split_pad(cw,ch,1,scale,100),cw,ch,1,{});
                for(int group=0;group<kTouchGroups;++group) {
                    auto bounds=touch_group_bounds(layout,(TouchGroup)group);
                    assert(bounds.x>=-.01f&&bounds.y>=-.01f&&bounds.x+bounds.w<=cw+.01f&&bounds.y+bounds.h<=ch+.01f);
                    auto center=touch_position_for_center(layout,(TouchGroup)group,cw,ch,1,bounds.x+bounds.w/2,bounds.y+bounds.h/2);
                    TouchPositions saved{};saved[group]=center;
                    auto restored=touch_positioned(layout,cw,ch,1,saved);
                    auto b=touch_group_bounds(restored,(TouchGroup)group);
                    assert(std::fabs(b.x-bounds.x)<.4f&&std::fabs(b.y-bounds.y)<.4f);
                }
                for(const auto& button:layout.buttons)assert(touch_buttons(layout,{{button.x,button.y,false}})&button.bit);
                const auto old=layout;
                for(int group=0;group<kTouchGroups;++group)touch_translate_group(layout,(TouchGroup)group,split.controls.x,split.controls.y);
                for(size_t i=0;i<layout.buttons.size();++i)assert(touch_buttons(layout,{{old.buttons[i].x+split.controls.x,old.buttons[i].y+split.controls.y,false}})&old.buttons[i].bit);
            }
        }
    }
    assert(layout_index("auto")==0&&layout_index("overlay")==1);
    assert(orientation_id("landscape")==0&&orientation_id("portrait")==1&&orientation_id("auto")==2);
    auto landscape=regions(2560,1600,"below",60,{});
    auto portrait=regions(1600,2560,"below",60,{});
    assert(landscape.game.w==1536&&landscape.controls.x==1536);
    assert(portrait.game.h==1536&&portrait.controls.y==1536);
    Fold invalid{true,1,{Rect{0,std::numeric_limits<float>::quiet_NaN(),1,.01f}}};
    assert(!regions(1000,1000,"auto",60,invalid).split);
    assert(!regions(0,1000,"right",60,{}).split);
    TouchLayout clipped{};clipped.clip_x=100;clipped.clip_y=100;clipped.clip_w=200;clipped.clip_h=200;
    clipped.dpad_x=105;clipped.dpad_y=105;clipped.dpad_r=30;
    clipped.buttons.push_back({"A",B_A,TouchButton::Round,105,105,20,20});
    assert(!touch_on_dpad(clipped,95,105));
    assert(touch_buttons(clipped,{{95,105,false}})==0);
    assert(touch_buttons(clipped,{{105,105,false}})==B_A);
    // A captured thumb retains the accepted walking rule while sliding off the pad.
    assert(touch_buttons(clipped,{{50,105,true}})&B_LEFT);
    Settings settings;std::vector<std::string> problems;
    settings.read("[display]\norientation = portrait\nlayout = right\ngame_percent = 70\n[touch]\nsplit_face_x = 9000\n",problems);
    assert(problems.empty());assert(settings.get("display","layout")=="right");
    assert(settings.number("touch","face_x")==-1&&settings.number("touch","split_face_x")==9000);
    Settings roundtrip;roundtrip.read(settings.write_over(Settings::default_text()),problems);
    assert(problems.empty()&&roundtrip.get("display","layout")=="right");
    assert(roundtrip.get("display","orientation")=="portrait");
    assert(Settings{}.get("display","orientation")=="landscape");
    settings.read("[display]\nlayout = other\ngame_percent = 99\n",problems);assert(problems.size()==2);
    std::vector<int16_t> input(10240*2),output;
    for(size_t i=0;i<input.size();++i)input[i]=(int16_t)i;
    pal_pcm::Batch<256> batch;
    auto sink=[&](const int16_t* data,int frames){assert(frames==256);output.insert(output.end(),data,data+frames*2);};
    int offset=0;
    for(int chunk:{1,7,1000,33,2000,7199}){batch.push(input.data()+offset*2,chunk,sink);offset+=chunk;}
    assert(offset==10240&&output==input);
    batch.push(input.data(),1,sink);batch.clear();output.clear();batch.push(input.data()+2,256,sink);
    assert(output==std::vector<int16_t>(input.begin()+2,input.begin()+514));
    assert(pal_pcm::desktop_lead(480,48000)==2205);
    assert(pal_pcm::desktop_lead(1024,48000)==2705);
    assert(pal_pcm::desktop_limit(2205,480,48000)==2816);
    std::cout<<"aspect, fold split, touch hit/edit, settings and PCM order passed\n";
}
