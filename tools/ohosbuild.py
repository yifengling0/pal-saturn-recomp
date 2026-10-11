#!/usr/bin/env python3
"""构建 HarmonyOS 包：先跑重编译生成器，再用 DevEco 自带的 hvigor 出 HAP。

    python tools/ohosbuild.py                 # 生成 + assembleHap
    python tools/ohosbuild.py --install        # 再 hdc install（需要已签名）
    python tools/ohosbuild.py --selftest on --launch   # 合成盘自测：装机、启动、回打 hilog
    python tools/ohosbuild.py --deveco "D:/DevEco Studio"

产物 harmony/pal-saturn-openharmony/entry/build/default/outputs/default/。
没有 signingConfigs 时 hvigor 只会出 entry-default-unsigned.hap：装到真机前要在
DevEco Studio 里 File ▸ Project Structure  Signing Configs ▸ Automatically generate
signature（需要华为开发者账号登录），这一步无法在命令行完成，见 docs/README-harmonyos.md。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'harmony' / 'pal-saturn-openharmony'
HAP_OUT = PROJECT / 'entry' / 'build' / 'default' / 'outputs' / 'default'
BUNDLE = 'com.palhero.palsaturn'
DEFAULT_DEVECO = Path(r'C:/Program Files/Huawei/DevEco Studio')


def deveco_home(cli: Path | None) -> Path:
    if cli:
        return cli
    env = os.environ.get('DEVECO_HOME')
    if env:
        return Path(env)
    if DEFAULT_DEVECO.is_dir():
        return DEFAULT_DEVECO
    raise SystemExit('找不到 DevEco Studio：给 --deveco 或设 DEVECO_HOME')


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    print('+', ' '.join(str(c) for c in cmd), flush=True)
    done = subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=env)
    if done.returncode:
        raise SystemExit(f'退出码 {done.returncode}')


def set_selftest(on: str | None) -> None:
    """合成盘自测开关落在 cpp/selftest.txt，由壳层 CMake 读；改了它才会重新 configure。"""
    if not on:
        return
    switch = PROJECT / 'entry' / 'src' / 'main' / 'cpp' / 'selftest.txt'
    switch.write_text(on + '\n', encoding='utf-8', newline='\n')
    print(f'selftest.txt -> {on}')


def hdc_target(hdc: str, wanted: str | None) -> str:
    out = subprocess.run([hdc, 'list', 'targets', '-v'], capture_output=True, text=True).stdout
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 4 and cols[2] == 'Connected' and (not wanted or cols[0] == wanted):
            return cols[0]
    raise SystemExit('hdc 没有在线设备（或 --device 指定的序列号不在线）')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--deveco', type=Path, default=None)
    ap.add_argument('--skip-learn', action='store_true', help='沿用已有的 build/recomp 生成物')
    ap.add_argument('--install', action='store_true', help='构建后用 hdc 安装（要求已签名）')
    ap.add_argument('--selftest', choices=('on', 'off'), help='真机自测：on 就打一张合成盘验 SDL 窗口')
    ap.add_argument('--device', help='hdc 序列号，默认取第一台在线的')
    ap.add_argument('--launch', action='store_true', help='装完启动并回打 hilog（隐含 --install）')
    args = ap.parse_args(argv)

    set_selftest(args.selftest)
    home = deveco_home(args.deveco)
    tools = home / 'tools'
    for p in (tools / 'hvigor' / 'bin' / 'hvigorw.bat', home / 'sdk'):
        if not p.exists():
            raise SystemExit(f'缺少 {p}')

    env = dict(os.environ)
    env['DEVECO_SDK_HOME'] = str(home / 'sdk')
    env['NODE_HOME'] = str(tools / 'node')
    env['PATH'] = os.pathsep.join([str(tools / 'node'), str(tools / 'ohpm' / 'bin'),
                                   str(tools / 'hvigor' / 'bin'), env.get('PATH', '')])

    python = ROOT / 'build' / 'venv' / 'Scripts' / 'python.exe'
    if not python.is_file():
        python = Path(sys.executable)
    if not args.skip_learn:
        run([python, ROOT / 'tools' / 'winbuild.py', 'learn'], ROOT, env)
    run([tools / 'hvigor' / 'bin' / 'hvigorw.bat', 'assembleHap', '--mode', 'module',
         '-p', 'product=default', '-p', 'buildMode=debug', '--no-daemon'], PROJECT, env)

    haps = sorted(HAP_OUT.glob('*.hap'))
    if not haps:
        raise SystemExit('hvigor 说成功了但没找到 .hap')
    for h in haps:
        print(f'  {h.name}  {h.stat().st_size:,} 字节')
    signed = [h for h in haps if 'signed' in h.name and 'unsigned' not in h.name]
    if not signed:
        print('未签名，装不了真机：在 DevEco Studio 的 Signing Configs 里自动生成签名后重跑。')
    if args.install or args.launch:
        hdc = shutil.which('hdc') or str(home / 'sdk' / 'default' / 'openharmony' / 'toolchains' / 'hdc.exe')
        hap = str((signed or haps)[0])
        device = hdc_target(hdc, args.device) if args.launch else None
        if device:
            run([hdc, '-t', device, 'shell', 'hilog', '-r'], ROOT, env)
        run([hdc] + (['-t', device] if device else []) + ['install', '-r', hap], ROOT, env)
        if device:
            run([hdc, '-t', device, 'shell', 'aa', 'start', '-a', 'EntryAbility', '-b', BUNDLE], ROOT, env)
            time.sleep(6)
            logs = subprocess.run([hdc, '-t', device, 'shell', 'hilog', '-x'],
                                  capture_output=True, text=True, errors='replace').stdout
            for line in logs.splitlines():
                if 'PAL/OHOS' in line or 'SDL/STARTUP' in line or ' SDL' in line:
                    print(line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
