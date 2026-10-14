#!/usr/bin/env python3
"""组装可运行的 Windows 分发包：主程序 + SDL3 + 启动脚本 + 说明，不附带原版光盘或资源文件。

用法: python tools/make_dist.py [--output 新目录] [--with-save 源.bup]

刻意不做的事：不复制 disc/ 下的 BIN/CUE/MDS，不复制私有检查点包。原版镜像由玩家自己
放进包内的 disc\\ 。已有输出（包括存档、设置和光盘）一律不动；只向新目录发布。
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build' / 'windows-pal-options' / 'recomp-build'
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
  echo This package ships no disc images or asset files.  See disc\README.txt for which version, in Chinese.
  pause
  exit /b 1
)
"%~dp0saturn.exe" --cue "%DISC%" --settings "%~dp0settings.ini" --save "%~dp0saves\pal-saturn.bup" --cart "%~dp0saves\pal-saturn-cart.bup" --clock 1998-11-01T12:00:00
'''

DISC_README = f'''原版光盘（请自行放入本目录）

本包不附带仙剑奇侠传土星版的光盘镜像或资源文件。请使用你有权使用的光盘备份：

  disc\\pal_t37401h_v1000_jt.bin
  disc\\pal_t37401h_v1000_jt.cue

要的版本是 T-37401H V1.000, areas JT（LEGEND OF SWORD AND FAIRY），使用
单个 BIN 文件加描述其 13 条轨道的 CUE：第 1 轨是 MODE1/2352 数据，
第 2–13 轨是 CD-DA 音频。整个 BIN 的 SHA-256 应为

  {DISC_BIN_SHA256}

哈希不符表示本次未验证，可能无法正常运行。文件名可以不同；把 CUE 与它引用的 BIN
放在一起，确保 CUE 内 FILE 引用与实际 BIN 文件名一致。disc\\ 中只放一份要启动的
.cue，run.bat 会自动找到它。保留完整 13 轨信息，不要改动镜像本身。
'''

NOTICE = f'''来源与权利说明

saturn.exe 包含运行时、本项目的游戏适配层，以及从原版程序静态重编译生成的游戏逻辑。
没有附带光盘镜像或资源文件，不等于没有包含原版程序的衍生内容。

- saturn-recomp 运行时：MIT License，Copyright (c) 2026 Samuele Voltan、Callum Jenkins；
  上游固定提交 {UPSTREAM_PIN}，并应用本仓库的运行时补丁。
  MIT 许可适用于其所覆盖的运行时代码，不能据此把整份 exe 或原作逻辑称为 MIT 软件。
- SDL3.dll：SDL3，zlib 许可；该许可适用于 SDL，不授予原作游戏的权利。
- 本项目适配代码 src/pal_game 与重编译生成的原版仙剑土星版游戏逻辑是不同组成部分。
  原作及其衍生游戏逻辑仍涉及原权利人的版权；本说明不声称已获大宇（Softstar）或其他
  权利人的授权，也不声称本包是纯粹不含游戏代码的运行时。请在分享或再分发前确认相关权利。

打包只接受 SATURN_VDP1_GPL=OFF 的构建配置。关闭该选项仅排除相应 Mednafen 派生 VDP1
部件，不能解决其他组成部分的许可或原作版权问题，也不构成对整个程序许可的判断。

本包不附带原版光盘镜像、BIOS、图像、音乐或从光盘提取的资源文件。
saves\\ 下若有 .bup，是用户明确选择附带的私人进度备份；不要随发行包对外分享。
'''

README = '''仙剑奇侠传 土星版 · 静态重编译 Windows 包

怎么跑

1. 按 disc\\README.txt 把你自己的原版 BIN+CUE 放进 disc\\ 。
2. 双击 run.bat。第一次会慢一些（光盘要现读），看到片头即成功。
3. 片头动画（地球陨星 → 洞窟）会自己播完，播完自动进标题；标题选「新的故事」开新档，
   「舊的回憶」读取你自己的 saves\\pal-saturn.bup。本发行包不附带存档。

按键（PC98 档，本包 settings.ini 已启用）

  方向键      移动 / 选菜单
  Enter 空格  确认、继续对话
  Esc         场景里开菜单，菜单里返回/取消
  Tab         土星 START
  Z X C       土星 A B C
  V           土星 X
  E           场景里包袱；战斗主菜单里使用物品——土星原生的 R
  F           仙术——土星原生的 L 快捷页；在战斗主菜单里是"最强"
  A           战斗主菜单里围攻（剩余队友普通攻击，进入原生连续围攻；Esc 可取消）
  D           战斗主菜单里防御——土星原生的 X
  R           战斗里重复上一次指令——土星原生的 Z
  S           状态页——土星版能换装备的那一页（属性、立绘、七个装备格）
  W           场景里开物品/装备页；战斗主菜单里投掷——土星原生的 Y
  Q           系统页——土星版是「储存进度 / 读取进度」，不是 98 的退出画面
  F10         暂停菜单（截图、音量、退出）
  Alt+Enter   全屏切换
  F12         存一张截图

E/F/A/D/W/R 按当前上下文执行对应快捷操作；场景和战斗主菜单里的含义分开，
按下时按当前画面决定，不会把法术页带进回合、也不会把"最强"漏到地图里。

98 的 S / W / Q 在土星版没有能借用的按键，所以这三个字母由程序替你走菜单：先按 B 收掉
当前画面，把要的那一项直接写进菜单自己的光标变量 0x060768DA，再按 X 打开，等游戏自己
报告菜单确实进去了才按 A 选定。中途你手动按方向键不会把它带偏——目标是被写进去的，不是
追出来的；菜单四秒内不响应就放弃，不会跟游戏抢。战斗里的 E 打开使用物品列表，Q 逃跑尚未绑定。
E 后仍由你选择物品和目标；取消不会代替你使用物品，也不会清除先前角色已选指令。
W/D 只在四图标的战斗主菜单生效，不打断动画或替你选目标；W 后仍由你选投掷物和目标。
A 通过原生「其他 → 围攻」菜单，为剩余队友选普通攻击，保留先前角色已选指令；F 仍是
原生「最强」法术选择，两者不再混用。A 的导航遇到竞争输入、失焦或四秒超时即取消。

每个语义键按下后锁定到一个土星键，直到松开，所以按住 Esc 不会把"开菜单"变成"取消"。
想要原来的土星键位，把 settings.ini 里 [controls] 的 keyboard_profile 改成 saturn。

按键手感

游戏要连续看到两帧以上才算一次按键，而宿主每帧只轮询一次控制器，按得太快可能一个采样都拿不到——
表现就是"点了没反应，半拍后才出来"。走路和确认现在分开处理：

- 方向（走路）：一次轻点只在游戏原本的行动点被消费一次，走一步就停；松手立刻结束按住状态，
  不会按帧数补成长按。想退回原来的采样方式，运行前 set PAL_FIELD_INPUT=0。
- 确认、对话这类按键：不足两帧游戏看不见，所以至少送到游戏面前三帧。想按原始采样来，
  运行前 set PAL_TAP_HOLD=0。

带触屏的机器上还有一处：虚拟方向键的死区从半径的 0.2 缩到 0.1，拇指离开实心盘芯就算起步。

画面与触控布局

按 F10 打开宿主设置。Picture / 画面：Fit / 适应按游戏画面比例等比放大到最大，一边铺满；
Stretch / 拉伸横纵都铺满；4:3 是原始电视比例和 PAL 留边。
Move controls / 移动按键可拖动按键组，Done / 完成保存，Cancel / 取消放弃。
Windows 使用 GPU 呈现、主从 CPU 协程和每批 256 帧 PCM；音频仍走 SDL/WASAPI。


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


# These are the capabilities described by the bundled README, including the
# field-consume implementation. A mapping-only/older executable is not this pack.
REQUIRED_FEATURES = frozenset(('input_v4', 'effect_wait_v3', 'data_cd_speed',
    'effect_cadence_v4_manual_pair', 'paired_frame_queue_v3', 'keyboard_profile_v1',
    'field_input_v1'))
GUEST_MARKERS = {
    'input_v4': ('pal_input_script_before();', 'pal_input_wait_begin(c);'),
    'effect_wait_v3': ('pal_effect_wait::Scope pal_effect_scope(c);', 'pal_effect_wait::ready(c)'),
    'effect_cadence_v4_manual_pair': ('pal_effect_cadence::Cast pal_cadence_scope(c);',
                                    'pal_effect_cadence::prepare_sync(c);'),
    'paired_frame_queue_v3': ('pal_pfq_field_begin(c);', 'pal_pfq_slave_done();'),
    'keyboard_profile_v1': ('pal_keyboard::field_menu_at(ld16(pal_keyboard::MenuCursor));',
                           'pal_keyboard::boot();'),
    'field_input_v1': ('pal_field_input::enter();', 'pal_field_input::apply(c);',
                       'if (!pal_field_input::owns_input()) pal_input_tick();'),
}


def safe_path(path: Path) -> Path:
    """Reject traversal, symlinks/junctions and unsupported names, even if dangling."""
    path = Path(path)
    if '..' in path.parts or any(c in str(path) for c in '\r\n\0'):
        raise ValueError(f'不支持的路径：{path}')
    path = path.absolute()
    if path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f'不接受符号链接或重定向路径：{path}')
    return path


def regular_file(path: Path) -> Path:
    path = safe_path(path)
    if not path.is_file():
        raise ValueError(f'缺少普通文件：{path}')
    return path


def object_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'清单有重复字段 {key}：{path}')
            result[key] = value
        return result
    data = json.loads(regular_file(path).read_text(encoding='utf-8'), object_pairs_hook=unique)
    if not isinstance(data, dict):
        raise ValueError(f'清单必须是 JSON 对象：{path}')
    return data


def digest_field(value, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', value):
        raise ValueError(f'{label} 必须是非空的 64 位 SHA-256')
    return value.lower()


def verify_build() -> dict[Path, str]:
    """Read-only consistency gate, never generate/repair a missing build proof."""
    from pal_options import HEADERS, MANIFEST, VERSION, prepare_options
    from pal_paired_frame_queue import RUNTIME_FILES
    from pal_data_cd_speed import _SOURCE, _PATCHED_SHA256, _normalized

    build = safe_path(BUILD)
    recomp, runtime = (safe_path(build.parent / name) for name in ('recomp', 'runtime'))
    exe, dll, proof = (build / name for name in ('saturn.exe', 'SDL3.dll', 'pal-options-build.json'))
    data = object_json(proof)
    if type(data.get('schema')) is not int or data['schema'] != 1 or data.get('version') != VERSION:
        raise ValueError(f'构建清单 schema/version 缺失或过期：{proof}')
    features = data.get('features')
    if (not isinstance(features, list) or any(not isinstance(x, str) for x in features) or
            len(features) != len(set(features)) or set(features) != REQUIRED_FEATURES):
        raise ValueError(f'构建清单 features 与本包所需能力不符：{proof}')
    want = digest_field(data.get('exe_sha256'), 'exe_sha256')
    if sha256(regular_file(exe)) != want:
        raise ValueError(f'exe_sha256 与实际程序不符：{exe}')
    injected = recomp / MANIFEST
    expected_injected = digest_field(data.get('instrumentation_manifest_sha256'),
                                     'instrumentation_manifest_sha256')
    if sha256(regular_file(injected)) != expected_injected:
        raise ValueError(f'instrumentation_manifest_sha256 与实际清单不符：{injected}')
    staged = object_json(injected)
    if staged.get('version') != VERSION or staged.get('runtime') != '../runtime':
        raise ValueError(f'不匹配的 instrumentation version/runtime：{injected}')

    defaults = {'PAL_RESPONSIVE_INPUT': '0', 'PAL_RESPONSIVE_ALIGN': '0',
                'PAL_RESPONSIVE_WAKE': '0', 'PAL_SHORT_EFFECT_PREP': '1',
                'PAL_EFFECT_ANIMATION_SPEED': '1.5', 'PAL_PAIRED_FRAME_QUEUE': '0'}
    if staged.get('defaults') != defaults:
        raise ValueError('instrumentation defaults 与本包说明不符')

    # Require a complete inventory before the existing verifier reads it. Empty
    # maps and self-consistent feature names alone are not evidence of injection.
    inventories = {}
    for kind in ('inputs_sha256', 'outputs_sha256'):
        groups = staged.get(kind)
        if not isinstance(groups, dict) or set(groups) != {'recomp', 'runtime'}:
            raise ValueError(f'缺少 instrumentation {kind}')
        for group, base in (('recomp', recomp), ('runtime', runtime)):
            entries = groups[group]
            if not isinstance(entries, dict) or not entries:
                raise ValueError(f'空 instrumentation {kind}/{group}')
            for name, value in entries.items():
                if (not isinstance(name, str) or not name or '\\' in name or ':' in name or
                        Path(name).is_absolute() or '..' in Path(name).parts):
                    raise ValueError(f'不安全的 instrumentation 文件名：{name!r}')
                regular_file(base / name)
                digest_field(value, f'{kind}/{group}/{name}')
            inventories[kind, group] = entries
    needed_recomp = {'CMakeLists.txt', *HEADERS, 'pal_paired_frame_queue.cpp', 'pal_field_input.h', 'pal_release_gate.h', 'pal_release_runtime.h'}
    needed_runtime = {*RUNTIME_FILES, 'src/host/host_null.cpp', 'src/machine/smpc.cpp',
        'src/machine/machine.cpp', 'src/host/settings.cpp', 'src/host/settings.h',
        'src/host/launcher.cpp', 'src/host/pal_host_edge.h',
        'include/pal_paired_frame_queue.h', 'include/saturn/pal_keyboard_profile.h'}
    for group, required in (('recomp', needed_recomp), ('runtime', needed_runtime)):
        if not required.issubset(inventories['outputs_sha256', group]):
            raise ValueError(f'不完整的 instrumentation outputs_sha256/{group}')
    generated = sorted([*recomp.glob('p_prog_*.cpp'), *recomp.glob('p_true_*.cpp')])
    owned = {**inventories['inputs_sha256', 'recomp'], **inventories['outputs_sha256', 'recomp']}
    if not generated or any(path.name not in owned for path in generated):
        raise ValueError('重编译源码不在 instrumentation 清单中')
    for name in (*HEADERS, 'pal_host_edge.h', 'pal_paired_frame_queue.cpp',
                 'pal_paired_frame_queue.h', 'pal_keyboard_profile.h', 'pal_field_input.h', 'pal_release_gate.h', 'pal_release_runtime.h'):
        regular_file(ROOT / 'src/pal_game' / name)
    prepare_options(recomp, runtime, ROOT, verify_only=True)
    # A rehashed output must not silently substitute a different helper while
    # retaining the manifest's current source-header identity.
    copied_helpers = {recomp / name: name for name in (*HEADERS,
        'pal_paired_frame_queue.cpp', 'pal_field_input.h', 'pal_release_gate.h', 'pal_release_runtime.h')}
    copied_helpers.update({runtime / 'src/host/pal_host_edge.h': 'pal_host_edge.h',
        runtime / 'include/pal_paired_frame_queue.h': 'pal_paired_frame_queue.h',
        runtime / 'include/saturn/pal_keyboard_profile.h': 'pal_keyboard_profile.h'})
    for target, name in copied_helpers.items():
        if sha256(target) != staged['headers_sha256'][name]:
            raise ValueError(f'实际注入 helper 与来源不符：{target}')
    text = '\n'.join(regular_file(path).read_text(encoding='utf-8') for path in generated)
    for feature, markers in GUEST_MARKERS.items():
        if any(marker not in text for marker in markers):
            raise ValueError(f'实际重编译源码缺少 {feature} instrumentation')
    host = (runtime / 'src/host/host.cpp').read_text(encoding='utf-8')
    if 'pal_field_input_ledger.h' not in host or 'pal_keyboard::' not in host:
        raise ValueError('实际 runtime 缺少 field/keyboard instrumentation')
    if hashlib.sha256(_normalized(regular_file(runtime / _SOURCE).read_bytes())).hexdigest() != _PATCHED_SHA256:
        raise ValueError('实际 runtime 缺少已验证的 data_cd_speed')
    cache = regular_file(build / 'CMakeCache.txt').read_text(encoding='utf-8')
    if not re.search(r'^SATURN_VDP1_GPL:BOOL=OFF$', cache, re.M):
        raise ValueError('需要明确 SATURN_VDP1_GPL:BOOL=OFF 的构建配置')
    return {exe: want, dll: sha256(regular_file(dll)), proof: sha256(proof),
            injected: expected_injected}


def scan(root: Path):
    files = []
    for path in sorted(root.rglob('*')):
        safe_path(path)
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise ValueError(f'包内有非普通文件：{path}')
    return files


def refuse_disc_data(root: Path, stage: str):
    # This is a read-only validator. In particular it must NEVER delete root.
    bad = [str(p.relative_to(root)) for p in scan(root) if p.suffix.lower() in FORBIDDEN]
    if bad:
        raise ValueError(f'{stage}: 包里出现光盘镜像类文件，拒绝产出：{bad}')


def validate_save(path: Path):
    """Accept only the runtime's bounded internal BUP record format, not a ROM."""
    path = regular_file(path)
    if path.suffix.lower() != '.bup' or path.stat().st_size > 32768:
        raise ValueError(f'--with-save 只接受内部备份进度 .bup（不超过 32 KiB）：{path}')
    data = path.read_bytes()
    if not data:
        raise ValueError(f'BUP 进度为空：{path}')
    offset = 0
    while offset < len(data):
        if len(data) - offset < 32 or not data[offset:offset + 12].split(b'\0', 1)[0]:
            raise ValueError(f'不是完整的 BUP 进度：{path}')
        size = int.from_bytes(data[offset + 28:offset + 32], 'little')
        offset += 32 + size
        if offset > len(data):
            raise ValueError(f'BUP 进度长度不符：{path}')
    return hashlib.sha256(data).hexdigest()


