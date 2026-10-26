// Switch-only launcher: compiled alongside the unchanged PAL host/core.
#include <switch.h>
#include <SDL3/SDL.h>
#include "disc_files.h"
#include <cstdio>
#include <unistd.h>
#include <vector>
#include <string>
extern int pal_runtime_main(int argc, char** argv);
static constexpr const char* Root="sdmc:/switch/pal-saturn-recomp";
static bool message(const std::string& text, bool retry) {
    consoleInit(nullptr); PadState pad; padConfigureInput(1,HidNpadStyleSet_NpadStandard); padInitializeDefault(&pad);
    std::printf("PAL Saturn Recomp - Switch preview\n\n%s\n\n%s\n",text.c_str(),retry?"A: Retry    PLUS: Exit":"PLUS: Exit");
    bool result=false;
    while(appletMainLoop()) {
        padUpdate(&pad); const u64 down=padGetButtonsDown(&pad);
        if(down&HidNpadButton_Plus) break;
        if(retry && (down&HidNpadButton_A)) {result=true;break;}
        consoleUpdate(nullptr);
    }
    consoleExit(nullptr); return result;
}
int main(int, char**) {
    // libnx mounts sdmc before main. Root-relative CUE paths use this default device.
    if(chdir("sdmc:/")!=0) {message("Cannot access the SD card",false);return 2;}
    // Never write within the resource directory.
    const std::filesystem::path root(Root), resources=root/"resources", saves=root/"saves";
    std::error_code ec; std::filesystem::create_directories(resources,ec);
    if(ec) {message("Cannot access SD directory:\n"+resources.string()+"\n"+ec.message(),false);return 2;}
    std::filesystem::create_directories(saves,ec);
    if(ec) {message("Cannot create save directory:\n"+saves.string()+"\n"+ec.message(),false);return 2;}
    std::string cue;
    const auto launch_cue=root/"launch.cue";
    for(;;) {
        auto discs=pal_switch::find_discs(resources); std::string error,normalized;
        if(discs.size()!=1) error="Put exactly one legal Saturn PAL CUE and ALL its BIN tracks into:\n"+resources.string()+"\nKeep original filenames/subfolders. Found CUE files: "+std::to_string(discs.size());
        else if(pal_switch::validate_disc(discs[0],error,&normalized)) {
            std::ofstream out(launch_cue,std::ios::trunc);out<<normalized;out.close();
            if(out) {cue=launch_cue.string();break;}
            error="Cannot write launch.cue metadata; check SD free space/write access";
        }
        if(!message(error,true)) return 2;
    }
    // Explicit paths: settings/saves do not depend on homebrew loader cwd or SDL PrefPath.
    std::vector<std::string> args={"pal-saturn-recomp","--cue",cue,"--save",(saves/"pal-saturn.bup").string(),
        "--cart",(saves/"pal-saturn-cart.bup").string(),"--clock","1998-11-01T12:00:00","--settings",(root/"settings.ini").string(),"--log",(root/"runtime.log").string(),"--fullscreen","--launcher"};
    std::vector<char*> argv; for(auto& s:args) argv.push_back(s.data()); argv.push_back(nullptr);
    const int original_out=dup(STDOUT_FILENO), original_err=dup(STDERR_FILENO);
    int rc=pal_runtime_main(int(args.size()),argv.data()); SDL_Quit();
    std::fflush(stdout); std::fflush(stderr);
    if(original_out>=0) {dup2(original_out,STDOUT_FILENO);close(original_out);}
    if(original_err>=0) {dup2(original_err,STDERR_FILENO);close(original_err);}
    if(rc) message("Game failed to start/run (code "+std::to_string(rc)+").\nCheck sdmc:/switch/pal-saturn-recomp/runtime.log",false);
    return rc;
}
