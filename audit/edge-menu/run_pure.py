#!/usr/bin/env python3
"""Build pure policy and three deliberately broken copies; retain all red logs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--runtime', type=Path, required=True)
p.add_argument('--build-dir', type=Path, required=True)
p.add_argument('--cxx', default='g++')
a = p.parse_args()
source = Path(__file__).resolve().parent / 'pure_edge_tests.cpp'
header = a.runtime.resolve() / 'src/host/touch_edge_swipe.h'
out = a.build_dir.resolve()
if out == a.runtime.resolve() or a.runtime.resolve() in out.parents or source.parent in out.parents or out == source.parent:
    p.error('build-dir must be outside runtime and audit source trees')
out.mkdir(parents=True, exist_ok=True)
manifest = out / 'pure-manifest.json'
manifest.write_text('{"status":"running"}\n')
commands, results = [], []
text = header.read_text()
variants = [
    ('green', text, False),
    ('red-multitouch', text.replace('if (!first) candidate_ = false;', 'if (!first) {} // deliberately broken cancellation'), True),
    ('red-direction', text.replace('2.0f * vertical', '1.0f * vertical'), True),
    ('red-timeout', text.replace('now_ns - start_ns_ > 450000000ULL', 'false /* deliberately broken timeout */'), True),
]
try:
    for name, contents, red in variants:
        if red and contents == text:
            raise RuntimeError(f'{name}: mutation did not change source')
        selected = header
        if red:
            selected = out / (name + '.h')
            selected.write_text(contents)
        binary = out / (name + '-tests')
        command = [a.cxx, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-DEDGE_SOURCE="' + str(selected) + '"', str(source), '-o', str(binary)]
        commands.append(command)
        compile = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out / (name + '-build.log')).write_text(compile.stdout)
        if compile.returncode:
            raise RuntimeError(f'{name}: compiler failed ({compile.returncode})')
        command = [str(binary)]
        commands.append(command)
        run = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out / (name + '.log')).write_text(run.stdout)
        print(name + ': ' + run.stdout.strip().splitlines()[-1], flush=True)
        results.append({'name': name, 'expected_failure': red, 'returncode': run.returncode})
        if (run.returncode != 0) != red:
            raise RuntimeError(f'{name}: unexpected result ({run.returncode})')
    data = {'status': 'passed', 'scope': 'pure helper only; actual host tested separately',
            'sources': {str(x): hashlib.sha256(x.read_bytes()).hexdigest() for x in [source,header]},
            'results': results}
except Exception as error:
    data = {'status': 'failed', 'error': str(error), 'results': results}
    raise
finally:
    manifest.write_text(json.dumps(data, indent=2)+'\n')
    (out / 'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
