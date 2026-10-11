"""Instrument selected generated PROG entries without changing guest state."""
from pathlib import Path

def add_headers(out, root):
    addresses = ('06020094', '0602FA8C', '0602FB48')
    found = set()
    for path in Path(out).glob('p_prog_*.cpp'):
        text = path.read_text()
        changed = False
        for address in addresses:
            marker = f'void f_{address}(SH2Context& c) {{\n'
            if marker in text:
                assert address not in found
                found.add(address)
                text = text.replace(marker, marker + f'    pal_resource_probe(c, 0x{address}u);\n')
                changed = True
        if path.name == 'p_prog_004.cpp':
            marker='void f_060344A0(SH2Context& c) {\n'
            assert marker in text
            text=text.replace(marker,marker+'    pal_map_draw(c);\n')
            changed=True
        if path.name == 'p_prog_003.cpp':
            for pc in ('0602F290', '0602F2BC'):
                lines = text.splitlines(keepends=True)
                candidates = [i for i, line in enumerate(lines) if '// ' + pc + ' ' in line]
                assert len(candidates) == 1
                lines.insert(candidates[0], f'    pal_map_snapshot(c, 0x{pc}u);\n')
                text = ''.join(lines)
        if path.name == 'p_prog_000.cpp':
            marker = '    c.r[14] += 24;  // 06020116 add #24,r14'
            assert marker in text
            text = text.replace(marker, '    pal_resource_result(c);\n' + marker)
        if changed:
            text = '#include "' + str(Path(root) / 'src/pal_game/pal_resource_probe.h') + '"\n' + text
            path.write_text(text)
    if found != set(addresses):
        raise RuntimeError('Missing resource probe entries: ' + str(set(addresses)-found))
