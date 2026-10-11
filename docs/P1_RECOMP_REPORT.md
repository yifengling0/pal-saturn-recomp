# P1 Windows 可运行性验证报告

日期：2026-10-10 　平台：Windows 11 x64 　上游：`saturn-recomp` 固定提交 `086c372`
＋ 本仓库 `patches/0001-cdrom-is-audio-per-track.patch`（光盘模型）、
`0002-watch-fold-wram-mirrors.patch`（`--watch` 别名折叠）、`0003-call-into-swapped-module-returns.patch`
（装载器 `jsr` 进程序后允许返回）；子模块工作树除这三处补丁外干净、LF 原样。

结论先说：**土星真盘在这台 Windows 机器上以本机重编译码启动，已经从光盘依次换入并执行
PROG.BIN → TRUE.BIN → 再回到 PROG.BIN，片头 logo、山峦云海影片与俯视角地图三幕都真正出了图**
（图证 `build/run/dump-title/`、`dump-movie/`、`dump-map/`，取证方法见 §5）。
但**游戏还不能算可玩**：片头放完、PROG 于 VB4886 换回之后，VDP2 VRAM 被清空且再没填回去，
画面永久停在黑屏 + 一个 VDP1 人物上，11 个键逐个按过都无响应 —— 这就是当前硬阻塞 `PAL-P1-009`（§4.8）。
另外两条仍未成立：进地图的输入序列还没简化到能说明每个键的作用；
人物坐标与位移量一次都没测（那是 P2 的第一步）。
今天闭环的点号阻塞：`PAL-P1-001`（光盘混合模式 CUE，§4）、`PAL-P1-005`（watch 别名，§4.3）、
`PAL-P1-006`（同址换入 TRUE.BIN 未声明，§4.5）、`PAL-P1-007`（程序返回被当致命，§4.6）；
`PAL-P1-008`（VDP2 SCRCTL 致黑）**本轮撤回**，由 `PAL-P1-009` 取代（§4.7/§4.8）。


---

## 1. Windows 工具链：实测通过的部分

| 检查 | 上游原命令 | Windows 结果 |
|---|---|---|
| 上游 Python 测试 | `uv run pytest -q` | **200 通过 / 6 失败**，6 项失败全部是 Windows 平台缺陷（见 §2），不涉及重编译器与光盘码 |
| SH-2 指令自测（合成程序+向量） | `recomp --optest` + `selftest` | **775 functions / 9300 vectors / 0 failures**（本机 x86-64 原生执行） |
| 运行时单元测试 | `cmake -S runtime/tests` + `runtime_tests` | **44 tests, 0 failed**；`SATURN_VDP1_GPL=ON` 变体同样 **44 tests, 0 failed**（`evidence/p0-runtime-tests*.log`，退出码 0）。需要 §2 的两处垫片才能编出来 |
| 重编译产物 | `python -m saturnrecomp.build game.toml` | 3 个模块：P0 513 函数 / PROG 1,009 函数 / TRUE 759 函数，共 2,281 函数 209,274 指令，31 个 .cpp，链接出 `saturn.exe` |
| 真盘读取 | `disc --info/--list/--manifest/--extract` | 全部退出码 0，见 `P0_DISC_ANALYSIS.md` |

编译器选择：本机无 MSVC。用 Strawberry 的 **g++ 13.1（MinGW-w64, C++20）**，
`cmake -G Ninja`。**上游发布用的 clang 在这里可用（configure 能过），但上游发布路径依赖 MSVC 库**，本记录只用 g++ 实测。

## 2. 已定位并处理的 Windows 缺口（都是平台层，不是土星硬件层）

1. **`prereqs.check()` 硬编码 "Windows is not supported yet"**，而 `build.recompile()` 见到任何问题就中止，
   于是 `saturnrecomp.build` / `saturnrecomp.learn` 在 Windows 上根本不肯跑。
   → 处理：不改上游，项目层驱动 `tools/winbuild.py` **重新执行同一批前置检查**（cmake、ninja、
   C++20 编译器经 CMake 实测、SDL3 是否存在），用实测结论替换平台标签；SDL3 缺失按无头构建处理。
   依据：上游自身的发布工作流会编译 `windows-x64`（`playtest-release.yml` 的 `windows-latest` + `ilammy/msvc-dev-cmd`），
   说明平台可行，缺的是通过这两个假设的 Windows 路径。
2. **`build.recompile()` 写死 `-DCMAKE_CXX_COMPILER=clang++` 且不做静态链接**：
   Git for Windows 自带 `/mingw64/bin/libstdc++-6.dll`，会盖掉构建该 exe 的工具链的 DLL，进程加载即
   `0xC0000139`（STATUS_ENTRYPOINT_NOT_FOUND，退出 127）。
   → 处理：驱动里用本机编译器并加 `-DCMAKE_CXX_FLAGS=-static -DCMAKE_EXE_LINKER_FLAGS=-static`。
   顺带满足 P3 的"在没有开发环境的 Windows 机器上能启动"。
3. **`runtime/tests/bup_test.cpp` 用 POSIX `setenv`**，MinGW 没有；且它传 `path::c_str()`（Windows 下是 `wchar_t*`），
   而运行时在 Windows 读 `%APPDATA%` 而非 `XDG_DATA_HOME`（`bios.cpp: sat_data_dir`）。
   → 处理：`tools/wincompat.h` 由 `check_windows.sh` 对**测试构建**强制 include，把两个环境变量都设上，
   使这两项测试真的走 Windows 分支。重编译器与运行时不依赖它。
4. **`saturnrecomp.agent` 无法在 Windows 使用**：`agent.py` 用 `subprocess pass_fds` 把描述符交给子进程，
   Python 在 Windows 直接 `AssertionError: pass_fds not supported on Windows`（`test_agent.py` 4 项失败即此）。
   影响面：交互式机器人（逐步 VBlank、按手柄、读写内存、取帧）在 Windows 不可用。
   → 现阶段处理：P2 的测量改走**命令行自动化通道**（`--input @FILE`、`--watch`、`--peek`、`--shot`、`--trace`、
   `--coverage`、游戏层 hook），已验证可用；`test_playtest.py` 的 1 项失败同源（Windows 的进程/管道限制）。
   待办（P3 之前）：给 OHOS/Windows 都能用的句柄传递方案，或把 `--agent` 端口改为命名管道/本地 socket。
5. **`prereqs.probe()` 在 GBK 环境崩**：`subprocess(..., text=True)` 用本地编码解码 cmake 输出，
   遇非 GBK 字节抛 `UnicodeDecodeError`，且 `r.stdout` 为 None 时继续拼接 → `TypeError`。
   → 驱动里改为 `encoding="utf-8", errors="replace"` 后取尾部。
6. **git `core.autocrlf=true` 破坏已审查哈希**：checkout 时把 `disc.py` 转成 CRLF（513 处），
   `validation` 的 `toolchain_identity` 阶段判 `disc.py hash mismatch`。
   → 处理：`core.autocrlf=false` 后重新 clone 到同一固定提交，`disc.py` 的 SHA-256 与上一提交的审查值
   `3a63f6c4…20b6e` 重新吻合，`validation` 全流程转绿。**OHOS/Linux 与 Windows 之间共享工程时必须固定 LF**
   （建议仓库加 `.gitattributes: * text=auto eol=lf`）。
7. CMake/Ninja 的**陈旧缓存**会让 `ninja` 报 `missing .../CMakeFiles/selftest.exe, needed by saturn.exe`：
   改过 flags 后请删掉 `build/check` 重新配置（脚本已如此）。
8. 路径形态：MSYS 的 `/c/...` 传给原生 g++ 打不开，`-include` 之类必须用 `pwd -W` 的 `C:/...` 形式。

## 3. 真盘在本机码上的实际推进

### 3.0 修复 `PAL-P1-001` 之后（2026-10-10，`evidence/p1-boot-003.log`、`p1-boot-005.log`）

```
[  0.000] IP.BIN: T-37401H  V1.000, areas JT ; 1st read file 0, 53068 bytes at 06004000
[  0.000] boot: P0 at 06004000
[  0.184] PALDIAG 06004334 vb=11 r0=0x0000002E      ← 查询不再返回 -8；装载请求被接受
[  0.184] PALDIAG 06004EB0 vb=11                   ← 搬运例程第一次真的被调用（此前整轮 0 次）
[  0.838] PALDIAG 06004364 vb=50 r0=0x00061A70      ← 搬运结果写回
[  0.838] PROG activated by a call to 06020040       ← 注意：括号里的"data differs from the image's"消失
                                                       即 0x06020000 处的 RAM 与盘上 PROG.BIN 逐字节相同
[  0.918] PALDIAG 06059C34 vb=55                    ← PROG 自己的代码在跑
[ 20.017] stopped after 1200 VBlanks, 639 VDP1 frame changes, 639 draws   （无 FATAL）
[ 20.691] program start 1: (same module) at 06020000
[ 20.769] FATAL call to 0000001E … (from pr 06059C3E)   ← 新的阻塞点，见 §4.3
```

关键判据是第 4 行：运行时只在"目标 RAM 与映像文件不一致"时才打那句警告；
警告消失 = **PROG.BIN 由模拟 CD Block 从光盘真实读进 0x06020000 且校验一致**，
随后 1150 帧执行的是 PROG 自己的重编译码。**这是本项目的第一个"真盘主程序在本机码上连续运行"的证据。**

### 3.1 修复之前（存档，`evidence/p1-boot-002.log`）

```
[  0.084] CD-DA: play track 1, FAD 166-167   ← 错误地把数据区当音轨（根因见 §4）
[ 13.730] PALDIAG 06004334 vb=823 r0=FFFFFFF8 (-8)
[ 13.730] PROG activated by a call to 06020040 (its data differs from the image's)
[ 13.811] FATAL call to 00000000 … (from pr 060600F2)   ← 在未装载的 RAM 上执行 P0 残留字节
```

### 3.2 画面证据（早期全黑，已被 §3.3 取代）

`--headless --save - --out build/run/p1-long-001 --shot 1200,2000,2800,3590`：
只有 VB 1200 之前存活，`shot-1200.png` 的 MD5 仍是 `c0b615e846211c2afbeafc99d980a1d1`（全黑、320×224），
同期 `639 VDP1 frame changes, 639 draws`。硬件寄存器统计（`build/run/p1-fix-001/hw-log.txt`）显示
**PROG 每帧把 146 个 VDP2 寄存器全部写一遍**（含 BGON@0x20、BCR@0x30、 scroll 寄存器，各 627 次），
所以"游戏没有配背景"这一假设已被排除；黑屏与 `VDP2: RBG0/RBG1 (0013) is not done`（VB 1200 触发）
同时出现 —— **当时标为待验证**，因为 BGON=0x0013 打开的是 NBG0+NBG1+RBG0，运行时明说 RBG 未实现。
**本节的两条怀疑都被 §3.3 推翻**：黑屏的直接原因是"根本没在跑换入镜像的码"（PAL-P1-006），
补上 TRUE 模块后同一套 VDP2 代码直接出图。但 `is not done` 并没有消失，只是换了条目：
进入影片幕时打的是 `VDP2: line or vertical cell scroll (SCRCTL) (0002) is not done`（§4.7）。

### 3.3 声明 TRUE 模块 + 允许程序返回之后（2026-10-10，**已进入地图**）

`evidence/p1-map-001/run.log`（`--vblanks 4100 --input @build/input-walk2.txt --shot …`）：

```
[  0.000] IP.BIN: T-37401H  V1.000, areas JT ; 1st read file 0, 53068 bytes at 06004000
[  0.000] boot: P0 at 06004000
[  0.838] PROG activated by a call to 06020040
[ 20.691] program start 1: TRUE at 06020000        ← 换入镜像被运行时识别（打 0003 补丁后改为普通调用，见 §4.6）
[ 25.023] pad: 0800 / [26.691] pad: 0400           ← SMPC 每帧被请求一次，按键被读到
[ 26.960] PALDIAG 06004206 vb=1616                 ← TRUE 的码 rts 回 P0 的装载循环
[ 28.148] PROG activated by a call to 06020040      ← 装载器再次装入并进入 PROG
[ 68.398] stopped after 4100 VBlanks, 3152 VDP1 frame changes, 3152 draws   （无 FATAL）
```

画面（`evidence/p1-map-001/`，全部 320×224 PNG，非黑）：

| 文件 | VBlank | 内容（**只描述画面，不归因于按键**，理由见下） |
|---|---|---|
| `shot-3000-first-map.png` | 3000 | **俯视角地图**：人物站在土路上，左下有石块，四周草丛/树缘 |
| `shot-3200.png` | 3200 | 同一地图，人物朝向改变 |
| `shot-3600.png` | 3600 | 人物位置变化，地面出现第二块石与一根道具 |
| `shot-4050.png` | 4050 | **整幅换成蓝紫色石面/水面的新场景**——发生了一次场景切换 |

六张 `--shot` 的 MD5 互不相同（`579575c0…/db25a373…/418af3e4…/99a043b1…/3806fe3f…/dcea775b…`），画面确实在推进。

**但"人物响应方向输入"这一条被随后的实测否掉了**，不得按上面那张表下结论：

- 采样方法：同一最小序列跑三次，只在 VB3100-3400 分别不按键 / 长按 UP / 长按 LEFT，
  在 VB3500 用 `--peek 06000000:262144` 把整个 1 MiB 高工作 RAM 吐出来逐字比对。
- 结果：**三次的 1 MiB 只有 3 个字不同**（`0x0600C8C0`、`0x06034348`、`0x0605CFCC`，
  值 12552000/12552300/12552500，随运行时长变化的一个计时/随机量），
  **没有任何一个单元随 UP 或 LEFT 变化** → 这一幕里方向输入不改变任何游戏状态。
- 同一判据在 VB2650-2860 方向长按也是零差异（`evidence/p1-map-001/`、`build/pos-*.log`）。
- 结论（已验证部分）：地图能画出来、人物会做动作（VB3400 举剑、VB3600 位置变化），
  但那是**脚本演出**；结论（待验证部分）：什么时候才交接给玩家操作，未测出。
  所以本报告不使用"人物响应方向输入"这一说法，Gate P1 的这一判据**仍未满足**（见 §6）。

## 4. `PAL-P1-001` 已解决：根因在上游光盘模型（混合模式单文件 CUE）

### 4.1 定位过程（全部实测，命令见 §5）

装载链的判定被逐层拆开，每一层都用 `[[hook]]` + `--watch` + `--trace` 证实或否证，
最终沿"哪个返回值不满足"走到唯一未满足的原始条件：

