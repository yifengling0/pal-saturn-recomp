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

以下是 2026-10-11 平板的历史路径/权限记录，已被后续手机兼容启动页替代。当前实现及验证边界见 [OHOS_PHONE_STORAGE.md](OHOS_PHONE_STORAGE.md)。旧记录不能作为手机 API 支持或本次真机通过的依据。

当时目录在 native 侧计算，NDK API 平板记录如下：

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

自测开关：`cpp/selftest.txt` 写 `on` 时，设备上没有盘就在沙盒里生成一张全零合成盘（`<files>/selftest/disc/`）走到 `video_init()`，用来在没盘的情况下验窗口；`tools/ohosbuild.py --selftest on|off` 同时更新它和页面的 rawfile 开关；不要只手改其中一个。

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

## 12. 0010 这轮：图标、手柄桥接与两个构建坑（2026-10-11 傍晚）

### 图标（两端都换，落点在 `src/pal_game/app_icon/`）

同一套"玉剑"图我这边先按 `pal-saturn-platform-icons-v1.zip` 接过一次（四个用到的文件与包内
`validation.json` 的 SHA256 逐个对上：`pal_saturn.ico 86813d77…`、`harmony_foreground.png f1397687…`、
`harmony_background.png 415dcfb8…`、`windows_icon_1024.png 452b5351…`），专家那边同一时间也推了同图不同落点的
`05ce227/37f53d4/4281179/58ed8cd/8fa1b86`。合并时以他的为准，我那份 `assets/icons/` 副本删掉了，出处看 `docs/APP_ICON.md`。

- Windows：`src/pal_game/app_icon/pal_app.rc` + `pal_saturn.ico`，由 `src/pal_game/pal_game.cmake` 的
  `if(WIN32)` 分支挂进 `saturn` 目标，不碰上游。验证方式是从产物里把图标抠回来：
  `Add-Type -AssemblyName System.Drawing; [System.Drawing.Icon]::ExtractAssociatedIcon(...saturn.exe)`，
  取回 32×32 的剑与土星环，换 exe 前后位图哈希一致。
- 鸿蒙：`AppScope` 与 `entry` 两处 `resources/base/media/{background,foreground}.png` 换成 1024 图层，
  `startIcon.png` 用整幅合成图。打包后从签名 HAP 里解出来核对过：hvigor 会重压缩 PNG，所以哈希必然不同，
  只能看图——图是对的。真机桌面图标没截到（`keyEvent Home` 被 SDL 吃掉，应用一直停在前台），这一项留给用户目视确认。
- 顺手补的：`WIN32_EXECUTABLE TRUE`，双击不再弹控制台（`PAL_CONSOLE=1` 可以把日志要回来，见第 13 节）。

### 实体手柄桥接在真机上起来了

新 HAP 启动日志：`gamepad OHOS: API 21 callbacks registered, SDL native preference=0` →
`gamepad OHOS: enumerated=0 status=ok` → `gamepad: SDL joystick=0 mapped=0 opened=0`。
`dlopen` 与符号解析全部通过，只是手边没有蓝牙/USB 手柄可插，所以 `enumerated=0`。
#15 到"桥接可用"这一步为止，热插拔/按键映射/切后台仍要接了真手柄再测。

### 两个构建坑（都会让人白跑一次）

1. **鸿蒙 native 配置失败**：专家新加的 `target_link_libraries(saturn_host PUBLIC ${CMAKE_DL_LIBS})`
   写在 `entry/src/main/cpp/CMakeLists.txt`，而 `saturn_host` 是 `build/recomp` 子目录里的 target，
   `cmake_minimum_required(VERSION 3.5.0)` 下 `CMP0079` 是 OLD，直接报
   `Attempt to add link library "dl" to target "saturn_host" which is not built in this directory`。
   修法是在 `project()` 后加 `cmake_policy(SET CMP0079 NEW)`（本地壳工程改动，不进上游补丁）。
