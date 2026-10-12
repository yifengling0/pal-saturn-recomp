#!/usr/bin/env python3
"""构建 HarmonyOS 包：先跑重编译生成器，再用 DevEco 自带的 hvigor 出 HAP。

    python tools/ohosbuild.py                 # 生成 + assembleHap（默认 release）
    python tools/ohosbuild.py --build-mode debug  # 显式选调试包
    python tools/ohosbuild.py --install        # 再 hdc install（需要已签名）
    python tools/ohosbuild.py --selftest on --launch   # 合成盘自测：装机、启动、回打 hilog
    python tools/ohosbuild.py --deveco "D:/DevEco Studio"
    python tools/ohosbuild.py --logs --device DEVICE  # 游戏 Quit 后取 hilog，不构建/安装/清日志

产物 harmony/pal-saturn-openharmony/entry/build/default/outputs/default/。
没有 signingConfigs 时 hvigor 只会出 entry-default-unsigned.hap：装到真机前要在
DevEco Studio 里 File ▸ Project Structure  Signing Configs ▸ Automatically generate
signature（需要华为开发者账号登录），这一步无法在命令行完成，见 docs/P4_HARMONYOS.md。
release 是传给 hvigor 的模式；实际 native 编译旗标仍须核查构建输出/compile_commands.json。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
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

# OHOS packaging requires this UI generation even though desktop planners retain
# older complete runtime variants. Filled only with reviewed post-PC98 source
# hashes after the current UI source is frozen; an empty set fails closed.
OHOS_HOST_UI_VERSION = 13
# UI generation remains 13; require its current 0014/0015 source, in whichever of
# the two generations a HAP may be built from: the mapping-only host and the
# accelerated (pal-options) host that adds the spell/effect hooks on top of it.
OHOS_HOST_UI_SHA256: frozenset[str] = frozenset({
    # mapping generation: tools/winbuild.py build --recompile
    'fc6905e7db4acdd74372706a83461e0cf463c91d27835428eee947262e0c0398',
    # accelerated generation: winbuild.py learn --pal-options
    '808098fd058a034da91e63cda91745dfd9e58716ff537fbdc6409c79fa12a3af',
})

# The accelerated generation is the one the Windows package ships, so the tablet gets the same
# spell preparation, spell animation speed and data-CD delivery as the PC build.
ACCELERATED = {'recomp': 'windows-pal-options/recomp', 'runtime': 'windows-pal-options/runtime',
               'manifest': 'pal-options-manifest.json', 'planner': 'pal_options'}
MAPPING = {'recomp': 'recomp', 'runtime': 'pal-keyboard-runtime',
           'manifest': 'pal-keyboard-manifest.json', 'planner': 'pal_keyboard_profile'}
GENERATION_POINTER_NAME = 'pal-ohos-generation.cmake'


def deveco_home(cli: Path | None) -> Path:
    if cli:
        return cli
    env = os.environ.get('DEVECO_HOME')
    if env:
        return Path(env)
    if DEFAULT_DEVECO.is_dir():
        return DEFAULT_DEVECO
    raise SystemExit('找不到 DevEco Studio：给 --deveco 或设 DEVECO_HOME')


def deveco_cli_paths(home: Path) -> tuple[Path, Path, Path]:
    """Resolve DevEco Studio or official command-line layouts without copying SDKs."""
    home = Path(home)
    suffix = '.bat' if os.name == 'nt' else ''
    layouts = (
        (home / 'tools' / 'hvigor' / 'bin' / ('hvigorw' + suffix),
         home / 'tools' / 'node', home / 'tools' / 'ohpm' / 'bin'),
        (home / 'bin' / ('hvigorw' + suffix),
         home / 'tool' / 'node', home / 'bin'),
        (home / 'hvigor' / 'bin' / ('hvigorw' + suffix),
         home / 'node', home / 'ohpm' / 'bin'),
    )
    for hvigor, node_home, ohpm_bin in layouts:
        node_bin = node_home / 'bin' if (node_home / 'bin').is_dir() else node_home
        node = node_bin / ('node.exe' if os.name == 'nt' else 'node')
        if hvigor.is_file() and node.is_file() and ohpm_bin.is_dir() and (home / 'sdk').is_dir():
            return hvigor, node_home, ohpm_bin
    raise SystemExit(f'找不到完整 DevEco/Command Line Tools 工具布局：{home}')


def project_python(root: Path) -> Path:
    """Use the project's host virtualenv when present on either desktop OS."""
    relative = ('Scripts', 'python.exe') if os.name == 'nt' else ('bin', 'python')
    candidate = root / 'build' / 'venv' / relative[0] / relative[1]
    return candidate if candidate.is_file() else Path(sys.executable)


