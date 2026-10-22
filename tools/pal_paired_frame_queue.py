"""Pure, fail-closed planning of the reviewed default-off paired RGB queue.

The parent installer owns all file reads, writes, race checks and its single
manifest. Inputs must already contain precise-input v4 hooks, including the
in-memory SDL host edge hooks. This module never reads or writes a file and
never modifies a caller mapping. See README.md for the transaction example.
"""
from pathlib import Path
import hashlib
import re

EXPECTED = {'version': 'paired-rgb-queue-prototype-v3-portable-release-gate-1', 'runtime_sha256': {'src/video/vdp1.cpp': 'fa02008639d95c8cf4495ba90105787601d7ea736dbcdc806aac945193be9257', 'src/video/video.cpp': 'c5b60810fd60d0dd84863b880b377fcb77be5950765538afbee8c681ff5236a3', 'src/video/video.h': 'ac712aceb90eba545dc64570ef35aa9f534e897da05326f638648d7dc94a1c92', 'src/video/vdp2.cpp': '52921c0ba3b3ba6c48d055252a8ad598bd0c7266966aff174274a453ec7c6169', 'src/machine/scu.cpp': '29b796d946d821fd111de4ba5ade0a410e50c7ac80cf0e3a80331f6a25985ee2', 'src/host/host.cpp': '72e5be22df26c094f438ae35e74746b1337a0f29c297bbe9bea2011c1c09f2d6'}, 'input_headers_sha256': {'pal_responsive_input.h': '53152f3895590c8308cd05b654b93eb4329b848deb3617412e865f0dd065e366', 'pal_input_intent.h': '5c0389dfd664c3a4f8bf3d7aeb76b37d4952017c95624073cf3872a798a36ba7', 'pal_input_wait.h': '2eb804283850210ae7eb41316bba9100572117ddfc5da9557cfc7608b9d45378'}, 'source_sha256': {'pal_paired_frame_queue.cpp': 'bcf4798b875a9a975aac9ca3be44049422235b04efa33313d6051eab51dd4226', 'pal_paired_frame_queue.h': '1ddce67acdcbca8f4dcb697166f704666333587c105e46f75a084bdd6c385a2c'}}
HOST_DISPLAY_PIN='5ad60b79602b47adaa8478eda042005cbc1e57b10a9e3a846f8f497f69026454'
RUNTIME_FILES = tuple(EXPECTED["runtime_sha256"])
HELPER_FILES = tuple(EXPECTED["source_sha256"])
# Exact post-input host variants; unrelated runtime drift remains rejected.
# One entry per accepted host.cpp generation: 0009 touch layout, 0011 Chinese menu UI, 0013 tap hold.
HOST_INPUT_SHA256 = {EXPECTED['runtime_sha256']['src/host/host.cpp'],
 'a50e312b94040e4110ac5c38ab92dbf121b96a793831c228bb4f3b2409d58843',
 'e64c92f63a209e67e00619a8f1ac31096b766521d4a17ca4bc97181d412700fe',
 '2a562eb0c593029c9363691fc3e500385cfbe031e2473ed70070c4968fea3cb1',
 'baa0ebd22bc2e364a5a398d59f0f6bddaf9de54bc79284b4f6647e55ec1ecb74',
 'bafa40a8fa223e74b3a5ea65ad1b69b077704c1f77b694a4bac50b38570c6658'}

# UI13 + 0014/0015 after the unchanged precise-input host transform.
HOST_INPUT_SHA256.add(HOST_DISPLAY_PIN)
HOST_INPUT_SHA256.add('811c1789dae3b183c059922cd3f977ef0d43dae3db727fb7d1ce990c39c57681')

# Frozen field-host r2 after the unchanged precise-input transform, full-chain replay.
HOST_INPUT_SHA256.add('7441a6f17a9b448fd8b383f6baf760eed517297b37bac6dc61daee09c9847771')
# 0018, independently replayed unchanged precise-host transform.
HOST_INPUT_SHA256.add('810165bb7e2cee839b3147708e7788f8587be49878fc9524da30c3612f61dec3')