2. **`tools/winbuild.py build` 不带 `--sdl-dir` 会静默产出无窗口 exe**：只链 KERNEL32/msvcrt，
   双击后立刻退出，而构建本身 exit 0。带图标的正确姿势是
   `tools/winbuild.py build --sdl-dir third_party/sdl3/SDL3-3.4.18/cmake`，
   然后用 `objdump -p build/recomp-build/saturn.exe | grep "DLL Name"` 确认出现 `SDL3.dll`。
   `tools/make_dist.py` 会先 `shutil.rmtree(dist/…)` 再重建，包里的 `saves/`（玩家进度）会被一起删掉，
   所以**不要**在已有存档的情况下拿它重打发行包；原地换 exe 并同步 `SHA256SUMS.txt` 里的 `saturn.exe` 行就行。

### PC 版实机跑法（带本機進度）

```bash
dist/pal-saturn-recomp-win-x64/saturn.exe \
  --cue <repo>/disc/pal_t37401h_13tr.cue \
  --settings <dist>/settings.ini \
  --save <dist>/saves/pal-saturn.bup \
  --cart <dist>/saves/pal-saturn-cart.bup \
  --clock 1998-11-01T12:00:00
```

`settings.ini` 里 `keyboard_profile = pc98`，所以专家这轮的 F（最强武功）/ R（重复上次指令）在这条路上生效。
包内 `saves/pal-saturn.bup` 就是白河村三人队胜利那份（`a4d8f748…`，与 `baihe-first-three-party-victory.bup` 同哈希）；
启动前先另存了一份 `pal-saturn.before-pc-session-20261011-1812.bak.bup`，并写进了 SHA256SUMS。
标题选「舊的回憶」读的就是这份本機進度；要四格存档位则用卡匣（第一次往卡匣存盘才会长出 `pal-saturn-cart.bup`）。

## 13. 方向键第一帧与收手（2026-10-11 深夜，0012）

诉求：按下去的第一帧还是慢，收手也慢。先算清延迟是从哪儿来的，再动代码。

宿主这条链一共两跳，都不怪死区：

1. `events()` 每宿主帧只做一次 `SDL_PollEvent` + `read_pads()`（host.cpp:1113-1119），手指坐标在这一步进 `g_fingers`；
2. `sample_host()` 在每根模拟 VBlank 里把 `host_pad()` 的结果交给 SMPC（smpc.cpp:178-186）。

60 Hz 出图时这两跳合计最坏 ≈ 33 ms、平均 ≈ 16 ms；`--input` 脚本只在有脚本时打 `pad: %04X`，
所以实时手指的延迟现在没有遥测。抬手的分支不是死区问题：手指一抬起 `g_fingers` 就少了它，`touch_read()`
下一帧直接返回 0，再慢也是这两跳 + 游戏自己的行走减速，不是 0.2r 的圈。

真正能量化的只有起始半径：`touch_pad.h` 原来 `if (d < 0.2f * l.dpad_r) continue;`，而 hub 是实心画的，
拇指要从 hub 上挪出 0.2r（平板上约 54 px）才有方向，视觉上就是"点了没反应"。

### 为什么最终不是非对称阈值

先写的是 `previous` 参与的迟滞：按下用 0.10r、已按住用 0.16r。推一遍状态机就知道符号反了：
按住后 `d < 0.16r` 就松、闲置时 `d ≥ 0.10r` 就起，于是 0.10r..0.16r 这一圈里
"没按→起→松→起"每帧翻转，拇指停在圈上会以 ~30 Hz 抖动出行进指令。
稳定要求是 松手半径 ≤ 按下半径；而"起得更快"要按下半径小、"停得更快"要松手半径大，两条在这套圆形判定里
不可能同时满足。所以 0012 只留一个对称的小死区：

```c
if (d < 0.1f * l.dpad_r) continue;        // 原来 0.2f
```

抬手路径本来就即时；径向回拉的停手比原来晚 0.10r（平板约 27 px 行程，十几毫秒），
换来起手快一倍。`host.cpp` 的调用点因此不用改，补丁只碰 `touch_pad.h` 一个文件。

### 构建与验收

