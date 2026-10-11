from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class HostEdgeTests(unittest.TestCase):
    def test_one_shot_direction_edge_and_boundaries(self):
        source=r'''
#include "pal_host_edge.h"
#include <cassert>
int main(){PalHostEdge e;
 e.down(0x8000,false,true,false); // a key-up follows without a second down
 assert(e.take()==0x8000);assert(e.take()==0);
 e.down(0x8000,true,true,false);assert(e.take()==0);
 e.down(0x8000,false,true,false);e.down(0x2000,false,true,false);
 assert(e.take()==0x2000);assert(e.take()==0);
 e.down(0x8000,false,true,false);e.clear();assert(e.take()==0);
 e.down(0x8000,false,false,false);assert(e.take()==0);
 e.down(0x8000,false,true,true);assert(e.take()==0);
 e.down(0x0400,false,true,false);assert(e.take()==0);
}
'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.cpp';p.write_text(source);exe=Path(d)/'test'
            subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src/pal_game'),str(p),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