# 0019 OHAudio identity fix after the unchanged precise-host transform.
HOST_INPUT_SHA256.add('eda0a7d87e08dc9ddd3c7b7c1cb8a9bcaa83501864ac38fd8494657315692f2e')
# Exact 0022 after unchanged precise-host transform.
HOST_INPUT_SHA256.add('8920466d7255926378f292e8736097b095538070aa83fb2fc00e2bfc95804f3e')
# 0023 after the same precise-input transform; audio only, guest cadence unchanged.
HOST_INPUT_SHA256.add('6c16924bf27a3b197f01818e4b61aead2b4929c9f880b2b6542425136e1ef14d')
# Exact 0027 after the unchanged precise-input transform.
HOST_INPUT_SHA256.add('259fca8a0ce494fd3099318079a0ff5de812b7f65e87b5f868c48f76ba773d5c')

# 0031 after the unchanged precise-input transform.
HOST_INPUT_SHA256.add('fb125442836fd99a36e3b220bc831fa252858a29434bf4a1c1ebb447dfe5dd9c')

# 0032 after unchanged precise-input transformation.
HOST_INPUT_SHA256.add('c221502f58d9ce2eea1282a8cad25e822edb72f1d64e388b9dd83c6857518cfa')

# 0024 preserves RGB composition while caching frame-local decode work.
VDP2_INPUT_SHA256 = {EXPECTED['runtime_sha256']['src/video/vdp2.cpp'],
 'eb23040fd2b53af5ca16f15cf776239c5cccf199e2503289c4849a702fadf08f'}

def sha(x):return hashlib.sha256(x).hexdigest()
def norm(s):return re.sub(r'#include "[^"\n]*[/\\]pal_host_edge.h"','#include "pal_host_edge.h"',s.replace('\r\n','\n'))
def once(s,a,b,label):
 if s.count(a)!=1:raise ValueError(f'{label}: expected exactly one anchor, got {s.count(a)}')
 return s.replace(a,b,1)
def scope(texts,fn,transform):
 marker=f'void f_{fn}(SH2Context& c) {{\n';hits=[p for p,s in texts.items()if marker in s]
 if len(hits)!=1 or texts[hits[0]].count(marker)!=1:raise ValueError('Function anchor '+fn)
 p=hits[0];s=texts[p];a=s.index(marker);m=re.search(r'\nvoid f_[0-9A-F]+\(SH2Context& c\) \{',s[a+len(marker):]);z=a+len(marker)+m.start()if m else len(s);texts[p]=s[:a]+transform(s[a:z])+s[z:];return p
def pc(s,addr,expected,call):
 lines=s.splitlines(True);hits=[i for i,l in enumerate(lines)if '// '+addr+' 'in l]
 if len(hits)!=1 or expected not in lines[hits[0]]:raise ValueError('Instruction anchor '+addr)
 lines.insert(hits[0],'    '+call+'\n');return ''.join(lines)