- 补丁：`patches/0014-harmony-smaller-dpad-dead-zone.patch`（专家先占了 0012/0013，这两枚顺延到 0014/0015）；清单 1-5、7-15。
- 判据登记：`HARMONY_RUNTIME_HELPERS['touch_pad.h']` 和 `HARMONY_UI_RUNTIME_FILES['src/host/touch_pad.h']`
  **必须一起改**——后者在 `runtime_support_inputs()` 里会覆盖前者，只改一处等于没改（这次就踩过）。
  两处现在都是 `c8da777f3f1964b26e11327d229290b60a8cc0117ed83243dcd5160e94efdfc2`。
- Windows 选项构建过门，读档回归 VB3401 仍是 `7f410a40b8ee582a9a9db9514d801ee03ad09f9f4cbc1ab25a1e53565598ff10`
  （`build/run/gate-0012/`），标题 `9abeb31b`、读档菜单 `e3c59071` 也没动；发行包 `dist/pal-saturn-recomp-win-x64/`
  的 exe 已原地换成 `95667798cceb…`，`SHA256SUMS.txt` 同步，`saves/` 四份哈希未变。
- 鸿蒙 HAP 已出签名包（29,416,846 字节）。装的那一步要接平板：`hdc list targets` 现在是 `[Empty]`，
  插上后 `build/venv/Scripts/python.exe tools/ohosbuild.py --skip-learn --launch` 一条龙装+启动。

### 顺手补上的构建检查（tools/tests 从没绿到过绿）

`python -m pytest tools/tests` 在 Windows 上一度 21 项红，都不是游戏代码的问题，是检查本身缺 Windows 条件：

| 现象 | 根因 | 处理 |
| --- | --- | --- |
| 十多项 `UnicodeDecodeError: 'gbk'` | 测试 `read_text()` 不写编码，仓库源码是带中文的 UTF-8 | `tools/check_windows.sh` 里 `export PYTHONUTF8=1` |
| `Harmony runtime helper changed or missing` | 0011 之后 `runtime_support_inputs()` 只接受"完整一个变体"，合成 fixture 只放了真 host.cpp | fixture 现在按登记表把 Settings 与全部 helper/UI 文件一起拷进临时树 |
| `SDL host` 断言不报错 | 用例改的锚点 `g_menu_open, g_quitting` 被 0011 写宽了，替换成了空操作 | 改破两代都有的 `static void menu_close() {` |
| 探针跑出 0xC0000005 / 0xC0000409 | exe 加载了 Git for Windows 的 `libstdc++-6.dll`，不是编译它的那套装运行时 | 探针在 Windows 上加 `-static`，与 `check_windows.sh` 对运行时测试的做法一致 |
| `g++` 编译 `release_gate.cpp` 失败 | 用例用了 POSIX `setenv`，MinGW 没有 | Windows 上 `-include tools/wincompat.h`，并接住 MinGW 给 `-o` 补的 `.exe` |
| cmake fixture 配置失败 | `pal_game.cmake` 的 WIN32 分支要 `app_icon/pal_app.rc`，fixture 只拷了 cmake 文件 | fixture 连 `app_icon/` 一起拷 |
| `test_winbuild_options` 路径不符 | 断言用 `str(path)`（反斜杠），winbuild 发的是 `as_posix()` | 断言改用 `as_posix()` |

现在 `194 passed, 1 skipped, 73 subtests passed`。`third_party/saturn-recomp-pal/tests`（6 项）和
`validation/tests` 仍然红——那是上游 harness 的 Windows 适配，`check_windows.sh` 的注释明确说要让它可见而不是
假装通过，另在任务里跟。

## 14. 「点了没反应，半拍后才出来」：0013 按压保底（2026-10-11 深夜）

现象在 PC 和平板上都有，所以不是触摸死区，而是**按键根本没被游戏看到**。两条实测：

1. `tools/measure_message_ack.py`（SMPC 脚本通路，无窗口、逐帧确定）：标题→读档→白河村那五次按键，
   每次只按 **1 根 VBlank** 时整条路都走不下去（VB3401 仍是标题 `9abeb31b`）；按住 **2 根**起，
   VB2700/VB3401 就逐字节回到基准 `e3c59071`/`7f410a40`。游戏是按自己的节奏采样的，一次采样不够就丢。
