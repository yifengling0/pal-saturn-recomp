# P4 鸿蒙移植方案（手机 / 平板 / PC）

日期 2026-10-11。对应任务 #11–#15。图形、音频、输入按用户指定走 SDL3；真机测试由用户自己做。

## 1. 先核实过的地基（不是推测）

| 结论 | 证据 |
| --- | --- |
| SDL3 官方已有 HarmonyOS/OpenHarmony 后端，但**只在 `main` 分支** | `src/core/openharmony/`、`src/video/openharmony/`（16 个文件，含 window/events/keyboard/mouse/clipboard/opengl/vulkan）；`release-3.4.x` 与 tag `release-3.4.18` 下同样的路径返回 404；合入时间 2026-09-15 的提交 `harmonyos: Port SDL3 to HarmonyOS/OpenHarmony.` |
| 音频也有鸿蒙专属后端，不用自己写 | 用 DevEco 的 NDK 配置 SDL3 后打印 `Audio drivers: disk dummy **ohaudio**`，源码在 `src/audio/ohaudio` |
| 本机工具链齐全 | `C:\Program Files\Huawei\DevEco Studio`（`DS-261.23567.138.36.2600851`）；SDK `sdk/default/openharmony/{ets,js,native,toolchains}`；NDK `apiVersion 26 / 26.0.0.105`，`native/build/cmake/ohos.toolchain.cmake`，Windows 版 `llvm/bin/clang.exe`；`hdc` 已在 PATH |
| **SDL3 的 OHOS 交叉编译在本机可用** | 配置 + 编译均 exit 0，产物 `build/sdl3-ohos-arm64/libSDL3.a`，目标文件 `ELF64 / AArch64` |
| 缺口：**SDL3 没有实体手柄的 OHOS 后端** | `src/joystick/` 下只有 android/apple/bsd/dummy/emscripten/gdk/haiku/hidapi/linux/virtual/windows…，配置输出也是 `Joystick drivers: dummy virtual`；`src/haptic/` 同样没有 ohos |

复现命令：

```
git clone --depth 1 -b main https://github.com/libsdl-org/SDL.git third_party/sdl3-src
NATIVE="/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/native"
cmake -S third_party/sdl3-src -B build/sdl3-ohos-arm64 -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$NATIVE/build/cmake/ohos.toolchain.cmake" \
  -DOHOS_ARCH=arm64-v8a -DCMAKE_BUILD_TYPE=Release -DSDL_SHARED=OFF -DSDL_STATIC=ON \
  -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF -DSDL_HAPTIC=OFF
cmake --build build/sdl3-ohos-arm64 --target SDL3-static --parallel 8
```

## 2. 版本策略（要先定）

Windows 现在用的是 SDL3 **3.4.18 预编译包**，而鸿蒙需要 **main**。两端不同版本的 SDL 会在手柄、事件与渲染细节上产生差异，而本项目的验收方式是"同一输入脚本比 PNG 哈希"。建议：把两端都统一到同一个 SDL3 提交（main 上取一个固定 SHA），Windows 侧改为从源码编 SDL3，`game.toml` 的 `SDL3_DIR` 指向自建产物；这样"鸿蒙与 Windows 行为一致"才是可验证的命题，而不是碰运气。

## 3. 结构

```
HarmonyOS App (HAP)
├─ ArkTS 壳：EntryAbility + XComponent(或 SDL 的 native 入口)
│   ├─ 左右边缘划出 → 设置抽屉（#13）
│   ├─ 土星造型虚拟手柄（#14，矢量绘制，接实体手柄时自动隐藏）
│   ├─ 设备/布局：手机、平板、PC 三档（#13/#14）
│   └─ 手柄：inputDevice.getDeviceList / inputMonitor → NAPI → SDL 虚拟手柄事件（#15）
└─ native：libsaturn_ohos.so = saturn 运行时(交叉编译) + libSDL3.a + 仙剑游戏层
```

游戏侧代码不动：`runtime/src/host/host.cpp` 已是纯 SDL 实现（窗口、键盘、手柄、节奏、菜单），鸿蒙上换的是**编译目标 + 平台后端**，不是宿主逻辑。上游改动仍走 `patches/*`，SDL3 侧若需要补丁，单独放 `patches/sdl3/` 并记哈希。

## 4. 资源与存档（#12，用户明确要求）