| 步骤 | 手段 | 实测结果 |
|---|---|---|
| 装载请求的槽位登记 | hook `06004758` 入口/`060047B8` 写回 | 参数 `r4=2`（槽位）、`r5=0x06017A90`；`mov.l r10,@r9` 真的执行，`[06018848]=0x06017A90` |
| 请求是否被登记为"可读" | hook `060057F8`、`060048EC` | `060057F8` 进入 1 次，**`060048EC` 0 次** → 链路断在 `060057F8` 内部 |
| 断在哪一条判定 | 反汇编 `06005802`：`mov.b @0x06000CCC` 与 1 比较 | 走"未初始化"分支（`bf/s → 06005854`），继而 `jsr 06005E50` |
| `06005E50` 的返回 | hook `06005876` | 60 帧内**从未返回** → 卡在它的第一个子调用 `06005D5C` |
| `06005D5C` 在等什么 | `--trace` 的 CD 命令流（`evidence/p1-trace-cd-001.log`） | 游戏发 `cmd 10`（Play）读 FAD 166-167，随后 **`cmd 00`(Get Status) 与 `cmd 51`(Get Part Size) 各十万次**，`51` 的答始终 `out[3]=0` → 扇区从未进入缓冲 |
| 为什么进不去 | 读 `runtime/src/machine/{cdrom,cdblock}.cpp` + `--trace` 首行 | 出现 `CD-DA: play track 1, FAD 166-167`：FAD 166（=LBA 16，数据轨）**被判定为音轨**，于是 `g_audio_play=true`，`cd_tick()` 只走音频分支，`deliver_sector()` 永不被调 |

结构性原因（`cdrom.cpp`，固定提交 `086c372`）：`CueFile` 只有一个 `audio` 标志，
但解析器在**每一条 `TRACK` 行**都执行 `f.audio = cur_audio`（`f` 是"当前 FILE"）。
本盘是土星rips 常见的**一个 BIN 里 13 条轨**（1 条 MODE1/2352 + 12 条 AUDIO），
于是最后一条 AUDIO 把整个文件的 `audio` 置为 `true`，数据区被当成音轨；
`cdrom_is_audio()` 读的就是这个文件级标志。同一文件的 TOC 侧（`CueTrack::audio` →
`ctrladr` 0x41/0x01）本来就是按轨存的，因此**运行时内部自相矛盾**，可判定是缺陷而非设计。

### 4.2 修复与验证

- 改动：`cdrom_is_audio(fad)` 改为"取起始地址不超过 fad 的最后一条轨"的轨级判定。
  上游子模块工作树保持固定提交，改动以补丁形式入库：`patches/0001-cdrom-is-audio-per-track.patch`（20 行）。
- 为什么不算"为单个游戏破坏上游通用硬件行为"：它只修光盘描述模型，不动任何寄存器时序；
  对"一条轨一个 FILE"的常规 CUE，文件只对应一条轨，新旧判定结果**完全一致**（无行为变化）。
- 回归（同一命令、同一台机器，`evidence/p1-check-after-cuefix.log`，`SCRIPT_EXIT=0`）：
  Python `200 passed / 6 failed`（6 项与修复前逐条相同，均为 §2 的 Windows 平台缺陷）；
  `optest 775 functions, 9300 vectors, 0 failures`；运行时测试 `44 tests, 0 failed`（默认与 `SATURN_VDP1_GPL=ON` 两种）。
- 正向验证：修复后 `--trace` 第一处变化就是 `CD: read FAD 166-167 into filter 0`（不再是 CD-DA），
  紧接着出现 `cmd 61`（Get Sector Data）、`cmd 62`（Delete），并连续读取 FAD 170-172、201-397 ——
  即游戏真的开始从盘上取数据；随后 `PROG activated` 的警告消失、PROG 连续执行 1150 帧（§3.0）。
- 上游测试缺口：`tests/` 里没有"单文件多轨混合模式 CUE"的用例（`test_disc.py:41` 只有单条 AUDIO），
  所以该缺陷不被现有测试覆盖。建议上游补一条；本仓库先以补丁 + 复现命令记录。

### 4.3 `PAL-P1-006` 的定位过程：BIOS 服务向量 0xD1 被游戏数据覆盖（结论见 §4.5）

`jsr @r1`（`PROG:06059C3A`，`r1=[0x06000344]`，即运行时命名为 `SYS_CHGSCUIM` 的服务槽）取到 `0x0000001E`
而 FATAL。实测事实：

- 启动时 `bios.cpp` 把 `0x06000344` 写成 `0x00001344`（`--watch` 可见，VBlank 0，全轮仅此一次写入）；
- 同一段代码在 **VB 55、VB 59 两次执行时槽位仍是 `0x00001344`** 并正常返回（hook `06059C34` + `PAL_DUMP`）；
- 到 `20.769`（"program start 1" 之后）槽位区变成周期性模式：
  `[06000320]=0000001E [06000324]=25CAB360 [06000328]=00001328 [0600032C]=0000001E [06000330]=25CAB380 …`
  —— 以 12 字节为步长写每条记录的前两个字段，`0x25CAB360/80/A0/C0` 是 VDP1 帧缓冲（cache-through 别名）指针；
- 因此这是**数据表撞进了运行时会当成 BIOS 服务向量的地址区间**；
- `--watch 06000344` 整轮只报出一次写（启动那次）：说明写它的指令用的是**别的地址别名**，
  而 store watch 是按**原始地址**区间比较的（`core.cpp` 里 WRAM-H 会按 `& 0xFFFFF` 回绕到同一片 RAM）——
  **现有 watch 看不到别名写**，这是本次调查中确认的第 2 个工具缺口。

下一步（尚未做，顺序即优先级）：① 让 watch 对 WRAM 别名归一化后再点出写入者；
② 判定真机 BIOS 的服务指针区间到底是 `0x06000200-0x060003FF` 还是更窄（若游戏合法使用 0x06000320 起的数据区，
则需要收窄运行时的占位区间而不是改游戏）；③ 在此之前不要把 FATAL 归因到"游戏有问题"。

### 4.4 调查中更正的两条早期结论（避免以后误用）

1. `0x25890008` **不是 SMPC 状态**，按 `hw.py` 是 **CD Block 的 HIRQ**（区 0x05800000-0x05900000 的 +0x90008）。
   `f_060045CC` 是"等 HIRQ 掩码"的原语，实测它返回 0（成功），此前"它返回 -1/-2/-5 卡住"的推测**不成立**。
2. 上一提交对本报告的早期版本里"`--watch` 报 `?:00000000` 就是运行时内部写的"要加限定：
   `host_function()` 只按宿主函数入口地址做上界查找，**归属解析本身不精确**；
   已实测到一条确实由 SH-2 指令（`P0:060047B8`）完成的 store 被打成 `?:00000000`。
   同理，SH-2 的 `tst` 是"为 0 则 T=1"（本次一度因此误判分支方向），后续记录以实测分支为准。

### 4.5 `PAL-P1-006` 已解决：游戏在 0x06020000 处把 PROG.BIN 换入成 TRUE.BIN

打了 0002 补丁（watch 比较折叠地址、报告原始地址）之后，覆写者当场现形：

```
[ 20.769 S] store32 06100324 = 25CAB360 in PROG:0605FD92 (pr 0605FE56, VBlank 1245)
[ 20.769 S] store32 06100320 = 0000001E in PROG:0605FD92 (pr 0605FE56, VBlank 1245)
   … 0610032C/30、06100338/3C、06100344/48 同样成对，随后 FATAL
```

即写入用的是 **WRAM-H 的 1 MiB 镜像别名 0x06100320**，折叠后正好落在 BIOS 服务槽上。逐环取证：

| 手段 | 实测结果 |
|---|---|
| 反汇编 `build/prog_full.asm` 0605FD92..0605FF82 | 该函数里唯一形状吻合的是 `0605FE64` 的循环：`st32(r3,r2=30)`、`st32(r3+4,r0)`、`r3+=12`、`bf/s`，基址 `r3=[0x060663D8]`、结束 `r1=r3+[0x06020088]` |
| hook `0605FE60`（`evidence/p1-true-004-loop-regs.log`） | VB55/59：`r3=060C0000 r1=060C4FF8`（长度 0x4FF8，1706 条，正常）；VB1245：`r3=060C0000 r1=0C100C40`（长度 0x06040C40，**失控 2 万余条**）——铺过 `0x060FFFFF` 后第一条落进窗口就是 `0x06100320`，与 watch 报出的地址/数值（`+32` 与 `+12` 步长同时吻合，第 21912 次迭代）完全一致 |
| `--watch 06020088:06020090`（`evidence/p1-true-001-watch-len.log`） | VB11 写入 `00004FF8/0001DFD0/00008000`、VB1227 写入 `06040C40/060552A0/06020E38`，写入者同为 `P0:06007E90`（pr `06007FDE`） |
| `PROG.BIN` 与 `TRUE.BIN` 文件同址字节 | PROG 的 0x88/0x8C/0x90 = `00004FF8/0001DFD0/00008000`；TRUE 的 = `06040C40/060552A0/06020E38` —— **逐字节相同** |
| hook `06007E96` 打印装载请求块（`evidence/p1-true-002/003`） | `[r9=0601875C] +00=06020000 +04=00021000 +18=00000042(=66 扇区)`，每块 0x800 字节、源 = CD 缓冲区 `0x25818000`；盘上唯一落在 (65,66] 扇区的文件是 **TRUE.BIN(134,200 B)** |

结论：**不是游戏数据有问题，也不是内存模型有问题，是 `game.toml` 少声明了一个同址换入的模块。**
处置只在配置层：新增 `[[module]] TRUE`（base `0x06020000`，seed `0x06020058` 取自 TRUE 镜像头部 `[0x24]`，
与 PROG 的 `0x06020040` 同一字段，不是猜的）。之后运行时自己打出
`program start 1: TRUE at 06020000`，画面立刻从全黑变成开场地球（`MD5 f4f674fd69ab30268b692bb8049e74f0`，
215 KB PNG），`--vblanks 3000` 无 FATAL，68000 也起来了（`68000 on, pc 0010DA`，非静音样本 73 万）。
`learn` 只需一轮（seed `TRUE 0603548C`）即跑满 3000 帧（`evidence/p1-true-007-learn-002.log`）。

### 4.6 `PAL-P1-007` 已解决：装载器是 `jsr` 进程序，程序会 `rts` 回来

地图画面出现前还差一步。`--trace` 显示游戏在 23.472 s 停止一切 CD 读与 SCU DMA（`evidence/p1-true-009-trace-3000.log`），
画面停在开场影片的最后一帧 —— 也就是**在等玩家**，不是死循环。按键之后立刻撞上游缺口：

```
[ 26.960 FATAL] the program at 06020000 returned
  cpu 0  pr 06004206  pc 06004206
```

`build/p0_full.asm` 证明这是游戏的正常控制流：

```
060041F6  mov.w @(0x0601FA00),r2 ; extu.w
060041FC  cmp/eq #7,r0
060041FE  bt 0x06004206
06004200  mov.l #0x06020000,r8
06004202  jsr @r8            ← 调用换入的程序，等它返回
06004206  mov #1,r6          ← 返回后继续装载循环（hook 打这里，实测 vb=1616 命中）
```

而 `core.cpp:182` 把"调用模块基址"一律当 program start：`sh2_program_start()` 抛 `ProgramStart`
展开宿主栈，P0 的栈帧没了，程序的 `rts` 无处可回 → 顶层函数返回即 FATAL。
`patches/0003-call-into-swapped-module-returns.patch`（14 行）：基址处镜像能识别为已知模块、
且该地址确有入口时，按普通嵌套调用处理（先 `sh2_activate` 再调用），否则保持原语义。
验证：同一输入序列下修复前 FATAL（`evidence/p1-map-001/p1-007-program-returned-fatal.log`）→
修复后 P0 于 28.148 s 重新 `PROG activated by a call to 06020040` 并进地图（§3.3）。
无输入的老路径不受影响（`shot-1800/2900` 仍是同一张地球，MD5 与修复前一致）。

上游测试缺口：`is_base` 的两种语义（jmp 式接管 vs jsr 式调用）没有用例区分，建议连 0001/0002 一起回流。

### 4.7 ~~新的点号阻塞 `PAL-P1-008`：影片幕要 VDP2 的行滚动/垂直单元滚动，运行时未实现~~（**本节结论已于 §4.8 撤回**）

> **撤回（2026-10-10）**：下面"该幕背景黑是因为 SCRCTL 未实现"的推断是错的。
> 用 `--dump` 取到那一帧的 VDP2 VRAM/CRAM/寄存器，再喂给一份独立复刻的合成器
> （`tools/vdp2_replay.js`），渲出的正是运行时自己拍到的那幅山峦云海
> （`build/run/replay-movie-default.png` vs `build/run/dump-movie/shot-3900.png`）。
> 这一幕 runtime 本来就画对了；`SCRCTL is not done` 只表示"某个效果被忽略"，不是黑屏原因。
> 真正的问题见 §4.8。本节保留作审计痕迹，其中寄存器数值仍然有效，只是**因果解释作废**。

最小按键序列（实测，见 §5）是 `VB1500 START`（结束开场影片）→ `VB2500 START` → `VB2600 A`（标题确认，VB2700 已是地图）。
继续用 A 每 120 帧推进，VB4000 是一张漩涡状的影片画面，VB5000 起变成**人物画在纯黑背景上**并停住。
这一幕里游戏并不僵：`--trace`（`evidence/p1-vdp2-002-trace-in-scene.log`）显示 t>84 s 的窗口里仍有
321 次完整读盘循环（`52/53/61/06/62`）、每帧一次 SCU 间接 DMA、VDP1 每帧出图 —— 也就是**数据在流、画面在画**，
只是合成出来的背景是黑的。

同一时刻运行时打出：

```
[ 100.931 M] VDP2: line or vertical cell scroll (SCRCTL) (0002) is not done
```

`vdp2.cpp` 只在**真正合成一帧**时做这个检查，所以必须带 `--shot` 才会出现（不带 `--shot` 的 6100 帧跑一次都没打，
这条本身是工具行为，别误读成"时好时坏"）。为拿到寄存器值，临时在 `note_unsupported()` 里加了一次性转储
（**已撤回，不进补丁**；`git diff --stat` 现在仍是 3 个文件），日志留在
`evidence/p1-vdp2-001-regdump.log`、`evidence/p1-vdp2-003-regs.txt`：