2. 同一次运行里把光标那一下按下后的画面每 2 帧抓一张：第一次变化出现在 **VB2506**，即按下发布后约 6 帧，
   这是游戏自己的响应+动画，宿主再快也吃掉不了这条。

宿主的采样有多薄：`host.cpp` 里 `g_lifted` 的注释写明"比一帧还快的轻点只保留**一次**采样"；键盘和手柄
更是走 `SDL_GetKeyboardState`/`SDL_GetGamepadButton` 的**实时状态**，一次按下的 down/up 若落在两次轮询之间，
连一次都不到 —— 这就是"慢半拍"里真正丢东西的那部分。

### 改法

新增 `runtime/src/host/pal_tap_hold.h`，在 `read_pads()` 发布前把每个 bit 的按压补足到
**至少 3 根 VBlank**，按 `sat_vblanks()` 计而不是按宿主帧计（宿主一慢，几根 VBlank 共享一次轮询，
只按帧数补还是会丢）；`SDL_EVENT_KEY_DOWN` / `GAMEPAD_BUTTON_DOWN` 单独记一次边沿，
专门捞"落在两次轮询之间"的快按。三处防串味：菜单开时不记账、`menu_open()` 清掉欠账、
`g_held_over` 吞掉的按键不再被补发，失焦/退到后台一并清账。`PAL_TAP_HOLD=0` 回到只发实测状态的原始行为。

`0.2f→0.1f` 的死区（0012）只解决起步行程，这一条解决"按下有没有被看见"，两者互不影响。

### 验收

- `tools/tests/tap_hold_test.cpp` + `test_tap_hold.py`：不碰 ROM、不开窗口、不依赖帧率，直接对着这台机器的
  VBlank 断言补足长度、长按不加尾巴、`forget()` 与 `PAL_TAP_HOLD=0`。`pytest tools/tests` 现在 **196 passed**。
- 读档回归不受影响：`--input` 走的是 SMPC 通路，`host_drives()` 为假，补发逻辑根本不参与；
  VB3401 仍是 `7f410a40b8ee582a9a9db9514d801ee03ad09f9f4cbc1ab25a1e53565598ff10`（`build/run/gate-0013/`）。
- 发行包 `saturn.exe` 换成 `3138d43e7b87…`，`pal-options-build.json` 与 12 行 `SHA256SUMS.txt` 全部自校验通过，
  `saves/` 四份逐一比对未变；README 增加「按键手感」一节，`tools/make_dist.py` 的模板同步。
- 鸿蒙签名 HAP 已重出：29,427,332 字节。

### 一条要记着的坑：实时通路不能在这种机器上做 A/B

`--virtual-input`（SDL 虚拟手柄，走真实 `read_pads()`）看着是最合适的对照，但它只在
**宿主每帧恰好跑一根 VBlank** 时才有意义。我这台机器在后台还有构建/测试在跑的时候，三次 12 帧长按的
运行只录到 `3099:START,3106:,` 一次发布——多次 VBlank 挤进同一次轮询，长按也被吞了；而机器空闲时手跑一次，
五次按键全部按点发布，标题/菜单/村庄三个哈希与基准逐字节相同。所以 `tools/measure_live_tap.py` 的结论
只有在"机器空闲 + 窗口可见 + `--record-input` 录到的发布与脚本一致"时才可读；要判定按压长度，用上面的确定性探针。

## 15. 0013 补过头了：方向键按一次走太远（2026-10-11 20:4x）

装机复测的反馈：鸿蒙上"按下按键移动过多"，PC 上反而还好。两条都对得上：

- 平板轻点原本只有 1 个采样，被 0013 一口气补到 3 帧；角色每帧都在走，多两帧就是明显多走一截。
- PC 上普通敲键本来就有 3-6 帧长，补足条件（不足下限才补）对它几乎不触发，所以"还好"。

于是把补足分成两档，仍然只在"短于下限"时补，长按一律不加尾巴：

