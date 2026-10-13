"""Preserve five ROM-proven one-frame render rejections in generated PAL code.

This is a build-time lowering correction, not a game-state patch. All original
instructions, delay slots and polls run. Global SH2_RET remains strict. Only the
five audited call edges may unwind one host frame after their guest frame was
popped. No ROM, save, runtime source, or guest register is changed by the guard.
"""
from pathlib import Path
import hashlib
import re

VERSION = 'pal-render-one-frame-return-v1'
MODULE_SHA256 = {'PROG': '808acfdb56a885a3949a8f3910705e077edb974d9985327e887acfba20afad6d',
                 'TRUE': '41722e108b9091d6b7554a4350a0bf960a668da2879752708d6e5e820baa9d07'}
PINS = {
    '06038F14': 'd405763d1e1fa791f7ba46c6792f6e029a3bdbe553eb34d299411d24c7d1a12c',
    '06038F72': 'f8c7f8775fb6a29d85ffd44a3a94533132ae7f2a86a720bfc04789de09fd383d',
    '06038FD8': 'c84ef08e5ee7cdb29dce8b692003dc27eee2e09cb9c9e9f221b9d2648dffd337',
    '0605E398': '36a3680699a78e8c049efe0bddfed421752b547d16d2d333b3714a5cf961357b',
    '06060870': '6380091000848413485460b0dd2443e405aa01c9329276bbe1a1e05c50225ecb',
    '06065DC8': '789645639e556af6de295fc79d93141a02471eec4c862cac1f225002e6d1a865',
    '06065E26': '0395576ea27a0d72858c3add3b8fe7f805b512063e01eeca98c4ed330d6b9090',
    '06065E8C': '2c980b941f373819553b0f227025787dbacfaf959a4f8e170189c14935842532',
}
# Exact observation-only literal_probe.install() generation of the same modules.
# No text is stripped: an altered probe argument/statement still fails closed.
PROBE_PINS = {'06038F14': 'd405763d1e1fa791f7ba46c6792f6e029a3bdbe553eb34d299411d24c7d1a12c',
 '06038F72': 'f8c7f8775fb6a29d85ffd44a3a94533132ae7f2a86a720bfc04789de09fd383d',
 '06038FD8': 'c84ef08e5ee7cdb29dce8b692003dc27eee2e09cb9c9e9f221b9d2648dffd337',
 '0605E398': 'b960e54136c1eb9e55b64f6570632333c6c769dd1beee48b2f9517a7bc476825',
 '06060870': '6380091000848413485460b0dd2443e405aa01c9329276bbe1a1e05c50225ecb',
 '06065DC8': '789645639e556af6de295fc79d93141a02471eec4c862cac1f225002e6d1a865',
 '06065E26': '0395576ea27a0d72858c3add3b8fe7f805b512063e01eeca98c4ed330d6b9090',
 '06065E8C': '2c980b941f373819553b0f227025787dbacfaf959a4f8e170189c14935842532'}

# function, call instruction, ordinary continuation, callee, reject signature
EDGES = (
    ('06038F72', '06038F74', '06038F78', '06038F14', 'c.t && c.r[2] == 20 && c.r[4] == pal_return_r4 + 20u'),
    ('06038FD8', '06038FDA', '06038FDE', '06038F14', 'c.t && c.r[2] == 28 && c.r[4] == pal_return_r4 + 28u'),
    ('0605E398', '0605E39C', '0605E3A0', '06060870', 'x == 0x06060870u && c.r[0] == 0'),
    ('06065E26', '06065E28', '06065E2C', '06065DC8', 'c.t && c.r[2] == 20 && c.r[4] == pal_return_r4 + 20u'),
    ('06065E8C', '06065E8E', '06065E92', '06065DC8', 'c.t && c.r[2] == 28 && c.r[4] == pal_return_r4 + 28u'),
)


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def body(text, address):
    matches = list(re.finditer(r'void f_' + address + r'\(SH2Context& c\) \{\n.*?\n\}', text, re.S))
    if len(matches) != 1:
        raise ValueError(f'{address}: expected one complete generated function')
    return matches[0]


def lower_call(line, expected, signature):
    """Called only after complete caller/callee and exact module identity checks."""
    ret = f'SH2_RET(c, 0x{expected}u);'
    if line.count(ret) != 1:
        raise ValueError('Render return check anchor changed')
    guard = ('if (c.pc == pal_return_pr && c.pr == pal_return_pr && '
             'c.r[15] == pal_return_sp + 4u && ' + signature + ') return; ')
    code, comment = line.split('  // ', 1)
    capture = ('const uint32_t pal_return_sp = c.r[15]; '
               'const uint32_t pal_return_pr = ld32(pal_return_sp); '
               'const uint32_t pal_return_r4 = c.r[4]; ')
    # JSR has a local x already. Keep it in scope for the callee identity guard.
    if code.strip().startswith('{'):
        code = code.replace('{ ', '{ ' + capture, 1)
    else:
        code = '    { ' + capture + code.strip() + ' }'
    return code.replace(ret, guard + ret) + '  // ' + comment


def plan(texts):
    """Validate all eight original functions before staging any of the five edits."""
    located = {}
    for address, pin in PINS.items():
        matches = [(p, body(text, address)) for p, text in texts.items()
                   if f'void f_{address}(' in text]
        if len(matches) != 1:
            raise ValueError(f'{address}: expected one generated function across files')
        p, m = matches[0]
        normalized = re.sub(r'ran\[\d+\]', 'ran[INDEX]', m.group())
        if sha(normalized) not in (pin, PROBE_PINS[address]):
            raise ValueError(f'{address}: original function identity changed; regenerate/review')
        located[address] = p
    staged = dict(texts)
    for address, pc, expected, callee, signature in EDGES:
        p = located[address]
        m = body(staged[p], address)
        lines = m.group().splitlines(keepends=True)
        indices = [i for i, line in enumerate(lines) if f'// {pc} ' in line]
        if len(indices) != 1 or f'f_{callee}(c)' not in lines[indices[0]]:
            raise ValueError(f'{pc}: original call edge changed')
        i = indices[0]
        lines[i] = lower_call(lines[i], expected, signature)
        staged[p] = staged[p][:m.start()] + ''.join(lines) + staged[p][m.end():]
    return staged


def prepare(recomp, modules):
    """Run once immediately after fresh generation, before optional transforms."""
    for name, pin in MODULE_SHA256.items():
        matches = [m for m in modules if m.name == name]
        if len(matches) != 1 or matches[0].base != 0x06020000:
            raise ValueError(f'Render return fix requires verified {name} module/base')
        if sha(Path(matches[0].file).read_bytes()) != pin:
            raise ValueError(f'Render return fix: {name}.BIN identity changed')
    files = sorted(Path(recomp).glob('p_prog_*.cpp')) + sorted(Path(recomp).glob('p_true_*.cpp'))
    texts = {p: p.read_text(encoding='utf-8') for p in files}
    staged = plan(texts)
    for p, text in staged.items():
        if text != texts[p]:
            p.write_text(text, encoding='utf-8')
