# PAL-Saturn-Recomp（Windows 阶段）

《仙剑奇侠传1》土星版 SH-2 静态重编译移植。实施蓝图见 `../../PAL_Saturn_Recomp_Windows_HarmonyOS_实施方案.md`；
上一提交的 Linux 准备包内容保留在 `validation/`（其 `TASK_WORKFLOW.md` 的分阶段规程继续适用）。

**当前仍未完成完整游戏验收。** 2026-10-10 Linux 云端已完成真实 SDL3 窗口、开场视频、键盘接收及真盘重编译验证。早期截图中的户外/洞窟是 `A3.AVI` 开场影片，不能作为可操作地图证据。旧版后续黑背景已定位到 SH-2 DMA 16-byte burst 的短拷贝缺陷，最小补丁及合成红绿回归见 `docs/DMA_BURST_FIX.md`；真实修复后客栈背景、头像、对白已恢复，原生 SDL 键盘成功推进对白；完整移动、切场和存取档继续验证。

## 鸿蒙手机启动与镜像目录

当前源码修复了手机横屏与 Download 首次创建：启动前使用系统应用专用下载目录，缺盘或无访问权限时保留准备界面，也可通过系统文件选择器导入完整 CUE + BIN。原存档目录保留，不自动覆盖。操作步骤、支持边界和真机检查清单见 [docs/OHOS_PHONE_STORAGE.md](docs/OHOS_PHONE_STORAGE.md)。此修复晚于 `v0.1.0-preview.2`，旧发行 HAP 不包含它。

## 横屏、竖屏与分屏布局

鸿蒙支持横竖屏独立保存画面与按键布局，手动选择上下/左右分区、调整画面大小并拖动位置。升级兼容规则、操作与验证入口见 [docs/FLEXIBLE_LAYOUT.md](docs/FLEXIBLE_LAYOUT.md)。

## Windows 选项验证入口

本轮跨平台接入与本地测试步骤见 [docs/WINDOWS_OPTIONS_TEST.md](docs/WINDOWS_OPTIONS_TEST.md)。`winbuild.py --pal-options` 编入精准输入v4及快速施法v3，两者运行时默认关闭；用新的Python profile启动器分别对照，不再依赖Linux实验目录。Windows实际声卡仍待本地验证。数据扇区提速的默认1、可选2/4档见 [docs/DATA_CD_SPEED.md](docs/DATA_CD_SPEED.md)，不改变CDDA或全局时钟。当前玩法覆盖见 [docs/COVERAGE_STATUS.md](docs/COVERAGE_STATUS.md)，不要把下文早期阶段描述当成最新验收范围。

## 一分钟结论

- 输入版本：`T-37401H V1.000 19981101`，areas `JT`，`LEGEND OF SWORD AND FAIRY`，SOFTSTAR；新提供 BIN/CUE 的哈希与历史证据相同。
- Linux 环境、命令、测试结果：`docs/LINUX_CLOUD_BUILD.md`；真实 SDL3 桌面配置：`docs/SDL_LINUX_PROBE.md`。
- 最新诊断：DMA burst 重复除以4，使地图和纹理只复制四分之一，却报告完成。`0005` 删除多余循环增量，四项 DMA 数据/地址/结束标志回归通过。
- 历史 RBG 黑屏结论已撤回：正确 BE 解码的 BGON 是 `0x0043`，旋转层 enable 位未开；旧报告把端序、位掩码及黑色像素的非零量混为证据。保留原历史报告以供对照，但不作为当前根因。
- 完整自由移动、剧情、场景切换、存取档及 Windows 实机音频尚不能由合成或 Linux headless 成功代替。

## 目录

```
game.toml                 真盘模块与地址（每个地址都注明证据来源）
disc/                     由 MDF 还原的 RAW BIN + 13 轨 CUE（原盘文件只读；不入库）
third_party/saturn-recomp 上游固定提交 086c372（core.autocrlf=false，工作树干净；不入库，见下）
patches/                  对上游的改动，逐个补丁文件（0001-0005 已落地）
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
# These files are raw diffs, not git-am mail patches. Keep a clean parser checkout.
git clone --no-hardlinks third_party/saturn-recomp third_party/saturn-recomp-pal
for p in "$PWD"/patches/000{1,2,3,4,5}-*.patch; do
  git -C third_party/saturn-recomp-pal apply --check "$p" && \
  git -C third_party/saturn-recomp-pal apply "$p" || exit 1
done
# 想要窗口/手柄/声音，再放一份 SDL3（本仓库也不入库）。机器路径不进 game.toml——用命令行传：
#   SDL3-devel-<ver>-VC.zip 解压到 third_party/sdl3/ ，然后
#   python tools/winbuild.py build --sdl-dir third_party/sdl3/SDL3-<ver>/cmake
#   并把 SDL3.dll 复制到 build/recomp-build/（exe 旁边）；不带 --sdl-dir 时用 --headless
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

## Linux cloud validation (2026-10-10)

See `docs/LINUX_CLOUD_BUILD.md`. Linux uses isolated build directories, a clean pinned parser checkout, and a separately patched runtime. `tools/check_linux.sh` fails on every failing stage. Historical Windows results above are not Linux test results.

### PC keyboard support

The portable Windows build driver now prepares context-aware Enter/Esc keyboard
profiles independently of optional timing changes. Rebuild, then select PC98
in the launcher Controls page for an existing settings file; fresh settings
already default to PC98. Old custom bindings and gamepad maps are retained.
See [PC keyboard guide](docs/PC_KEYBOARD.md) and
[Windows test commands](docs/WINDOWS_OPTIONS_TEST.md).
