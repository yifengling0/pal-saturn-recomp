"""Prepare an isolated, opt-in PAL input experiment; baseline files are unchanged."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def instrument(out):
    specs={
      'p_prog_001.cpp': {
        '06026E1C':('pal_input_script_before();','pal_input_script_after();'),
        '06026E58':('', 'pal_input_apply(c);'),
        '06026E6C':('', 'pal_input_align();'),
        '06026E76':('pal_input_wait_begin(c);','pal_input_wait_end();'),
        '06026E84':('pal_input_script_before();','pal_input_script_after();'),
        '06026E90':('pal_input_clear();','pal_input_clear();'),
        '06026EB8':('pal_input_clear();','pal_input_clear();'),
        '06026F44':('pal_input_clear();','pal_input_clear();'),
        '06026F52':('pal_input_clear();','pal_input_clear();'),
      },
    }
    for name,points in specs.items():
        p=out/name;lines=p.read_text().splitlines(True)
        for pc,(before,after) in points.items():
            matches=[i for i,line in enumerate(lines) if '// '+pc+' ' in line]
            if len(matches)!=1:raise ValueError((pc,len(matches)))
            at=matches[0];line=lines[at]
            lines[at]=(f'    {before}\n' if before else '')+line+(f'    {after}\n' if after else '')
        text=''.join(lines)
        text=text.replace('void f_06026F90(SH2Context& c) {\n','void f_06026F90(SH2Context& c) {\n    pal_input_clear();\n')
        p.write_text('#include "'+str(ROOT/'src/pal_game/pal_responsive_input.h')+'"\n'+text)
    p=out/'p_prog_015.cpp';text=p.read_text();marker='void f_0606016E(SH2Context& c) {\n';assert text.count(marker)==1
    text=text.replace(marker,marker+'    pal_input_tick();\n')
    start=text.index('void f_0605D68A(SH2Context& c) {');end=text.index('\nvoid ',start+1)
    section=text[start:end]
    for pc,call in [('0605D6B0','pal_input_sync_enter(c);'),('0605D6BC','pal_input_sync_leave();')]:
        lines=section.splitlines(True);matches=[i for i,line in enumerate(lines) if '// '+pc+' ' in line]
        if len(matches)!=1:raise ValueError((pc,len(matches)))
        lines.insert(matches[0],'    '+call+'\n');section=''.join(lines)
    text=text[:start]+section+text[end:]
    p.write_text('#include "'+str(ROOT/'src/pal_game/pal_responsive_input.h')+'"\n'+text)
def patch_runtime(runtime):
    smpc=runtime/'src/machine/smpc.cpp'
    with smpc.open('a') as f:
        f.write('\n// PAL opt-in input observation API; INTBACK stays unchanged.\n'
                'uint16_t pal_host_direction_edge();\n'
                'uint16_t pal_input_peek() { return static_cast<uint16_t>(~pad_now(0)) & 0xFFF8; }\n'
                'uint16_t pal_input_edges() { uint16_t edge=pal_host_direction_edge(); return host_drives() ? edge : 0; }\n')
    null=runtime/'src/host/host_null.cpp'
    with null.open('a') as f:f.write('\nuint16_t pal_host_direction_edge() { return 0; }\n')
    host=runtime/'src/host/host.cpp';text=host.read_text()
    text='#include "'+str(ROOT/'src/pal_game/pal_host_edge.h')+'"\n'+text
    def replace_once(old,new):
        nonlocal text
        if text.count(old)!=1:raise ValueError('Unexpected SDL host source: '+old)
        text=text.replace(old,new)
    replace_once('static bool g_menu_open, g_quitting;',
      'static bool g_menu_open, g_quitting;\nstatic PalHostEdge g_pal_edge;\n'
      'uint16_t pal_host_direction_edge() { return g_pal_edge.take(); }\n'
      'static void pal_host_clear_edge() { g_pal_edge.clear(); }')
    replace_once('static uint16_t touch_read();','static uint16_t touch_read();\nstatic void pal_host_clear_edge();')
    replace_once('    for (int s = 0; s < kHostSlots; ++s) {',
      '    for (int s = 0; s < kHostSlots; ++s) {\n'
      '        if(s==0 && (((b[s]&0xC000)==0xC000) || ((b[s]&0x3000)==0x3000))) pal_host_clear_edge();')
    replace_once('static void menu_open() {','static void menu_open() {\n    g_pal_edge.clear();')
    replace_once('static void menu_close() {','static void menu_close() {\n    g_pal_edge.clear();')
    replace_once('static void on_event(const SDL_Event& e) {',
      'static void on_event(const SDL_Event& e) {\n'
      '    if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID == SDL_GetWindowID(g_win)) g_pal_edge.clear();\n'
      '    if (e.type == SDL_EVENT_KEY_DOWN && e.key.windowID == SDL_GetWindowID(g_win)) {\n'
      '        uint16_t direction=0;\n'
      '        for (auto& [key,bit] : g_keys) if (key==e.key.scancode) direction |= bit & 0xF000;\n'
      '        g_pal_edge.down(direction,e.key.repeat,SDL_GetKeyboardFocus()==g_win,g_menu_open || (direction & g_held_over[0]));\n'
      '    }')
    host.write_text(text)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--sdl-prefix',type=Path)
    p.add_argument('--jobs',type=int,default=2)
    a=p.parse_args();out=a.out.resolve()
    if out.exists():raise SystemExit('Refusing to overwrite existing experiment: '+str(out))
    baseline=ROOT/'build/linux-game-sdl/recomp'
    runtime=ROOT/'third_party/saturn-recomp-pal/runtime'
    if not (baseline/'CMakeLists.txt').is_file():raise SystemExit('Build the verified baseline first')
    out.mkdir(parents=True)
    shutil.copytree(baseline,out/'recomp')
    shutil.copytree(runtime,out/'runtime')
    patch_runtime(out/'runtime')
    instrument(out/'recomp')
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    provenance={'baseline_smpc_sha256':sha(runtime/'src/machine/smpc.cpp'),
                'baseline_generated_sha256':{p.name:sha(p) for p in baseline.glob('*.cpp')},
                'source_headers_sha256':{p.name:sha(p) for p in (ROOT/'src/pal_game').glob('pal_*input*.h')},
                'mode':'PAL_RESPONSIVE_INPUT=1 opt-in; unset/0 preserves original game input',
                'scope':'field direction only; no direct position writes; original collision and non-direction actions'}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    env=os.environ.copy();env['PATH']=str(ROOT/'build/venv/bin')+os.pathsep+env['PATH']
    cmd=['cmake','-S',str(out/'recomp'),'-B',str(out/'recomp-build'),'-G','Ninja',
         '-DSATURN_RUNTIME='+str(out/'runtime'),'-DSATURN_NO_SDL='+('OFF' if a.sdl_prefix else 'ON'),
         '-DSATURN_EXTRA='+str(ROOT/'src/pal_game/pal_game.cmake')]
    if a.sdl_prefix:cmd.append('-DCMAKE_PREFIX_PATH='+str(a.sdl_prefix.resolve()))
    subprocess.run(cmd,env=env,check=True)
    subprocess.run(['cmake','--build',str(out/'recomp-build'),'--target','saturn','-j',str(a.jobs)],env=env,check=True)
    print(out/'recomp-build/saturn')
if __name__=='__main__':main()