- HAP 内**不放**任何原版内容：不打进 BIN/CUE、图像、音乐、BIOS。
- 运行数据统一放 `download/<bundleName>/`：`disc/`（玩家的 CUE+BIN）、`saves/`（`.bup`）、`settings.ini`。
- Windows 保持现有 `disc\` 行为；把路径解析收进一个 `pal_paths` 小模块，两端各自实现根目录（Windows=exe 目录，鸿蒙=Download 下按包名建的目录）。
- 首次运行找不到盘：给出明确提示与"选择文件"入口（鸿蒙侧要处理用户授权与持久化 URI 权限），不要静默失败。
- 存档一律走工作副本，测试永不覆盖玩家存档（沿用 `--save -` 约定）。

## 5. 里程碑

| 里程碑 | 内容 | 完成判据 |
| --- | --- | --- |
| M1（#11） | SDL3 + 运行时交叉编译进 HAP，模拟器里出一个 SDL 窗口 | `hdc` 起应用，窗口出现，hilog 无 FATAL |
| M2（#12） | 从 `download/<bundleName>/` 读盘读档 | 模拟器/真机上跑到标题，PNG 与 Windows 基准同哈希 |
| M3（#14/#13） | 虚拟土星手柄 + 左右划设置抽屉 | 触屏能走路、开菜单、改设置并持久化 |
| M4（#15） | 实体手柄（鸿蒙自研后端或 ArkTS→NAPI 转发）+ Windows 手柄补齐 | Xbox/Switch Pro 两种设备可走路、确认、开菜单 |
| M5 | 手机/平板/PC 布局与性能收尾 | 三档分辨率无裁切，帧率与发热可接受 |

## 6. 已知风险与待验

1. **实体手柄**：SDL3 无 OHOS 手柄后端，且 `multimodalinput` 的 C 头文件里 `SOURCE_TYPE_*` 只有 MOUSE/TOUCHSCREEN/TOUCHPAD，轴类型也只有滚动/捏合，看不到摇杆轴。可行路线是 ArkTS `inputDevice`/`inputMonitor` 拿到设备与轴值，经 NAPI 灌给 SDL 的虚拟手柄（`src/joystick/virtual` 已在编译里）。真机插手柄后 `inputDevice.getDeviceList()` 能否列出 JOYSTICK 类型，**必须在真机验证**，这是 M4 的第一个实验。
2. **短按丢失（已在 Windows 实测到）**：用 `--virtual-input` 走 SDL 手柄路径跑读档脚本，菜单能打开，但后续两次 START 没生效，画面停在读档菜单；同一脚本走键盘 `--input` 则正常进游戏。说明 SDL 手柄→SMPC 这条链会吞掉 12 VBlank 的短按。虚拟手柄和实体手柄都会踩到，M3/M4 之前要先定口径（消费一次意图 + 最小按住时长，参考 `docs/INPUT_RESPONSIVENESS.md` 的既有选项）。
3. **`--headless` 下 SDL 宿主不生效**：`--virtual-input` 在无窗口构建里完全不起作用，验证手柄链路要用 `SDL_VIDEODRIVER=dummy` 且不带 `--headless`。鸿蒙侧的自动化测试同理。
4. **模拟器架构**：本机 HVD 镜像大概率是 x86_64，需要再出一份 `OHOS_ARCH=x86_64` 的 SDL 与运行时；`--parallel` 编译运行时的 2283 个重编译函数会比 Windows 慢，先按 arm64 做真机路径。
5. **VDP1 GPL 选项**：鸿蒙包同样保持 `SATURN_VDP1_GPL=OFF`，否则整个应用变 GPL 作品，分发方式要重定。

## 7. 资源与存档到底怎么加载（2026-10-11 真机已验）

运行时只认命令行：`--cue` 必需（`app/main.cpp:175` 没有就退出），`--save` / `--settings` 缺省落在 `sat_data_dir()`（`machine/bios.cpp`），设备上这两个环境变量基本不存在，所以鸿蒙必须显式给路径。

入口这一层 SDL 已经规定死了，实测纠正了第 7 节早先的判断：

- SDL3 的 `main` 分支**有** `src/main/openharmony/SDL_sysmain_runapp.c`（3.4.18 的发行包里没有，我们的 `third_party/sdl3-src` 是 main）。
- XComponent 建好后它 `dlopen("libmain.so")`，**先找 `SDL_main`**，找到就起一个线程跑；找不到才退回去找 `SDL_AppInit/Iterate/Event/Quit` 四件套。
- 运行时的 `main.cpp` 只在 `#if defined(__ANDROID__)` 里 `#include <SDL3/SDL_main.h>`，所以鸿蒙上导出的仍是 `main`，第一次真机启动就死在 `Couldn't find SDL_AppInit in libmain.so`（hilog 里 SDL/STARTUP 打的）。
- 修法不动上游：HAP 的 cpp 里把 `main.cpp` 单独加 `-Dmain=saturn_main`，再由 `pal_ohos_entry.cpp` 导出 `extern "C" int SDL_main()`，自己拼 argv 再调 `saturn_main`。鸿蒙本来就要求 `libmain.so` 这个名字，壳层跟运行时同在一个 so 里，没有额外产物。

