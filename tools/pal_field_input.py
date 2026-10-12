"""Pure last-stage field-input planner, after ordinary or combined PC98 mapping.

The caller owns reads, source/runtime validation, race checks, writes and the
single manifest. Pass every final p_prog_*.cpp and p_true_*.cpp source in memory.
This planner returns only changed generated files plus pal_field_input.h; it
never reads, writes, resolves paths, or mutates the caller's mapping. The host
installer separately provides pal_field_input_api.h in the runtime include path.
"""
from pathlib import Path
import hashlib
import re

VERSION = 'pal-field-input-planner-v1'
HELPER_FILE = 'pal_field_input.h'
HELPER_SHA256 = 'bec7e3713f164dcac5a64c0bc76884ed9d269f685fbb32d23ec8b6bdd37d43df'
REQUIRED_FUNCTIONS = ('06026D84', '06026F90', '06020040', '06020058',
                      '0606016E', '06021F14', '0604A0BC', '060516B4', '0605D68A')
# Exact complete functions after reviewed ordinary PC98 / all-options injection.
# Select ONE coherent generation across every function, never a mix of variants.
INPUT_FUNCTION_SHA256 = {'ordinary': {'06026D84': 'd54d6b12b7ad488a70e4935fcffffdc0152702fe35887cf284d15038132525de', '06026F90': 'ef61d21b3eb1fc567f59d9ce73ba868c1b1f2cfbcf0374b08841ded4faeb95e5', '06020040': '05f6bf085730d1dedce0eaa443966b6a45cc73cf9d7d88331c379e67ee25e364', '06020058': 'f45d9f62b9e00eedea63e3a97dda48712dcdab062b6829996559ae47d11fd2c2', '0606016E': 'b6c03e7ed948d6e983c69a65720143e76180247cfb425bfd8f693aa93a884199', '06021F14': '8055167ecc24fa94c06f6c14d5388373a2dd1b370eab884918f763cd7890c419', '0604A0BC': '99c2822813d61d8b3ad8bc17770b5c5c2109803d6c3fd4819b8886ad86b42bc7', '060516B4': 'b1b84367f2f2f96995a27ed048e5934460c456e94f12a49879b1ea03bf1bf372', '0605D68A': '6381c96e6c65eb0eb08e8f3c651c79b214cdff02878f5531d50d6206f52a1ad7'}, 'options': {'06026D84': '9df8c08c0f0b862a17c5b8e6245ccad434983bbdf4123ded1e6a708d35f49cbc', '06026F90': 'c275be954a0d2be12e23c2fb0e31364deb9dcdbe62bc1628342255f1c0ed7ae7', '06020040': '05f6bf085730d1dedce0eaa443966b6a45cc73cf9d7d88331c379e67ee25e364', '06020058': 'f45d9f62b9e00eedea63e3a97dda48712dcdab062b6829996559ae47d11fd2c2', '0606016E': '849cdec8a0d26ee8c88a6d32e6bf1ad8a319b6b283b4e7cb2535fb1af9968c30', '06021F14': '8055167ecc24fa94c06f6c14d5388373a2dd1b370eab884918f763cd7890c419', '0604A0BC': '99c2822813d61d8b3ad8bc17770b5c5c2109803d6c3fd4819b8886ad86b42bc7', '060516B4': 'b1b84367f2f2f96995a27ed048e5934460c456e94f12a49879b1ea03bf1bf372', '0605D68A': '14bf0ccfea912cf84252207c38b52a780c9a6f5eb09a87e2d3b9539ebc15cde5'}}
SCRIPT_CALLS = {'06026E1C': '06035410', '06026E84': '06023C64'}
UI_CALLS = {'06026E90': '0604C45C', '06026EB8': '060235B8',
            '06026F44': '0604C5AC', '06026F52': '0604C5AC'}
LEGACY_CALLS = ('pal_input_apply(c);', 'pal_input_tick();', 'pal_input_align();')


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def _function(texts, address):
    marker = f'void f_{address}(SH2Context& c) {{\n'
    prefix = 'p_true_' if address == '06020058' else 'p_prog_'
    found = [(p, text) for p, text in texts.items()
             if p.name.startswith(prefix) and marker in text]
    if len(found) != 1 or found[0][1].count(marker) != 1:
        raise ValueError('Missing or ambiguous field-input function: ' + address)
    path, text = found[0]
    start = text.index(marker)
    match = re.search(r'\nvoid f_[0-9A-F]+\(SH2Context& c\) \{',
                      text[start + len(marker):])
    end = (start + len(marker) + match.start() if match
           else text.rfind('\n}  // namespace'))
    if end <= start:
        raise ValueError('Generated function boundary changed: ' + address)
    return path, start, end, text[start:end]


def _once(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError('Field-input anchor changed: ' + label)
    return text.replace(before, after, 1)


def _instruction(text, address, expected, *, before='', after=''):
    lines = text.splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if '// ' + address + ' ' in line]
    if len(hits) != 1 or expected not in lines[hits[0]]:
        raise ValueError('Field-input instruction changed: ' + address)
    i = hits[0]
    lines[i] = (('    ' + before + '\n') if before else '') + lines[i] + (
        ('    ' + after + '\n') if after else '')
    return ''.join(lines)