def native_learner(root: Path, generation: dict) -> Path:
    """A host learner is native Linux ELF or Windows EXE, never an OHOS binary."""
    name = 'saturn.exe' if os.name == 'nt' else 'saturn'
    return root / 'build' / generation['recomp'].split('/')[0] / 'recomp-build' / name


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
    page_switch = PROJECT / 'entry' / 'src' / 'main' / 'resources' / 'rawfile' / 'pal-selftest.txt'
    page_switch.parent.mkdir(parents=True, exist_ok=True)
    page_switch.write_text(on + '\n', encoding='utf-8', newline='\n')
    print(f'selftest.txt -> {on}')


def hdc_target(hdc: str, wanted: str | None) -> str:
    try:
        done = subprocess.run([hdc, 'list', 'targets', '-v'], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        raise SystemExit('hdc 设备查询失败或超时') from None
    if done.returncode:
        raise SystemExit(f'hdc 设备查询失败，退出码 {done.returncode}')
    online = []
    for line in done.stdout.splitlines():
        cols = line.split()
        if len(cols) >= 4 and cols[2] == 'Connected' and cols[0] not in online:
            online.append(cols[0])
    if wanted is not None:
        if wanted not in online:
            raise SystemExit('--device 指定的序列号不在线；不会改选其他设备')
        return wanted
    if not online:
        raise SystemExit('hdc 没有在线设备')
    if len(online) != 1:
        raise SystemExit('hdc 有多台在线设备；请用 --device 指定，不自动选择')
    return online[0]


def find_hdc(home: Path | None = None) -> str:
    found = shutil.which('hdc')
    if found:
        return found
    if home is None:
        home = deveco_home(None)
    hdc = home / 'sdk' / 'default' / 'openharmony' / 'toolchains' / ('hdc.exe' if os.name == 'nt' else 'hdc')
    if not hdc.is_file():
        raise SystemExit('找不到 hdc：加入 PATH，或用 --deveco 指定 DevEco Studio')
    return str(hdc)


def log_snapshot(hdc: str, device: str, timeout: int) -> None:
    """读取已有环形日志的一次快照；不安装、启动、清日志，也不声明属于哪一次运行。"""
    try:
        done = subprocess.run([hdc, '-t', device, 'shell', 'hilog', '-x'],
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise SystemExit('hilog 快照失败或超时；可在设备连通后单独重试 --logs') from None
    if done.returncode:
        raise SystemExit(f'hilog 快照失败，退出码 {done.returncode}')
    lines = [line for line in done.stdout.splitlines()
             if 'PAL/OHOS' in line or 'SDL/STARTUP' in line or ' SDL' in line]
    print('已有 hilog 环形缓冲区快照（可能含多次运行；未清空日志）：')
    if not lines:
        print('没有匹配的 PAL/SDL 日志；可能已被环形缓冲区覆盖。')
    for line in lines:
        print(line)


def print_sdl_revision() -> None:
    """只报告提交及是否有本地改动，不读远端 URL、签名配置或凭据。"""
    source = ROOT / 'third_party' / 'sdl3-src'
    if not (source / '.git').exists():
        print('SDL source revision: unavailable (not a Git checkout)')
        return
    try:
        rev = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=str(source),
                             capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5)
        sha = rev.stdout.strip()
        if rev.returncode or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', sha):
            print('SDL source revision: unavailable')
            return
        status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=normal'],
                                cwd=str(source), capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=5)
        state = 'unknown' if status.returncode else ('modified' if status.stdout.strip() else 'clean')
        print(f'SDL source revision: {sha}; worktree={state}')
    except (OSError, subprocess.TimeoutExpired):
        print('SDL source revision: unavailable')


