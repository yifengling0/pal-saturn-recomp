#include "disc_files.h"
#include "saturn.h"
#include <cassert>
#include <cstring>
#include <iostream>
int main(int argc,char** argv) {
 assert(argc==3);std::string error,normalized;
 assert(pal_switch::validate_disc(argv[1],error,&normalized));
 std::ofstream out(argv[2]);out<<normalized;out.close();assert(out);
 assert(cdrom_open(argv[2]));uint8_t raw[2352];assert(cdrom_read(150,raw));
 assert(std::memcmp(raw+16,"SEGA SEGASATURN ",16)==0);
 assert(cdrom_is_audio(150)==false);assert(cdrom_is_audio(150+(29*60+21)*75+63)==true);
 uint32_t fad=0,size=0;assert(cdrom_find("PROG.BIN",&fad,&size));assert(size>0);
 std::cout<<"PASS actual cdrom_open, sector 150 header, CD-DA boundary, PROG.BIN ISO lookup using normalized relative CUE\n";
}
