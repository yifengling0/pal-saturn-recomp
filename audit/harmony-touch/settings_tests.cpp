// Independent settings acceptance candidate. Compile against the candidate's real settings.cpp.
// Args: isolated output directory, actual display key, expected default presentation, expected default opacity.
#include "settings.h"
#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>
static int checks=0,failures=0;
#define CHECK(expr) do {++checks;if(!(expr)){++failures;std::printf("FAIL line %d: %s\n",__LINE__,#expr);}}while(0)
static bool contains(const std::string& s,const std::string& v){return s.find(v)!=std::string::npos;}
int main(int argc,char**argv) {
  if(argc!=5){std::fprintf(stderr,"usage: settings-test OWNED_AUDIT_DIR DISPLAY_KEY DEFAULT_MODE DEFAULT_OPACITY\n");return 2;}
  const std::string directory=argv[1],key=argv[2],mode=argv[3];const int alpha=std::stoi(argv[4]);
  // Edge-menu defaults, strict booleans, and exact restart persistence.
#if defined(PAL_OHOS_DEFAULTS)
  CHECK(Settings{}.flag("touch","edge_menu"));
#else
  CHECK(!Settings{}.flag("touch","edge_menu"));
#endif
  for(const auto* value:{"true","false"}) {
    Settings edge;std::vector<std::string> errors;
    edge.read(std::string("[touch]\nedge_menu = ")+value+"\n",errors);
    CHECK(errors.empty());CHECK(edge.get("touch","edge_menu")==value);
    auto text=edge.write_over("; preserve\n[touch]\n");Settings restart;restart.read(text,errors);
    CHECK(restart.get("touch","edge_menu")==value);CHECK(restart.write_over(text)==text);
  }
  for(const auto* bad:{"True","1","yes","","null"}) {
    Settings edge;std::vector<std::string> errors;
    edge.read(std::string("[touch]\nedge_menu = ")+bad+"\n",errors);
    CHECK(errors.size()==1);CHECK(edge.get("touch","edge_menu")==Settings{}.get("touch","edge_menu"));
  }
  // Missing version upgrades geometry, while existing explicit preferences survive.
  Settings migrated;std::vector<std::string> migration_problems;
  migrated.read("[touch]\nsize = 140\nopacity = 75\nstyle = japanese\n[display]\npresentation = original\n",migration_problems);
  CHECK(migration_problems.empty());CHECK(migrated.number("touch","size")==140);CHECK(migrated.number("touch","opacity")==75);CHECK(migrated.get("display","presentation")=="original");
#if defined(PAL_OHOS_DEFAULTS)
  CHECK(migrated.number("touch","layout_version")==2);
#else
  CHECK(migrated.number("touch","layout_version")==1);
#endif
  auto upgraded=migrated.write_over("[touch]\nsize = 140\nopacity = 75\n");CHECK(contains(upgraded,"layout_version = "));Settings reloaded;reloaded.read(upgraded,migration_problems);CHECK(reloaded.number("touch","size")==140);CHECK(reloaded.number("touch","opacity")==75);CHECK(reloaded.write_over(upgraded)==upgraded);
  for(int value:{50,100,200}) { Settings v;std::vector<std::string> p;v.read("[touch]\nspacing = "+std::to_string(value)+"\n",p);CHECK(p.empty());CHECK(v.number("touch","spacing")==value);auto t=v.write_over("[touch]\n");Settings r;r.read(t,p);CHECK(r.number("touch","spacing")==value); }
  for(const auto* bad:{"49","201","","nan","50.5"}) { Settings v;std::vector<std::string> p;v.read(std::string("[touch]\nspacing = ")+bad+"\n",p);CHECK(p.size()==1);CHECK(v.number("touch","spacing")==100); }
  for(const std::string& name:{"dpad_x","dpad_y","face_x","face_y","left_x","left_y","right_x","right_y","start_x","start_y","menu_x","menu_y"}) {
    for(int n:{-1,0,1700,10000}){Settings v;std::vector<std::string> p;v.read("[touch]\n"+name+" = "+std::to_string(n)+"\n",p);CHECK(p.empty());CHECK(v.number("touch",name)==n);auto text=v.write_over("[touch]\n");Settings back;back.read(text,p);CHECK(back.number("touch",name)==n);}
    for(const auto* bad:{"-2","10001","NaN","1.5"}){Settings v;std::vector<std::string> p;v.read("[touch]\n"+name+" = "+bad+"\n",p);CHECK(p.size()==1);CHECK(v.number("touch",name)==-1);}
  }
  Settings defaults;
  CHECK(defaults.number("touch","opacity")==alpha);
  CHECK(defaults.get("display",key)==mode);
  CHECK(defaults.number("touch","size")==100);
  CHECK(defaults.write_over(Settings::default_text())==Settings::default_text());
  for(int v:{20,55,100}) {
    Settings s;std::vector<std::string> problems;
    s.read("[touch]\nopacity = "+std::to_string(v)+"\n",problems);
    CHECK(problems.empty());CHECK(s.number("touch","opacity")==v);
    auto out=s.write_over("; retain header\n[touch]\nsize = 150\nopacity = "+std::to_string(v)+"\n");
    Settings back;back.read(out,problems);CHECK(back.number("touch","opacity")==v);CHECK(contains(out,"; retain header"));
  }
  for(const std::string& bad:{"19","101","-1","55.5","alpha","","100garbage","9999999999999999999999999"}) {
    Settings s;std::vector<std::string> problems;s.read("[touch]\nopacity = "+bad+"\n",problems);
    CHECK(problems.size()==1);CHECK(s.number("touch","opacity")==alpha);
  }
  for(const std::string& value:{"fit","stretch","original"}) {
    Settings s;std::vector<std::string> problems;s.read("[display]\n"+key+" = "+value+"\n",problems);
    CHECK(problems.empty());CHECK(s.get("display",key)==value);
    auto out=s.write_over("[display]\n");Settings back;back.read(out,problems);CHECK(back.get("display",key)==value);
    CHECK(back.write_over(out)==out); // idempotent serialization
  }
  for(const std::string& bad:{"fill","Fit","stretched",""}) {
    Settings s;std::vector<std::string> problems;s.read("[display]\n"+key+" = "+bad+"\n",problems);
    CHECK(problems.size()==1);CHECK(s.get("display",key)==mode);
  }
  // Existing user file without new fields: retain selected values, comments and future/independent profiles.
  const std::string old="; user heading\n[display]\nfullscreen = true\nscale = 2\n[touch]\n; user layout note\nsize = 150\nstyle = japanese\nmenu_button = false\n[keyboard]\na = Space\n[gamepad]\na = b\n[controls]\nkeyboard_profile = pc98\n[keyboard pc98]\nconfirm = Return\nmenu_cancel = Escape\n[future]\nfoo = custom-value\n";
  Settings upgrade;std::vector<std::string> notices;upgrade.read(old,notices);
  CHECK(upgrade.number("touch","size")==150);CHECK(upgrade.get("touch","style")=="japanese");
  CHECK(upgrade.number("touch","opacity")==alpha);CHECK(upgrade.get("display",key)==mode);
  CHECK(upgrade.get("keyboard","a")=="Space");CHECK(upgrade.get("gamepad","a")=="b");
  upgrade.set("touch","opacity","80");upgrade.set("display",key,"stretch");
  auto written=upgrade.write_over(old);
  CHECK(contains(written,"opacity = 80"));CHECK(contains(written,key+" = stretch"));
  for(const std::string& keep:{"; user heading","; user layout note","keyboard_profile = pc98","confirm = Return","menu_cancel = Escape","foo = custom-value"}) CHECK(contains(written,keep));
  Settings reread;std::vector<std::string> reread_notes;reread.read(written,reread_notes);
  CHECK(reread.number("touch","opacity")==80);CHECK(reread.get("display",key)=="stretch");CHECK(reread.number("touch","size")==150);
  CHECK(reread.write_over(written)==written);
  // Touch-only reset contract; actual host action is also tested in actual_host_tests.cpp.
  for(const auto& name:defaults.keys("touch")) reread.set("touch",name,defaults.get("touch",name));
  CHECK(reread.number("touch","opacity")==alpha);CHECK(reread.number("touch","size")==100);
  CHECK(reread.get("keyboard","a")=="Space");CHECK(reread.get("gamepad","a")=="b");CHECK(reread.get("display",key)=="stretch");
  auto reset=reread.write_over(written);CHECK(contains(reset,"keyboard_profile = pc98"));CHECK(contains(reset,"confirm = Return"));
  std::filesystem::create_directories(directory);const std::string path=directory+"/settings-candidate.ini";
  CHECK(settings_store(path,written));bool found=false;auto disk=settings_load(path,found);CHECK(found);CHECK(disk==written);CHECK(!std::filesystem::exists(path+".new"));
  Settings restart;std::vector<std::string> restart_notes;restart.read(disk,restart_notes);
  CHECK(restart.number("touch","opacity")==80);CHECK(restart.get("display",key)=="stretch");CHECK(restart.get("keyboard","a")=="Space");
  std::printf("%d settings checks, %d failures\n",checks,failures);return failures?1:0;
}
