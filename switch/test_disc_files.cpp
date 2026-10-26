#include "disc_files.h"
#include <cassert>
#include <iostream>
static void put(const std::filesystem::path& p,const std::string& s){std::ofstream(p,std::ios::binary)<<s;}
static std::string cue_text(){
 const unsigned starts[]={0,132138,144036,154279,164654,176293,187263,197931,206294,219441,222337,223840,235392};
 std::string s="FILE \"tracks/Track 01.bin\" BINARY\n";
 for(int i=0;i<13;++i)s+="TRACK "+std::to_string(i+1)+(i==0?" MODE1/2352\n":" AUDIO\n")+"INDEX 01 "+std::to_string(starts[i]/4500)+":"+std::to_string(starts[i]/75%60)+":"+std::to_string(starts[i]%75)+"\n";
 return s;
}
static void bin(const std::filesystem::path& p,uint64_t size,bool good=true){
 std::string h(96,'\0');h.replace(16,16,"SEGA SEGASATURN ");h.replace(48,16,good?"T-37401H  V1.000":"X-37401H  V1.000");put(p,h);std::filesystem::resize_file(p,size);
}
int main(int argc,char** argv){
 assert(argc>=2);namespace fs=std::filesystem;fs::path d=argv[1];fs::create_directories(d/"tracks");
 std::string e,normalized;auto cue=d/"game.cue";const auto text=cue_text();
 assert(!pal_switch::validate_disc(cue,e));put(cue,text);assert(!pal_switch::validate_disc(cue,e));
 bin(d/"tracks/Track 01.bin",573401136);assert(pal_switch::validate_disc(cue,e,&normalized));
 assert(normalized.find((d.filename()/"tracks/Track 01.bin").generic_string())!=std::string::npos);
 assert(pal_switch::find_discs(d).size()==1);
 for(auto bad:{std::string("FILE \"../secret.bin\" BINARY\n"),std::string("FILE \"/absolute.bin\" BINARY\n"),std::string("FILE \"tracks/Track 01.bin\" MP3\n"),std::string("REM nothing\n"),text+"PREGAP 00:02:00\n",text+"INDEX 01 00:00:00\n"}){put(cue,bad);assert(!pal_switch::validate_disc(cue,e));}
 auto missing=text.substr(0,text.rfind("INDEX"));put(cue,missing);assert(!pal_switch::validate_disc(cue,e));
 auto lower=text;for(auto& c:lower)if(c>='A'&&c<='Z')c+=32;
 // Lowercase directives, retain exact case-sensitive filename.
 lower.replace(lower.find("tracks/track 01.bin"),19,"tracks/Track 01.bin");
 put(cue,"\xef\xbb\xbf"+lower);if(!pal_switch::validate_disc(cue,e)){std::cerr<<e<<"\n";return 1;}
 put(cue,text);bin(d/"tracks/Track 01.bin",573401137);assert(!pal_switch::validate_disc(cue,e));
 bin(d/"tracks/Track 01.bin",573401136,false);assert(!pal_switch::validate_disc(cue,e));
 bin(d/"tracks/Track 01.bin",573401136-2352);assert(!pal_switch::validate_disc(cue,e));
 put(d/"tracks/Track 01.bin","");assert(!pal_switch::validate_disc(cue,e));
 put(d/"second.CUE","REM another");assert(pal_switch::find_discs(d).size()==2);
 const uint64_t offsets[]={0,132138,144036,154279,164654,176293,187263,197931,206294,219441,222337,223840,235392,243793};
 fs::create_directories(d/"split");std::string split;
 for(int n=1;n<=13;++n){auto name="track"+std::to_string(n)+".bin";bin(d/"split"/name,(offsets[n]-offsets[n-1])*2352);split+="FILE \""+name+"\" BINARY\nTRACK "+std::to_string(n)+(n==1?" MODE1/2352\n":" AUDIO\n")+"INDEX 01 00:00:00\n";}
 put(d/"split/game.cue",split);assert(pal_switch::validate_disc(d/"split/game.cue",e));
 fs::resize_file(d/"split/track13.bin",(243793-235392-1)*2352);assert(!pal_switch::validate_disc(d/"split/game.cue",e));
 std::cout<<"PASS exact TOC/total sectors, sector-aligned truncation rejection, single-file and 13-file layout\n";
 if(argc>2){assert(pal_switch::validate_disc(argv[2],e,&normalized));std::cout<<"PASS internal original 13-track CUE validation\n";}
 std::cout<<"PASS synthetic validation: missing files, 13 tracks, indices, spaces, nested paths, traversal, absolute paths, format, BOM/case, alignment, identity, multiple CUEs\n";
}