def hap_snapshot() -> dict[Path, tuple[int, int, str]]:
    """记录产物身份，拒绝把上轮未变动的 signed HAP 当成本轮结果。"""
    result = {}
    for path in HAP_OUT.glob('*.hap'):
        if not path.is_file():
            continue
        stat = path.stat()
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        result[path] = (stat.st_mtime_ns, stat.st_size, digest.hexdigest())
    return result


def verify_required_ohos_ui(root: Path, runtime: Path = None) -> None:
    """Require the reviewed actual host source, after full manifest verification.

    The profile verifier already checks every helper/font hash and rejects mixed
    variants. This OHOS-only gate also rejects a self-consistent old variant.
    A version string or a matching manifest alone is never UI identity proof.
    """
    root = Path(root).resolve()
    runtime = Path(runtime) if runtime else root / 'build' / MAPPING['runtime']
    host = runtime / 'src' / 'host' / 'host.cpp'
    labels = runtime / 'src' / 'host' / 'host_menu_text.h'
    remedy = ('请使用当前仓库 tools/winbuild.py build --recompile（加速生成用 '
              '--pal-options）重新生成 runtime，确认成功后再构建 HAP；不会修改旧 runtime 或自动绕过校验。')
    if (runtime.resolve() != runtime or not runtime.is_dir() or
            any(p.is_symlink() or p.resolve() != p or not p.is_file() for p in (host, labels))):
        raise SystemExit('OHOS UI 缺件或路径不安全；' + remedy)
    source = host.read_bytes().replace(b'\r\n', b'\n')
    if b'#include "host_menu_text.h"' not in source:
        raise SystemExit('OHOS 不接受完整旧 UI runtime；' + remedy)
    digest = hashlib.sha256(source).hexdigest()
    if digest not in OHOS_HOST_UI_SHA256:
        raise SystemExit(f'OHOS UI v{OHOS_HOST_UI_VERSION} host.cpp 身份不符 '
                         f'(normalized_lf_sha256={digest})；' + remedy)
    print(f'OHOS host UI identity: v{OHOS_HOST_UI_VERSION}; host.cpp normalized_lf_sha256={digest}; PASS')


def verify_existing_runtime(root: Path, generation: dict = MAPPING) -> None:
    """只校验已生成的 runtime；缺 manifest 时禁止走 prepare 的注入分支。"""
    root = Path(root).resolve()
    recomp = root / 'build' / generation['recomp']
    runtime = root / 'build' / generation['runtime']
    manifest = recomp / generation['manifest']
    if manifest.is_symlink() or manifest.resolve() != manifest or not manifest.is_file():
        raise SystemExit(f'缺少或不安全的 {generation["manifest"]}；请先重新生成 runtime，不会自动注入。')
    # 普通 import 使用本脚本所在 tools 目录；不生成新的字节码缓存。
    bytecode_setting = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        planner = __import__(generation['planner'])
    except ImportError:
        raise SystemExit(f'无法导入本仓库的 {generation["planner"]}；请更新 tools 后重新生成。') from None
    finally:
        sys.dont_write_bytecode = bytecode_setting
    source = getattr(planner, '__file__', None)
    if source is None or Path(source).resolve() != (root / 'tools' / f'{generation["planner"]}.py').resolve():
        raise SystemExit(f'拒绝使用其他目录的 {generation["planner"]}；请从本仓库启动。')
    try:
        # Both planners no-op on a generation that is already current; verify_only keeps the
        # accelerated one from being injected here when it is stale.
        if generation['planner'] == 'pal_options':
            planner.prepare_options(recomp, runtime, root, verify_only=True)
        else:
            planner.prepare_keyboard(recomp, runtime, root, verify_only=True)
        verify_required_ohos_ui(root, runtime)
    except (OSError, ValueError) as error:
        raise SystemExit(f'现有 runtime 校验失败；请先重新生成再打包'
                         f'（Windows: tools/winbuild.py build；Linux: python -m saturnrecomp.build）：{error}') from None
    print(f'Existing {generation["planner"]} runtime version/hash verification: PASS')