| 位 | 保底发布 | 理由 |
| --- | --- | --- |
| 方向 B_UP/B_DOWN/B_LEFT/B_RIGHT | **2 根 VBlank** | 实测下限就是 2；每帧都在移动角色，一帧都不能多补 |
| 其余（A/B/C/X/Y/Z/L/R/START） | 3 根 VBlank | 只用于确认一帧消息，多留一帧换可靠性，远不到菜单的连发阈值 |

`PalTapHold::publish(live, vblank, moving)` 因此多了 `moving` 参数：`pal_tap_hold.h` 不 include
`host.h`（`host.h` 会拉进 `video.h`，纯逻辑探针就没有独立编译的资格了），方向位由 `read_pads()`
在调用处传进来，头文件只留两个常数。

改名也要如实：补丁现在叫 `patches/0015-windows-harmony-presses-held-for-the-game.patch`，
不再叫"三帧"。

### 复验

- `tools/tests/tap_hold_test.cpp` 增断言：`Right` 在第 2 帧后必须消失、按钮仍在第 3 帧消失、长按无尾巴；
  `pytest tools/tests` **196 passed**。
- 读档回归仍 `7f410a40b8ee…`（`build/run/gate-0013b/`），VB2700 仍 `e3c59071…`。
- Windows 包 `saturn.exe` = `f2cb607b5e11…`，`SHA256SUMS.txt` 12 行自校验通过，`saves/` 未动；
  README 与 `tools/make_dist.py` 模板改成"方向键两帧 / 确认键三帧"。
- 鸿蒙：`entry-default-signed.hap` 29,427,293 字节，`hdc install -r` 成功，20:43:39 起在前台跑新包
  （`PROG activated by a call to 06020040`）。注意 `ohosbuild.py --launch` 有一条"本轮没有新产物就拒绝拾取旧
  HAP"的守卫：上一轮产物即使已是最新也会被拦，改动被编译进去之后它才会装。

## 16. 交接给专家：0013 仍判"不太合理"，请把杠杆换到采样点上（2026-10-11 21:0x）

装机复测的结论是"还是不太合理"。我不再往下调帧数了——继续猜参数对这个手感问题没有意义，
先把已经测死的事实和没做的两条结构性路子写清楚，接手的人可以直接从这里走。

### 已测死的三条

1. **游戏的下限是 2 根 VBlank。** `tools/measure_message_ack.py` 走 title→村庄全路：按下只可见 1 根 VBlank
   时整条路失败（按键被完全丢弃），≥2 根则与基线逐字节一致（`9abeb31b` 标题 / `e3c59071` VB2700）。
   所以"保底 2 帧"不是保守，是地板，再低就丢键。
2. **游戏自己的反应约 6 帧。** VB2500 的按下，画面变化落在 VB2506。这一段是 guest 的循环，
   补足只决定"按下能不能送到游戏面前"，**不能**缩短这 6 帧。如果玩家说的"慢半拍"指的是这一段，
   0013 这个方向再怎么调都不会有改善。
3. **宿主每根帧只轮询一次控制器，掉帧时多根 VBlank 共享一次轮询。** `--record-input` 里能看到
   `3099:START,3106:`——7 根 VBlank 落到同一次采样。平板比 PC 更容易掉帧，所以同一份补丁在两边手感不同。

### 没做的两条结构性路子（我认为真正能改命的）

- **按"读"采样，取代按"帧"轮询。** 现在 `read_pads()` 每根帧取一次宿主状态；更准的做法是在 SMPC/游戏
   真正读键的那一刻去取宿主状态，谁读给谁现采。仓库里已经有 `sh2_hook` 这套机制（影片用的
   `0x06021c1e` 就是先例），缺的是找到 pad 读取点并挂上去。这条路能把"多根 VBlank 共享一次采样"彻底消掉，
   0013 的帧数补足也就退化成保险而不是主机制。