| 寄存器（上游 `hw.py` 的 VDP2 名字表定序） | 值 | 含义 |
|---|---|---|
| `0x00 TVMD` | 8100 | 显示开 |
| `0x04 SMRSTA` | 0002 | 行请求/滚动模式相关位非零 |
| `0x20 BGON` | 0043 | NBG0+NBG1 开，另有一位（按 BGON 位序是 RBG2）被运行时**静默忽略**（它只对 RBG0/RBG1 打提示） |
| `0x9A SCRCTL` | 0002 | 运行时明说未实现：行滚动 / 垂直单元滚动 |
| `0xA0/0xA2 LSTA0U/L` | 12F2/E08E | 游戏确实备好了一张**行滚动系数表** |
| `0x70..0x8E`（NBG0/NBG1 滚动与增量） | SCY=FFF4，SXINC=SYINC=1 | 两块普通滚动屏本身是配好的 |

旁证：这一幕的 `hw-log.txt` 里 `area W VDP2 VRAM 05E00000 05E7FFFE` 有 **419 万次写**，
即影片像素确实被搬进了 VDP2 VRAM；而人物（VDP1 层）正常显示。
所以最可能的解释是"该幕用行滚动/垂直单元滚动来铺影片，运行时不实现该模式 → 背景层出不来"。

**这条因果仍标为待验证**：必须实现 SCRCTL（并确认 BGON 中被静默忽略的那一位到底是什么）之后，
同一输入序列能取到非黑的影片画面，才算证明。在此之前不得宣称"补了 VDP2 就有画面"，
也不得把它当作"人物不响应方向键"的结论 —— 后者是独立事实：三次对照（不按键/UP/LEFT）在 1 MiB 里零差异（§3.3）。

### 4.8 `PAL-P1-009`：片头放完、PROG 换回之后 VDP2 VRAM 被清空且再没填回去（当前硬阻塞）

用 `--dump N`（VDP1 VRAM + VDP1 帧缓冲 + VDP1 寄存器 + VDP2 VRAM + CRAM + 寄存器，一次全出）
在多个 VBlank 上取整帧状态，再配一份离线复刻合成器，把"画面为什么黑"从猜测变成了分段测量。

**时间线（最小序列 `START@1500, START@2500, A@2600`）**

| VBlank | 状态 | 证据 |
|---|---|---|
| 700 | TTC 线框 logo 正常（VDP2 NBG0/NBG1 位图模式） | `build/run/dump-title/shot-700.png` + `dump-700.bin` |
| 1400 / 3900 | 山峦云海正常，50688/71680 像素由 NBG0 以 16M RGB 画出 | `build/run/dump-movie/shot-3900.png`，离线复刻 `replay-movie-default.png` 一致 |
| 2700-3350 | 俯视地图正常，VB3350 地上自己长出影子（场景在自走） | `build/run/dump-map/shot-2700.png`、`shots-min3/shot-3350.png` |
| **4886** | `PROG activated by a call to 06020040`（无 "data differs" 后缀 = CRC 与镜像逐字节相符） | `build/run/hook-copy-6200.log` |
| 6000 → 20000 | 纯黑 + 一个 VDP1 人物，永久停住 | `build/run/dump-black/shot-6000.png` == `shot-12000.png` == `shots-long2/shot-19900.png`（MD5 全等） |

**停滞幕的实测事实**

1. VDP2 寄存器就是 VB700 logo 那一套（`BGON=0x43`、`CHCTLA=0x1212`、`SCRCTL=0x0002`、`MPOFN=0x10`、`MPABN0=0x3B3B`），
   但 **VDP2 VRAM 只剩 640 / 524288 个非零字节**（VB3900 是 413646）。
2. VB6000 与 VB12000 的 VDP1 VRAM / VDP1 帧缓冲 / VDP2 VRAM / VDP2 CRAM **逐字节完全相同**
   （只有 VDP2 寄存器差 1 字节），而这段时间 hw-log 仍记着约 **1405 次/帧**的 VDP2 VRAM 写 → 反复写入的是同一份空数据。
3. 两幕的存储占用正好互补：地图/影片 = VDP2 满、VDP1 几乎空（293 字节）；停滞幕 = VDP1 有内容
   （VRAM 65697、帧缓冲 72359 非零字节）、VDP2 空。
4. **不是等键**：VB6000-9100 把 11 个键逐个按过（`build/mash-all.txt`），与不按键对照，
   VB7500/8500/9100 三帧 PNG MD5 完全一致。
5. **不是光盘**：`--trace` 6200 帧无 FATAL、无未实现命令，`51/52/53/61/06/62` 读循环 2734 轮仍在走；
   FAD→BIN 偏移映射独立校验过（LBA16 扇区内第 17 字节正是 `CD001`）。
6. **不是死锁**：`last polls in` 99% 落在 `PROG:0605D68A`，但 `--watch 060FFC10:060FFC18` 显示
   `gbr+19` 每 VBlank 被 `PROG:0605CECC` 递减（5→4→…→-1 后重装），一直减到 VB6199 ——
   那是 SEGA 声音驱动 Tick 的**等下一帧空转**，帧循环活着。

**三条被实测否掉的猜测**（都留了原始数据，防止以后重走）

- MPEG 卡：hw-log 里没有任何 `0588xxxx` 访问，盘里的 `A1-A6.AVI` 不经过这条路。
- SCU 定时器：重编译码里根本没有 `0x05FE0090/94/98`，`TIMER0/1`（向量 0x43/0x44）全程 0 次。
- SCSP→主 CPU 中断：`SOUND_REQ`（0x46）12050 帧 0 次，但实测游戏**从不写** `MCIEB(0x42A)`，
  只写 `SCIEB(0x41E)=0x0088`。临时给 `scsp.cpp` 加的写追踪证实了这点（**测完已撤回**，
  `git status` 仍是 3 个补丁文件，三张补丁 `apply --check --reverse` 全部一致）。
  runtime 的 SCSP 偏移与 yabause wiki 的 `SCIEB=0x10041E` / `MCIEB=0x10042A` 对得上，不是移植侧映射错。

**因此收窄成的问题**：PROG 第二次跑标题流程时，"把已经读到的数据搬进 VDP2 VRAM"那一步没有发生。
抓手：`--coverage` 两窗差集给出停滞段独有的 70 个 PROG 函数（`build/run/cov-4880.txt` vs `cov-6200.txt`），
其中 8 个是引用 `0x25E00000/0x25E20000/0x25E5C000` 的 VDP2 写函数
（`0602313C/060232A4/0602335C/06023914/0602475C/06024FD8/06026B88/06026D84`；`06026D84` 每帧都跑，
就是它把 `gbr+18` 置成 3/6 的），下一步用 `game.toml [[hook]]` 逐个下探针。
判据：VDP2 VRAM 非零字节从 640 回到 40 万级、同一最小序列下标题重新出图。

**顺手否掉的一个分支**：不是"源缓冲是零"。VB6200 时 `--peek 0607F800:16`
（VB4885-4886 那批 `25818000 → 0607F800/06080000/06080800…` 块拷贝的目的区）拿到的是成形的记录表
`00000017 0000A4BD 0000A4EF 00000000 00180000 … 00000019 0000A4BD 0000A3EF 001A0000`，不是空数据 ——
所以问题在"从这张表出发的那一步"，不在光盘搬运。

**再收窄（同一批 hook 的实测）**：给这 8 个函数入口挂 `[[hook]]`（`game.toml` 已入库，重编译 2283 函数）后，
命中窗口是 **VB4895 → VB5660**，之后到 VB6200 一次都不再命中：

| 探针 | 次数 | 首次 VB | 末次 VB |
|---|---|---|---|
| 06026B88 | 1 | 4895 | 4895 |
| 06023914 | 2 | 4929 | 5610 |
| 06026D84 | 1 | 5005 | 5005 |
| 0602475C | 2 | 5016 | 5626 |
| 060232A4 / 06024FD8 | 4 / 14 | 5025 | 5660 |
| 0602313C | 50 | 5052 | 5660 |
| 0602335C | 5 | 5121 | 5385 |

也就是说：换入 PROG 之后，场景/图形装配**确实整趟跑过一遍**（VB4895-5660），
而它结束的 VB5660 正好贴着 `--trace` 里最后一轮读盘（VB5663-5666，`cmd 10` 读 FAD 5334-5350 后 `play ended`）。
**从 VB5660 起游戏只剩帧循环 + 声音 Tick，再没有任何场景代码在跑。**
~~所以问题不再是"VRAM 为什么是空的"，而是"这趟装配跑完之后，游戏在等一个永不到来的事件"。~~
**这句结论已在 §4.9 被本轮实测推翻**（既不是"等事件"，也不只有"VRAM 空"这一件事）。

**顺带更正的记录口径**：VB2700-3800 地图幕里 UP/RIGHT/不按键三组的五帧 PNG 逐帧 MD5 相同，
但这一幕本身是自走脚本，**不能**当作"输入链路坏了"的证据；START/A 在标题处是有响应的。
（§4.9 进一步把"输入链路"这个候选整体作废。）

---

### 4.9 `PAL-P1-009` 第二次收窄：游戏是活的，缺的是这一幕的 VDP2 背景数据（当前口径）

§4.8 末尾把问题写成"装配跑完之后在等一个永不到来的事件"，并留下"SCSP→主 CPU 中断"这一个候选。
本轮把四条候选逐一实测，**四条全部否掉**，问题因此换了性质。临时诊断（`cdblock.cpp` 的
`CDHB/CDSTALL/CDROUTE` 三类打印）测完已 `git checkout --` 撤回，上游工作树回到"仅 3 处补丁"，
三处补丁 `git apply --check --reverse` 全部 OK。

**① 光盘没饿着。** 驱动器心跳（`--trace`，VB6200）：
`CDHB st=1 fad=5350 start=5334 end=5350 audio=0 dev=00 free=200 done=16 due=0 xfer=0 hirq=07D5`。
最后一次 `cmd 10 (1080 14D6 0080 0010)` 要 16 扇区，16 扇区全部投递、`CD: play ended at FAD 5350`，
游戏接着发 `cmd 48`（Reset Selector）就**再没碰过 CD，一直到 VB9000**。
`cmd 51`（Get Part Size）恒 0 是"读完并 delete"之后的正常终态——同一命令全程 81542 次轮询里有 448 次
答 `0xC8`=200，说明这条答复通路本身是对的。所以"投递太慢/分区恒空"不成立。

**② 声音中断不是等待条件。** 停滞全程主 CPU 对 SCSP 公共寄存器只写过**一个**：
`reg W 2 05B00400`（MVOL，4 次）；`MCIEB(0x42A)` 一次都没写。§4.8 留下的唯一候选作废。

**③ 主循环没卡死，是严格 6 VBlank 一周期的自走。**
`--watch 060FFC12:060FFC13 --watch-vblanks 5700:6200` 抓到（VB6192-6199 一段）：

```
VB6192  gbr+19 = FFFFFFFF → 05   (PROG:0605CECC, pr 06022354)   gbr+18 = 06 (PROG:06026D84, pr 06026E58)
VB6193  04   VB6194 03   VB6195 02   VB6196 01   VB6197 00   VB6198 FFFFFFFF → 05, gbr+18 = 06 …
```

500 帧里 668 次写入、周期严格 6 帧。所以 `last polls in PROG:0605D68A ×4052` 是声音/CD 驱动 Tick 的
**常规等待**，不是死锁。回调槽 `gbr+972 = 0x06060394`（`rts ; nop` 空桩）在健康段 VB55/59/67 也是同一个值，
它由驱动自己的初始化在 `0x0606036C-0x06060372` 装上，**不是异常**。

**④ 镜像、轨表、字面量池都干净。** 原始 `仙剑奇侠传（中）.mds` 的 TOC 里 12 条音轨 MSF
（track2 `1d:17:3f`、track3 `20:02:24` … track13 `34:14:2a`）与 `disc/pal_t37401h_13tr.cue` 的
`INDEX 01` **逐条吻合**（CUE 位置 = 绝对 MSF − 2 秒），运行时 `cdrom_open()` 再加回 150 → 轨边界正确；
抽样扇区的 BCD MSF 与其位置一致（LBA 5184 → `01 11 09`）；整盘全零数据段只有 150 扇区量级的引前空隙与常规填充。
`0x0605D77C` 这个被重编译期折成常量的池单元，镜像里与运行期 `--peek` 都是 `0x21000000`，
且由装载器 `P0:06007E90` 在 VB35 / VB1672 写入 → 不存在"池被运行期改写而常量过期"的错编。

**⑤ 输入是认的（§4.8 的"任何键都无响应"作废）。** 先前用 `mash-all.txt` 得到的"三帧 MD5 一致"是
**按键时点不对**造成的假阴性。用停滞幕时点重测（`build/holdup.txt`：`6000:UP` 一直按到 6500）：

| 帧号 | VB5950 | VB6000 | VB6100 | VB6200 | VB6300 | VB6400 | VB6500 |
|---|---|---|---|---|---|---|---|
| PNG MD5 前 8 位 | `471770e4` | `471770e4` | **`be3ff755`** | **`1f25ea67`** | `1f25ea67` | `1f25ea67` | `1f25ea67` |

人物在停滞幕里随方向键换了姿势与位置；`build/press2.txt`（6000:START / 6100:A / 6200:B / 6300:UP / 6400:A）
同样在 6400 之后换帧。反过来，每 40 帧猛按 A 从 VB6000 按到 VB12000（`build/run/pressA/shot-*.png` 六帧）
画面纹丝不动，所以它也不是"再按一下就过"的界面。

**⑥ 两幕的存储占用正好互补，指向很干净**（`--dump` 分段非零字节）：

| | VDP2 VRAM | VDP2 CRAM | VDP1 VRAM | VDP1 FB | 结论 |
|---|---|---|---|---|---|
| 地图幕 VB2700 | **413642** | 999 | 293 | **0** | 整幅画由 VDP2 出 |
| 停滞幕 VB6000 / VB12000 | **640** | 1011 | **65697** | **72359** | 只有 VDP1 人物，VDP2 背景从未被填 |

停滞幕的 VDP2 配置是 `BGON=0x0043`（NBG0 + NBG1 位图模式 + **RBG2**）、两层名称表全 0、
`SCRCTL=0x0002`、`CCCTL=0x0043`、`SPCTL=0x2122`。

