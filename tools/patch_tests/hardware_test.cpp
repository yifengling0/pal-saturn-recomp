#include "saturn.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
int main(int argc,char**argv) {
    assert(argc==2);
    std::filesystem::path d(argv[1]); std::filesystem::create_directories(d);
    std::ofstream bin(d/"mixed.bin",std::ios::binary); std::string sectors(2352*8,'\0'); bin.write(sectors.data(),sectors.size()); bin.close();
    std::ofstream cue(d/"mixed.cue");
    cue << "FILE \"mixed.bin\" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n TRACK 02 AUDIO\n INDEX 01 00:00:04\n"; cue.close();
    assert(cdrom_open((d/"mixed.cue").string()));
    assert(!cdrom_is_audio(150)); assert(!cdrom_is_audio(153)); assert(cdrom_is_audio(154)); assert(cdrom_is_audio(157));
    g_cpu=&g_master; g_cfg.trace=true; g_cfg.save="-";
    mmio_watch(0x05F80020,0x05F80020);
    sh2_mmio_write(0x05F80020,0x0013,2);
    assert(sh2_mmio_read(0x05F80020,2)==0x0013);
    mmio_log_write((d/"mmio.txt").string());
    std::ifstream in(d/"mmio.txt"); std::string s((std::istreambuf_iterator<char>(in)),{});
    assert(s.find("watch W 05F80020 1")!=std::string::npos);
    assert(s.find("watch R 05F80020 1")!=std::string::npos);
    std::cout << "patch0001+0004: 9 assertions passed; single BIN mixed track, register read/write watch\n";
}