目录在 native 侧就能算出来，NDK API 实测可用：

| 用途 | 原生 API | 平板上实测值 |
| --- | --- | --- |
| 用户 Download 根 | `OH_Environment_GetUserDownloadDir()` | `/storage/Users/currentUser/Download`（大写 D） |
| 包名 | `OH_AbilityRuntime_ApplicationContextGetBundleName()`（`libability_runtime.so`） | `com.palhero.palsaturn` |
| 沙盒兜底 | `OH_AbilityRuntime_ApplicationContextGetFilesDir()` | `/data/storage/el2/base/files` |

查找顺序：`<Download>/<包名>/` → `<files>/<包名>/` → `<files>/`；每个根里先 `disc/` 再本层，`.cue` 优先于 `.bin`。存档跟着盘走（`<root>/saves/pal-saturn.bup`），只有盘所在目录不可写时才退回沙盒，避免悄悄丢档。

权限只有一条实测结论：`ohos.permission.READ_WRITE_DOWNLOAD_DIRECTORY`（user_grant，DevEco 自动签名可动态申请，装机不报错）**必须先在应用里点一次"允许"**。没授权时 `<Download>` 能 stat、不能 mkdir（EPERM）；授权后 readdir、新建文件、`mkdir <Download>/com.palhero.palsaturn/disc` 全部成功，所以首次运行就能把目录摆好等玩家放盘。已授权后 `SDL_RequestOpenHarmonyPermission()` 不再弹窗，百毫秒内回调。注意该权限的"支持设备"只写了 PC/2in1 与 Tablet，手机仍要走沙盒兜底。

## 8. 目前进度（2026-10-11，真机 MLR-AL10 平板：已经跑出游戏画面）

`build/venv/Scripts/python.exe tools/ohosbuild.py --skip-learn --launch` 一条龙：出签名包 → `hdc install -r` → `aa start` → 回打 hilog。装到真机后 hilog 走通这条链：

```
SDL/STARTUP: Handing control from ArkTS to native SDL.   // EntryAbility 把对象交给 native
SDL/STARTUP: Calling SDL_main!                           // 引导在 libmain.so 里找到了入口
PAL/OHOS:   argv: saturn --cue /storage/Users/currentUser/Download/com.palhero.palsaturn/disc/pal_t37401h_13tr.cue ...
PAL/OHOS:   SDL: drawing with opengles2
PAL/OHOS:   IP.BIN: T-37401H   V1.000, areas JT; 1st read file 0, 53068 bytes at 06004000
PAL/OHOS:   boot: P0 at 06004000 / PROG activated by a call to 06020040
```

`uitest screenCap` 收到的是全屏、比例正确的 SOFTSTAR 片头（`build/oh-game3.png`）。`VDP2: RBG0/RBG1 (0013) is not done` 在 Windows 的六次运行里同样出现，不是鸿蒙独有的分叉。

链路上确定下来的几件事：

- 入口只认 `SDL_main`：壳层给 `main.cpp` 单独加 `-Dmain=saturn_main`，`pal_ohos_entry.cpp` 导出 `extern "C" int SDL_main()` 自己拼 argv，不改上游。
- 鸿蒙没有控制台，所以 `pal_ohos_entry.cpp` 把 stdout/stderr 接进管道再逐行送 hilog；不然 `sat_note` 全部丢掉，出问题只能靠猜。
- `runtime.cmake` 用 `find_package(SDL3 CONFIG)` 决定 `host.cpp` 还是 `host_null.cpp`。源码 `add_subdirectory` 没有 config 文件，一开始静悄悄链进了空 host，日志只留一句 `built without SDL`。现在由 `cpp/cmake/SDL3Config.cmake` 补一份"已找到"的凭据。
- 全屏靠 `--fullscreen`：SDL 的鸿蒙后端用 `setSystemBarEnable` 实现，状态栏和手势条都会收掉。
- `--settings` 必须显式给，否则 `sat_data_dir()` 会去写 `$HOME/.local/share`（设备上 EPERM）。现在 settings/saves 都落在盘所在的那个目录。
- 默认**不进**那套 ImGui 大菜单，直接起游戏；`<root>/advanced.txt` 存在才带 `--launcher`，留给"扩展设定"面板用。

