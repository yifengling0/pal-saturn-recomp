"""Portable pure-planner tests. Synthetic functions never contain extracted code.

Only synthetic function pins/helper pins are scoped mocks. Unmocked production
replay and every real function's negative hash checks are separate integration
checks. No runtime, ROM, compiler, or filesystem access is needed by the planner.
"""
from pathlib import Path
import builtins
import importlib.util
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('field_planner', Path(__file__).parents[1] / 'pal_field_input.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def function(addr, body):
    return f'void f_{addr}(SH2Context& c) {{\n' + body + '}\n'


def fixture(mode):
    # Absolute on every platform: Path('/...') is absolute on POSIX but not on Windows, where it
    # carries no drive, and the planner's first check is is_absolute(). Never touched on disk.
    root = Path(Path.cwd().anchor) / 'synthetic generated 空格'
    field = '    pal_keyboard::field();\n'
    for addr,callee in p.SCRIPT_CALLS.items():
        field += ('    pal_input_script_before();\n' if mode == 'options' else '')
        field += f'    f_{callee}(c); // {addr} synthetic jsr\n'
        field += ('    pal_input_script_after();\n' if mode == 'options' else '')
    field += '    f_06022D5C(c); // 06026E54 synthetic converter\n'
    field += '    exts(); // 06026E58 exts.w r0,r1\n'
    if mode == 'options': field += '    pal_input_apply(c);\n'
    field += '    write_scheduler(); // 06026E6C synthetic scheduler\n'
    if mode == 'options': field += '    pal_input_align();\n'
    field += '    f_06033654(c); // 06026E70 original mover\n'
    field += '    c.r[8] = 0x0603440Cu; // 06026E74 original load\n'
    if mode == 'options': field += '    pal_input_wait_begin(c);\n    if (pal_pfq_enabled) pal_pfq_field_begin(c);\n'
    field += '    original_wait(); // 06026E76 original wait\n'
    if mode == 'options': field += '    pal_input_wait_end();\n'
    for addr,callee in p.UI_CALLS.items():
        if mode == 'options': field += '    pal_input_clear();\n'
        field += f'    f_{callee}(c); // {addr} synthetic guest UI\n'
        if mode == 'options': field += '    pal_input_clear();\n'
    field += '    SH2_POLL(c);\n'
    bodies = {addr: function(addr, '    original_step();\n') for addr in p.REQUIRED_FUNCTIONS}
    bodies['06026D84'] = function('06026D84', field)
    bodies['0606016E'] = function('0606016E', ('    pal_input_tick();\n' if mode == 'options' else '') + '    original_tick();\n')
    if mode == 'options': bodies['06026F90'] = function('06026F90', '    pal_input_clear();\n    original_step();\n')
    texts = {root / f'{"p_true" if addr == "06020058" else "p_prog"}_{i:03}.cpp':
             'namespace fixture {\n\n' + body + '\n}  // namespace fixture\n'
             for i,(addr,body) in enumerate(bodies.items())}
    return root, texts, bodies


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.helper = b'// Exact synthetic helper; no ROM content.\n'
        self.fixtures = {mode: fixture(mode) for mode in ('ordinary','options')}
        pins = {mode: {addr: p.sha(body) for addr,body in f[2].items()}
                for mode,f in self.fixtures.items()}
        for mocker in (patch.object(p, 'INPUT_FUNCTION_SHA256', pins),
                       patch.object(p, 'HELPER_SHA256', p.sha(self.helper))):
            mocker.start()
            self.addCleanup(mocker.stop)

    def plan(self, mode='ordinary', texts=None, helper=None, root=None):
        default_root, default_texts, _ = self.fixtures[mode]
        return p.plan_field_input(root or default_root,
               types.MappingProxyType(default_texts if texts is None else texts),
               self.helper if helper is None else helper)

    def test_two_coherent_variants_succeed(self):
        for mode in self.fixtures:
            changes = self.plan(mode)
            self.assertTrue(all(isinstance(x,bytes) for x in changes.values()))
            self.assertEqual(changes[self.fixtures[mode][0] / p.HELPER_FILE], self.helper)
            self.assertEqual(len(changes), 9 if mode == 'ordinary' else 10)

    def test_no_io_or_path_resolution(self):
        with patch.object(builtins,'open',side_effect=AssertionError('I/O')), \
             patch.object(Path,'read_bytes',side_effect=AssertionError('I/O')), \
             patch.object(Path,'read_text',side_effect=AssertionError('I/O')), \
             patch.object(Path,'write_bytes',side_effect=AssertionError('I/O')), \
             patch.object(Path,'write_text',side_effect=AssertionError('I/O')), \
             patch.object(Path,'resolve',side_effect=AssertionError('resolve')):
            self.plan('ordinary')
            self.plan('options')

    def test_input_mapping_is_not_mutated(self):
        for mode,(_,texts,_) in self.fixtures.items():
            old=dict(texts); self.plan(mode); self.assertEqual(texts,old)

    def test_every_target_missing_drift_or_duplicate_rejected(self):
        for mode,(_,texts,_) in self.fixtures.items():
            for addr in p.REQUIRED_FUNCTIONS:
                path,a,z,body=p._function(texts,addr)
                for changed in ('', body + '\n' + body, body.replace('{\n','{ \n',1)):
                    with self.subTest(mode=mode,address=addr,change=changed[:30]):
                        bad=dict(texts); bad[path]=bad[path][:a]+changed+bad[path][z:]
                        old=dict(bad)
                        with self.assertRaises(ValueError):self.plan(mode,bad)
                        self.assertEqual(bad,old)

    def test_coherent_function_pins_do_not_accept_hybrid(self):
        root,texts,_=self.fixtures['ordinary'];_,other,_=self.fixtures['options']
        path,a,z,_=p._function(texts,'06026D84');_,_,_,body=p._function(other,'06026D84')
        bad=dict(texts);bad[path]=bad[path][:a]+body+bad[path][z:]
        with self.assertRaisesRegex(ValueError,'mixed generation'):self.plan(texts=bad)

    def test_repeat_and_partial_injection_rejected(self):
        for mode,(_,texts,_) in self.fixtures.items():
            changes=self.plan(mode);updated=dict(texts)
            updated.update({path:data.decode() for path,data in changes.items() if path.suffix=='.cpp'})
            with self.assertRaisesRegex(ValueError,'already injected'):self.plan(mode,updated)
            path=next(iter(texts));partial=dict(texts);partial[path]+='// pal_field_input::partial\n'
            with self.assertRaisesRegex(ValueError,'already injected'):self.plan(mode,partial)

    def test_helper_drift_rejected(self):
        with self.assertRaisesRegex(ValueError,'helper source/version'):self.plan(helper=self.helper+b'// drift')

    def test_crlf_normalized_and_helper_bytes_preserved(self):
        for mode,(_,texts,_) in self.fixtures.items():
            expected=self.plan(mode);raw=self.helper.replace(b'\n',b'\r\n')
            actual=self.plan(mode,{path:text.replace('\n','\r\n') for path,text in texts.items()},raw)
            self.assertEqual({x:y for x,y in actual.items() if x.suffix=='.cpp'},
                             {x:y for x,y in expected.items() if x.suffix=='.cpp'})
            self.assertEqual(actual[self.fixtures[mode][0]/p.HELPER_FILE],raw)

    def test_instruction_positions(self):
        for mode in self.fixtures:
            outputs=self.plan(mode);path,*_=p._function(self.fixtures[mode][1],'06026D84');lines=outputs[path].decode().splitlines()
            expectations={'06026E54':(-1,'pal_field_input::begin();'),
                          '06026E58':(1,'pal_field_input::apply(c);'),
                          '06026E74':(1,'pal_field_input::outcome();')}
            for addr,(offset,code) in expectations.items():
                i=next(i for i,line in enumerate(lines) if '// '+addr+' ' in line)
                self.assertEqual(lines[i+offset].strip(),code)
            for addresses,name in ((p.SCRIPT_CALLS,'script'),(p.UI_CALLS,'ui')):
                for addr in addresses:
                    i=next(i for i,line in enumerate(lines) if '// '+addr+' ' in line)
                    self.assertEqual(lines[i-1].strip(),f'pal_field_input::{name}_before();')
                    self.assertEqual(lines[i+1].strip(),f'pal_field_input::{name}_after();')

    def test_approved_entry_clear_boundaries(self):
        for mode in self.fixtures:
            out=self.plan(mode)
            for addr in ('06026F90','06020040','06020058','06021F14','0604A0BC','060516B4'):
                path,*_=p._function(self.fixtures[mode][1],addr)
                self.assertIn(f'void f_{addr}(SH2Context& c) {{\n    pal_field_input::clear();\n',out[path].decode())

    def test_real_wait_entry_note_preserves_original_body(self):
        for mode in self.fixtures:
            out = self.plan(mode)
            path, _, _, _ = p._function(self.fixtures[mode][1], '0605D68A')
            self.assertIn('void f_0605D68A(SH2Context& c) {\n    pal_field_input::note_wait();\n', out[path].decode())
            self.assertEqual(p._without_field_changes(out[path].decode()), self.fixtures[mode][1][path])

    def test_only_three_legacy_writes_are_guarded(self):
        outputs=self.plan('options');text=''.join(raw.decode() for path,raw in outputs.items() if path.suffix=='.cpp')
        self.assertEqual(text.count('if (!pal_field_input::owns_input()) '),3)
        for call in p.LEGACY_CALLS:self.assertEqual(text.count('if (!pal_field_input::owns_input()) '+call),1)
        for call in ('pal_input_wait_begin(c);','pal_input_wait_end();','pal_input_script_before();',
                     'pal_input_script_after();','pal_pfq_field_begin(c);','pal_input_clear();'):
            before=sum(x.count(call) for x in self.fixtures['options'][1].values())
            self.assertEqual(text.count(call),before)

    def test_exact_inverse_preserves_every_original_byte(self):
        for mode,(_,texts,_) in self.fixtures.items():
            for path,raw in self.plan(mode).items():
                if path.suffix=='.cpp':self.assertEqual(p._without_field_changes(raw.decode()),texts[path])

    def test_unrelated_source_is_not_returned_or_modified(self):
        root,texts,_=self.fixtures['ordinary'];more=dict(texts);extra=root/'p_prog_999.cpp';more[extra]='// unrelated source\n'
        self.assertNotIn(extra,self.plan(texts=more));self.assertEqual(more[extra],'// unrelated source\n')

    def test_extra_legacy_ownership_call_rejected(self):
        root,texts,_=self.fixtures['options'];more=dict(texts);more[root/'p_prog_999.cpp']='void extra() { pal_input_tick(); }\n'
        with self.assertRaisesRegex(ValueError,'ownership inventory'):self.plan('options',more)

    def test_wrong_module_same_numeric_address_is_untouched(self):
        root,texts,bodies=self.fixtures['ordinary'];more=dict(texts);extra=root/'p_prog_999.cpp';more[extra]='namespace other {\n'+bodies['06020058']+'\n}  // namespace other\n'
        self.assertNotIn(extra,self.plan(texts=more))

    def test_relative_root_rejected(self):
        with self.assertRaisesRegex(ValueError,'absolute detached'):self.plan(root=Path('relative'))

    def test_parent_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError,'traversal'):self.plan(root=Path('/one/../two'))

    def test_outside_nested_or_wrong_file_path_rejected(self):
        root,texts,_=self.fixtures['ordinary'];first=next(iter(texts))
        for path in (root/'nested/p_prog_000.cpp',Path('/outside/p_prog_000.cpp'),root/'bad.cpp',root/'../p_prog_000.cpp'):
            more=dict(texts);more[path]=more.pop(first)
            with self.assertRaisesRegex(ValueError,'source paths'):self.plan(texts=more)

    def test_empty_inventory_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing generated'):self.plan(texts={})


if __name__ == '__main__':
    unittest.main()
