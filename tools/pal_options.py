"""Inject guarded PAL input, spell preparation, cadence and paired RGB options.

The caller generates the PAL modules, copies its verified five-patch runtime to
an isolated build directory, then calls prepare_options(recomp, runtime, root).
No compiler, game process, source-runtime modification or external tool is run.
Defaults retain original behavior: input/preparation/queue off, effect cadence 1.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

VERSION = 'pal-options-input-v4-release-gate-v1-effect-v3-cadence-v4-manual-pair-queue-v3-keyboard-v1-9-field-consume'
MANIFEST = 'pal-options-manifest.json'
CADENCE_RUNTIME_SUPPORT = '// PAL effect cadence uses ordinary C++/TLS scopes, unsupported on fibers whose\n// stacks can be discarded without C++ unwinding. This is read-only and is never\n// called in the default speed=1 path.\nbool pal_effect_cadence_scope_supported() noexcept {\n    return !g_cfg.task_setjmp && !g_sh2_tasks[0] && g_cfg.state_in.empty();\n}\n'

HEADERS = ('pal_responsive_input.h', 'pal_input_intent.h', 'pal_input_wait.h',
           'pal_effect_wait.h', 'pal_effect_wait_runtime.h',
           'pal_effect_cadence.h', 'pal_effect_cadence_runtime.h')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError(f'{label}: expected one source anchor; got {text.count(before)}')
    return text.replace(before, after, 1)


def instruction(text, pc, before='', after='', expected=''):
    lines = text.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if f'// {pc} ' in line]
    if len(matches) != 1 or (expected and expected not in lines[matches[0]]):
        raise ValueError(f'{pc}: instruction anchor changed (matches={len(matches)})')
    i = matches[0]
    lines[i] = ('    ' + before + '\n' if before else '') + lines[i] + ('    ' + after + '\n' if after else '')
    return ''.join(lines)


def function(texts, pc, transform):
    marker = f'void f_{pc}(SH2Context& c) {{\n'
    found = [(p, text.count(marker)) for p, text in texts.items() if marker in text]
    if sum(n for _, n in found) != 1:
        raise ValueError(f'f_{pc}: expected one function entry; got {found}')
    p = found[0][0]
    text = texts[p]
    start = text.index(marker)
    # Generated entry functions are top-level; duplicated decoded instruction
    # labels in other entry functions must not be instrumented accidentally.
    match = re.search(r'\nvoid f_[0-9A-F]+\(SH2Context& c\) \{', text[start + len(marker):])
    end = start + len(marker) + match.start() if match else len(text)
    texts[p] = text[:start] + transform(text[start:end]) + text[end:]
    return p


def prepare_options(recomp: Path, runtime: Path, root: Path, *, verify_only: bool = False):
    root, recomp, runtime = (Path(p).resolve() for p in (root, recomp, runtime))
    build = root / 'build'
    if not all(p.is_relative_to(build) for p in (recomp, runtime)):
        raise ValueError('Only detached generated/runtime directories under ROOT/build may be changed')
    if recomp == runtime or recomp.is_relative_to(runtime) or runtime.is_relative_to(recomp):
        raise ValueError('Generated and runtime directories must not overlap')
    if not (recomp / 'CMakeLists.txt').is_file() or not (runtime / 'runtime.cmake').is_file():
        raise ValueError('Generate sources and copy the verified runtime first')
    # Nothing from the rejected presentation preview or observation-only battle
    # snapshot is part of the combined option path.
    files = sorted(recomp.glob('p_prog_*.cpp'))
    if not files:
        raise ValueError('No generated PROG sources')
    source_headers = {name: (root / 'src/pal_game' / name).read_bytes() for name in (*HEADERS, 'pal_host_edge.h', 'pal_paired_frame_queue.cpp', 'pal_paired_frame_queue.h', 'pal_keyboard_profile.h')}
    field_enabled = b'pal_field_input_ledger.h' in (runtime/'src/host/host.cpp').read_bytes()
    if field_enabled:
        source_headers['pal_field_input.h'] = (root/'src/pal_game/pal_field_input.h').read_bytes()
    header_hashes = {name: digest(data) for name, data in source_headers.items()}
    from pal_keyboard_profile import runtime_support_inputs, verify_runtime_support_manifest
    support_inputs = runtime_support_inputs(runtime)
    manifest = recomp / MANIFEST
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding='utf-8'))
        verify_runtime_support_manifest(previous, runtime, support_inputs)
        if previous.get('version') != VERSION or previous.get('headers_sha256') != header_hashes:
            raise ValueError('Option/header version changed; regenerate a fresh detached build')
        if previous.get('runtime') != os.path.relpath(runtime, recomp).replace('\\', '/'):
            raise ValueError('Detached runtime changed; regenerate a fresh detached build')
        if field_enabled and 'pal_field_input.h' not in previous.get('outputs_sha256', {}).get('recomp', {}):
            raise ValueError('Incomplete field input output manifest')
        for group, base in [('recomp', recomp), ('runtime', runtime)]:
            verified = {**previous.get('inputs_sha256', {}).get(group, {}),
                        **previous['outputs_sha256'][group]}
            for name, expected in verified.items():
                p = base / name
                if ('..' in Path(name).parts or Path(name).is_absolute() or p.resolve() != p or
                        not p.is_relative_to(base) or not p.is_file() or digest(p.read_bytes()) != expected):
                    raise ValueError(f'Previously injected {group}/{name} changed; regenerate a fresh build')
        return previous  # Strictly no writes on an identical second application.

    if verify_only:
        # ohosbuild calls this before packaging: a matching manifest above already returned, so
        # reaching here means the generation is missing or stale and must be regenerated, not injected.
        raise ValueError('Existing option generation is not current; regenerate it before packaging')

    originals = {p: p.read_bytes() for p in files}
    texts = {p: data.decode('utf-8').replace('\r\n', '\n') for p, data in originals.items()}
    for text in texts.values():
        if any(marker in text for marker in ('pal_input_', 'pal_effect_wait::', 'pal_battle_probe', 'completed_frame_preview')):
            raise ValueError('Source is already instrumented without a matching option manifest')
    changed_input = set()
    def field(text):
        points = [
            ('06026E1C', 'pal_input_script_before();', 'pal_input_script_after();', 'f_06035410(c)'),
            ('06026E58', '', 'pal_input_apply(c);', 'exts.w r0,r1'),
            ('06026E6C', '', 'pal_input_align();', 'mov.b r2,@r1'),
            ('06026E76', 'pal_input_wait_begin(c);', 'pal_input_wait_end();', 'f_0603440C(c)'),
            ('06026E84', 'pal_input_script_before();', 'pal_input_script_after();', 'f_06023C64(c)'),
            ('06026E90', 'pal_input_clear();', 'pal_input_clear();', 'f_0604C45C(c)'),
            ('06026EB8', 'pal_input_clear();', 'pal_input_clear();', 'f_060235B8(c)'),
            ('06026F44', 'pal_input_clear();', 'pal_input_clear();', 'f_0604C5AC(c)'),
            ('06026F52', 'pal_input_clear();', 'pal_input_clear();', 'f_0604C5AC(c)'),
        ]
        for pc, before, after, expected in points:
            text = instruction(text, pc, before, after, expected)
        return text
    changed_input.add(function(texts, '06026D84', field))
    for pc, code in [('06026F90', 'pal_input_clear();'), ('0606016E', 'pal_input_tick();')]:
        marker = f'void f_{pc}(SH2Context& c) {{\n'
        changed_input.add(function(texts, pc, lambda text, marker=marker, code=code: replace_once(text, marker, marker + '    ' + code + '\n', pc)))
    def sync(text):
        text = instruction(text, '0605D6B0', before='pal_input_sync_enter(c);', expected='ld32(c.gbr + 972)')
        return instruction(text, '0605D6BC', before='pal_input_sync_leave();', expected='0x0602008Cu')
    changed_input.add(function(texts, '0605D68A', sync))
    changed_effect = set()
    changed_effect.add(function(texts, '06022458', lambda text: instruction(text, '060224E0',
        before='{ pal_effect_wait::Scope pal_effect_scope(c);', after='}', expected='f_06021FD8(c)')))
    changed_effect.add(function(texts, '06021FD8', lambda text: instruction(text, '0602202C',
        before='if (!c.t && pal_effect_wait::ready(c)) c.t=true;', expected='if (!c.t)')))
    for p in changed_input:
        texts[p] = '#include "pal_responsive_input.h"\n' + texts[p]
    for p in changed_effect:
        texts[p] = '#include "pal_effect_wait_runtime.h"\n' + texts[p]

    changed_cadence = set()
    for pc, kind in [('0603BDE8', 'Cast'), ('0603108C', 'Prepare'),
                     ('060223C0', 'Frame'), ('0605D68A', 'Sync')]:
        marker = f'void f_{pc}(SH2Context& c) {{\n'
        changed_cadence.add(function(texts, pc, lambda text, marker=marker, kind=kind:
            replace_once(text, marker, marker + f'    pal_effect_cadence::{kind} pal_cadence_scope(c);\n', kind)))
    changed_cadence.add(function(texts, '060223C0', lambda text: instruction(text, '06022426',
        before='{ pal_effect_cadence::Wait pal_cadence_wait(c);', after='}', expected='f_0603E818(c)')))
    def cadence_sync(text):
        return instruction(text, '0605D6B0', before='pal_effect_cadence::prepare_sync(c);', expected='c.r[0] = ld32(c.gbr + 972)')
    changed_cadence.add(function(texts, '0605D68A', cadence_sync))
    for p in changed_cadence:
        texts[p] = '#include "pal_effect_cadence_runtime.h"\n' + texts[p]

    host = runtime / 'src/host/host.cpp'
    null = runtime / 'src/host/host_null.cpp'
    smpc = runtime / 'src/machine/smpc.cpp'
    runtime_original = {p: p.read_bytes() for p in (host, null, smpc)}
    rt = {p: data.decode('utf-8').replace('\r\n', '\n') for p, data in runtime_original.items()}
    runtime_original.update(support_inputs)
    if any('pal_host_direction_edge' in text or 'g_pal_edge' in text for text in rt.values()):
        raise ValueError('Runtime is already instrumented without a matching option manifest')
    rt[smpc] += ('\n// PAL opt-in input observation API; INTBACK stays unchanged.\n'
        'uint16_t pal_host_direction_edge();\n'
        'uint16_t pal_input_peek() { return static_cast<uint16_t>(~pad_now(0)) & 0xFFF8; }\n'
        'uint16_t pal_input_edges() { uint16_t edge=pal_host_direction_edge(); return host_drives() ? edge : 0; }\n')
    rt[null] += '\nuint16_t pal_host_direction_edge() { return 0; }\n'
    host_text = '#include "pal_host_edge.h"\n' + rt[host]
    menu_states = [anchor for anchor in ('static bool g_menu_open, g_quitting;',
                                         'static bool g_menu_open, g_quitting, g_confirm_quit;',
                                         'static bool g_menu_open, g_quitting, g_confirm_quit, g_confirm_layout;')
                   if host_text.count(anchor) == 1]
    if len(menu_states) != 1:
        raise ValueError('SDL host: menu state declaration changed')
    menu_state = menu_states[0]
    replacements = [
        (menu_state,
         menu_state + '\nstatic PalHostEdge g_pal_edge;\n'
         'uint16_t pal_host_direction_edge() { return g_pal_edge.take(); }\n'
         'static void pal_host_clear_edge() { g_pal_edge.clear(); }'),
        ('static uint16_t touch_read();', 'static uint16_t touch_read();\nstatic void pal_host_clear_edge();'),
        ('    for (int s = 0; s < kHostSlots; ++s) {',
         '    for (int s = 0; s < kHostSlots; ++s) {\n'
         '        if(s==0 && (((b[s]&0xC000)==0xC000) || ((b[s]&0x3000)==0x3000))) pal_host_clear_edge();'),
        ('static void menu_open() {', 'static void menu_open() {\n    g_pal_edge.clear();'),
        ('static void menu_close() {', 'static void menu_close() {\n    g_pal_edge.clear();'),
        ('static void on_event(const SDL_Event& e) {',
         'static void on_event(const SDL_Event& e) {\n'
         '    if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && e.window.windowID == SDL_GetWindowID(g_win)) g_pal_edge.clear();\n'
         '    if (e.type == SDL_EVENT_KEY_DOWN && e.key.windowID == SDL_GetWindowID(g_win)) {\n'
         '        uint16_t direction=0;\n'
         '        for (auto& [key,bit] : g_keys) if (key==e.key.scancode) direction |= bit & 0xF000;\n'
         '        g_pal_edge.down(direction,e.key.repeat,SDL_GetKeyboardFocus()==g_win,g_menu_open || (direction & g_held_over[0]));\n'
         '    }'),
    ]
    for before, after in replacements:
        host_text = replace_once(host_text, before, after, 'SDL host')
    rt[host] = host_text

    cmake = recomp / 'CMakeLists.txt'
    cmake_original = cmake.read_bytes()
    cmake_text = cmake_original.decode('utf-8').replace('\r\n', '\n')
    relative_runtime = os.path.relpath(runtime, recomp).replace('\\', '/')
    if any(c in relative_runtime for c in '\n\r";$'):
        raise ValueError('Detached runtime path contains unsupported CMake characters')
    pattern = r'  set\(SATURN_RUNTIME "[^"\n]+"\)'
    if len(re.findall(pattern, cmake_text)) != 1:
        raise ValueError('Generated CMake runtime anchor changed')
    cmake_text = re.sub(pattern, '  set(SATURN_RUNTIME "${CMAKE_CURRENT_LIST_DIR}/' + relative_runtime + '")', cmake_text)
    # A copied CMake tree must not silently select the clean/unpatched runtime.
    anchor = 'include(${SATURN_RUNTIME}/runtime.cmake)'
    guard = ('get_filename_component(_pal_option_rt "${SATURN_RUNTIME}" REALPATH)\n'
        'get_filename_component(_pal_option_expected "${CMAKE_CURRENT_LIST_DIR}/' + relative_runtime + '" REALPATH)\n'
        'if(NOT _pal_option_rt STREQUAL _pal_option_expected)\n'
        '  message(FATAL_ERROR "Use the detached runtime for this PAL option build")\n'
        'endif()\n')
    cmake_text = replace_once(cmake_text, anchor, guard + anchor, 'CMake runtime include')
    machine = runtime / 'src/machine/machine.cpp'
    runtime_original[machine] = machine.read_bytes()
    rt[machine] = runtime_original[machine].decode('utf-8').replace('\r\n', '\n')
    if 'pal_effect_cadence_scope_supported' in rt[machine]:
        raise ValueError('Unexpected existing cadence task guard')
    if rt[machine].count('bool tasks = cfg.task_setjmp || g_sh2_tasks[0];') != 1 or rt[machine].count('if (!cfg.state_in.empty()) {') != 1:
        raise ValueError('Cadence task-mode scope anchor changed')
    rt[machine] += '\n' + CADENCE_RUNTIME_SUPPORT
    from pal_paired_frame_queue import plan_queue, RUNTIME_FILES
    for name in RUNTIME_FILES:
        p = runtime / name
        if p not in runtime_original:
            runtime_original[p] = p.read_bytes()
            rt[p] = runtime_original[p].decode('utf-8').replace('\r\n', '\n')
    queue_changes = plan_queue(recomp, runtime, texts, rt, cmake_text, source_headers)
    changes = {p: text.encode('utf-8') for p, text in texts.items() if text.encode('utf-8') != originals[p]}
    changes.update({p: text.encode('utf-8') for p, text in rt.items()})
    changes[cmake] = cmake_text.encode('utf-8')
    for name in HEADERS:
        changes[recomp / name] = source_headers[name]
    changes[runtime / 'src/host/pal_host_edge.h'] = source_headers['pal_host_edge.h']
    for p in [*(recomp / name for name in HEADERS), runtime / 'src/host/pal_host_edge.h']:
        if p.exists():
            raise ValueError(f'Unexpected preexisting option header: {p}')
    for p in (recomp / 'pal_paired_frame_queue.cpp', runtime / 'include/pal_paired_frame_queue.h'):
        if p.exists():
            raise ValueError(f'Unexpected preexisting queue source: {p}')
    changes.update(queue_changes)
    # Keyboard semantics apply to ordinary and enhanced builds. Plan this last,
    # over staged options, so one manifest owns the final bytes atomically.
    from pal_keyboard_profile import plan_keyboard
    keyboard_texts = dict(texts)
    keyboard_texts.update({p: content.decode('utf-8') for p, content in changes.items() if p in keyboard_texts})
    for p in sorted(recomp.glob('p_true_*.cpp')):
        originals[p] = p.read_bytes()
        keyboard_texts[p] = originals[p].decode('utf-8').replace('\r\n', '\n')
    for name in ('settings.cpp', 'launcher.cpp', 'settings.h'):
        p = runtime / 'src/host' / name
        runtime_original[p] = p.read_bytes()
        rt[p] = runtime_original[p].decode('utf-8').replace('\r\n', '\n')
    rt.update({p: content.decode('utf-8') for p, content in changes.items() if p in rt})
    keyboard_header = runtime / 'include/saturn/pal_keyboard_profile.h'
    if keyboard_header.exists():
        raise ValueError('Unexpected preexisting keyboard helper; regenerate')
    changes.update(plan_keyboard(recomp, runtime, keyboard_texts, rt,
                                 source_headers['pal_keyboard_profile.h']))
    if field_enabled:
        field_output = recomp / 'pal_field_input.h'
        if field_output.exists() or field_output.is_symlink():
            raise ValueError('Unexpected preexisting field helper; regenerate')
        from pal_field_input import plan_field_input
        field_texts = {p: changes.get(p, originals[p]).decode('utf-8').replace('\r\n','\n') for p in keyboard_texts}
        changes.update(plan_field_input(recomp, field_texts, source_headers['pal_field_input.h']))
        if (root/'src/pal_game/pal_field_input.h').read_bytes() != source_headers['pal_field_input.h']:
            raise ValueError('Field helper changed while preparing injection')
    all_original = {**originals, **runtime_original, cmake: cmake_original}
    for p, data in all_original.items():
        if p.resolve() != p or p.read_bytes() != data:
            raise ValueError(f'Source changed while preparing injection: {p}')
    data = {'version': VERSION, 'runtime': relative_runtime, 'headers_sha256': header_hashes,
        'defaults': {'PAL_RESPONSIVE_INPUT': '0', 'PAL_RESPONSIVE_ALIGN': '0',
                     'PAL_RESPONSIVE_WAKE': '0', 'PAL_SHORT_EFFECT_PREP': '1',
                     'PAL_EFFECT_ANIMATION_SPEED': '1.5', 'PAL_PAIRED_FRAME_QUEUE': '0'},
        'input_scope': 'precise v4 + guest release gate fix v1; timing experiments remain separately gated',
        'effect_scope': 'v3 bank7 commit-gated early exit; changes RNG/idle trajectory',
        'cadence_scope': 'bank7 tested effects 33/20,10/26,43/14,1/7; retain frames/ticks, optional 1/1.25/1.5/2',
        'inputs_sha256': {}, 'outputs_sha256': {}}
    for group, base in [('recomp', recomp), ('runtime', runtime)]:
        data['inputs_sha256'][group] = {p.relative_to(base).as_posix(): digest(v) for p, v in all_original.items() if p.is_relative_to(base)}
        data['outputs_sha256'][group] = {p.relative_to(base).as_posix(): digest(v) for p, v in changes.items() if p.is_relative_to(base)}
    # Every source and structural check above succeeds before the first write.
    # An I/O failure leaves no success manifest; the caller must use a fresh tree.
    for p, content in changes.items():
        p.write_bytes(content)
    manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--recomp', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    a = p.parse_args()
    result = prepare_options(a.recomp, a.runtime, a.root)
    print(result['version'] + ': injected/verified; spell timing is accelerated by default, '
          'PAL_SHORT_EFFECT_PREP=0 PAL_EFFECT_ANIMATION_SPEED=1 restores the original')


if __name__ == '__main__':
    main()
