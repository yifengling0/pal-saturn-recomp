#!/usr/bin/env python3
"""Replay repository host transforms in memory; never edit pins or runtime.
Run against the FINAL integration checkout (including its keyboard planner).
Full planner/build validation is still required; this audits host stages only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import pal_options as options
import pal_keyboard_profile as keyboard
import pal_paired_frame_queue as queue
import pal_prompt_confirm as prompt

def replay(host):
    source = (ROOT/'tools/pal_options.py').read_text()
    a = source.index('    host_text = ')
    z = source.index('    rt[host] = host_text', a)
    env = {'rt': {'host': host}, 'host': 'host', 'replace_once': options.replace_once}
    exec(textwrap.dedent(source[a:z]), env)
    precise = env['host_text']
    source = (ROOT/'tools/pal_paired_frame_queue.py').read_text()
    a = source.index(" edit('src/host/host.cpp',[")
    z = source.index(' cmake=recomp/', a)
    box = [precise]
    def edit(name, pairs, include=False):
        text = box[0]
        for before, after in pairs: text = queue.once(text, before, after, name)
        box[0] = ('#include "pal_paired_frame_queue.h"\n' if include else '') + text
    exec(textwrap.dedent(source[a:z]), {'edit': edit})
    paired = box[0]
    stages = {'raw': host, 'precise': precise, 'paired': paired,
              'mapping_final': keyboard.guard_master_input(prompt.host(keyboard.guard_host(keyboard.host(host)))),
              'accelerated_final': keyboard.guard_master_input(prompt.host(keyboard.guard_host(keyboard.host(paired))))}
    return {name: hashlib.sha256(text.encode()).hexdigest() for name,text in stages.items()}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    args=parser.parse_args()
    print(json.dumps(replay(args.host.read_text()), indent=2))