**另记一条真缺口（与上面分开）**：`vdp2.cpp` 的 `note_unsupported()` 只测 `reg(0x20) & 0x30`（RBG0/RBG1），
**RBG2/RBG3（bit6/bit7）被静默忽略**，既不渲染也不提示。所以即便背景数据填进去，这一幕仍会缺一层。
它不是"数据没写入"的成因，修的时候也不要混为一谈。

**PAL-P1-009 的当前定义**：游戏活着、认键、主循环 6 帧一周自走；缺的是这一幕的 VDP2 背景数据，
而场景/图形装配的 8 个 hook 入口末次命中都在 VB5660 及以前。下一步查**场景脚本被什么条件门住**：
对主循环的两个返回点 `0x06022354`、`0x06026E58` 下 hook 打印脚本步序号与 `gbr+160..200`，
并弄清 `gbr+182` 那个每帧 +3734 的累加器是什么。判据不变：
同一最小序列下停滞幕的 VDP2 VRAM 非零字节从 640 回到 40 万级并出背景。
**已作废、不要再当根因的口径**：等声音中断、CD 饿着、主循环死锁、输入链路坏、镜像/轨表错、
字面量池过期、SCRCTL 导致黑屏。

### 4.10 `PAL-P1-009` 第四次收窄：P0 状态机把控制权交给了 PROG，是 PROG 自己不把状态推回 TRUE 那一档（当前口径）

2026-10-10 后半程。这一节**推翻 §4.9 的"场景/图形装配被门住"的框架**，并更正 §4.9 的两处读数。
全部证据是本轮实测：`build/run/{statewatch,flagwatch,queuewatch,loads2,gchain2,fchain,mashlong}.log`。

**① 先更正 §4.9 的两条错读（已验证）**

- `BGON=0x0043` 的位序是 bit0=RBG0、bit1=RBG1、bit2=RBG2、bit3=RBG3、bit4=NBG0…bit6=NBG2，
  所以 0x43 = **RBG0 + RBG1 + NBG2**，不是 §4.9 写的"NBG0 + NBG1 + RBG2"。
- `PNCN0=0x800C` 的 bit15 是 **SPCL（特殊显示模式）**，配上 `SCRCTL=0x0002` 与
  `LSTA0U/LSTA0L=0x12F2/0xE07C`（行表地址）→ 这一幕的 RBG0 走的是**行滚动特殊显示**，
  不是普通名称表。VDP2 VRAM 只剩 640 非零字节，恰好只够一张行表，像素数据一层都没有。

**② P0 主循环是一张状态表，不是"等事件"（已验证，静态解码）**

`build/disc-extract/0` 偏移 0x138（绝对 0x06004138）起 13 个字，`target = 0x06004138 + (int16)word`：

| `[0x0601FA00]` | 跳转目标 | 干什么 |
|---|---|---|
| 0,2,3,4,7,8 | `0x06004152` | 装载 `"PROG.BIN"`（字面量池 0x06004094）到 0x06020000，`jsr @0x06020040` |
| 1,5,6,9,11,12 | `0x060041CE` | 装载 `"TRUE.BIN"`（0x060040A0），`[0x0601FA00]!=7` 时 `jsr @0x06020000` |
| 10 以及 >12 | `0x06004254` | 空转 |

`mova` 折成常量 0x06004138 是对的：运行时 `gbr=0x060FFC00`，`gbr & 3 == 0`。

**③ 状态轨迹与装载序列一一对上（已验证）**

`--watch 0601FA00:0601FA01` 打到 0(VB5)→1(VB1173)→2(VB1501)→6(VB2505)→8(VB4707)；
`PAL_HOOKS=06007E96 PAL_DUMP=0601875C:32` 打到请求块序列
PROG(VB11) / TRUE(VB1227) / PROG(VB1648) / TRUE(VB2559) / **PROG(VB4847)**。
**三次 PROG.BIN 装载全部走完**：`+04=0x00062000`、`+18=0xC4`(196 扇区)，VB4886 时 `+08=0x00061800`、
`+1C=0xC3` → 末扇区。所以"CD 没读完 / 装载不完整"这条**排除**（已验证）。

**④ PROG 换进来之后游戏是活的，帧链一路跑到头（已验证）**

`--watch 060FFC10:060FFC18` + 8 个新 hook（`0x06026E58/0x06026E74/0x06026E7A/0x06034438/0x06034456/
0x0603445C/0x06034462/0x06034468`，`PAL_LIMIT=100000`）：

```
06026E58  hits=71 lastVB=6096 after4886=71   ret of jsr f_06022D5C
06026E74  hits=71 lastVB=6096 after4886=71   ret of jsr f_06033654
06026E7A  hits=70 lastVB=6096 after4886=70   ret of jsr f_0603440C
06034438  hits=71 lastVB=6096 after4886=71   ret of jsr f_06033DD8
06034456  hits=71 lastVB=6096 after4886=71   ret of jsr f_060344A0（场景脚本 VM）
0603445C  hits=71 lastVB=6096 after4886=71   ret of jsr f_06032C64
06034462  hits=71 lastVB=6096 after4886=71   ret of jsr f_06034FA0
06034468  hits=70 lastVB=6096 after4886=70   ret of jsr f_0602222C（帧末/VSync）
```

`f_0605D68A` 不是"卡死点"，它就是**每帧 VSync 同步**（`L_0605D6B0: jsr @[972,gbr]; cmp/pz [19,gbr]; bt` 循环，
`[19,gbr]` 由 `f_0605CECC` 每 VB 递减并 5→0→FF 回卷，`[972,gbr]=0x06060394` 是一条 `rts` 空任务）。
主从命令队列也健康：`--watch 060FFC44:060FFC4B` 里主机 `PROG:0605CECC` 每写一次 060FFC48，
从机 `PROG:0605FC10` 立刻把 060FFC44 跟到同值（日志里 `[M]`/`[S]` 成对）。
**所以 §4.9 说的"场景脚本被门住 / 主循环没跑完"是错的**：帧链每帧都跑完。

**⑤ 真正的缺口：PROG 第 3 次运行从不把 `[0x0601FA00]` 推到 9/11/12 那一档**

写 `[0x0601FA00]` 的只有两处：`P0:06010A80`（→1、→6）和 `PROG:060662D8`（→2、→8）。
VB4707 之后它停在 8，`--peek 0601FA00:2` 到 VB16000 仍是 `00080000`。
状态 8 → 装载并 `jsr` 进 PROG；只有 PROG 自己把状态改成 9/11/12，P0 下一轮才会去装载 TRUE.BIN，
而 **TRUE 才是画 VDP2 背景的那个模块**（地图幕 VB2700 的 VDP2 VRAM 有 413,642 非零字节，
停滞幕只有 640）。VB4886 之后 `--watch` 再没打到任何 VDP2 VRAM 写入，画面就是
"VDP1 一个人物 + 全黑背景"（`build/run/long30k/shot-30000.png`）。

**⑥ 输入彻底排除（已验证）**

`build/mashlong.txt`（VB4700 起每 60 VB 轮换 A/B/START/UP/DOWN/LEFT/RIGHT，共 187 次按键，跑到 VB16000）
→ `0601FA00: 00080000`，状态纹丝不动。§4.9 里"游戏认键"这句仍然成立，但**这一幕不是在等按键**。

**⑦ 下一步的具体目标（待验证）**

`f_06026D84` 里 `jsr f_06022D5C` 返回 0 时把 `[18,gbr]` 设成 6、非 0 时设成 3（0x06026E5E/0x06026E6A），
VB4886 之后 71 帧**全部走 6 那一支**；而 `f_06022D5C` 是一个 14 个操作码（`[r14+12]` 从 0 数到 13）的
命令解释器。所以门就在这个解释器"这一帧没吃到任何该吃的命令"。
下一步：给 `f_06022D5C` 的入参 `r4/r5/r6` 与它写回的 `[r14+14]/[r14+16]/[r14+18]` 下 hook，
比对 VB1648-2527（PROG 第 2 次运行，正常交权）与 VB4886+（第 3 次，不交权）两段的差别，
找出第 3 次少掉的那条命令是谁该投递的。判据不变：
同一最小序列下停滞幕的 VDP2 VRAM 非零字节从 640 回到 40 万级并出背景。

**新增作废口径**：`f_0605D68A` 卡死、从机 SH-2 挂住、PROG.BIN 装载不完整、"帧链没跑完"、
`[972,gbr]` 空任务是异常（它是正常空档）。

**⑧ §4.10 的复现命令（Windows，Git Bash）**

```bash
cd PAL-Saturn-Recomp
# 状态轨迹 + 写入者（②③⑤）
build/recomp-build/saturn.exe --out build/run/statewatch --cue disc/pal_t37401h_13tr.cue \
  --headless --save - --vblanks 6100 --input @build/min3.txt \
  --watch 0601FA00:0601FA01 --peek 0601FA00:4

# P0 状态表静态解码（②）：build/disc-extract/0 偏移 0x138 起 13 个字
od -An -tx2 -j $((0x138)) -N 26 build/disc-extract/0

# 帧链 8 个返回点命中数（④）—— 需要先 python tools/winbuild.py build --recompile
PAL_HOOKS=06026D84,06026E58,06026E74,06026E7A,06034438,06034456,0603445C,06034462,06034468 \
PAL_LIMIT=100000 build/recomp-build/saturn.exe --out build/run/fchain \
  --cue disc/pal_t37401h_13tr.cue --headless --save - --vblanks 6100 --input @build/min3.txt

# 装载请求块是否走完（③）
PAL_HOOKS=06007E96 PAL_DUMP=0601875C:32 PAL_LIMIT=100000 \
  build/recomp-build/saturn.exe --out build/run/loads2 --cue disc/pal_t37401h_13tr.cue \
  --headless --save - --vblanks 6100 --input @build/min3.txt

# 主从命令队列（④）与 VSync 计数（④）
build/recomp-build/saturn.exe --out build/run/queuewatch --cue disc/pal_t37401h_13tr.cue \
  --headless --save - --vblanks 6100 --input @build/min3.txt --watch 060FFC44:060FFC4B
build/recomp-build/saturn.exe --out build/run/flagwatch --cue disc/pal_t37401h_13tr.cue \
  --headless --save - --vblanks 6100 --input @build/min3.txt --watch 060FFC10:060FFC18

# 输入彻底排除（⑥）
build/recomp-build/saturn.exe --out build/run/mashlong --cue disc/pal_t37401h_13tr.cue \
  --headless --save - --vblanks 16000 --input @build/mashlong.txt --peek 0601FA00:2
```


**⑨ 端到端闭环：对象数组每帧被清零、再没人重建（已验证，`build/run/oqueue.log`）**

`--watch 060768E8:060768EB`（`f_06022D5C(r4=[0x060768E8], r5=[0x060768EA])` 读的那对区间字）打到两类写入者：

| 写入者 | 次数 | 时机 | 含义 |
|---|---|---|---|
| `TRUE:0602D5C8` / `TRUE:0602E3D0` / `TRUE:0602CDBC`（pr 均 `0x0602E610`） | 持续增长 | VB2615→2736 | **地图幕把这段数组从 0x0A 一路铺到 0x5E60** —— 这才是"有内容"的样子 |
| `PROG:0603237C`（pr `0x06026E74`）与 `P0:06010A80`（pr `0x06022EFA`） | **各 71 次，每帧一对** | VB4886 之后 | 每帧把 `[0x060768E8]` 和 `[0x060768EA]` **双双写 0** |

`--peek 060768E4:8` 对照：VB2700 该段是 TRUE 铺出来的 ASCII 数据（4A/4C/4E/50/54），
VB6100 则是 `E8=0000 EA=0000` —— **区间 `[0,0)` 空**。

于是整条因果链闭合，且与 VDP1 侧的实测一致（`dump-black/dump-6000.bin` 的命令表只有
`0x1008`、`0x100A` 两条 quad + `0x0E01` END，即**只交 2 个人物精灵**；VDP1 那 65,697 非零字节是
图案数据不是命令）：

1. P0 状态停在 8 → 装载 PROG.BIN → PROG 顶层 `f_06021DE8` 按 `[0x06076828]` 分派。
   **静态解码 `f_06021DE8` 的 9 项表（PROG.BIN 偏移 0x1E48）**：
   mode 0→`f_06021440`，2/7→`f_060215A0`，3/8→`f_06026B88`，**4→`f_06026D84`**，1/5/6→直接出口。
   （`f_06026D84` 自己在 0x06026DA2 把 mode 写成 4，所以运行期看到的是 mode 4 常驻循环。）
2. mode-4 循环每帧调 `f_06022D5C`，而它读的对象区间 `[0x060768E8, 0x060768EA)` **每帧被清成 [0,0)**，
   所以返回 0 → `[18,gbr]=6` → 这一帧什么都不装配，**既不发 CD 装载（VB4886 之后装载次数 0），
   也不写 VDP2 VRAM（非零字节停在 640）**。
3. 会重建这段数组的是 **TRUE 的图形装配**（`0602D5C8`/`0602E3D0`/`0602CDBC`，同一调用点 pr `0x0602E610`），
   而 TRUE.BIN 在 run #3 里根本没被装载 —— 因为 P0 要等 `[0x0601FA00]` 变成 9/11/12 才会去装它。
4. **`P0:06010A80`（P0 的状态写入服务）每帧都在被调用**（pr `0x06022EFA`，就在 `f_06022D5C` 里面），
   只是没人拿新的状态值去调它。VB1173 它被拿去写 1、VB2505 写 6，都是正常的交权。

**所以 PAL-P1-009 的最终落点**：`f_06022D5C` 的调用树里存在一处"本应把状态推进到 9/11/12
（装载 TRUE.BIN 去画背景）"的判断，它从未成立。下一步就盯 `f_06022D5C` → `P0:06010A80` 这条边：
把 `f_06022D5C` 内每次调用 `06010A80` 的入参 `r4` 打出来，比对地图幕（VB2615-2736，数组在长）
与停滞幕（VB4886+，数组每帧归零）两段，找出停滞幕少掉的那一次带状态值的调用。
判据不变：VDP2 VRAM 非零字节从 640 回到 40 万级并出背景。

**再补一条作废**：`[0x060768E8]` 不是"队列游标被谁忘了推进"，而是**每帧被显式清零**；
"对象数组没人写"与"数组被清零"是同一件事的两面，别再当成两个候选。

**⑩ 追到底：PROG 的 mode-4 循环里根本没有装配场景的那条分支（已验证，别再往这上面查）**

