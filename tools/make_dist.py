#!/usr/bin/env python3
"""组装可运行的 Windows 分发包：主程序 + SDL3 + 启动脚本 + 说明，不含任何原版游戏数据。

用法: python tools/make_dist.py [--with-save 源.bup]

刻意不做的事：不复制 disc/ 下的 BIN/CUE/MDS，不复制私有检查点包。原版镜像由玩家自己
放进 dist 的 disc\\ ；脚本会在打包前确认包内没有光盘镜像，打包后再确认一次。
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build' / 'recomp-build'
OUT = ROOT / 'dist' / 'pal-saturn-recomp-win-x64'

UPSTREAM_PIN = '086c372c67d9e0f94fcc64cedd6e6b63cc5542b5'
DISC_BIN_SHA256 = '4c76366e3178289c3e73264d8f3a0b9b8b3d78f7baa0862561ce48ce4199d4b5'
FORBIDDEN = ('.bin', '.cue', '.mds', '.mdf', '.iso', '.zip', '.7z', '.tar')

RUN_BAT = r'''@echo off
setlocal
set "DISC="
for %%f in ("%~dp0disc\*.cue") do set "DISC=%%~ff"
if not defined DISC (
  echo Put your own BIN and the matching CUE into the "disc" folder of this package, then run me again.
  echo This package ships no game data.  See disc\README.txt for which version, in Chinese.
  pause
  exit /b 1
)
"%~dp0saturn.exe" --cue "%DISC%" --settings "%~dp0settings.ini" --save "%~dp0saves\pal-saturn.bup" --cart "%~dp0saves\pal-saturn-cart.bup" --clock 1998-11-01T12:00:00
'''

DISC_README = f'''原版光盘（请自行放入本目录）

本包不含、也不会提供仙剑奇侠传土星版的游戏数据。放你自己的正版备份：

  disc\\pal_t37401h_v1000_jt.bin
  disc\\pal_t37401h_v1000_jt.cue

要的版本是 T-37401H V1.000, areas JT（LEGEND OF SWORD AND FAIRY），MODE1/2352 的
单轨 BIN 加它的 CUE，13 轨（含 CD-DA 音轨）。整个 BIN 的 SHA-256 应为

  {DISC_BIN_SHA256}

对不上也能跑，但版本不同就可能撞到没测过的代码。文件名随你，run.bat 会自动找
disc\\ 里第一个 .cue；CUE 与 BIN 必须同名且放在一起。不要改动镜像本身。
'''

NOTICE = f'''来源与许可

主程序 saturn.exe 由 PAL-Saturn-Recomp 构建：

- 上游 saturn-recomp，MIT License (c) 2026 Samuele Voltan，固定在提交 {UPSTREAM_PIN}；
  本仓库 patches/0001-0005 与 0007 六个补丁打在其 runtime 上（含 SH-2 DMA 16 字节突发短拷
  修复，以及 0007 的土星备份卡匣 BUP 设备 1）。
- 仙剑游戏层 src/pal_game（本仓库），随本包一起编进 exe。
- SDL3 3.4.18，zlib 许可，以 SDL3.dll 的形式随包分发。

本构建 SATURN_VDP1_GPL=OFF，没有编入 Mednafen 派生的 VDP1 栅格化部件，所以整个程序按
MIT + zlib 对待。若在配置时把 SATURN_VDP1_GPL 打开，该构建整体成为 GPL 作品，需要按
GPL 提供源码，不能再直接用本包的说明。

本包不含任何原版游戏内容：没有光盘镜像、BIOS、图像、音乐或从原版提取的资源。
saves\\ 下若有 .bup，那是玩家自己的游戏进度备份，属私人文件，不要对外分享。
'''

README = '''仙剑奇侠传 土星版 · 静态重编译 Windows 包

怎么跑

1. 按 disc\\README.txt 把你自己的原版 BIN+CUE 放进 disc\\ 。
2. 双击 run.bat。第一次会慢一些（光盘要现读），看到片头即成功。
3. 片头动画（地球陨星 → 洞窟）会自己播完，播完自动进标题；标题选「新的故事」开新档，
   「舊的回憶」读本包 saves\\pal-saturn.bup 里的进度。

按键（PC98 档，本包 settings.ini 已启用）

  方向键      移动 / 选菜单
  Enter 空格  确认、继续对话
  Esc         场景里开菜单，菜单里返回/取消
  Tab         土星 START
  Z X C       土星 A B C
  A S D       土星 X Y Z
  Q W         土星 L R
  F10         暂停菜单（截图、音量、退出）
  Alt+Enter   全屏切换
  F12         存一张截图

每个语义键按下后锁定到一个土星键，直到松开，所以按住 Esc 不会把"开菜单"变成"取消"。
想要原来的土星键位，把 settings.ini 里 [controls] 的 keyboard_profile 改成 saturn。

按键手感

游戏要连续看到两帧以上才算一次按键，而宿主每帧只轮询一次控制器，按得太快可能一个采样都拿不到——
表现就是"点了没反应，半拍后才出来"。现在一次轻点至少会被送到游戏面前：方向键两帧（角色每帧都在走，
多补一帧就明显走过头），确认与对话这类按键三帧。想按原始采样来，运行前 set PAL_TAP_HOLD=0。
带触屏的机器上还有一处：虚拟方向键的死区从半径的 0.2 缩到 0.1，拇指离开实心盘芯就算起步。


施法与法术动画

本包默认缩短已验证的施法准备，并把法术动画放到 1.5 倍（逐帧解码都保留，只是每帧少等几个场）。
想回到原版节奏，在包目录下开一个 cmd 敲：

  set PAL_SHORT_EFFECT_PREP=0
  set PAL_EFFECT_ANIMATION_SPEED=1
  run.bat

1.25 与 2 也是可选倍率。程序默认不再弹控制台窗口；要看日志就再加一行 set PAL_CONSOLE=1。

存档与设置

存档有两个地方（土星的两种记忆）：

- 本機進度：saves\\pal-saturn.bup，是土星备份内存的整卡镜像，一张卡只装一份进度，存盘即整张重写。
- 卡匣進度一到四：saves\\pal-saturn-cart.bup，游戏内的外接记忆卡，标题读档与游戏内「儲存進度」
  都能选这四格。想把当前进度留着做基准或回滚，就存进卡匣一格；想换进度，就从卡匣读那一格。
  第一次往卡匣存盘时这个文件才会出现。

设置写在 settings.ini，都跟着文件夹走，拷到别的电脑就是完整的一套。

命令行

run.bat 只是把下面这条包起来，需要自己加参数时直接敲：

  saturn.exe --cue disc\\你的.cue --settings settings.ini --save saves\\pal-saturn.bup --cart saves\\pal-saturn-cart.bup
  saturn.exe --help          全部参数
  --headless --vblanks N --shot A,B --out 目录    无窗口跑到第 N 帧并截图（取证用）

已知情况

- 窗口标题是 saturn-recomp；第一次启动 Windows 可能弹防火墙提示，取消即可（游戏不联网）。
- 水面/彩虹一类的逐行滚动（VDP2 SCRCTL）与 RBG 旋转上游还没实现，个别场景的边缘效果会不对，
  不影响操作。
- 3D 音效、震动手柄不做。音频异常时先试设置菜单里的音量，或加环境变量 SDL_AUDIODRIVER=dummy。
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan(root: Path):
    return sorted(p for p in root.rglob('*') if p.is_file())


def refuse_disc_data(root: Path, stage: str):
    bad = [str(p.relative_to(root)) for p in scan(root) if p.suffix.lower() in FORBIDDEN]
    if bad:
        shutil.rmtree(root)
        raise SystemExit(f'{stage}: 包里出现光盘镜像类文件，拒绝产出：{bad}')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-save', type=Path, default=None,
                    help='把这个 .bup 作为包内初始进度复制进去（不写回源文件）')
    args = ap.parse_args(argv)

    exe, dll = BUILD / 'saturn.exe', BUILD / 'SDL3.dll'
    for p in (exe, dll):
        if not p.is_file():
            raise SystemExit(f'缺少 {p}；先跑 python tools/winbuild.py build --sdl-dir ...')

    imports = subprocess.run(['objdump', '-p', str(exe)], capture_output=True, text=True).stdout
    if not re.search(r'DLL Name: SDL3\.dll', imports):
        raise SystemExit('saturn.exe 没有链接 SDL3，这个 exe 开不出窗口；用带 --sdl-dir 的构建')

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'disc').mkdir(parents=True)
    (OUT / 'saves').mkdir()
    shutil.copy2(exe, OUT / 'saturn.exe')
    shutil.copy2(dll, OUT / 'SDL3.dll')
    if args.with_save:
        src = args.with_save if args.with_save.is_absolute() else ROOT / args.with_save
        if not src.is_file():
            raise SystemExit(f'找不到存档 {src}')
        shutil.copy2(src, OUT / 'saves' / 'pal-saturn.bup')
    else:
        (OUT / 'saves' / 'README.txt').write_text(
            '本機進度写在 pal-saturn.bup；卡匣進度一到四写在 pal-saturn-cart.bup（第一次往卡匣存盘才会出现）。'
            '这个文件夹里的东西是玩家私有的，别对外分享。\n',
            encoding='utf-8')

    for name, text in (('run.bat', RUN_BAT), ('README.txt', README), ('NOTICE.txt', NOTICE),
                       ('disc/README.txt', DISC_README)):
        (OUT / name).write_text(text, encoding='utf-8', newline='\r\n')
    (OUT / 'settings.ini').write_text(
        '; 本包的设置。删掉某一行就恢复默认。\n'
        '[display]\nfullscreen = false\nscale = 3\n\n[audio]\nvolume = 100\n\n'
        '[controls]\nkeyboard_profile = pc98\n', encoding='utf-8', newline='\r\n')

    refuse_disc_data(OUT, '打包后')
    files = scan(OUT)
    (OUT / 'SHA256SUMS.txt').write_text(
        ''.join(f'{sha256(p)}  {p.relative_to(OUT).as_posix()}\n' for p in files), encoding='utf-8',
        newline='\n')   # LF, so `sha256sum -c` reads the names cleanly on Git Bash
    print(f'产出 {OUT}')
    for p in files:
        print(f'  {p.relative_to(OUT).as_posix():24s} {p.stat().st_size:>10,} 字节')
    print(f'  合计 {sum(p.stat().st_size for p in files):,} 字节，{len(files)} 个文件；无原版数据。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