def verify_movie_hook(root: Path, generation: dict = MAPPING) -> None:
    """The registry implementation and generated callsite are both required."""
    root = Path(root).resolve()
    import re
    hook = re.compile(r"\bsh2_hook\s*\(\s*c\s*,\s*0x06021[Cc]1[Ee][uU]?\s*\)")
    sources = sorted((root / 'build' / generation['recomp']).glob('p_true_*.cpp'))
    found = []
    for source in sources:
        if source.is_symlink() or source.resolve() != source:
            raise SystemExit('TRUE generated source path is unsafe; regenerate before HAP build.')
        text = source.read_text(encoding='utf-8')
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        if hook.search(text):
            found.append(source.name)
    if len(found) != 1:
        raise SystemExit('Missing or ambiguous TRUE movie-cache hook 06021C1E; run winbuild.py build --recompile before --skip-learn. Refusing a stale HAP.')
    print('PAL generated movie hook: 06021C1E present in ' + found[0])


def drop_stale_native_caches(runtime: Path) -> int:
    """Discard a recorded SATURN_RUNTIME that no longer matches the generation being packaged.

    hvigor reuses entry/.cxx/**/CMakeCache.txt, and a CACHE default cannot replace the value already
    in it, so switching generation would otherwise fail the entry's identity check until someone
    deletes the cache by hand. Only a cache that disagrees is dropped; a matching one is kept.
    """
    import re
    dropped = 0
    for cache in (PROJECT / 'entry' / '.cxx').rglob('CMakeCache.txt'):
        if cache.is_symlink():
            continue
        recorded = re.search(r'^SATURN_RUNTIME:PATH=(.*)$', cache.read_text(encoding='utf-8', errors='replace'),
                             re.M)
        if recorded and recorded.group(1).replace('\\', '/') != runtime.as_posix():
            cache.unlink()
            dropped += 1
    return dropped