`build-profile.json5` 的坑：DevEco 26.0.0（API 26）会拒绝 `compileSdkVersion: "6.1.0(23)"`（00303313），删掉这一行由 DevEco 内置 SDK 决定；只留 `targetSdkVersion` 与 `compatibleSdkVersion`，并满足 compatible <= target <= compile。

自测开关：`cpp/selftest.txt` 写 `on` 时，设备上没有盘就在沙盒里生成一张全零合成盘（`<files>/selftest/disc/`）走到 `video_init()`，用来在没盘的情况下验窗口；`tools/ohosbuild.py --selftest on|off` 改它。

剩下的：划出的"扩展设定"面板（#13）、土星造型虚拟按键并在无键盘/手柄时自动开（#14）、手柄（SDL 鸿蒙没有 joystick 后端，#15）。另外 `libmain.so` 里带着 2,270 个从原版 PROG 重编译出来的函数，等于游戏程序随包分发——**这个 HAP 只能自用，不能公开**；要出可分发的包，得把 learn 挪到玩家自己那一步。

## 9. 音频卡顿交接（2026-10-11，请专家接手）

现象：真机（MLR-AL10 平板，`MLR-AL10 7.0.0.109(SP6C00E105R1P2)`）片头和游戏的音频明显卡顿，玩家判定"还是卡"。

已经排除的两件事：

- **不是算力**。收尾是 `stopped (...) after 5086 VBlanks, 84.848 s` —— 正好 60.0 fps 实时；`top` 看整个进程约 137% CPU（12 核机器）。
- **不是片头那次的逻辑 bug**。同一份 `build/recomp` 在 Windows 上跑同样的开场是 `audio stream: 0 times empty, 0 chunks dropped`（六次运行里最多 2 次）。

量到的数：

```
SDL: drawing with opengles2
audio: device 44100 Hz 2 ch, 4096 frames a pull, lead 4410     // 改后
audio stream: 906 times empty, 0 chunks dropped                // 改前（lead 2205 = 50 ms），约 10.7 次/秒
```

机制推测：SDL 的 ohaudio 后端把 renderer 固定成 `AUDIOSTREAM_LATENCY_MODE_FAST`（`third_party/sdl3-src/src/audio/ohaudio/SDL_ohaudio.c:405`），设备一次回调要 **4096 帧（93 ms）**；而 `host_audio_push` 每个 VBlank 只喂 735 帧，一旦 `SDL_GetAudioStreamQueued()` 归零就补一段静音，于是每次抽干都是一次听得见的间断。

我改了什么、效果如何（`patches/0008-harmonyos-touch-and-audio.patch`）：

- `SDL_SetHint(SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES, "1024")` —— **没生效**，打点显示设备仍然 4096 帧一次，说明 OHOS 后端不理这个 hint。
- lead 从固定 50 ms 改成 `clamp(3 * 设备的 frames, 2205, 4410)`（这次算到 100 ms）。**改后到底还饿不饿我没量到**：平板当时在前台跑别的应用，我没再点它。这是下一步第一个要取的数。

复测一条命令：`build/venv/Scripts/python.exe tools/ohosbuild.py --skip-learn --launch`，进游戏后点顶部 ☰ → Quit，收尾会打 `stopped (...) after N VBlanks, X s` 和 `audio stream: N times empty`；hilog 标签 `PAL/OHOS`（stdout 已经被接进 hilog，见第 8 节）。

没验证的线索，按我判断的价值排序：

1. SDL 侧：把 ohaudio 的 latency mode 换成 NON-TIMING，或真正把 `SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES` 落到 `OH_AudioStreamBuilder_SetFramesPerCallback`。这是上游 SDL 的改动，不在我们补丁体系里。
2. 生产端：`sound.cpp` 能否一次凑够 4096 帧再入队，而不是每帧 735 帧；抽干窗口会成倍变长。
3. `queued == 0` 就补 `g_lead` 静音，等于把延迟一次性抬高 100 ms；也许该按设备剩余量补，或者允许一次小欠载而不插静音。
4. 44100 → 设备 48000 的重采样在 FAST 模式下的抖动没测过。

