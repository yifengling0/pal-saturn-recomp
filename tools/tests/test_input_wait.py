from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class InputWaitTests(unittest.TestCase):
    def test_only_safe_field_wait_is_clamped(self):
        text=r'''
#include "pal_input_wait.h"
#include <cassert>
int main(){
 for(int count=-5;count<=12;++count)for(int flags=0;flags<32;++flags){
   bool scope=flags&1,edge=flags&2,ready=flags&4,dma=flags&8;int interval=(flags&16)?6:3;
   int got=pal_input_wake_target(count,interval,scope,edge,ready,dma);
   assert(got==((count>1&&scope&&edge&&ready&&dma&&interval==6)?1:count));
   assert(got>=0 || got==count);
 }
 for(int count=-5;count<=12;++count){
   assert(pal_input_align_target(count,false)==count);
   assert(pal_input_align_target(count,true)==(count>2?2:count));
 }
}
'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.cpp';p.write_text(text);exe=Path(d)/'test'
            subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src/pal_game'),str(p),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
