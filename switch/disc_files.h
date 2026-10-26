#pragma once
// Read-only preflight. A normalized CUE is returned, never written over source files.
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <set>
#include <string>
#include <vector>
namespace pal_switch {
namespace fs = std::filesystem;
inline std::string upper(std::string s) {for(auto& c:s)c=char(std::toupper((unsigned char)c));return s;}
inline bool validate_disc(const fs::path& cue,std::string& error,std::string* normalized=nullptr) {
 std::ifstream in(cue); if(!in){error="Cannot open CUE: "+cue.string();return false;}
 std::string line; unsigned line_no=0,tracks=0,files=0; bool indexed=true;
 constexpr uint64_t expected_starts[]={0,132138,144036,154279,164654,176293,187263,197931,206294,219441,222337,223840,235392};
 uint64_t sectors=0,file_base=0,last_index=0,last_start=0; bool has_last=false,has_start=false;
 unsigned file_start_tracks=0; fs::path current;
 std::ostringstream output;std::set<std::string> seen_files;
 auto fail=[&](std::string s){error=s+" (CUE line "+std::to_string(line_no)+")";return false;};
 while(std::getline(in,line)) {
  ++line_no; if(line_no==1 && line.compare(0,3,"\xef\xbb\xbf")==0)line.erase(0,3);
  std::istringstream row(line);std::string word;row>>word;word=upper(word);
  if(word=="FILE") {
   if(!indexed)return fail("Previous track has no INDEX 01");
   if(files && tracks==file_start_tracks)return fail("FILE has no tracks");
   file_start_tracks=tracks;
   row>>std::ws;std::string name,type;
   if(row.peek()=='"'){row.get();std::getline(row,name,'"');}else row>>name;
   row>>type;std::replace(name.begin(),name.end(),'\\','/');
   fs::path rel(name);bool safe=!name.empty()&&!rel.is_absolute()&&name.find(':')==std::string::npos;
   for(const auto& p:rel)if(p=="..")safe=false;
   if(!safe||upper(type)!="BINARY")return fail("Unsupported or unsafe FILE");
   current=cue.parent_path()/rel;std::error_code ec;
   if(!seen_files.insert(current.lexically_normal().generic_string()).second)return fail("Duplicate FILE source");
   if(!fs::is_regular_file(current,ec))return fail("Missing track: "+name+"; keep exact filenames/subfolders");
   const auto size=fs::file_size(current,ec);
   if(ec||!size||size%2352)return fail("Empty/truncated raw track (must be a multiple of 2352 bytes): "+name);
   std::ifstream bin(current,std::ios::binary);if(!bin)return fail("Cannot read track: "+name);
   file_base+=sectors;sectors=size/2352;has_last=false;has_start=false;++files;
   // Generated launch.cue lives one level above resources/. Core prepends its
   // directory to these paths, preserving libnx's sdmc:/ device prefix.
   auto runtime_path=current.lexically_relative(cue.parent_path().parent_path()).generic_string();
   output<<"FILE \""<<runtime_path<<"\" BINARY\n";
  }else if(word=="TRACK") {
   if(!indexed)return fail("Previous track has no INDEX 01");
   unsigned n=0;std::string mode;row>>n>>mode;mode=upper(mode);
   if(!files||n!=tracks+1||n>13||mode!=(n==1?"MODE1/2352":"AUDIO"))return fail("Expected PAL track 1 MODE1/2352, tracks 2-13 AUDIO in order");
   ++tracks;indexed=false;output<<"  TRACK "<<n<<" "<<mode<<"\n";
  }else if(word=="INDEX") {
   unsigned n,m,s,f;char c1,c2;std::string extra;
   if(!(row>>n>>m>>c1>>s>>c2>>f)||c1!=':'||c2!=':'||s>=60||f>=75||n>1||!tracks||(row>>extra))return fail("Invalid INDEX timestamp");
   uint64_t pos=(uint64_t(m)*60+s)*75+f;
   if(pos>=sectors||(has_last&&pos<last_index))return fail("INDEX outside track file or out of order");
   if(n==1){
    if(indexed)return fail("Duplicate INDEX 01");
    if((tracks==1 && pos!=0)||(has_start && pos<=last_start))return fail("Track starts must increase; first track must start at zero");
    if(file_base+pos!=expected_starts[tracks-1])return fail("Track layout differs from the supported T-37401H raw rip");
    last_start=pos;has_start=true;
    indexed=true;
    if(tracks==1){
     std::ifstream bin(current,std::ios::binary);bin.seekg(pos*2352+16);char header[96]{};bin.read(header,sizeof header);
     if(!bin||std::string(header,16)!="SEGA SEGASATURN "||std::string(header+32,16)!="T-37401H  V1.000")return fail("Wrong disc: requires Taiwan T-37401H V1.000");
    }
   }
   last_index=pos;has_last=true;output<<"    INDEX "<<n<<" "<<m<<":"<<s<<":"<<f<<"\n";
  }else if(word=="PREGAP"||word=="POSTGAP")return fail("Separate PREGAP/POSTGAP is unsupported; use a complete raw CUE/BIN rip");
 }
 if(in.bad()||!files||tracks==file_start_tracks||tracks!=13||!indexed){error="Incomplete PAL CUE: requires all 13 tracks, each with INDEX 01";return false;}
 if(file_base+sectors!=243793){error="Incomplete/wrong disc length: expected 243793 raw sectors (573401136 bytes total)";return false;}
 if(normalized)*normalized=output.str();
 error.clear();return true;
}
inline std::vector<fs::path> find_discs(const fs::path& directory){
 std::vector<fs::path> cues;std::error_code ec;
 for(fs::directory_iterator i(directory,ec),end;!ec&&i!=end;i.increment(ec))
  if(i->is_regular_file(ec)&&upper(i->path().extension().string())==".CUE")cues.push_back(i->path());
 std::sort(cues.begin(),cues.end());return cues;
}
}