def write_generation_pointer(generation: dict) -> None:
    """Tell the entry CMake which generation ohosbuild just verified.

    The entry refuses a SATURN_RUNTIME that differs from what was verified, so the two have to agree
    by construction: this file is the single place that says which pair of directories the HAP is
    compiled from. Removing it puts the entry back on the mapping generation.
    """
    pointer = ROOT / 'build' / GENERATION_POINTER_NAME
    if generation is MAPPING:
        pointer.unlink(missing_ok=True)
        print('OHOS generation: build/recomp (mapping, original timing)')
        return
    runtime = ROOT / 'build' / generation['runtime']
    pointer.write_text(
        '# written by tools/ohosbuild.py; do not edit - the pair below is what the manifest was verified against\n'
        f'set(PAL_OHOS_RECOMP "{(ROOT / "build" / generation["recomp"]).as_posix()}")\n'
        f'set(PAL_OHOS_RUNTIME "{runtime.as_posix()}")\n',
        encoding='utf-8', newline='\n')
    stale = drop_stale_native_caches(runtime)
    print(f'OHOS generation: {generation["recomp"]} (accelerated); pointer {pointer.name}'
          + (f'; dropped {stale} stale native cache(s)' if stale else ''))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--deveco', type=Path, default=None)
    ap.add_argument('--skip-learn', action='store_true', help='沿用已有生成；仍需通过 runtime 版本/哈希校验')
    ap.add_argument('--speed', choices=('accelerated', 'mapping'), default='accelerated',
                    help='打包用哪一份生成：accelerated（默认，与 Windows 发行包同一份，含施法准备/法术动画/读盘提速）'
                         '或 mapping（原始节奏，只带键盘映射）')
    ap.add_argument('--install', action='store_true', help='构建后用 hdc 安装（要求已签名）')
    ap.add_argument('--selftest', choices=('on', 'off'), help='真机自测：on 就打一张合成盘验 SDL 窗口')
    ap.add_argument('--device', help='hdc 在线序列号；单台在线自动选，多台必须指定')
    ap.add_argument('--launch', action='store_true', help='装完启动并回打 hilog（隐含 --install）')
    ap.add_argument('--build-mode', choices=('debug', 'release'), default='release',
                    help='hvigor 构建模式，默认 release；实际 native 旗标仍需核查')
    ap.add_argument('--logs', action='store_true', help='只取已有 hilog 快照，不构建/安装/启动/清日志')
    ap.add_argument('--log-timeout', type=int, default=30, help='一次 hilog 快照超时秒数（1–120）')
    args = ap.parse_args(argv)
    if not 1 <= args.log_timeout <= 120:
        ap.error('--log-timeout 必须在 1–120 秒之间')
    if args.logs:
        if args.install or args.launch or args.selftest or args.skip_learn:
            ap.error('--logs 是独立快照，不能与 --install/--launch/--selftest/--skip-learn 合用')
        hdc = find_hdc(args.deveco)
        log_snapshot(hdc, hdc_target(hdc, args.device), args.log_timeout)
        return 0

    set_selftest(args.selftest)
    home = deveco_home(args.deveco)
    hvigor, node_home, ohpm_bin = deveco_cli_paths(home)
    node_bin = node_home / 'bin' if (node_home / 'bin').is_dir() else node_home
    env = dict(os.environ)
    env['DEVECO_SDK_HOME'] = str(home / 'sdk')
    env['NODE_HOME'] = str(node_home)
    env['DEVECO_NODE_HOME'] = str(node_home)
    env['PATH'] = os.pathsep.join([str(node_bin), str(ohpm_bin),
                                   str(hvigor.parent), env.get('PATH', '')])

    python = project_python(ROOT)
    generation = ACCELERATED if args.speed == 'accelerated' else MAPPING
    if not args.skip_learn:
        command = [python, ROOT / 'tools' / 'winbuild.py', 'learn']
        if generation is ACCELERATED:
            command.append('--pal-options')
            learner = native_learner(ROOT, ACCELERATED)
            if not learner.is_file():
                raise SystemExit('加速生成还没有可运行的学习器；先跑 '
                                 'tools/winbuild.py build --recompile --pal-options --sdl-dir <SDL3 cmake 目录>。')
        run(command, ROOT, env)
    verify_existing_runtime(ROOT, generation)
    verify_movie_hook(ROOT, generation)
    write_generation_pointer(generation)
    print_sdl_revision()
    print(f'hvigor mode: {args.build_mode}; 请核查实际 native 编译旗标，模式名不是优化证明。')
    before = hap_snapshot()
    run([hvigor, 'assembleHap', '--mode', 'module',
         '-p', 'product=default', '-p', f'buildMode={args.build_mode}', '--no-daemon'], PROJECT, env)

    after = hap_snapshot()
    haps = sorted(path for path, identity in after.items()
                  if identity[1] > 0 and before.get(path) != identity)
    if not haps:
        raise SystemExit('没有本轮新建或变更的非空 HAP；拒绝拾取旧产物。请核查 hvigor 的输出或执行干净构建。')
    for h in haps:
        print(f'  {h.name}  {h.stat().st_size:,} 字节')
    signed = [h for h in haps if 'signed' in h.name and 'unsigned' not in h.name]
    if not signed:
        print('未签名，装不了真机：在 DevEco Studio 的 Signing Configs 里自动生成签名后重跑。')
    if args.install or args.launch:
        if len(signed) != 1:
            raise SystemExit('本轮必须恰有一个 signed HAP 才能安装；未签名或多个候选时不猜选。')
        hdc = find_hdc(home)
        device = hdc_target(hdc, args.device)
        run([hdc, '-t', device, 'install', '-r', str(signed[0])], ROOT, env)
        if args.launch:
            run([hdc, '-t', device, 'shell', 'aa', 'start', '-a', 'EntryAbility', '-b', BUNDLE], ROOT, env)
            time.sleep(6)
            log_snapshot(hdc, device, args.log_timeout)
            print('以上仅启动后快照；游戏 Quit 后单独运行 --logs --device DEVICE 取结束统计，无需重新安装。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