- **让触摸轻点在抬起边沿收敛，而不是发布固定帧数。** 现在是"不足下限就补到下限"（方向 2 / 按钮 3），
   手指停留时长和角色位移耦合：补多了"移动过多"，补少了丢键，两头都调不到玩家满意。更贴玩家预期的是
   以抬起事件为一次输入的终点，并按"角色实际走了几步"封顶，而不是按帧计数。

### 验证入口（都还在绿）

- `PYTHONUTF8=1 build/venv/Scripts/python.exe -m pytest tools/tests -q` → **196 passed, 1 skipped**。
- 纯逻辑断言 `tools/tests/tap_hold_test.cpp`（方向第 2 帧后消失、按钮第 3 帧消失、长按无尾巴）。
- 读档回归门 `7f410a40b8ee…`；`tools/measure_message_ack.py` 可直接复现"1 帧丢键 / 2 帧通过"。
- 构建：Windows `tools/winbuild.py --options`，鸿蒙 `tools/ohosbuild.py`。
- 开关：`PAL_TAP_HOLD=0` 回到原始采样；0012 的死区在 `touch_pad.h`（0.2→0.1）。

补丁本身在 `patches/0014-harmony-smaller-dpad-dead-zone.patch`、`patches/0015-windows-harmony-presses-held-for-the-game.patch`；
`third_party/` 不入库，按 README 拉固定上游提交后 `git am patches/*` 重放。

## 17. 拉到 0016 之后的本地复验：selftest 断链与平板存档落位（2026-10-11 深夜）

Windows 侧先把结论说清楚：**0016 让 `selftest` 目标在两个平台上都链不起来**。注入后的
`p_prog_001.cpp`（`pal_field_input::apply` 与 `f_06026D84`）引用 `sat_vblanks()`，而
`build/recomp/CMakeLists.txt:52` 的 `selftest` 只链 `saturn_core saturn_stub recomp`——
`sat_vblanks()` 唯一的定义在 `src/video/video.cpp`，不在这里面。OHOS 是在 hvigor 里撞上的，
本机 `cmake --build build/recomp-build --target selftest` 同样报
`undefined reference to 'sat_vblanks()'`，所以不是交叉工具链的毛病。

补了 `patches/0017-stub-supplies-the-vblank-clock.patch`：在 `services_stub.cpp` 里按 stub 的既有口径
给一个常量 0（这里没有硬件、帧也不会走），0016/0017 必须成对使用。`runtime_support_inputs()` 里
`src/stub/services_stub.cpp` 的钉法原来只收一个 digest，改成可接受集合并把 observed 值打印出来，
这样"配套补丁"是改钉而不是重来一遍注入。修完 `selftest.exe` 链接通过（7,510,025 字节）。

再生时被两类"上一轮残留"挡住，都按文档说的改名备份解决，别急着删：
`build/recomp/pal_field_input.h`（上一轮半途生成物）与 `third_party/saturn-recomp-pal`
（Windows 上 ninja/Defender 还握着句柄，`rd /s /q` 比 `rm -rf` 可靠）。

### 平板默认存档怎么落位

`hdc shell` 这台机器上进不去用户存储：`/storage/Users/currentUser/Download` 直接 No such file，
`/mnt/user`、`/storage/media` 是 Permission denied；但挂载表里能看到
`/storage/media/100/local/files/Docs` 挂在 sharefs 上，**应用的 Download 根实际落在**
`/storage/media/100/local/files/Docs/Download/com.palhero.palsaturn/`（`disc/`、`saves/` 都在下面）。

传文件只有 `hdc file send` 这条能用，而且有两个坑：

1. 远端参数给**目录**，不是给文件路径——给文件路径会报 `Not a directory`；
2. 它会按本地路径的结构建子目录，所以 `hdc file send build/pal-saturn.bup <saves>` 结果是
   `<saves>/build/pal-saturn.bup`。要么在文件的同级目录里用**裸文件名**发（`cd` 过去再
   `hdc file send pal-saturn.bup <saves>`），要么发完再自己收尾。
3. 覆盖能成，`mv`/`cp`/`rm` 同一个目录里的既有文件会被拒（属主是 `20001006:file_manager`），
   所以换档顺序只能是：先 `file recv` 把旧档拉回 PC 备份，再直接 send 同名文件覆盖。