def plan_queue(recomp, runtime, texts, rt, cmake_text, helper_bytes):
 """Return Path -> bytes changes; raise ValueError before any external mutation.

 texts: all generated p_prog_*.cpp Path -> str after precise-input injection.
 rt: Path -> str, containing all RUNTIME_FILES; host.cpp already has input hooks.
 cmake_text: generated CMake after the caller's runtime-path guard injection.
 helper_bytes: basename -> bytes for 3 precise-input headers and 2 queue files.
 Existing extra entries in rt/helper_bytes are accepted and left untouched.
 Paths are the caller's absolute, validated detached paths; no resolve() here.
 """
 recomp,runtime=Path(recomp),Path(runtime)
 if not recomp.is_absolute() or not runtime.is_absolute():
  raise ValueError('Pass absolute detached paths already validated by caller')
 if recomp==runtime or recomp.is_relative_to(runtime) or runtime.is_relative_to(recomp):
  raise ValueError('Generated and runtime paths must be separate')
 expected=EXPECTED
 for group in ['source_sha256','input_headers_sha256']:
  for n,h in expected[group].items():
   b=helper_bytes.get(n)
   if not isinstance(b,bytes) or sha(b.replace(b'\r\n',b'\n'))!=h:
    raise ValueError('Helper source/version changed: '+n)
 texts={Path(p):s.replace('\r\n','\n') for p,s in texts.items()}
 if not texts or any(not p.is_relative_to(recomp) for p in texts):
  raise ValueError('Expected generated source paths within recomp')
 before_texts=dict(texts)
 selected_rt={}
 for name,h in expected['runtime_sha256'].items():
  p=runtime/name
  # Quote the observed digest: a new accepted host.cpp generation is a pin update,
  # and re-deriving it means re-running the whole injection to find out what it is.
  got=sha(norm(rt[p]).encode()) if p in rt else ''
  accepted = HOST_INPUT_SHA256 if name=='src/host/host.cpp' else VDP2_INPUT_SHA256 if name=='src/video/vdp2.cpp' else {h}
  if p not in rt or got not in accepted:
   raise ValueError('Runtime source/version changed: '+name+' observed '+got)
  selected_rt[p]=rt[p].replace('\r\n','\n')
 rt=selected_rt
 changed=set()
 if any('pal_pfq_'in s or 'ledger_'in s or 'preview_'in s for s in texts.values()):raise ValueError('Requires detached sources without previous queue/ledger injection')
 def field(s):
  if s.count('    pal_input_wait_begin(c);\n')!=1 or s.count('    pal_input_clear();\n')!=8:raise ValueError('Precise-v4 field lifecycle anchors changed')
  # The exact guest call must still follow the existing wait-begin hook.
  s=pc(s,'06026E76','if (x == 0x0603440Cu) f_0603440C(c);','if (pal_pfq_enabled) pal_pfq_field_begin(c);')
  return s.replace('    pal_input_clear();\n','    if (pal_pfq_enabled) pal_pfq_clear("guest_action_clear");\n    pal_input_clear();\n')
 changed.add(scope(texts,'06026D84',field))
 changed.add(scope(texts,'06026F90',lambda s:once(s,'    pal_input_clear();\n','    if (pal_pfq_enabled) pal_pfq_clear("guest_action_clear");\n    pal_input_clear();\n','field clear entry')))
 for fn in ['0605D670','0605D68A']:changed.add(scope(texts,fn,lambda s:pc(s,'0605D6A2','st16(c.r[1], c.r[0]);','if (pal_pfq_enabled) pal_pfq_master_seal();')))
 changed.add(scope(texts,'060649D0',lambda s:pc(s,'06064AD6','c.pc = x; return;','if (pal_pfq_enabled) pal_pfq_slave_done();')))
 for p in changed:texts[p]='#include "pal_paired_frame_queue.h"\n'+texts[p]
 def edit(name,pairs,include=False,append=''):
  p=runtime/name;s=rt[p]
  for a,b in pairs:s=once(s,a,b,name)
  rt[p]=('#include "pal_paired_frame_queue.h"\n'if include else'')+s+append
 edit('src/machine/scu.cpp',[(
  '    Dma& d = g_dma[lvl];','    Dma& d = g_dma[lvl];\n    if (pal_pfq_enabled) pal_pfq_dma_begin(lvl,d.r,d.w,d.c,d.ad,d.md);'),(
  '    scu_raise(lvl == 0 ? IRQ_DMA0 : lvl == 1 ? IRQ_DMA1 : IRQ_DMA2);','    if (pal_pfq_enabled) pal_pfq_dma_end(lvl);\n    scu_raise(lvl == 0 ? IRQ_DMA0 : lvl == 1 ? IRQ_DMA1 : IRQ_DMA2);')],True)
 edit('src/video/vdp1.cpp',[
  ('    int shown = g_draw_fb ^ 1;','    int shown = pal_pfq_host_bank >= 0 ? pal_pfq_host_bank : (g_draw_fb ^ 1);'),
  ('    bool fb8 = g_reg[TVMR] & 1;\n    if (x >=','    bool fb8 = (pal_pfq_host_bank >= 0 ? pal_pfq_host_tvmr : g_reg[TVMR]) & 1;\n    if (x >='),
  ('static void draw() {','static void draw() {\n    if (pal_pfq_enabled) pal_pfq_draw_begin(g_draw_fb,g_draws+1,g_reg);'),
  ('        scu_frame_event(6);','        scu_frame_event(6);\n        if (pal_pfq_enabled) pal_pfq_sprite_end();'),
  ('static void erase(int which) {','static void erase(int which) {\n    if (pal_pfq_enabled) pal_pfq_bank_invalidate(which,"erase");'),
  ('void vdp1_fb_write(uint32_t off, uint32_t v, int size) {','void vdp1_fb_write(uint32_t off, uint32_t v, int size) {\n    if (pal_pfq_enabled) pal_pfq_bank_invalidate(g_draw_fb,"cpu_fb_write");'),
  ('    if (s.loading) {','    if (s.loading) {\n        if (pal_pfq_enabled) pal_pfq_clear("state_load");')],True,
  '\nbool pal_pfq_compose_frame(Frame& out) { return pal_pfq_choose(out,g_draw_fb,g_reg,g_drawing); }\n')
 edit('src/video/video.cpp',[
  ('    if (vdp1_interp_field(compose) && compose) {','    const bool interpolated = vdp1_interp_field(compose);\n    if (compose && pal_pfq_enabled && pal_pfq_compose_frame(g_frame)) {\n        if (shot) write_png(g_cfg.out + "/shot-" + n + ".png", g_frame);\n        movie_frame(g_frame);\n        host_present(g_frame);\n    } else if (interpolated && compose) {'),
  ('    scu_raise(IRQ_VBLANK_IN);','    pal_pfq_host_bank = -1;\n    scu_raise(IRQ_VBLANK_IN);')],True)
 p=runtime/'src/video/vdp2.cpp';s=rt[p];a=s.index('static uint16_t reg(');z=s.index('void vdp2_state(');mid=s[a:z].replace('g_vdp2_regs','view_regs').replace('g_vdp2_vram','view_vram').replace('g_vdp2_cram','view_cram');s=s[:a]+mid+s[z:]
 decl='uint8_t g_vdp2_vram[0x80000], g_vdp2_cram[0x1000], g_vdp2_regs[0x200];';s=once(s,decl,decl+'\nstatic const uint8_t* view_regs = g_vdp2_regs;\nstatic const uint8_t* view_vram = g_vdp2_vram;\nstatic const uint8_t* view_cram = g_vdp2_cram;','VDP2 arrays')
 s+='\nvoid vdp2_compose_snapshot(Frame& out, const uint8_t* regs, const uint8_t* vram, const uint8_t* cram) {\n    struct Restore {\n        const uint8_t *r=view_regs, *v=view_vram, *c=view_cram;\n        ~Restore() { view_regs=r; view_vram=v; view_cram=c; }\n    } restore;\n    view_regs=regs; view_vram=vram; view_cram=cram;\n    vdp2_compose(out);\n}\n';rt[p]=s
 edit('src/video/video.h',[],append='\nvoid vdp2_compose_snapshot(Frame&, const uint8_t*, const uint8_t*, const uint8_t*);\n')
 edit('src/host/host.cpp',[
  ('    if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID == SDL_GetWindowID(g_win)) g_pal_edge.clear();','    if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID == SDL_GetWindowID(g_win)) { g_pal_edge.clear(); if (pal_pfq_enabled) pal_pfq_clear("focus_lost"); }'),
  ('static void menu_open() {\n    g_pal_edge.clear();','static void menu_open() {\n    g_pal_edge.clear();\n    if (pal_pfq_enabled) pal_pfq_clear("host_menu_open");')],True)
 cmake=recomp/'CMakeLists.txt';s=cmake_text.replace('\r\n','\n')
 if s.count('target_link_libraries(saturn ')!=1:raise ValueError('CMake saturn target changed')
 s+='\n# Default-off reviewed separately from precise input. Local paths work on Windows.\ntarget_sources(saturn PRIVATE "${CMAKE_CURRENT_LIST_DIR}/pal_paired_frame_queue.cpp")\n'
 changes={p:texts[p].encode()for p in changed};changes.update({p:v.encode()for p,v in rt.items()});changes[cmake]=s.encode()
 changes[recomp/'pal_paired_frame_queue.cpp']=helper_bytes['pal_paired_frame_queue.cpp'];changes[runtime/'include/pal_paired_frame_queue.h']=helper_bytes['pal_paired_frame_queue.h']

 for p in changed:
  if texts[p].count('SH2_POLL')!=before_texts[p].count('SH2_POLL'):
   raise ValueError('Guest poll count changed')
 return changes