`f_06022D5C(r4=0x060768E8, r5=0x060768EA, r6=r14)` 是**遍历**这段记录的解释器（不是游标对）；
往这段记录里"挂东西"的分配器是 `PROG:060235B8`，全工程**只有一个调用点**：
`f_06026D84` 内 `0x06026EB8 jsr @r8`（返回点 `0x06026EBC`），前面是两道门：

```
L_06026EA0:  if ([r14] != 1) goto L_06026F3A        ; 门 1：阶段字必须是 1
L_06026EAA:  if ([0x06076B4B] != 0) goto L_06026F34 ; 门 2：一次性标志必须是 0
L_06026EB6:  jsr f_060235B8                          ; 唯一的分配器调用
```

实测（`--watch 06076B48:06076B4C`，`build/run/flagb4b.log`）：`[0x06076B4B]` 全程**只被写过 00**（70 次，
写点是 `PROG:06026D84`），VB6100 `--peek 06076B48:2` = `00000000 00000000`。
而 `[r14]` 在 `f_06026D84` 里**只有两处写**，两处都写 0：入口 `0x06026D90` 和 `0x06026E10`
（`L_06026E0E: mov #0,r1 ; mov.w r1,@r14`）。**全函数没有任何一处把 `[r14]` 写成 1。**

⇒ 门 1 在 **PROG 的这份代码里永远不成立**，`f_060235B8` 在 PROG 下是**不可达**的。
这不是 bug：地图幕时驻留在 0x06020000 的是 **TRUE.BIN**，同一地址上 TRUE 那份函数是**另一套指令**
（`f_0602D5C8`/`f_0602E3D0`/`f_0602CDBC`，pr 均 `0x0602E610`，实测它们把这段从 0x0A 铺到 0x5E60），
**装配场景的是 TRUE，不是 PROG**。PROG 的 mode-4 循环干的是另一件事：
`if ([0x060769DC] == 1) { f_060225A4(r4=0x25E20000, r5=0x0001C000) ; [0x060769DC]=0 }`
（清 VDP2 VRAM 高 0x1C000 个半字）再 `f_06035410(r4=-1)`，然后每帧调 `P0:06010A80`。

**所以 PAL-P1-009 的落点收敛成一句话**：PROG 的常驻循环每帧都在调 P0 的状态服务
（`P0:06010A80`，pr `0x06022EFA`），但从没拿"切到 9/11/12"的参数去调它 ——
要查的是 `f_06022D5C`/`f_06022B8C` 那张 14 操作码表里**哪一条**会带状态值去调 `06010A80`，
以及这一幕的脚本为什么没走到它。**不要再查"分配器为什么没被调"** —— 在 PROG 下它本来就不该被调。

**已排除清单（本轮全部有日志）**：CD 装载路径、模块身份与换入、主从队列、从机 SH-2、
`f_0605D68A` 是否卡死、帧链是否跑完、输入、VDP1 渲染（命令表实测只有 2 个 quad + END）、
VDP2 寄存器配置、`[0x060768E8..EA]` 分配器分支。

**⑪ 自我更正：`P0:06010A80` "每帧被调"这条不成立（作废，别再当线索）**

⑨/⑩ 里"状态服务每帧被 `pr 0x06022EFA` 调一次"是从 `--watch` 的 `in P0:06010A80` 归属推出来的。
把 hook 直接挂到 `0x06010A80` 入口实测（`build/run/svc.log`，296 次命中）：
**PROG#3（VB4886+）只有 6 次**，不是 71 次；而且**全部 `pr = FFFFFFE8`** —— 这是个假返回地址。
这正是 PAL-P1-005 记过的上游精度问题：`--watch` 报告里的 `in 模块:地址` 由宿主函数入口**上界查找**得出，
穿过这种间接/向量调用时会归错。所以：

- **可信的**：`[0x060768E8]`/`[0x060768EA]` 在 VB4886 后各被写 0 共 71 次（值与地址是真测到的）；
  `f_06022D5C` 返回 r0=0 共 71 次（hook 直读寄存器）；`f_06026D84` 内 `[r14]` 只被写 0（静态可查）。
- **不可信、已作废的**：那 71 次清零"是 `P0:06010A80` 干的"、以及"状态服务每帧都在被调"。
  清零者的真实身份要用 hook 直接挂在候选函数入口上重测，不能靠 `--watch` 的归属。

PROG#2 与 PROG#3 里 `06010A80` 的入参签名相同（`r4=0 r5=0 r6=060FFB5C`），所以它也不是分叉点。

**⑫ 第二次自我更正：`[0x060768E8]/[0x060768EA]` 不是"记录区间"，而是视口坐标（⑨ 的因果解释作废）**

顺着写点找到 `PROG:0x060237CE` / `0x060237F8`：两处都是 `f_06022718(...)` 的结果分别写进这两个字，
而 `f_06022718` 的入参来自 `0x0609EED0 + [r14]*22`（`muls.w #22`）—— **一张 22 字节步长的场景表**，
`0x0609EED0` 在 PROG.BIN 之外（运行时建在 WRAM 高位）。所以这两个字是**从场景表算出来的视口/原点**，
不是"记录数组的头尾"。

`--peek 0609EED0:12` 直接否掉了"场景表没建"这个猜测，方向和猜的正好相反：

```
vb=2700（地图幕，正常出背景）: 0609EED0: 00000000 ×12          ← 全 0
vb=6100（停滞幕）           : 0609EED0: 02000320 000000FB 00000000 00010500 ... ← 有内容
```

⇒ 停滞幕里这张场景表**是建好了的**，而 `[0x060768E8]=[0x060768EA]=0` 只是一个合法的 (0,0) 原点。
**⑨ 里"记录区间为空所以什么都不装配"这条因果链作废**；仍然成立的只有那些直接测到的事实：
`f_06022D5C` 每帧返回 0（hook 直读 r0）、`[18,gbr]` 因此取 6、
`[0x060768E8]/[EA]` 各被写 0 共 71 次、VB4886 之后 CD 装载 0 次、VDP2 VRAM 非零字节停在 640、
VDP1 只交 2 个 quad、`[0x0601FA00]` 停在 8 且 187 次按键推不动。

**方法论记一条**：`--watch` 的 `in 模块:地址` 归属和"某地址看起来像头尾对"都属于推断，
本轮两次被实测翻掉（⑪ 的归属、⑫ 的语义）。以后先把结论挂在 **hook 直读寄存器** 或 **--peek 对照** 上，
再由对照结果决定要不要动代码；不要从地址命名/相邻关系推结构语义。


### 4.11 `PAL-P1-009` 第五次收窄：PROG 的出场机制是模式字 `[0x06076828]`，停滞时它永远停在 4（当前口径）

本轮先用四条独立测量把 §4.10 的三条口径**证伪**，再给出新的抓手。所有结论只建立在
**hook 直读寄存器**、**`--peek` 差值**、**`hw-log.txt` 累计计数差值**这三类证据上。

#### ① 画面基线被重新确认：地图幕与洞穴幕都画得完好（已验证）

`build/run/dump-map/shot-2700.png` 是一帧完整的 45° 俯视角地图（地表纹理、草、石头、人物俱全）；
`build/run/trans/shot-4400.png` 是一帧带透视的洞穴幕。两者都不是"黑底只剩精灵"。
所以 **VDP2 的单元模式渲染、精灵、输入链路在本作上都是通的**，问题只在 VB4700 那一次换幕。

`build/run/trans/` 的 8 张 shot 的 MD5 分四组：`8a3217e7`(VB4400) / `04251e76`(4600) /
`c0b615e8`(4700,4800,4900,5000) / `471770e4`(5200,5600)。`471770e4` 与
`long30k/shot-30000.png` 同码 —— **停滞是永久的，不是慢**。

#### ② 撤回："VDP2 背景数据从未被写入"这句口径不准确（已验证，必须改）

`build/run/holdup/hw-log.txt` 的全程累计：

```
area W VDP2 VRAM  05E00000 05E7FFFE  31695800      ← 三千万次写，铺满整个 512 KB
area R VDP2 VRAM  05E20000 05E625FC     97536
area W VDP2 CRAM  05F00000 05F003FC       752
```

所以"从未被写入"是错的。用两次同输入、只改 `--vblanks` 的运行做**计数差值**，才拿到真正的口径
（`build/run/c5005/hw-log.txt` vs `build/run/c6100/hw-log.txt`，VB5005→VB6100 这一段）：

| 区域 | @VB5005 | @VB6100 | 停滞段增量 |
|---|---:|---:|---:|
| VDP2 VRAM/W | 31522272 | 31695800 | **173528** |
| VDP2 VRAM/R | 61696 | 97536 | 35840 |
| **VDP2 CRAM/W** | **752** | **752** | **0** |
| VDP1 VRAM/W | 427175 | 2075784 | 1648609 |

再用 `--watch 05E00000:05E7FFFF --watch-vblanks 5005:5020`（`build/run/vramwin.log`）看这 173528
次写到底落在哪：**512 个 32 位写、地址连续、步长 4、全部来自同一个 `pr 060247BC`、全部落在
VRAM 偏移 `0x5C000..0x5C7FC` 这 2 KB 里**（`0x25E5C000` 在 `0x0602479A` 处被装进 literal 池）。
173528 / 512 ≈ 339 次同样的 2 KB 突发。

**因此正确口径是**：停滞段里游戏只反复上传一张 2 KB 的小表（`f_0602475C` → `f_0605AE98`，
目标 `0x25E5C000`），**背景位图本体一次都没上传，CRAM 一次都没改**。

#### ③ 撤回 §4.10 的两条（已验证）

* **"`f_06026D84` 靠内部回边 `[0x060768DC]` 自转，是个装载泵"** —— 错。`[0x060768DC]` 是
  **请求寄存器**：`f_06026B88` 写 0x10、`f_060223C0` 写 0x1D（VB4929）、`f_06028F6C` 写 0x0C（VB5610），
  由 `f_06026F90` 服务后清零（`build/run/pending.log`）。回边 `L_06026E44` 只在请求未清零时才走。
  停滞段每 6 个 VBlank 出现一次"清零"，就是主循环正常自转一圈，**不是泵**。
* **"`[0x060768E8]/[0x060768EA]` 是视口坐标"** —— 错。它们是传给 `f_06022D5C` 的 `r4/r5`
  **脚本游标对**，且每圈都被 `f_06026F90` 在 `0x06026FB4/0x06026FBA` 清零。停滞末态实测
  `[0x060768E8]=0x0001`、`[0x060768EA]=0xFFFF`（`build/run/pk-stall.log`）—— `0xFFFF` 是
  `f_06022D5C` 自己在 `0x06022E30/0x06022E5C` 比较的"无"哨兵。

#### ④ 新抓手：PROG 的出场只有一条路，就是改模式字（已验证机制，待验证谁该写它）

`f_06021DE8` 的模式表（PROG 偏移 0x1E48，静态解出：`0012 003a 001c 0026 0030 003a 003a 001c 0026`）
把模式 1/5/6 指向 `0x06021E82` = **返回 P0**。全程 `[0x06076828]`（模式字）的写历史
（`build/run/scasel.log`，过滤后）：

```
VB59    =0  P0:06010A80   (pr 06021E1C)   P0 按 state 装入
VB1173  =1  PROG:06021440 (pr 0602152E)   ← PROG 主动出场 → P0 载 TRUE
VB1697  =2  P0:06010A80   (pr 06021E1C)
VB1765  =2  PROG:060215A0 (pr 06021616)
VB2505  =6  PROG:060215A0 (pr 0602166E)   ← PROG 主动出场 → P0 载 TRUE → VB2700 地图
VB4895  =8  P0:06010A80   (pr 06021E1C)
VB4929  =3  PROG:06026B88 (pr 06026BAC)   mode8 处理程序把 mode 改成 3
VB5005  =4  PROG:06026B88 (pr 06026D0C)   再改成 4
VB5005  =4  PROG:060223C0 (pr 06021E7E)   之后直到 VB9100 再没有任何一次写
```

配套：`P0` 的状态字 `[0x0601FA00]` 全程只有 `0→1→2→6→8` 五次变化，VB4707 之后不再变
（`build/run/flagfa00.log`）。**每次成功的换幕都是 PROG 把模式字写成 1/5/6 之一**，
停滞时它被钉在 4。

#### ⑤ 已排除清单（本轮新增，别再回头查）

| 候选 | 结论 | 证据 |
|---|---|---|
| 脚本门字 `[0x0605CFA2]` 被关 | **排除** | 停滞末态 `--peek 0605CFA2:2` = `0100FF00`，即 0x01=开（`build/run/gate2.log`）；地图幕同为 0x01 |
| 场景构造器再入锁 `[0x06076930]` 卡住 | **排除** | 全程 `--peek 06076930:2` = 0（`build/run/bldguard.log`）；`f_06035410` 正常进入 |
| 构造器条目数 `[0x060769E6]/[E8]` | **正常** | 实测 0 / 32 → 走 `L_0603542C` 并遍历 32 条 `0x0609EED0` 记录 |
| 缺输入（等确认键） | **排除** | `build/run/mashmenu.txt` 在 VB5200-9000 塞入 95 次 START/A/B，VB6000-9000 七张 shot 全等于停滞帧，模式字仍为 4 |
| VDP2 寄存器没配好 | **排除**（就"配置"而言） | 游戏每帧重写整个 VDP2 寄存器块（`reg W 2 05F80000..00FE` 各 4356 次）；黑幕下 NBG0/NBG1 是 **位图模式**（CHCTL0=0x1212），地图幕是 **单元模式**（0x1040）—— 说明它确实为新场景重配过 |
| WRAM 被写坏 | **排除** | 见 §4.10 的 1 MB 差值 |

#### ⑥ 调度器侧的对照量（已验证，是下一步的靶子）

`--peek` 对照（`build/run/pk-map.log` vs `build/run/pk-stall.log`，同一输入脚本）：

| 量 | 地图幕 VB2700 | 停滞 VB6100 |
|---|---|---|
| `[0x0601FA00]` P0 state | 6 | 8 |
| `[gbr+18]` `0x060FFC12` | 1 | **3** |
| `[gbr+19]` `0x060FFC13` | 0 | 2 |
| `[gbr+20]` 任务函数 | `0x060209A8` | `0x06026094` |
| `[gbr+32]` 计数 | 0x78 | 0x4B4 |
| **`[gbr+972]` `0x060FFFCC` 当前任务** | **`0x060375D0`（真任务）** | **`0x06060394`（光 `rts` 桩）** |
| `0x0609EED0` 场景表 | 全 0 | **有数据**（32 条 × 22 B） |