本轮按这个做法把默认存档换成 `hidden-dragon-before-fox-woman.bup`（`be8f0a28ded2276b…`）：
平板 `saves/pal-saturn.bup` 与 `dist/pal-saturn-recomp-win-x64/saves/pal-saturn.bup` 同一份；
换下来的两份分别备份成 `saves/pal-saturn.before-fox-woman-20261011.bak.bup`（Windows，`a4d8f748…`）
和 `saves/tablet-before-fox-woman-20261011.bup`（平板原档，`bb27077e…`）。

## 18. 平板终于和 PC 一样快：HAP 改走增强生成（2026-10-11 23:3x）

现象是"平板动画很卡、PC 没问题"。原因不在参数：施法准备、法术动画 1.5x、读盘提速这些**调用点**是
`tools/pal_options.py` 注入到生成代码里的，而 `tools/ohosbuild.py:277` 只跑 `winbuild.py learn`
（不带 `--pal-options`），`pal_keyboard_profile.py` 里 `cadence`/`effect_wait` 出现 0 次。
`src/pal_game/pal_effect_cadence_runtime.h` 的默认 1.5x 两边都编译，但没有调用点就无从生效，
设备上又设不了环境变量，所以没有绕法。

现在 HAP 默认就打在**和 Windows 发行包同一份增强生成**上：

- `tools/ohosbuild.py` 多一个 `--speed {accelerated,mapping}`，默认 `accelerated`；learn 变成
  `winbuild.py learn --pal-options`，生成物取 `build/windows-pal-options/{recomp,runtime}`。
  想要原始节奏就 `--speed mapping`，Windows 那条链完全没动。
- 入口 CMake 靠 `build/pal-ohos-generation.cmake` 这个指针对齐：ohosbuild 校验完哪一对目录就写哪一对，
  `SATURN_RUNTIME` 与 `add_subdirectory` 都按它取；没有指针文件时行为与过去逐字相同（`build/recomp` +
  `build/pal-keyboard-runtime`），所以原有身份测试照旧通过。
- 三道门各自补齐：UI 世代白名单加了增强代 host.cpp 的 `bd2449a5…`（映射代 `c69b7a17…` 仍在）；
  manifest 从 `pal-keyboard-manifest.json` 换成 `pal-options-manifest.json`（给 `prepare_options`
  加了 `verify_only`，只校验不注入）；换生成时旧 native cache 里记着的 `SATURN_RUNTIME` 会让入口门直接失败，
  所以 `drop_stale_native_caches()` 只删与实际生成不一致的那些缓存。

途中挖出两个只在整树构建下才暴露的坑：

1. **`selftest` 拖垮打包**。它只链 `core+stub`，而增强生成的 guest 代码引用真硬件符号
   （`g_vdp2_regs`、`pal_pfq_*`、`pal_input_peek`）。桌面链只编 `saturn` 目标所以从没撞上，hvigor 编整树
   就炸。它不参与 `libmain.so`，入口里 `EXCLUDE_FROM_ALL` 掉；要跑得照旧 `--target selftest` 显式编。
2. **配对帧队列的实现没进 libmain**。生成的 CMakeLists 把 `pal_paired_frame_queue.cpp` 只挂在桌面
   `saturn` 上（`build/windows-pal-options/recomp/CMakeLists.txt:67`），`main` 是另一个目标，
   `--no-undefined` 下 `scu.cpp` 找不到 `pal_pfq_enabled`。入口按同一份文件补挂到 `main`。

复验：`libmain.so` 里 `pal_effect_cadence`/`pal_effect_wait`/`pal_pfq_enabled`/`pal_input_peek` 符号都在；
HAP 29,607,822 字节装到 MLR-AL10，23:33:15 起新进程 `PROG activated`（旧包是同一份 argv，只能靠符号与
生成本认）；真人实机反馈动画速度已正常。`pytest tools/tests` **259 passed**（新增默认生成、`--speed mapping`
不留指针、只废弃不一致缓存三条）。