同一条补丁里顺带做的（都不是音频）：触摸面板和暂停菜单改成按画面尺寸放大；点面板外面算关闭；`--settings` 在鸿蒙上必须显式给（否则写 `$HOME/.local/share` 被拒）。还没做的：高级菜单（`--launcher`）在设备上没入口（#19）、菜单与按键的显隐规则没理清（#20）、手柄（#15，SDL 鸿蒙没有 joystick 后端）。

## 10. 0009 的复测结果（2026-10-11，同一台 MLR-AL10，release HAP）

设备上报：`audio: device 44100 Hz 2 ch, reported quantum 4096, source lead 4410/44100 (capped=1 valid=1 format=32784)`、
`audio: driver=OHAudio guest_realtime=0`。一次拉取 4096 帧 = 92.9 ms，lead 被 100 ms 上限截住，
**只比一个 quantum 多 7%**。第 9 节里第 4 条猜测可以直接划掉：设备就是 44100 Hz，没有重采样。

| 会话 | 模拟时长 | VBlank/s | times empty | 次/秒 | recovery_zeros | dropped_frames | query/put errors |
|---|---|---|---|---|---|---|---|
| 0008 前 | 84.8 s | 60.0 | 906 | 10.7 | — | — | — |
| 1（16:39–16:47） | 389.2 s | 59.94 | 123 | 0.32 | 542430 帧 = 12.3 s | 9358 | 0 / 0 |
| 2（16:49–16:54，含走路换幕） | 283.4 s | 59.94 | 44 | 0.155 | 194040 帧 = 4.4 s | 11209 | 0 / 0 |

Windows 基准：56 s 无头跑 `times empty` 0–2。

结论：频率掉了两个数量级，但没归零。每次 empty 事件补的正好是一整个 lead（542430/123 = 4410 帧），
所以残留缺陷是"每 3–6 秒一个 100 ms 的洞 + 100 ms 整体延迟"，不再是每秒十次的爆音。
`max_push_gap_us` 两次 22.3 s / 9.4 s 都落在菜单暂停期（`sat_resuming()` 不推 PCM），属预期。
第 9 节第 3 条现在有了数据支撑：`plan_push` 在 `queued==0` 时补 `min(headroom, lead)`，headroom 有 10290 帧，
所以每次都是硬补满 4410。两个抓手（都还没实机验证）：

- lead 上限 4410 与 quantum 4096 太贴，一次拉取抖动就吃光余量：改成 `max(lead, 2*quantum)`（≈8200 帧 / 186 ms）并同步放宽队列上限，代价是延迟。
- empty 后改成"补到 lead"（`lead - 已入队`）而不是"补一个 lead"，避免每次事件硬插 100 ms。

原始日志：`build/audio-after-quit-0009.txt`（会话 1）、`build/audio-session2.txt`（会话 2）。
复测流程与第 9 节末尾一致，只是 `--launch` 之后要跑 3–6 分钟再 Quit，统计只在退出时打印。

## 11. 触摸菜单与虚拟按键的实机验收（同一批构建）

已修好并被截图证实（`build/after0009.png`、`build/menu0009.png`、`build/fill.png`、`build/padoff.png`、`build/size70.png`、`build/walk.png`）：

- 虚拟按键按画面大小自适应：`touch_pad_unit = max(480*density, 0.45*屏高) * size/100`；2560×1600 平板上
  L/R、十字键、A B C / X Y Z、START 全部清晰可点，Size 每档 10% 且实时重排。
- 菜单三条关闭路径都有效：Resume、右上角 X、点面板外。Resume 后画面与暂停前逐字节相同（PNG SHA256 一致），
  暂停/恢复没有推进虚拟时间。
- Picture 三档 TV / Fit / Fill 都生效（Fit 左右黑边、Fill 拉满 16:10、TV 略宽于 Fit）。
- Show pad = Off 时按键全消失但 ☰ 保留；Auto/On/Off、Style、Opacity、Menu button 都写回 settings.ini 并在下次启动保留。
- 触摸确实能驱动土星手柄：点 A 推进对白、划十字键让李逍遥在客栈走动并换幕；平板上没有 Windows 那条走路停滞问题。

剩下：#13 没有左右划出手势（只有顶部中间一个 ☰，直径约 86 px ≈ 43 dp，低于 48 dp 建议值）、
#19 触摸菜单里没有高级设置/launcher 入口、#21 关掉 Menu button 会永久锁死菜单（静态取证，没敢在用户平板上实做）、
#22 菜单全英文且 Quit 没有二次确认。
