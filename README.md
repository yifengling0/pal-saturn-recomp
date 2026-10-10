# PAL-Saturn-Recomp（Windows 阶段）

《仙剑奇侠传1》土星版 SH-2 静态重编译移植。实施蓝图见 `../../PAL_Saturn_Recomp_Windows_HarmonyOS_实施方案.md`；
上一提交的 Linux 准备包内容保留在 `validation/`（其 `TASK_WORKFLOW.md` 的分阶段规程继续适用）。

**当前不是已经完成的游戏移植。** 现在的真实位置：真盘已在本机重编译码上启动，**并已渲染出可操作的等距地图与洞窟场景**
（含剧情、VDP1 精灵、SMPC 手柄、CD 装载），但进入旋转背景的一幕起恒定黑屏，Gate P1 仍未通过，走路问题**未测量**。

## 一分钟结论

- 输入：本地 `../仙剑奇侠传（中）.mdf/.mds` = 土星真盘 RAW 2352 扇区镜像，
  `T-37401H V1.000 19981101`，areas `JT`，`LEGEND OF SWORD AND FAIRY`，SOFTSTAR。
- 已验证：`/0` 装载 0x06004000（入口 0x06004040）；`PROG.BIN` 装载 0x06020000（入口 0x06020040）——两者由**运行时行为**证明。
- 已验证：上游无游戏数据自检在本机全绿（指令自测 9300 向量 0 失败；运行时单测 44/0，含 GPL VDP1 变体）。
- 阻塞（2026-10-10 第八次收窄后）：**运行时未实现 VDP2 的 RBG0/RBG1 旋转合成**。黑屏一幕 `NBG0CFG=0x4300`（HLMT+SDTT）、
  `CHCTL0=0x1212`，背景贴图在 VDP1 VRAM（该帧非零 65,697 字节）；`vdp2.cpp` 的 `note_unsupported` 会打出
  `VDP2: RBG0/RBG1 (0013) is not done`。游戏侧逻辑与 CD 装载是健康的——证据与已作废口径见 `docs/P1_RECOMP_REPORT.md` §4.14。

## 目录

```
game.toml                 真盘模块与地址（每个地址都注明证据来源）
disc/                     由 MDF 还原的 RAW BIN + 13 轨 CUE（原盘文件只读；不入库）
third_party/saturn-recomp 上游固定提交 086c372（core.autocrlf=false，工作树干净；不入库，见下）
patches/                  对上游的改动，逐个补丁文件（0001-0004 已落地，0005 待做）
src/pal_game/             游戏层：诊断 hook（不动上游）
tools/                    winbuild.py / check_windows.sh / vdp2_replay.js / vdp2_inspect.js / wincompat.h
validation/               上一提交的只读输入校验 + 走路 tick 指标 + 26 项自测
docs/                     P0_DISC_ANALYSIS / P1_RECOMP_REPORT / P0_MOVEMENT_BASELINE
evidence/                 日志、清单、模块证据 JSON
build/                    全部产物（不提交）
```

## 首次搭建（本仓库不含上游与版权资产）

```bash
git clone --revision 086c372 https://github.com/callumjenkins/saturn-recomp third_party/saturn-recomp
git -C third_party/saturn-recomp config core.autocrlf false
git -C third_party/saturn-recomp am patches/0001-*.patch patches/0002-*.patch patches/0003-*.patch patches/0004-*.patch
# 想要窗口/手柄/声音，再放一份 SDL3（本仓库也不入库）：解压后把 cmake 目录写进 game.toml 的 cmake 数组
#   SDL3-devel-<ver>-VC.zip → third_party/sdl3/ ，并加
#   "SDL3_DIR=<仓库绝对路径>/third_party/sdl3/SDL3-<ver>/cmake"；SDL3.dll 复制到 build/recomp-build/
# 原盘：把本地 MDF/MDS 还原出的 BIN+CUE 放进 disc/（自行准备，不提供下载）
```

## 复现

```bat
cd PAL-Saturn-Recomp
build\venv\Scripts\python.exe tools\winbuild.py check
build\venv\Scripts\python.exe tools\winbuild.py build --recompile
build\venv\Scripts\python.exe tools\winbuild.py run -- ^
  --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 1500 --shot 600
bash tools\check_windows.sh
cd validation && ..\build\venv\Scripts\python.exe -m unittest discover -s tests
```

环境要求与已实测版本：Python 3.12、cmake 3.26、ninja 1.11、g++ 13.1（MinGW-w64，无 MSVC）。
构建必须**静态链接**（Git for Windows 的 `libstdc++-6.dll` 会盖掉工具链自带的那份，动态产物加载即 0xC0000139），
上游 checkout 必须**保留 LF**（否则 `validation` 的已审查哈希校验失败）。原因写在 `docs/P1_RECOMP_REPORT.md` §2。

## 版权与分发边界

不提交、不打包、不上传任何游戏数据与 BIOS。`disc/` 下的 BIN 是本地 MDF 的逐字节副本，仅用于本机分析；
可提交的是分析代码、游戏层、补丁脚本与不含版权内容的元数据/哈希。个人持有镜像不等于分发移植版的许可。
