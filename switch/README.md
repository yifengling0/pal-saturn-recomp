# 仙剑土星重编译 · Switch homebrew 预览

这是 **NRO 自制程序**，不是零售 NSP，需已有可运行自制程序的 Switch 环境；本文不提供绕过主机安全机制的方法。只做了 AArch64 交叉编译和静态/宿主测试，**尚未做 Switch 真机启动、帧率、音频和手柄验证**。不要把可链接视为已流畅可玩。

## 放入程序和游戏资源

把压缩包的 `switch/` 合并复制到 SD 卡根目录，保持：

```
SD卡:/switch/pal-saturn-recomp/pal-saturn-recomp.nro
SD卡:/switch/pal-saturn-recomp/resources/你的原盘.cue
SD卡:/switch/pal-saturn-recomp/resources/原盘引用的全部.bin
```

资源必须由用户自行合法提供：台湾土星版 **T-37401H V1.000、13轨、原始2352字节扇区 CUE/BIN**。可以是一个多轨 BIN，也可以是逐轨 BIN。只放一个 CUE；保持 BIN 文件名（含大小写/空格）和 CUE 引用的子目录。不能只放第1轨，也不能只改压缩包/ISO的扩展名。独立 PREGAP/POSTGAP 暂不支持，会明确拒绝，不会静默错轨。

程序会检查缺文件、空文件、扇区对齐、13轨次序和类型、INDEX 时间/范围、确切原盘TOC、总计243793扇区（573401136字节）以及第一轨产品身份；不符时显示英文错误和路径，按 A 重试、+ 退出。仅支持和此版原盘一致的无虚拟gap raw布局；不同布局即使游戏相同也会拒绝。校验不等于完整光盘逐字节哈希校验，错误资源内容仍可能影响游戏。**不要在程序访问SD时拔卡**；需重拷贝时先退出，再安全移除。

程序不改写原始 CUE/BIN。它在程序目录生成 `launch.cue`（只是规范化的路径/轨道元数据），兼容指令大小写、UTF-8 BOM 和路径反斜杠。Windows路径盘符、上级目录引用等不接受。不会把光盘资源装进 NRO/ROMFS。

## 操作和存档

资源合格后进入原有启动设置菜单，方向键/摇杆选择；菜单确认按物理 B（SDL South），返回按物理 A（SDL East）。游戏使用原有土星映射：B→土星A、A→土星B、R→C、Y→X、X→Y、L→Z，ZL/ZR→L/R，+→Start；- 打开宿主菜单。可在设置中重新绑定。需真机确认系统实际映射。

存档独立在 `SD卡:/switch/pal-saturn-recomp/saves/`：
- `pal-saturn.bup`：本机备份内存；
- `pal-saturn-cart.bup`：卡匣进度，第一次存档时生成。

复制自己已有的同版本存档前先退出程序并备份整个 saves。重新导入/更换资源不会删除存档。设置保存在 `settings.ini`，运行日志是 `runtime.log`。不要删 saves 来解决缺资源。升级只替换 NRO，不覆盖存档或设置。默认游戏时钟与 preview7 一致为 1998-11-01T12:00:00。

## 构建和技术边界

基于主仓库 preview7 `d7d9306c7e7063dd136f468a0ba55a8aeb011573`，完整原版静态重编译逻辑与 PAL 适配层，不是启动空壳。

官方开源 SDK：devkitPro devkitA64 r30（GCC16.1.0、newlib4.6）、libnx4.12.0、switch-tools1.13.1、switch-cmake1.5.2、Mesa20.1.0-5、libdrm_nouveau1.0.1-2。安装官方 `switch-dev` / 对应 portlibs；SDK 不在源码补丁内。

SDL 来自 **devkitPro 官方 fork** `switch-sdl-3.4` 分支固定提交 `c329016c0e338ab4397ad930f83330c9fe058348`（SDL3.4.0），不是 SDL2，也不是 libsdl.org 提及的 Nintendo NDA 商业端。配置实际启用 switch 视频、音频、手柄和 OpenGL/OpenGL ES2 renderer。仅可选外部 ffmpeg MP4 导出和桌面 open-shell 禁用；WAV、SDL 音频和软件 VDP→GPU呈现保留。编译强制要求 SDL3，禁止默默降为 headless。SH-2 使用和 Windows/OHOS一致的串行协程调度。

先按主仓库现有工作流从自己合法原盘提取 `build/disc-extract` 并完成 `tools/winbuild.py build --pal-options` 的生成步骤（该脚本虽叫winbuild，生成器可在Linux执行）。`PAL_GENERATED` 指向其 `recomp/` 与 `runtime/` 的父目录。不要重新用未打PAL补丁的上游代码代替。

```
export DEVKITPRO=/path/to/devkitpro
export PAL_GENERATED=/path/to/full-options-generated-build
export SDL_SWITCH_SOURCE=/path/to/devkitPro-SDL-at-pinned-commit
export PAL_SWITCH_BUILD=$PWD/build/switch-fresh
JOBS=3 bash switch/build.sh
```

需 CMake/Ninja/Python3 在 PATH。脚本拒绝覆盖已有生成目录；使用新构建目录。最终产物在 `$PAL_SWITCH_BUILD/native/pal-saturn-recomp.nro`。脚本通过 `switch/platform.cmake` 添加入口、PAL适配和NRO元数据，不直接改写共同运行时。`switch/verify_nro.py` 检查NRO段/元数据/不含资源ROMFS。

宿主可用 `g++ -std=c++17 switch/test_disc_files.cpp -o test-disc` 后传入新的临时目录运行自造异常资源测试；`test_core_disc.cpp` 还需链接已生成运行时的 `src/machine/cdrom.cpp`，给合法CUE和位于其resources父目录的输出launch.cue进行真实解析回归，生成文件不能指向原始CUE。

官方源：
- https://github.com/devkitPro/SDL/tree/switch-sdl-3.4
- https://github.com/devkitPro/pacman-packages
- https://github.com/switchbrew/libnx
- https://devkitpro.org/wiki/Getting_Started

## 权利说明

NRO包含运行时、PAL适配层和从原版程序静态重编译的游戏逻辑。未附光盘资源并不代表没有原作衍生代码；运行时MIT、SDL zlib等许可证不能用来声称整包/原作逻辑是MIT或已获原作权利人授权。再分发前需自行确认相关权利。详见 NOTICE 和 licenses。未附光盘镜像、BIOS、用户存档或提取资源。
