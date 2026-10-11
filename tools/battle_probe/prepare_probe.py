#!/usr/bin/env python3
"""Validate/copy an existing generated PAL build and add observation-only scopes.
No compiler, game process, download or RAM/script operation is launched here.
Default is validation only. --output must be a new directory under ROOT/build.
"""
from pathlib import Path
import argparse, hashlib, json, re, shutil

BASELINE_SHA='f5aa1c835d82700ab802ce589ac242534d589de679c8db9753a84ab1aedbf030'
ENTRIES={
 '060422B8':'battle', '06020094':'resource', '0602F590':'sprite_upload',
 '0603108C':'effect_prepare', '06024220':'effect_decode', '0603E818':'animation_ticks',
 '0602222C':'frame_present', '0605D68A':'frame_sync',
}
MARKERS={
 '0604270C':'enemy_ready', '06042712':'party_ready',
 '060428E0':'background_ready', '060428F8':'display_enabled',
}
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def fail(message): raise SystemExit(message)
def inventory(root):
 return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--root',type=Path,required=True)
 ap.add_argument('--source',type=Path)
 ap.add_argument('--output',type=Path,help='new isolated build directory; omit for validation only')
 a=ap.parse_args(); root=a.root.resolve(); source=(a.source or root/'build/linux-game-sdl/recomp').resolve()
 runtime=root/'third_party/saturn-recomp-pal/runtime'
 baseline=root/'build/linux-game-sdl/recomp-build/saturn'
 if not source.is_dir() or not runtime.is_dir(): fail('Source/runtime not present')
 if sha(baseline)!=BASELINE_SHA: fail('Baseline executable SHA mismatch; stop and review')
 if not source.is_relative_to(root/'build'): fail('Generated source must be under ROOT/build')
 source_hashes=inventory(source); runtime_hashes=inventory(runtime)
 texts={p:p.read_text() for p in sorted(source.glob('p_prog_*.cpp'))}
 if any('pal_battle_probe' in s for s in texts.values()):fail('Source already instrumented')
 # Validate all matches before performing any filesystem write.
 matches=[]
 for pc,name in ENTRIES.items():
  needle=f'void f_{pc}(SH2Context& c) {{\n'
  found=[(p,s.count(needle)) for p,s in texts.items() if needle in s]
  if sum(n for _,n in found)!=1:fail(f'{pc}: function entry expected exactly once, got {found}')
  matches.append({'pc':pc,'name':name,'kind':'entry_scope','file':found[0][0].name,'matches':1})
 for pc,name in MARKERS.items():
  found=[(p,sum(f'// {pc} ' in line for line in s.splitlines())) for p,s in texts.items()]
  found=[(p,n) for p,n in found if n]
  if sum(n for _,n in found)!=1:fail(f'{pc}: phase marker expected exactly once, got {found}')
  matches.append({'pc':pc,'name':name,'kind':'before_instruction','file':found[0][0].name,'matches':1})
 print(json.dumps({'status':'validated','entries':len(ENTRIES),'phase_markers':len(MARKERS),
                  'baseline_sha256':BASELINE_SHA,'matches':matches},indent=2))
 if a.output is None:return
 output=a.output.resolve()
 if not output.is_relative_to(root/'build'):fail('Output must be under ROOT/build')
 if output.exists():fail('Output exists; refusing overwrite')
 if output==source or output.is_relative_to(source) or source.is_relative_to(output):fail('Output/source overlap')
 if output.is_relative_to(runtime) or runtime.is_relative_to(output):fail('Output/runtime overlap')
 output.mkdir(parents=True,exist_ok=False)
 shutil.copytree(source,output/'recomp')
 shutil.copytree(runtime,output/'runtime')
 # Detached snapshots prevent simultaneous PAL input work affecting this diagnostic tree.
 if inventory(output/'recomp')!=source_hashes or inventory(source)!=source_hashes:fail('Generated source changed during snapshot; do not build')
 if inventory(output/'runtime')!=runtime_hashes or inventory(runtime)!=runtime_hashes:fail('Runtime changed during snapshot; do not build')
 helper=Path(__file__).with_name('pal_battle_probe.h')
 shutil.copy2(helper,output/'recomp/pal_battle_probe.h')
 for p,s in texts.items():
  changed=False
  for pc in ENTRIES:
   needle=f'void f_{pc}(SH2Context& c) {{\n'
   if needle in s:
    s=s.replace(needle,needle+f'    pal_battle_probe::Scope pal_battle_scope(c, 0x{pc}u);\n',1);changed=True
  lines=s.splitlines(keepends=True)
  for pc,phase in MARKERS.items():
   inds=[i for i,line in enumerate(lines) if f'// {pc} ' in line]
   if inds:
    lines.insert(inds[0],f'    pal_battle_probe::mark(c, 0x{pc}u, "{phase}");\n');changed=True
  if changed:(output/'recomp'/p.name).write_text('#include "pal_battle_probe.h"\n'+''.join(lines))
 cmake=output/'recomp/CMakeLists.txt';txt=cmake.read_text()
 # Use only detached runtime and reject arbitrary SATURN_EXTRA to avoid new input code.
 pattern=r'  set\(SATURN_RUNTIME "[^"\n]+"\)'
 if len(re.findall(pattern,txt))!=1:fail('CMake default runtime match changed')
 txt=re.sub(pattern,'  set(SATURN_RUNTIME "${CMAKE_CURRENT_LIST_DIR}/../runtime")',txt)
 extra_marker='if(DEFINED SATURN_EXTRA)'
 if txt.count(extra_marker)!=1:fail('CMake extra include guard changed')
 guard='if(DEFINED SATURN_EXTRA AND NOT "${SATURN_EXTRA}" STREQUAL "")\n  message(FATAL_ERROR "This observation build does not accept SATURN_EXTRA; do not mix PAL input changes")\nendif()\n'
 txt=txt.replace(extra_marker,guard+extra_marker,1)
 runtime_marker='include(${SATURN_RUNTIME}/runtime.cmake)'
 if txt.count(runtime_marker)!=1:fail('CMake runtime include changed')
 rtguard='get_filename_component(_pal_probe_rt "${SATURN_RUNTIME}" REALPATH)\nget_filename_component(_pal_probe_expected "${CMAKE_CURRENT_LIST_DIR}/../runtime" REALPATH)\nif(NOT _pal_probe_rt STREQUAL _pal_probe_expected)\n  message(FATAL_ERROR "Use the detached runtime snapshot for this observation build")\nendif()\n'
 txt=txt.replace(runtime_marker,rtguard+runtime_marker,1)
 cmake.write_text(txt)
 manifest={'baseline_executable_sha256':BASELINE_SHA,'source':str(source),'runtime':str(runtime),
           'source_sha256':source_hashes,'runtime_sha256':runtime_hashes,
           'probe_header_sha256':sha(helper),'generator_sha256':sha(Path(__file__)),
           'probe_points':matches,'output':str(output),'game_run':False,
           'note':'Source snapshots are hashed; binary/screenshot equivalence is not yet established.'}
 (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('Prepared detached observation sources at '+str(output))
if __name__=='__main__':main()
