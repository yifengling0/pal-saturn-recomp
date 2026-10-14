"""Pure instruction-boundary additions for version-pinned PAL release provenance.

Called only from the validated field planner; never edits a runtime, disc or save.
The complete caller functions are checked by that planner; the additional original
functions below have their own exact complete-body pins. All original guest lines
remain byte-identical after removing the narrowly tagged additions.
"""
from pal_field_input import _function, _instruction, _once, sha
EXTRA_FUNCTION_SHA256 = {
 '06023C64':'f64bc140f53ef87994ba206abc4b3a66541c26ce11aa091228a767576145d9da',
 '06023914':'3edf4fbd56ce71a7c599fa83906c085a989aa985ced3180b489f806e1428d684',
 '0602B020':'a71508a045c56656a2accd2225b3482a1c4226e23c656c2551cd10769ef4ed41',
 '06022D5C':'f0afad533025a5fd8e71df52702050c83646e9727c3dd219ca057dccd5877785',
 '06022B8C':'01d64428b6d69caa1d6bd3cd07df230b84d20286f4d4e2e11143afe58f47a5de',
 '0603237C':'53baaf32c9b79b75bb926ca2da7ef994908d38018d943e57560ac5132723d9e3',
 '0602C288':'bfd9480ae844b72d213fe258d0b956bc872a29f26f774e3934b404c028f11d3e',
}
# Updated only after reviewing the exact portable policy and runtime wrapper.
HELPER_SHA256 = {'pal_release_gate.h': 'dd0064b8ed5b351c8fc35b6e3fbf6a11aae464eb77128d7a6ef5d96b1baf6c7f', 'pal_release_runtime.h': '8f8f8e192f33a96064fb481daad3bcf652d9256b75618834290834b6ee667a86'}

def plan_scene_continuity(recomp, original, staged, helpers):
    if set(helpers) != set(HELPER_SHA256) or not helpers:
        raise ValueError('Missing scene continuity helpers')
    for name,data in helpers.items():
        if not isinstance(data,bytes) or sha(data.replace(b'\r\n',b'\n')) != HELPER_SHA256[name]:
            raise ValueError('Scene continuity helper identity changed: '+name)
    for address,pin in EXTRA_FUNCTION_SHA256.items():
        if sha(_function(original,address)[3]) != pin:
            raise ValueError('Scene continuity original function identity changed: '+address)
    out=dict(staged)
    if any('pal_release_runtime::' in s for s in out.values()):
        raise ValueError('Scene continuity already injected; regenerate')
    def edit(address,transform):
        p,s,e,body=_function(out,address);out[p]=out[p][:s]+transform(body)+out[p][e:]
    def entry(address,code):
        marker=f'void f_{address}(SH2Context& c) {{\n'
        edit(address,lambda s:_once(s,marker,marker+'    '+code+'\n',address))
    entry('0603237C','pal_release_runtime::ResourceScope pal_release_resource(c.pr);')
    entry('06026F90','pal_release_runtime::SceneScope pal_release_scene(c.pr);')
    for function,pc,site in [('0603237C','060323B8','Resource'),('06026F90','06026FAC','Scene'),('0602C288','0602C384','Script')]:
        edit(function,lambda s,pc=pc,site=site:_instruction(s,pc,'st8(c.r[1], c.r[2]);',before=f'pal_release_runtime::writer_pre(c, 0x{pc}u);'))
    for function,pc in [('06022B8C','06022D1A'),('06022D5C','06022EEA')]:
        edit(function,lambda s,pc=pc:_instruction(s,pc,'st8(c.r[1], c.r[2]);',after='pal_release_runtime::neutral_post();'))
    edit('06022D5C',lambda s:_instruction(s,'06022FD8','if (c.t) { goto L_06022FDE; }',before='if (pal_release_runtime::permits(c)) goto L_06022FF2;'))
    edit('06026D84',lambda s:_instruction(s,'06026E54','f_06022D5C(c)',before='pal_release_runtime::capture_field_frame(c.r[14]);'))
    for pc,callee in [('0602704C','06024FD8'),('060270BA','060274FC')]:
        edit('06026F90',lambda s,pc=pc,callee=callee:_instruction(s,pc,f'f_{callee}(c)',
            before='{ pal_release_runtime::ScriptScope pal_release_scene_script;',
            after='} // pal_release_runtime::ScriptScope'))
    # Freeze eligible held sources before the original call's SH2_POLL. The
    # scope covers only opcode80's exact fade call, not all f23914 users.
    edit('0602B020',lambda s:_instruction(s,'0602B046','f_06023914(c)',
        before='{ pal_field_input::FadeScope pal_release_fade(0x0602B04Au); // pal_release_runtime::fade',
        after='} // pal_release_runtime::fade'))
    # The first field iteration reveals the just-loaded scene after moving.
    # A one-use completion ticket distinguishes this from unrelated script waits.
    edit('06026D84',lambda s:_instruction(s,'06026E84','f_06023C64(c)',
        before='{ pal_field_input::RevealScope pal_release_reveal(0x06026E88u); // pal_release_runtime::reveal',
        after='} // pal_release_runtime::reveal'))
    # Both original interval branches converge at E6E. Keep the interval/action
    # intact and reject only accumulated player displacement during scene debt.
    edit('06026D84',lambda s:_instruction(s,'06026E6E','c.r[8] = 0x06033654u;',
        before='pal_field_input::filter_scene_debt(c); // pal_release_runtime::movement_admission'))
    for p,text in out.items():
        inverse=''.join(line for line in text.splitlines(keepends=True) if 'pal_release_runtime::' not in line)
        if inverse != staged[p]:
            raise ValueError('Scene continuity modified original guest instructions')
    return out, {recomp/name:data for name,data in helpers.items()}