CPU 末态 `master pr 0605D6B6`、`last polls in: PROG:0605D68A x3997` —— 正停在
"每 6 帧调一次 `[gbr+972]`" 的等待循环里，而 `[gbr+972]` 是空桩。
**即：调度器活着，但没有任务可跑；场景表有数据，却没人把它变成任务。**

> **本节 ⑥/⑦ 中"`[gbr+18]`=6 是请求载 TRUE"的推论已被 §4.12 ① 更正**：`[gbr+18]` 是帧延时计数（`[gbr+19] = [gbr+18] - 1`），对照表本身仍然有效。

#### ⑦ 下一步（唯一靶子）

查 **谁该把 `0x0609EED0` 的记录变成任务并写进 `[gbr+972]`**。抓手已就位：
`f_06026D84` 里唯一装任务的地方是 `L_06026EB6: jsr f_060235B8`，它被
`L_06026E94: if ([r14]==0)` 与 `L_06026EA0: if ([r14]!=1) → L_06026F3A` 两道门挡住，
而 `[r14]` 由 `f_06022D5C` 写（`f_06022D5C` 在 `0x06022D8E` 先把 `[r14]=0`）。
所以要在 `0x06026E58`（已声明 hook）上用 `PAL_DUMP=06076820:32` 打每一圈的
`[r14]` 与请求字，确认 `[r14]` 是否恒为 0；若恒为 0，再回到 `f_06022D5C` 查它为什么
不置 1 —— 它读的正是游标对 `[0x060768E8]=1 / [0x060768EA]=0xFFFF`。

#### ⑧ 复现命令（本轮新增，注意三条工具口径）

```bash
export PYTHONPATH=third_party/saturn-recomp/src
P=build/venv/Scripts/python.exe
# 模式字全历史
mkdir -p build/run/scasel && $P tools/winbuild.py run --out build/run/scasel -- \
  --cue disc/pal_t37401h_13tr.cue --headless --save - --vblanks 6100 \
  --input @build/holdup.txt --watch 06076828:0607682D
# 停滞段硬件计数差值
for N in 5005 6100; do mkdir -p build/run/c$N; $P tools/winbuild.py run --out build/run/c$N -- \
  --cue disc/pal_t37401h_13tr.cue --headless --save - --vblanks $N --input @build/holdup.txt; done
# 停滞段 VDP2 VRAM 到底写了哪些地址
mkdir -p build/run/vramwin && $P tools/winbuild.py run --out build/run/vramwin -- \
  --cue disc/pal_t37401h_13tr.cue --headless --save - --vblanks 5030 \
  --input @build/holdup.txt --watch 05E00000:05E7FFFF --watch-vblanks 5005:5020
```

**本轮踩到并纠正的三条工具口径（以后照此用，别再误判）：**
1. **`--peek` 支持逗号分隔的多条 `ADDR[:词数]`**（`machine.cpp:230` 的 `peek()` 按 `,` 切分），
   一次运行可以抓任意多个 WRAM/设备窗口。之前记的"只有最后一条生效"是错的。
2. **`--watch` 看不见 VDP2/VDP1 寄存器**：`mmio.cpp` 的 `area_of()` 根本没有 VDP2 寄存器段
   （0x05F80000-0x05F80200）这一条，寄存器写走的是 `log_reg()` 而不是 `log_area()`，
   所以 `--watch 05F80000:...` 恒为空 —— 那是**测量工具的盲区，不是游戏没写**。
   要看寄存器写，读 `--out/hw-log.txt` 里的 `reg W 2 05F800xx COUNT` 普查。
   VRAM/CRAM/SCSP RAM 在 `area_of()` 里有条目，`--watch` 对它们有效。
3. **`--out` 目录不会被自动创建**：`--shot`/`hw-log.txt`/`--dump` 都往 `--out` 里写，
   目录不存在时**静默丢产物**（只保留 stderr）。跑之前先 `mkdir -p`。

### 4.12 `PAL-P1-009` 第六次收窄：PROG 的模式 4 是**游戏自己设计成不出场的主循环**，缺的是"装脚本"那一步（当前口径）

§4.11 里我把 `[gbr+18]` 读成"请求 P0 去载 TRUE"。**那条是错的，本轮用反汇编纠正了**；
同时用一次全模块扫描证明"PROG 回不来"不是重编译缺陷。以下每条都附证据来源。

#### ① 更正：`[gbr+18]` 是**帧延时计数**，不是状态请求（已验证）

`f_0605D670`（PROG 的每帧同步）在 `0x0605D678` 读 `[gbr+18]`：

```
0605D670  mov.l 0x0605D898,r2      ; r2 = 0x25F80004（VDP2 状态寄存器，cache-through 形式）
0605D672  mov.w @r2,r0
0605D674  tst #2,r0
0605D676  bt 0x0605D672            ; 自旋等 bit1
0605D678  mov.b @(18,gbr),r0
0605D67A  add #-1,r0
0605D67C  mov.b r0,@(19,gbr)       ; [gbr+19] = [gbr+18] - 1
...
0605D6B0  mov.l @(972,gbr),r0
0605D6B2  jsr @r0                  ; 跑一次"当前任务"
0605D6B6  mov.b @(19,gbr),r0
0605D6B8  cmp/pz r0
0605D6BA  bt 0x0605D6B0            ; [gbr+19] >= 0 就再跑
```

所以 `f_06026D84` 每圈写 `[gbr+18]=6`（或 3）的含义是**"等 6 帧"**，正好就是观测到的
6-VBlank 主循环周期。`[gbr+18]=6` **不代表**"请求载 TRUE"。§4.11 第 ⑥ 条的对照表仍然有效，
但那一句推论作废。

#### ② 更正并确认：`f_06026D84` 的收口在 `0x06026F72`，而且**全模块没有任何一条路能走到它**（已验证）

反汇编 `0x06026F70-0x06026F8E`：

```
06026F70  0009  nop
06026F72  7E04  add #4,r14
06026F74  6FE3  mov r14,r15
06026F76  4F26  lds.l @r15+,pr
06026F78  6EF6  mov.l @r15+,r14
06026F7A  68F6  mov.l @r15+,r8
06026F7C  000B  rts
06026F7E  0009  nop
06026F80  0607 ...                ; 从这里起是 literal 池（0x0604C5AC / 0x060768E6 / 0x060768DC）
```

`add #4,r14; mov r14,r15; 弹 pr/r14/r8; rts` 与 `f_06026D84` 的序言
（`mov.l r8,@-r15; mov.l r14,@-r15; sts.l pr,@-r15; add #-4,r15; mov r15,r14`）逐项对得上，
所以它就是 `f_06026D84` 的收口。

**对 `build/disc-extract/PROG.BIN` 全模块（399,984 B）逐条解码 `bra/bsr/bt/bf/bt/s/bf/s`
并搜索 32 位 literal，目标为 `0x06026F70/72/74/7C` 的结果全部为 0。** 扫描脚本见本节末。

⇒ **重编译没有错。PROG 的模式 4 在机器码层面就是一个永不返回的主循环。**
之前"收口被漏发现"的猜测**作废**。

#### ③ 当前任务槽 `[gbr+972]` 的全程历史（已验证，22 次写，一次运行抓完）

`--watch 060FFFCC:060FFFCD`（`build/run/curtask.log`）：

| VBlank | 写入值 | 写入点 (pr) | 含义 |
|---|---|---|---|
| 1, 6 | `0x0600E7BC` | `P0:0600E6F8` (0600AE28) | P0 装自己的任务 |
| 55, 59 | `0x06060394` | `PROG:0605CECC` (06059C1C) | PROG 第 1 次进入 → **清成空桩** |
| 1195, 1222 | `0x0600E7BC` | `P0:0600E6F8` | **P0 重新拿回任务** |
| 1242, 1247, 1511 | `0x060375D0` | `TRUE:06031B98` (06029578) | TRUE 的任务 |
| 1616, 1643 | `0x0600E7BC` | `P0:0600E6F8` | P0 |
| 1692, 1697 | `0x06060394` | `PROG:0605CECC` | PROG 第 2 次 → 空桩 |
| 2527, 2554 | `0x0600E7BC` | `P0:0600E6F8` | P0 又拿回 |
| 2574, 2579, 4710 | `0x060375D0` | `TRUE:06031B98` | TRUE（地图 + 洞穴都在这段） |
| 4815, 4842 | `0x0600E7BC` | `P0:0600E6F8` | P0 |
| **4891, 4895** | `0x06060394` | `PROG:0605CECC` | PROG 第 3 次 → 空桩，**此后再无任何写入** |

`f_060602D0`（`0x0606036C-0x06060372`，收口是 `rts ; mov.l r0,@(972,gbr)`，r0 恒为
`0x06060394`）是 **PROG 里唯一写 `[gbr+972]` 的地方**。
⇒ **PROG 从来不装自己的任务，只会清空。** 前两次 PROG 周期之所以能推进，是因为
`P0:0600E6F8` 又把 P0 的任务装了回去；第三次没有。

#### ④ 脚本游标 `[0x060768E8]/[0x060768EA]` 的写入者全history（已验证）

`--watch 060768E8:060768EB`（`build/run/cursor.log`）。**全程只出现过 `0x0000` 与 `0xFFFF` 两种值**，
末态每 3 个 VBlank 重复一次：

```
store16 060768E8 = 0001    in P0:06010A80 (pr 06022E4C)   ← f_060227F8 经通用写手设的
store16 060768EA = FFFF    in P0:06010A80 (pr 06022E4C)
store16 060768E8 = 0000    in P0:06010A80 (pr 06022EFA)
store16 060768EA = 0000    in P0:06010A80 (pr 06022EFA)
store16 060768E8 = 0000    in PROG:0603237C (pr 06026E74) ← f_06033654 之后清掉
store16 060768EA = 0000    in PROG:0603237C (pr 06026E74)
```

`0xFFFF` 正是 `f_06022D5C` 自己在 `0x06022E30/0x06022E5C` 比较的"无"哨兵。
⇒ **没有任何代码把游标设成真正的脚本地址**，所以 `f_06022D5C` 每圈返回 0，
`f_06026D84` 每圈只会写"等 6 帧"。这才是停滞的直接机制。

#### ⑤ 输入不是出口（已验证，两条独立实验）

* `build/mashmenu.txt`：VB5200-9000 塞 95 次 START/A/B → VB6000-9000 七张 shot 全等于停滞帧，
  模式字仍为 4（`build/run/mashmenu.log`）。
* `build/walk.txt`：VB2800-9400 共 234 个事件，按 UP/RIGHT/DOWN/LEFT 轮转 55 帧、每 5 段补一次 A
  → 末态仍 `[0x0601FA00]=8`、`master pr 0605D6B6`；VB6000/7000/8000/9000/9400 各帧不同，
  但 `build/run/walk/shot-7000.png` 显示**只是人物在黑底上换位换姿势**，背景始终没有。
  ⇒ 精灵层活着、输入链路活着，**这条路过不去**。

#### ⑥ 顺带排除：VDP2 位图模式不是缺口（已验证）

黑幕那帧 NBG0/NBG1 是位图模式（CHCTL0=0x1212），地图那帧是单元模式（0x1040）。
`vdp2.cpp:138` 与 `vdp2.cpp:199` 都有 `if (s.bitmap)` 分支，头注释也写明支持
"NBG0/NBG1 in bitmap"。所以**位图模式已实现**，黑幕不是因为模式没做。

#### ⑦ 本轮把"下一步"收敛成一问

缺口很清楚：**PROG 模式 4 不出场（设计如此），所以场景只能由 PROG 自己装脚本驱动；
而"装脚本"那一步从未发生（游标恒为 0/0xFFFF），"装任务"那一步 PROG 根本没有（只写空桩）。**

下一问：**谁本该把非 `0xFFFF` 的脚本地址写进 `[0x060768E8]/[0x060768EA]`？**
抓手：`f_060227F8`（写 `(1,0xFFFF)` 的那个调用者，返回地址 `0x06022E4C` 落在 `f_06022D5C` 体内）
的调用链，以及 `0x0609EED0` 那张 32 条 × 22 B 的记录表被谁消费 ——
`f_06035410` 已经在遍历它（条目数 `[0x060769E6]=0`、上界 `[0x060769E8]=32`，再入锁
`[0x06076930]=0`，都已实测），所以要查的是**它遍历完之后为什么不留下游标**。

#### ⑧ 本节用的全模块分支扫描（可复用，判"某收口是否可达"）

```bash
python - <<'PY'
BASE=0x06020000
d=open('build/disc-extract/PROG.BIN','rb').read()
def sext(v,b):
    m=1<<(b-1); return (v&(m-1))-(v&m)
tg={}
for A in range(BASE,BASE+len(d)-1,2):
    W=int.from_bytes(d[A-BASE:A-BASE+2],'big'); hi=W>>12
    t=None
    if   hi in (0xA,0xB): t=A+4+sext(W&0xFFF,12)*2          # bra / bsr
    elif (W&0xFF00)in(0x8900,0x8B00,0x8D00,0x8F00): t=A+4+sext(W&0xFF,8)*2  # bt/bf(+/s)
    if t is not None: tg.setdefault(t,[]).append((A,hex(W)))
for w in (0x06026F70,0x06026F72,0x06026F74,0x06026F7C): print(hex(w), tg.get(w,'NONE'))
PY
```

复现本节的三条测量：

```bash
export PYTHONPATH=third_party/saturn-recomp/src
P=build/venv/Scripts/python.exe
mkdir -p build/run/curtask && $P tools/winbuild.py run --out build/run/curtask -- \
  --cue disc/pal_t37401h_13tr.cue --headless --save - --vblanks 6100 \
  --input @build/holdup.txt --watch 060FFFCC:060FFFCD
mkdir -p build/run/cursor && $P tools/winbuild.py run --out build/run/cursor -- \
  --cue disc/pal_t37401h_13tr.cue --headless --save - --vblanks 6100 \
  --input @build/holdup.txt --watch 060768E8:060768EB
mkdir -p build/run/walk && $P tools/winbuild.py run --out build/run/walk -- \
  --cue disc/pal_t37401h_13tr.cue --headless --save - --vblanks 9500 \
  --input @build/walk.txt --peek 0601FA00:1,06076828:1 --shot 3000,4500,6000,7000,8000,9000
```

#### ⑨ 补记：两条"注入/强制"路线均为否定结果（已验证，别再试）

