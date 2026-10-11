"""No-ROM cadence policy, nested scope, timing and exception regression."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

def test_cadence_policy_and_runtime_scope():
    with tempfile.TemporaryDirectory(prefix='PAL cadence 空格 ') as folder:
        exe = Path(folder) / ('cadence.exe' if os.name == 'nt' else 'cadence')
        subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-Wall', '-Wextra', '-Werror',
            '-I'+str(ROOT/'src/pal_game'),
            '-I'+str(ROOT/'third_party/saturn-recomp-pal/runtime/include'),
            str(ROOT/'tools/tests/effect_cadence_test.cpp'), '-o', str(exe)], check=True, capture_output=True)
        for speed in ('1', '1.25', '1.5', '2', 'bad'):
            subprocess.run([str(exe)], env=dict(os.environ, PAL_EFFECT_ANIMATION_SPEED=speed), check=True, capture_output=True)


def test_runtime_fiber_modes_fail_closed():
    import importlib.util
    spec = importlib.util.spec_from_file_location('cadence_installer_test', ROOT/'tools/pal_options.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = r"""
#include <cstdint>
#include <string>
#include <cassert>
struct {uint32_t task_setjmp=0;std::string state_in;} g_cfg;
uint32_t g_sh2_tasks[2]{};
""" + module.CADENCE_RUNTIME_SUPPORT + r"""
int main() {
 for(unsigned mask=0;mask<8;++mask) {
  g_cfg.task_setjmp=mask&1?1:0;
  g_sh2_tasks[0]=mask&2?1:0;
  g_cfg.state_in=mask&4?"example.state":"";
  assert(pal_effect_cadence_scope_supported()==(mask==0));
 }
}
"""
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder)/'scope.cpp'
        source.write_text(code)
        exe = Path(folder)/('scope.exe' if os.name == 'nt' else 'scope')
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)], check=True,capture_output=True)
        subprocess.run([str(exe)],check=True,capture_output=True)