def _without_field_changes(text):
    """Exact inverse for this planner's limited additions, for safety assertions."""
    guard = 'if (!pal_field_input::owns_input()) '
    for call in LEGACY_CALLS:
        text = text.replace(guard + call, call)
    return ''.join(line for line in text.splitlines(keepends=True)
                   if 'pal_field_input::' not in line and 'pal_release_runtime::' not in line and
                   line != '#include "pal_field_input.h"\n')


def plan_field_input(recomp, texts, helper_bytes, release_helpers=None):
    """Return Path -> bytes over an already staged PC98 generation, without I/O.

    recomp: absolute detached generated-source directory, validated by caller.
    texts: complete Path -> str inventory of p_prog_*.cpp and p_true_*.cpp.
    helper_bytes: exact reviewed guest helper bytes (CRLF is accepted/preserved).
    Outputs: changed cpp files and recomp/pal_field_input.h; no runtime outputs.
    Raw repeats, partial injection, hybrid generations and source drift fail closed.
    """
    recomp = Path(recomp)
    if not recomp.is_absolute() or '..' in recomp.parts:
        raise ValueError('Pass an absolute detached generated directory without traversal')
    if not isinstance(helper_bytes, bytes) or sha(helper_bytes.replace(b'\r\n', b'\n')) != HELPER_SHA256:
        raise ValueError('Field-input helper source/version changed')
    original = {}
    for key, text in texts.items():
        path = Path(key)
        if (not isinstance(text, str) or not path.is_absolute() or '..' in path.parts or
                path.parent != recomp or
                not re.fullmatch(r'p_(?:prog|true)_[A-Za-z0-9_]+\.cpp', path.name)):
            raise ValueError('Expected generated PROG/TRUE source paths inside recomp')
        if path in original:
            raise ValueError('Duplicate generated source path')
        if 'pal_field_input::' in text or 'pal_field_input.h' in text:
            raise ValueError('Field input already injected; use the manifest or regenerate')
        original[path] = text.replace('\r\n', '\n')
    if not original:
        raise ValueError('Missing generated source inventory')

    bodies = {address: _function(original, address) for address in REQUIRED_FUNCTIONS}
    variants = [name for name, pins in INPUT_FUNCTION_SHA256.items()
                if all(sha(bodies[address][3]) == pins[address]
                       for address in REQUIRED_FUNCTIONS)]
    if len(variants) != 1:
        raise ValueError('Field-input guest source/version changed or mixed generation')
    variant = variants[0]
    expected_count = 1 if variant == 'options' else 0
    if any(sum(text.count(call) for text in original.values()) != expected_count
           for call in LEGACY_CALLS):
        raise ValueError('Legacy input ownership inventory changed')
    staged = dict(original)

    def edit(address, transform):
        path, start, end, body = _function(staged, address)
        staged[path] = staged[path][:start] + transform(body) + staged[path][end:]

    def entry(address, call):
        marker = f'void f_{address}(SH2Context& c) {{\n'
        edit(address, lambda body: _once(body, marker, marker + '    ' + call + '\n', address))

    entry('06026D84', 'pal_field_input::enter();')
    entry('0605D68A', 'pal_field_input::note_wait();')
    entry('06026F90', 'pal_field_input::scene_clear();')
    for address in ('06020040', '06020058',
                    '06021F14', '0604A0BC', '060516B4'):
        entry(address, 'pal_field_input::clear();')

    def field(body):
        body = _instruction(body, '06026E54', 'f_06022D5C(c)',
                            before='pal_field_input::begin();')
        body = _instruction(body, '06026E58', 'exts.w r0,r1',
                            after='pal_field_input::apply(c);')
        body = _instruction(body, '06026E74', 'c.r[8] = 0x0603440Cu;',
                            after='pal_field_input::outcome();')
        for address, callee in SCRIPT_CALLS.items():
            body = _instruction(body, address, f'f_{callee}(c)',
                                before='pal_field_input::script_before();',
                                after='pal_field_input::script_after();')
        for address, callee in UI_CALLS.items():
            body = _instruction(body, address, f'f_{callee}(c)',
                                before='pal_field_input::ui_before();',
                                after='pal_field_input::ui_after();')
        if variant == 'options':
            for call in ('pal_input_apply(c);', 'pal_input_align();'):
                body = _once(body, '    ' + call + '\n',
                             '    if (!pal_field_input::owns_input()) ' + call + '\n', call)
        return body

    edit('06026D84', field)
    if variant == 'options':
        edit('0606016E', lambda body: _once(body, '    pal_input_tick();\n',
             '    if (!pal_field_input::owns_input()) pal_input_tick();\n', 'pal_input_tick'))

    outputs = {}
    if release_helpers is not None:
        from pal_scene_continuity import plan_scene_continuity
        staged, release_outputs = plan_scene_continuity(recomp, original, staged, release_helpers)
        outputs.update(release_outputs)
    elif b'pal_release_runtime.h' in helper_bytes:
        raise ValueError('Missing required scene continuity helpers')
    for path, text in staged.items():
        if text == original[path]:
            continue
        text = '#include "pal_field_input.h"\n' + text
        # Removing only our exact inserts/guards must reproduce every original
        # byte: guest instructions, mover/NPC calls, RNG, polls, waits, FFC13 and
        # all old script/sync/frame-queue bookkeeping are therefore unchanged.
        if _without_field_changes(text) != original[path]:
            raise ValueError('Field-input planner changed unrelated generated source')
        outputs[path] = text.encode()
    outputs[recomp / HELPER_FILE] = helper_bytes
    return outputs