* `--write 5200:060FFFCC=0600E7BC`（把 P0 的任务地址注回当前任务槽）已生效（日志有 `write 060FFFCC: 4 bytes`），但游戏**不恢复**：末态仍 `[0x0601FA00]=8`、VB5300-6000 仍是停滞帧 （`build/run/inj.log`，VB7000 之后才因 UP 而换姿势）。原因：`0x0600E7BC` 是被游戏任务切换器从 `jmp_buf` 唤醒的协程入口，不是一条可以直接 `jsr` 的函数，冷调用没有意义。
* 用输入强行推场景同样否定（见本节 ⑤）。
⇒ 剩下的唯一出路是**读懂场景命令字 `[0x0607682A]/[0x0607682C]` 的生产者**：空闲值是 `0xFFFF`，`PROG:06022190` 每圈把它重设回 `0xFFFF`，全程只出现过 `0xFFFEFFFF/0xFFFFF7FF/0xFFFFEFFF` 这类单 bit 清除（各 93/12/6 次）。`f_060227F8` 就是解码器（对 `~index` 逐个比 `0x800/0x400/0x100/...`，返回一个槽号，再由 `f_06022D5C` 在 `0x06089B00` 那张 14 字节表上标 `3`）。

#### ⑩ 再更正（同轮内自我否定，必须记）：`[0x0607682A]/[0x0607682C]` 是**手柄状态字**，不是场景命令字（已验证）

⑨ 末尾把 `0xFFFEFFFF / 0xFFFFF7FF / 0xFFFFEFFF` 这类"单 bit 清除"当成场景命令，**这条是错的**。
把清除发生的时间点和输入脚本对齐就否定了它 —— `build/holdup.txt` 是
`1500:START,1512:,2500:START,2512:,2600:A,2612:,6000:UP,6500:`，而 `build/run/scasel.log` 里
这两个字的非 `0xFFFF` 取值只出现在两段，且与按键窗口逐帧吻合：

| 出现的值 | 清除的 bit | 发生区间 | 对应按键 |
|---|---|---|---|
| `0xFFFFF7FF` | 11 | VB2504-2515 | START@2500 → 释放@2512 |
| `0xFFFEFFFF` | 13 | VB6007-6034+ | UP@6000 → 释放@6500 |

⇒ **`[0x0607682A]/[0x0607682C]` 是"按下为 0"的手柄状态字**，`PROG:06022190` 每帧从 SMPC 刷新它们
（所以每帧看到 `0xFFFF` = 没按键）。这也第三次独立证明**输入链路在模式 4 里是通的**。

顺着这条把 `f_06022D5C` 的真实职责也纠正过来：**它不是场景脚本解释器，而是按键→动作的扫描器**。
证据：`f_060227F8` 拿到 `[0x0607682A]` 后先 `not`（把"按下为 0"翻成"按下为 1"），再逐个
`cmp/eq` 与 `0x800 / 0x400 / 0x100 / …` 比较，命中就把一个动作号写进 `[r14+8]`，
`f_06022D5C` 再用它把 `0x06089B00` 那张 **14 槽**表标成 `3`。
所以 §4.11/§4.12 里"场景脚本游标 `[0x060768E8]/[0x060768EA]`"的说法也要降级：
它们是 `f_06022D5C` 的**两个入参指针**（`f_06026D84` 在 `L_06026E48` 传的是地址，不是值），
其含义尚未证实，不要再当"脚本游标"使用。

#### ⑪ 于是缺口重新表述（当前口径，待验证）

排除掉误读之后，剩下的硬事实是这三条：

1. `f_06026D84`（模式 4）每圈都会调 `f_06035410`（构造器，`r4=-1`），构造器的再入锁为 0、
   条目数 `[0x060769E6]=0`、上界 `[0x060769E8]=32` ⇒ **它确实在遍历 `0x0609EED0` 的 32 条记录**。
2. 遍历期间对 VDP2 VRAM 的唯一产出是 **`f_0602475C → f_0605AE98` 往 `0x25E5C000` 上传 2 KB**
   （512 个 32 位写，`pr 060247BC`），而黑幕那帧 NBG0/NBG1 是位图模式、需要的是
   `f_060225A4` 清掉的那 `0x20000` 起 `0x1C000` 字节（114 KB）。
3. 那 32 条记录是**换幕时从 CD 读进来的**；而实测 VB4700 之后游戏再没发过任何 CD 读
   （见 §PAL-P1-009 早期口径：最后一次 cmd 10 要 16 扇区、16 扇区全部投递，之后到 VB9000 不再读 CD）。

⇒ **新的主假设（待验证）**：`0x0609EED0` 里装的是**上一幕的残留记录**，新一幕的记录本该由一次
CD 读填充，而那次读从未被发起；构造器拿着残留记录自然只产出 2 KB 的边角，背景因此是黑的。
下一问随之变成：**换幕流程里"发起新一幕 CD 读"的那一步在哪、被什么条件挡住**。
抓手：`f_06026B88`（模式 8/3 处理程序，VB4929/VB5005 是换幕后唯一跑过的前台初始化），
以及 `f_0602475C` 的调用链上那个决定"读哪个文件、读到哪"的请求块
（PROG 的 literal 池里能看到候选文件名 `ABC.J / FFF.J / MGO.J / FBP.PX / MGO.NEW / RGM.JOE`
就在 `0x06076A10` 起）。


## 5. 复现命令（Windows）

```bat
cd PAL-Saturn-Recomp
build\venv\Scripts\python.exe tools\winbuild.py check
build\venv\Scripts\python.exe tools\winbuild.py build --recompile
build\venv\Scripts\python.exe tools\winbuild.py learn --out build\learn-001 --limit 25 -- ^
  --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 3000
build\venv\Scripts\python.exe tools\winbuild.py run -- ^
  --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 1500 --shot 600,1200
:: 无游戏数据的完整自检（Windows 版 tools/check.sh）
bash tools\check_windows.sh
```

`PAL-P1-001` 的复现与验证（`--shot` 必须配 `--out`，目录要先建）：

```bat
:: 修复前：cmd 10 之后只有 00/51 轮询，51 的 out[3] 恒为 0（数据进不了缓冲）
build\recomp-build\saturn.exe --out build\run\cd-001 --cue disc\pal_t37401h_13tr.cue ^
  --headless --save - --vblanks 8 --trace > build\cd60.log 2>&1
findstr "CD-DA CD: cmd_51" build\cd60.log
:: 打上 patches\0001-cdrom-is-audio-per-track.patch 后同一命令应变成
::   CD: read FAD 166-167 into filter 0 / CD cmd 61 … / CD cmd 10 / CD: read FAD 170-172
git -C third_party\saturn-recomp apply ..\..\patches\0001-cdrom-is-audio-per-track.patch
build\venv\Scripts\python.exe tools\winbuild.py build

:: 装载成功的判据：警告句里不再出现 "its data differs from the image's"
build\recomp-build\saturn.exe --out build\run\p1-fix-001 --cue disc\pal_t37401h_13tr.cue ^
  --headless --save - --vblanks 1200 --shot 100,400,1190
:: 链路取证（游戏层 hook；注意 hook 必须先在 game.toml 的 [[hook]] 声明才会生成 sh2_hook 调用）
set PAL_HOOKS=06004758,060048EC,060057F8,06004950,06004EB0&& set PAL_LIMIT=4&& set PAL_DUMP=06017A90:48&& ^
  build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 830
:: PAL-P1-006 的取证：向量区随时间的值
set PAL_HOOKS=06059C34&& set PAL_LIMIT=64&& set PAL_DUMP=06000320:48&& ^
  build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 1300
```

`PAL-P1-006 / 007` 的取证与验证（同一批命令，Windows 实测）：

```bat
:: ① 别名写只有打了 0002 补丁才看得见；报出的是原始地址 0x06100320
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - ^
  --vblanks 1300 --watch 06000320:0600034c > build\watch-raw.log 2>&1
:: ② 那张 {30,指针} 表的基址与长度（循环前一行 + 循环体首）
set PAL_HOOKS=0605FE60,0605FE64&& set PAL_DUMP=060663D0:32&& set PAL_LIMIT=3000&& ^
  build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 1300
:: ③ 长度单元被谁改写：VB11=PROG.BIN 原字节，VB1227=TRUE.BIN 原字节
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - ^
  --vblanks 1300 --watch 06020088:06020090
:: ④ 装载请求块（目标/长度/扇区数）与换入的文件
set PAL_HOOKS=06007E96&& set PAL_DUMP=r9:64&& set PAL_LIMIT=3000&& ^
  build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 1230
:: ⑤ 声明 TRUE 模块后：应打出 "program start 1: TRUE at 06020000"，且 --shot 出非黑画面
build\venv\Scripts\python.exe tools\winbuild.py build --recompile
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - ^
  --vblanks 3000 --out build\run\shots-TRUE1 --shot 1300,1800,2400,2900
:: ⑥ PAL-P1-007：程序返回装载器的探针 + 进地图与方向响应
set PAL_HOOKS=06004206&& set PAL_LIMIT=40&& ^
  build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - ^
  --vblanks 4100 --input @build\input-walk2.txt --out build\run\shots-walk2 ^
  --shot 3050,3200,3400,3600,3800,4050
:: ⑦ 三补丁之后的回归（应与打补丁前完全一致）
bash tools\check_windows.sh > evidence\p1-check-after-3patches.log 2>&1
```

**最小可复现路径到地图**（逐键实测，`evidence/p1-map-002-minpath/`；注意 `--peek` 的字数按**十进制**解析）：

```bat
echo 1500:START,1512:,2500:START,2512:,2600:A,2612:> build\min3.txt
:: VB1500 的 START 结束开场影片（VB1616 程序 rts 回 P0），VB2500 START + VB2600 A 过标题，VB2700 已是地图
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - ^
  --vblanks 3400 --input @build\min3.txt --out build\run\shots-final --shot 2700,3350
:: 对照实测：同一序列下分别不按键 / 长按 UP / 长按 LEFT，各吐一次 1 MiB 高 RAM 逐字比对
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - ^
  --vblanks 3500 --input @build\w.txt --peek 06000000:262144 > build\pos-up.log 2>&1
```

`PAL-P1-009` 的取证（不需要改上游，`--dump` + 离线工具就够；比临时加转储更省）：

```bat
:: ① 同一帧的状态与画面一起取：--dump 写 dump-N.bin
::    布局 = [VDP1 VRAM 512K][VDP1 帧缓冲 256K][VDP1 寄存器 32][VDP2 VRAM 512K][CRAM 4K][寄存器 512]
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - ^
  --vblanks 3950 --input @build\min3.txt --out build\run\dump-movie --shot 3900 --dump 3900
:: ② 解寄存器（名表取自上游 src/saturnrecomp/hw.py，每 2 字节一项）
node tools\vdp2_inspect.js build\run\dump-movie\dump-3900.bin
:: ③ 离线复刻合成：能重现运行时截图 = 该幕 runtime 画对了（这就是撤回 PAL-P1-008 的那一步）
node tools\vdp2_replay.js build\run\dump-movie\dump-3900.bin build\run\replay-movie.png
:: ④ 是不是在等键：11 个键逐个按，与不按键对照同一批 VBlank 的 PNG MD5
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 9200 ^
  --input @build\mash-all.txt --out build\run\mashA --shot 7500,8500,9100
:: ⑤ 声音驱动 Tick 到底是死锁还是空转：盯住工作单元的计数器字节
build\recomp-build\saturn.exe --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 6200 ^
  --input @build\min3.txt --watch 060FFC10:060FFC18
:: ⑥ 停滞段独有的代码：两窗覆盖率差集（4880 在 VB4886 换入之前，6200 在之后）
... --vblanks 4880 ... --coverage build\run\cov-4880.txt
... --vblanks 6200 ... --coverage build\run\cov-6200.txt
:: ⑦ FAD 反查盘内文件（MODE1/2352：数据在扇区内第 17 字节；LBA = FAD-1）
node tools\disc_ls.js disc\pal_t37401h_v1000_jt.bin 5334 13862 35823
```

## 6. Gate P1 状态

| 判据 | 结果 |
|---|---|
| Windows 上可启动 | **已验证**（HLE 启动 + 真盘 + 本机码） |
| 主程序是否真从光盘装载 | **已验证**（PROG.BIN 装载到 0x06020000 且与映像一致，§3.0/§4.2） |
| 同址换入的下一个程序 | **已验证**（TRUE.BIN 换入并被运行时识别，§4.5；返回装载器后再次装入 PROG，§4.6） |
| 进入至少一个地图 | **已验证**（`build/run/dump-map/shot-2700.png`：俯视角地图 + 人物 + 地面石块，由最小按键序列直达；离线复刻 `tools/vdp2_replay.js` 能从同帧 `--dump` 重现同一幅图） |
| 人物响应方向输入 | **未判定**（原先记作"未达到"不成立）：VB2700-3800 地图幕里 UP/RIGHT/不按键三组在 VB2900-3700 五帧 PNG 逐帧 MD5 相同，但这一幕是自走脚本，不能当输入链路的证据；START/A 在标题处有响应。要等走到真正交给玩家操作的那一幕再判（§4.8） |
| 可采样的游戏状态 | **可用**：`--peek/--watch/--shot/--trace/--dump/--coverage` + 游戏层 hook；`--watch` 需 0002 补丁才不漏别名写，`in ?:%08X` 归属仍不精确（§4.3/§4.4）；`note_unsupported()` 只在带 `--shot` 真正合成时才打；新增离线工具 `tools/vdp2_inspect.js`、`tools/vdp2_replay.js`、`tools/disc_ls.js`（§5） |
| 阻塞报告与 A/B 评估 | 本报告即阻塞报告；`PAL-P1-001/005/006/007` 已闭环；`PAL-P1-008`（VDP2 SCRCTL 致黑）**已撤回**，改立 `PAL-P1-009`（PROG 换回后 VDP2 VRAM 被清空且再没填回去，§4.8）；结论仍是**继续路线 A**，不切换 |

Gate P1 的判据里"进入地图"已成立，"人物响应方向输入"因当前流程走不到可操作的一幕而**无法判定**。要判过 Gate P1，需要：
① 先解 `PAL-P1-009`，让游戏回到能出图、能推进的流程（判据：VDP2 VRAM 非零字节从 640 回到 40 万级、标题重新出图）；
② 走到真正交给玩家操作的那一幕，用 `--peek` 差值法 + PNG 差值法测出人物坐标单元与每帧位移，填 `docs/P0_MOVEMENT_BASELINE.md` §3。



