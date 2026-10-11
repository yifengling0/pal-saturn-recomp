#!/usr/bin/env python3
"""Portable edge-menu acceptance; compiles actual supplied hosts, never opens a window."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--runtime',type=Path,required=True)
p.add_argument('--baseline-runtime',type=Path,required=True,help='Frozen UI12, used as expected-failing control')
p.add_argument('--sdl-prefix',type=Path,required=True)
p.add_argument('--build-dir',type=Path,required=True)
p.add_argument('--cxx',default='g++')
a=p.parse_args();here=Path(__file__).resolve().parent;out=a.build_dir.resolve();runtime=a.runtime.resolve();base=a.baseline_runtime.resolve();prefix=a.sdl_prefix.resolve()
for root in [runtime,base,here]:
 if out==root or root in out.parents:p.error('build-dir must not be within source trees')
out.mkdir(parents=True,exist_ok=True);manifest=out/'edge-manifest.json';manifest.write_text('{"status":"running"}\n');commands=[];results=[]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(command,name,red=False):
 commands.append({'name':name,'argv':list(map(str,command))});(out/'edge-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=subprocess.run(command,cwd=out,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
 (out/(name+'.log')).write_text(result.stdout);print(name+': '+result.stdout.strip().splitlines()[-1] if result.stdout.strip() else name,flush=True)
 results.append({'name':name,'returncode':result.returncode,'expected_failure':red})
 if (result.returncode!=0)!=red:raise RuntimeError(name+': unexpected result '+str(result.returncode))
def body(source,name):
 pos=source.index(name+'(');start=source.index('{',pos);depth=1;i=start+1
 while depth:
  if source[i]=='{':depth+=1
  if source[i]=='}':depth-=1
  i+=1
 return source[pos:i]
try:
 run([sys.executable,str(here/'run_pure.py'),'--runtime',str(runtime),'--build-dir',str(out/'pure'),'--cxx',a.cxx],'pure-policy')
 for name,root,ohos,red in [('host-ohos',runtime,True,False),('host-desktop',runtime,False,False),('red-ui12-host',base,True,True)]:
  binary=out/name;includes=[root/'include']+[root/'src'/d for d in ['host','machine','video','sound']]+[prefix/'include']
  command=[a.cxx,'-std=c++17','-O2','-pthread','-DHOST_SOURCE="host.cpp"','-ffunction-sections','-fdata-sections']
  if ohos:command+=['-DPAL_OHOS_DEFAULTS=1']
  command+=['-I'+str(x) for x in includes]+[str(here/'edge_host_tests.cpp'),str(root/'src/host/settings.cpp'),'-Wl,--gc-sections','-L'+str(prefix/'lib'),'-Wl,-rpath,'+str(prefix/'lib'),'-lSDL3','-o',str(binary)]
  run(command,'build-'+name);run([str(binary),str(out/'tmp'/name)],name,red)
 baseline=(base/'src/host/host.cpp').read_text();candidate=(runtime/'src/host/host.cpp').read_text()
 preserved={}
 for name in ['menu_open','menu_close','menu_loop','audio_pause_for_menu','audio_resume_after_menu','audio_reset_observation','read_pads','touch_edit_begin','touch_edit_finish','pal_host_ui_source_hash']:
  # Declarations precede some functions: locate the actual definition's opening brace.
  import re
  signature=re.compile(r'^[^\n;{}]*\b'+name+r'\([^;{}]*\)\s*\{',re.M)
  def extract(text):
   m=signature.search(text)
   if not m:raise RuntimeError('Missing function '+name)
   return body(text[m.start():],name)
  old,new=extract(baseline),extract(candidate)
  if old!=new:raise RuntimeError('Protected function changed: '+name)
  preserved[name]=hashlib.sha256(new.encode()).hexdigest()
 data={'status':'passed','scope':'candidate only; not release or device validation','results':results,'protected_function_sha256':preserved,'runtime_host_sha256':sha(runtime/'src/host/host.cpp'),'baseline_host_sha256':sha(base/'src/host/host.cpp'),'audit_sources':{x.name:sha(x) for x in sorted(here.iterdir()) if x.is_file()}}
except Exception as error:
 data={'status':'failed','error':str(error),'results':results}
 raise
finally:manifest.write_text(json.dumps(data,indent=2)+'\n')
