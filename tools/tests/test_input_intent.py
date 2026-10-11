from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class IntentTests(unittest.TestCase):
    def test_direction_intents(self):
        program=r'''
#include "pal_input_intent.h"
#include <cassert>
int main(){
  for(unsigned duration: {1,2,3,6,12}) for(unsigned phase=0;phase<6;++phase){
    PalInputIntent s;s.clear(0);unsigned t=100+phase;
    s.sample(0x8000,t,true);s.sample(0,t+duration,true);
    assert(s.take(t+duration)==0x8000);assert(s.take(t+duration+1)==0);
  }
  PalInputIntent s;s.clear(0);s.sample(0x8000,0,true);
  assert(s.take(0)==0x8000);assert(s.take(3)==0);assert(s.take(11)==0);
  assert(s.take(12)==0x8000);assert(s.take(14)==0);assert(s.take(15)==0x8000);
  s.sample(0,16,true);assert(s.take(18)==0);
  s.clear(0);s.sample(0x8000,20,true);s.sample(0x2000,21,true);s.sample(0x1000,22,true);
  assert(s.take(22)==0x1000);assert(s.take(23)==0);
  s.sample(0,24,true);assert(s.take(30)==0);
  s.clear(0);s.sample(0x4000,40,true);s.sample(0x4000,41,false);
  assert(s.take(42)==0);s.sample(0x4000,43,true);assert(s.take(44)==0);
  s.sample(0,45,true);s.sample(0x4000,46,true);assert(s.take(46)==0x4000);
  s.clear(0);s.sample(0x8000,40,true);s.take(40);s.sample(0xA000,41,true);
  assert(s.take(41)==0x2000);s.sample(0xA000,42,true);assert(s.take(53)==0x2000);
  s.clear(0);s.sample(0x8000,49,true);s.sample(0xC000,50,true);assert(s.take(50)==0);
  s.clear(0);s.sample(0,60,true);s.edge(0x8000,60,true);assert(s.take(60)==0x8000);assert(s.take(61)==0);
  s.clear(0);s.edge(0x8000,60,false);assert(s.take(60)==0);
  s.clear(0);s.sample(0x8000,0,true);s.edge(0x8000,0,true);
  s.sample(0xC000,1,true);s.edge(0x4000,1,true);s.sample(0,2,true);assert(s.take(5)==0);
  s.clear(0);s.sample(0xA000,60,true);s.edge(0x2000,60,true);assert(s.take(60)==0x2000);
  s.sample(0xA000,61,true);assert(s.take(72)==0x2000);
  s.clear(0);s.sample(0x3000,50,true);assert(s.take(50)==0);
}
'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'intent.cpp';exe=Path(d)/'intent';source.write_text(program)
            subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src/pal_game'),str(source),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