### 4.13 第七次收窄：停滞不是"等 CD"，也不是任务槽（2026-10-10，patch 0004 之后）

本轮先把工具补好，再用新工具一次性否证了两条旧假设，并把现场从"请求没发"改写成"上膛了但没人兑现"。

**① `[gbr+972]` 任务槽假设作废（结构证据，不是猜测）**

PROG 的 `f_060602D0`（`p_prog_015.cpp:4063`）、P0 的 `f_0600E794..E79A`（`p_p0_002.cpp:390-399`）、TRUE 的 `f_060375A8..75AE`（`p_true_004.cpp:7888-7891`）是**同一个"模块复位"例程**的同形三段：清 8×20 B 的表 → `[gbr+178]/[gbr+181]=0` → 把本模块的 idle 入口写进 `[gbr+20]/[gbr+832]/[gbr+972]`。PROG 装的 `0x06060394` 和 P0 装的 `0x0600E7BC` **都是 `rts; nop`**（`p_prog_015.cpp:4148`、`p_p0_002.cpp:402-405`），只有 TRUE 装的 `0x060375D0` 是真函数。所以"健康循环里装的是 P0 的真任务、停滞时只剩空桩"这个说法不成立——健康循环装的也是空桩。上一轮在 VB5200 注入 P0 任务地址的实验因此本来就无效（注入的是等价空桩）。

**② 停滞不是"在等 CD"**（实测否证）

用 patch 0004 把 `--watch` 扩到寄存器带值打印后，VB5200-5220 这 20 帧里**全部 CD 访问只有一条**：`watch R 05890008 = 000007D5 (2 bytes, pr 06026126, VBlank …)`，每帧一次；命令寄存器 `0x90018/1C/20/24` 一次都没写。`0x07D5 = SCDQ|EFLS|ECPY|EHST|PEND|CSCT|CMOK`，游戏只读不写回清除（清除例程是 PROG 自己的 `f_06054D74`，`p_prog_013.cpp:7904` 附近）。也就是说 **PEND/SCDQ 挂着是"游戏不再管 CD"的结果，不是原因**。上一轮按 4700→8000 聚合算出的"CD 命令写 102,941 次"全部集中在 VB4886-5005 的 PROG.BIN 装载段，稳态段 CD 完全静默。

**③ 模式 4 循环的真身：等玩家动作的分派器**

`f_06026D84` 的 `L_06026E48` 用 `f_06022D5C` 把手柄译码成动作码写进 `[r14]`，然后按 `[r14]` 分派：`==7 → f_0604C45C`、`==1 → f_060235B8`、`==0xA/0xB → f_0604C5AC`（`p_prog_001.cpp:4436-4483`）；`[r14]==0` 时只做 `[gbr+18]=6` 帧延时、把 `[0x060768E6]` 异或 1（闪烁位），回 `L_06026DAE`。停滞段确实收到过按键并走到过 `f_060235B8`（该函数在 stall_new 集合里）。输入、译码、分配器都是活的。

**④ 现场改写：背景装载"已上膛、从未兑现"**

- 换幕后的模式 8 处理程序 `f_06026B88` 在 `0x06026BBC`、以及它调用的 `f_06026744` 在 `0x0602675C`，都把 **`[0x06076A04] = 0x25E20000`**——正是 `f_060225A4` 清空的那 114 KB 位图区的硬件直通地址；同时 `f_06026F90` 在 `0x06026FAC` 置 **`[0x06076A09] = -1`**（上膛标志）。
- VB5220 实测 `[0x06076A04]=0x25E20000`、`[0x06076A09]=0xFF`；VB2600 健康地图同样 `[0x06076A04]=0x25E20000` 但 **`[0x06076A09]=0`**（已放行）。
- 全模块里清这个字节的只有一处：`f_06022D06..D1A`，条件是 `[0x06076A09]==-1 且 [0x06089B00]==0`（`p_prog_000.cpp:5076-5089`）。

**⑤ 黑帧期间 VDP1 提交队列为空**

8 项 ×20 B 的队列表 `0x0605D8F4` 是 VDP1 图元提交队列：`f_0605D79E` 每帧走一遍（判据 `byte0 == 0x70`，`p_prog_015.cpp:562`），`f_0606039E` 按 `byte0 & 0x7C` 查 `0x0606067C` 的 7 项跳转表分派。`--peek 0605D8F4:40` 对比：VB2600 的 entry0 = `000007FF 0027E022 25A7C000 00002150`（有活），VB5220 **全 0**。黑帧期间没有任何绘制提交，与 ④ 自洽。

**⑥ 工具学（别再踩）**

- `--watch LO:HI` 原先只在 `log_area()` 里判断，而 `area_of()` 只给"内存类"区域起名（VDP1/VDP2 VRAM、CRAM、SCSP RAM、BIOS、备份 RAM、卡带）；**CD 寄存器和 VDP2 寄存器没有名字**，所以这两类访问永远打不出 watch 行——这解释了此前两次"0 命中"导致的误读（VDP2 寄存器一次、CD 一次）。
- `patches/0004-watch-covers-register-accesses.patch` 把 watch 提到 `sh2_mmio_read`/`sh2_mmio_write` 入口，读写都带值，是本轮 ② 的唯一取证手段。只做诊断，不改任何硬件语义。回归：`bash tools/check_windows.sh` → 运行时单测 `44 tests, 0 failed`（含 `SATURN_VDP1_GPL` 两遍），Python 侧仍是已知 6 个 Windows 专有失败（test_agent / test_playtest / test_prereqs）。
- `--coverage FILE`（配 `--checkpoint 秒`）给每个重编译函数"跑过没有"；在不同 `--vblanks` 停止点做集合差，是判断"停滞段到底有没有在干活"最省事的办法。本轮用它测出停滞段仍**新跑了 81 个 PROG 函数**，因此"死循环空转"的说法也不成立。
- 复现：
  - `mkdir -p build/run/cdw3 && PYTHONPATH=third_party/saturn-recomp/src build/venv/Scripts/python.exe tools/winbuild.py run -- --cue disc/pal_t37401h_v1000_jt.cue --headless --vblanks 5220 --save - --input @build/walk.txt --watch 05818000:05890024 --watch-vblanks 5200:5220 --out build/run/cdw3`
  - `… --peek 0605D8F4:40 --out build/run/tb-h`（VB2600）/ `--vblanks 5220`（VB5220）
  - 覆盖差：`for N in 2600 4400 4700 8000; do … --coverage build/run/cov$N.txt; done`，再 `awk '$4==1{print $1,$2}'` + `comm -13`。

**⑦ 下一个问题（待验证）**

"谁负责把 `[0x06076A04]=0x25E20000` 这次上膛的背景兑现"。已排除 P0：`grep` 全模块证明 **P0 里没有任何引用 `0x060768DC` 请求块的代码**（p_p0_*.cpp 0 命中），所以那块信箱是 PROG 内部信箱；PROG 自己发 CD 命令的例程是 `f_06054D44`/`f_06054D84`/`f_06054F84`/`f_06054FC0`（`p_prog_013.cpp`，VB4700 前都跑过）。抓手：查停滞段 `[0x06089B00]` 的值（它非 0 就会卡住 ④ 里唯一的放行路径），以及 `f_06026F90` 上膛之后本该由谁把数据搬进 `0x25E20000`。

### 4.14 第八次收窄：**推翻 4.11–4.13 的口径**——黑屏是 VDP2 旋转层没实现，不是游戏没装背景（2026-10-10）

窗口实机反馈（用户）：启动画面颜色/尺寸不对，按 START 之后黑屏。据此回头量同一批 `--dump`，结论与前三次收窄相反。

**① 现场数据**（dump 布局：`[VDP1 VRAM 0x80000][VDP1 FB 0x40000][VDP1 regs 0x20][VDP2 VRAM 0x80000][VDP2 CRAM 0x1000][VDP2 regs 0x200]`）

| dump | 场景 | VDP1 VRAM 非零 | VDP1 FB 非零 | VDP2 VRAM 非零 | NBG0CFG(0x20) | CHCTL0(0x28) |
|---|---|---|---|---|---|---|
| `dmadiag/dump-2800.bin` | 等距地图（出画） | 293 | 0 | **413,638** | 0x0100 | 0x4010 |
| `dmadiag/dump-4500.bin` | 洞窟（出画） | 293 | 0 | **413,644** | 0x0100 | 0x4010 |
| `ab_none/dump-6100.bin` | 黑屏 | **65,697** | **72,359** | 640 | **0x4300** | **0x1212** |

**② 0x4300 / 0x1212 的含义**

`NBG0CFG & 0x30 = 0x30` → HLMT(bit4) + SDTT(bit5) 同时置位，即 **RBG0/RBG1 旋转（rotation）模式**；`CHCTL0 = 0x1212` → SDT/SCS=1（特殊/直接贴图）、PLRS=2（1/4 缩减率）。旋转层的贴图数据源就是 **VDP1 VRAM**——而黑屏帧里 VDP1 VRAM 非零字节 65,697 ≈ 一张 256×256×8bpp 贴图，VDP1 帧缓冲也有 72,359 字节内容。

**③ 运行时明说它没做**

- `third_party/saturn-recomp/runtime/src/video/vdp2.cpp:349`：`once(0, reg(0x20) & 0x30, "RBG0/RBG1", reg(0x20));` —— 实时窗口日志里那条 `VDP2: RBG0/RBG1 (0013) is not done` 就是它。
- 同文件头注释（:19-21）：`the high resolutions (640 and 704 …)` 亦未做。
- `setup_nbg`（:102-124）只对 n=0..3 按普通 cell 层取 `s.on = bgon >> n & 1`、`chctl = reg(0x28)/reg(0x2A)`，没有任何 RBG 旋转/缩减贴图路径。

**④ 作废的口径（记录在案，别再复用）**

- §4.11/4.12 的"停滞段 VDP2 VRAM 只有 640 非零字节 ⇒ 背景从未上传"：**误读**。那 640 字节是因为这一幕**根本不用 VDP2 VRAM 存背景**，背景在 VDP1 VRAM 里当旋转贴图。
- §4.12/4.13 的"换幕后没人发起新一幕 CD 读 / 场景记录为空 / `[0x06076A04]=0x25E20000` 上膛未兑现"：**误读**，把"运行时不画"当成了"游戏没装"。
- §4.13 的"VDP1 提交队列 `0x0605D8F4` 全空 ⇒ 没有绘制提交"：该表是 `f_0605D79E`/`f_0606039E` 用的 8 项表，与 VDP1 是否收到命令无必然关系；黑屏帧 VDP1 FB 有 72 KB 内容，说明 VDP1 侧确实在出东西。
- 保留仍然有效的结论：输入活着、模式 4 是等动作的分派器、`[gbr+972]` 是模块 idle 桩（PROG/P0 都是 `rts;nop`）、停滞段仍新跑 81 个 PROG 函数。

**⑤ 下一步（明确、可验收）**

实现 VDP2 的 **RBG0/RBG1 旋转合成**（含 1/4 缩减率、从 VDP1 VRAM 取纹理、坐标/参数表——游戏每 ~3 帧向 VDP2 VRAM `0x5C000` 上传 2 KB，正是这类参数块）。顺序按项目规矩来：

1. 先离线用 `tools/vdp2_replay.js` 对 `build/run/ab_none/dump-6100.bin` 复原该幕画面（该工具已能复刻 `setup_nbg/nbg_pixel/dot/back`，需加 RBG 分支），确认取数路径（贴图基址、缩减率、坐标表步长）能拼出可辨认的图。
2. 取数路径确认后再改 `vdp2.cpp`，作为 `patches/0005-vdp2-rbg-rotation.patch`；不得为这一个游戏破坏上游通用硬件行为，且原版/增强模式要可切换。
3. 验收判据（改口径，以此为准）：
   - 离线：`dump-6100.bin` 经 replay 能画出可辨认的场景图（不再是纯黑）。
   - 实机：窗口里按 START 进幕不再黑屏；`--shot` 在 VB5200-30000 区间从恒定黑帧变成有内容的帧。
   - 回归：`bash tools/check_windows.sh` 运行时单测仍 `44 tests, 0 failed`。

**⑥ 复现命令**

```
# 量 dump 的 VRAM 填充度与 VDP2 模式寄存器（VDP2 regs 在文件末尾 0x200 字节）
build/venv/Scripts/python.exe -c "
for p in ['build/run/dmadiag/dump-2800.bin','build/run/ab_none/dump-6100.bin']:
    d=open(p,'rb').read(); r=d[len(d)-0x200:]
    print(p, 'VDP1VRAM', sum(1 for x in d[:0x80000] if x), 'VDP1FB', sum(1 for x in d[0x80000:0xC0000] if x),
          'VDP2VRAM', sum(1 for x in d[0xC0020:0xC0020+0x80000] if x), 'NBG0CFG %04X'%(r[0x20]|r[0x21]<<8),
          'CHCTL0 %04X'%(r[0x28]|r[0x29]<<8))
"
# 实时窗口（键盘：方向=十字键 Enter=START Z X C=A B C A S D=X Y Z Q W=L R，F12 截图）
./build/recomp-build/saturn.exe --cue disc/pal_t37401h_v1000_jt.cue --save - --out build/run/live
# 离线复刻 VDP2 合成
node tools/vdp2_replay.js build/run/ab_none/dump-6100.bin build/run/replay-6100.png
```

**⑦ 环境新增（本轮）**

- 为出窗口装了 SDL3：`third_party/sdl3/SDL3-3.4.18`（官方 `SDL3-devel-3.4.18-VC.zip`，本机 clang 是 `x86_64-pc-windows-msvc` ABI 所以用 VC 包），`game.toml` 的 `cmake` 加 `SDL3_DIR=…/SDL3-3.4.18/cmake`，`SDL3.dll` 复制到 `build/recomp-build/`。`objdump -p` 已确认 `DLL Name: SDL3.dll`，`saturn_host` 从 `host_null.cpp` 切到 `host.cpp`。SDL3 属本地依赖，不入库。

### Linux 静态复核补记（2026-10-10；待镜像核对）

本次无镜像静态复核发现 §4.14 的 `0x4300 & 0x30 = 0x30` 算术不成立，实际为 `0`；该节的 `0013` 运行日志与所列 dump 值需要按同一帧、寄存器偏移及字节序重新对齐。上游缺少 RBG 实现可由源码确认，但它与特定黑屏的因果关系尚未由本轮复现。保留历史记录，不将旧结论升级为 Linux 已验证。详见 `LINUX_CLOUD_BUILD.md`。