def fresh_output(path: Path) -> Path:
    path = safe_path(path)
    if path.exists():
        raise ValueError(f'输出已存在，原样保留：{path}；请用 --output 指定新目录')
    if path.is_relative_to(safe_path(BUILD.parent)):
        raise ValueError(f'输出不能放在构建输入目录中：{path}')
    return path


def publish_new(stage: Path, output: Path):
    """Atomic no-replace publish, including a destination created after preflight."""
    fresh_output(output)
    if sys.platform == 'win32':
        os.rename(stage, output)  # Windows refuses any existing destination.
    elif sys.platform.startswith('linux'):
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, 'renameat2', None)
        if rename is None:
            raise OSError('系统没有 renameat2；不能安全地无覆盖发布')
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(stage), -100, os.fsencode(output), 1) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(output))
    else:
        raise OSError('此平台尚无已验证的无覆盖发布方式；请使用 Windows 或 Linux')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=OUT, help='全新的输出目录；绝不覆盖已有目录')
    ap.add_argument('--with-save', type=Path, default=None,
                    help='把这个内部备份 .bup 复制为私人初始进度（不改源文件，不适合公开分发）')
    args = ap.parse_args(argv)
    stage = None
    try:
        output = fresh_output(args.output if args.output.is_absolute() else ROOT / args.output)
        inputs = verify_build()
        exe, dll, proof = (BUILD / name for name in ('saturn.exe', 'SDL3.dll', 'pal-options-build.json'))
        saved = None
        if args.with_save:
            saved = args.with_save if args.with_save.is_absolute() else ROOT / args.with_save
            inputs[saved] = validate_save(saved)
        result = subprocess.run(['objdump', '-p', str(exe)], capture_output=True, text=True,
                                encoding='utf-8', errors='replace')
        if result.returncode != 0 or not re.search(r'DLL Name: SDL3\.dll\s*$', result.stdout, re.M):
            raise ValueError('objdump 失败或 saturn.exe 没有链接 SDL3；用带 --sdl-dir 的构建')
        output.parent.mkdir(parents=True, exist_ok=True)
        safe_path(output.parent)
        stage = Path(tempfile.mkdtemp(prefix=f'.{output.name}.staging-', dir=output.parent))
        (stage / 'disc').mkdir()
        (stage / 'saves').mkdir()
        copies = {exe: stage / 'saturn.exe', dll: stage / 'SDL3.dll', proof: stage / proof.name}
        if saved:
            copies[saved] = stage / 'saves/pal-saturn.bup'
        for source, target in copies.items():
            shutil.copy2(source, target)
            if sha256(target) != inputs[source]:
                raise ValueError(f'复制校验失败：{source}')
        if not saved:
            (stage / 'saves/README.txt').write_text(
                '本機進度写在 pal-saturn.bup；卡匣進度一到四写在 pal-saturn-cart.bup。'
                '这个文件夹里的东西是玩家私有的，别对外分享。\n', encoding='utf-8')
        for name, content in (('run.bat', RUN_BAT), ('README.txt', README), ('NOTICE.txt', NOTICE),
                              ('disc/README.txt', DISC_README)):
            (stage / name).write_text(content, encoding='utf-8', newline='\r\n')
        (stage / 'settings.ini').write_text(
            '; 本包的设置。删掉某一行就恢复默认。\n'
            '[display]\nfullscreen = false\nscale = 3\n\n[audio]\nvolume = 100\n\n'
            '[controls]\nkeyboard_profile = pc98\n', encoding='utf-8', newline='\r\n')
        refuse_disc_data(stage, '打包后')
        files = scan(stage)
        allowed = {p.relative_to(stage).as_posix() for p in copies.values()} | {
            'run.bat', 'README.txt', 'NOTICE.txt', 'disc/README.txt', 'settings.ini'}
        if not saved:
            allowed.add('saves/README.txt')
        if {p.relative_to(stage).as_posix() for p in files} != allowed:
            raise ValueError('包内文件不在固定分发白名单中')
        expected = {p.relative_to(stage).as_posix(): sha256(p) for p in files}
        sums = ''.join(f'{digest}  {name}\n' for name, digest in expected.items())
        (stage / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
        if ((stage / 'SHA256SUMS.txt').read_text(encoding='utf-8') != sums or
                {p.relative_to(stage).as_posix(): sha256(p) for p in scan(stage)
                 if p != stage / 'SHA256SUMS.txt'} != expected):
            raise ValueError('SHA256SUMS 或包内文件在校验时发生变化')
        if verify_build() != {p: h for p, h in inputs.items() if p != saved}:
            raise ValueError('构建在打包时发生变化，请重新构建')
        if any(sha256(regular_file(p)) != h for p, h in inputs.items()):
            raise ValueError('打包输入在复制时发生变化')
        publish_new(stage, output)
        stage = None
        print(f'产出 {output}；{len(expected) + 1} 个文件；未附带光盘镜像或原版资源文件。')
        if saved:
            print('注意：含私人存档，不要公开分发。')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(f'拒绝打包：{exc}') from exc
    finally:
        if stage is not None:
            # Only this invocation's uniquely-created staging tree is ours.
            # Never remove output, any prior .saves directory, or source inputs.
            shutil.rmtree(stage)


if __name__ == '__main__':
    raise SystemExit(main())
