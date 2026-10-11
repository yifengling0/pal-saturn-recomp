# HarmonyOS 宿主修正候选：本地复测说明

这批代码基于 `2c615c1`。已完成 Linux 下的独立 C++/Python 测试，**尚无本轮 Harmony 真机、HAP 编译或可听音频验收**。音频部分是确定的代码边界修正和诊断增强，不能据此说卡顿已经消失。

## 改动

- `0009` 修正触控尺寸单位：原 `0008` 将密度项 `480` 缩成 `4.8`，再除以百分比，导致按钮明显缩小。
- 宿主暂停菜单增加透明度、Picture（TV / Fit / Fill）、明确关闭按钮。短屏不再整体缩小，改为分页，Back/Next、行及分段控制的命中区在支持的尺寸矩阵内至少 48 个逻辑单位；上下导航可跨页，Next 可循环。翻页、退出、失焦、转屏清理触点，保留多指方向操作。
- `touch.opacity` 范围 20–100，缺省 55；`touch.size` 仍 50–200、缺省 100。配置通过原 settings.ini 保存。控制器绑定不重置。
- `display.presentation` 可选 `original`、`fit`、`stretch`。桌面缺省 original；Harmony 构建通过明确的 CMake 定义让缺字段缺省 fit。用户明确写出的 original 仍有效。Fit 放大有效画面且保持原可见图像比例，Fill 才会拉伸。旋转或在暂停中调整窗口也重算目标矩形。
- 音频 quantum 按设备采样率换算到 44100 Hz 输入帧，再维持原 50–100 ms lead 上限；并未扩大成更大的缓冲。队列查询错误不再被 `-1 / 4 == 0` 误记为 empty。补静音与真实 PCM 共用 250 ms 容量上限；只有成功提交才记 accepted，真实 PCM 数据不改写。
- 音频日志新增独立单调墙钟、最后一次真实音频提交时刻、accepted / dropped / failed / 初始及恢复静音帧数、查询和提交错误、最大提交间隔。`times empty` 是 SDL 输入队列观察值，**不是设备实际欠载数**。时间标注包含暂停；总墙钟还包含退出时输出报告的耗时。
- `ohosbuild.py` 支持 `--build-mode release|debug`，默认 release；`--logs` 可在退出后单独采集现有日志。构建仅选择本轮新建/变化的 HAP，安装要求明确的新 signed HAP；多台设备时必须给 `--device`。不会全局清空 hilog。
- 打包前总是只读校验最新 runtime manifest，包括 `--skip-learn`。旧版本、被改动或缺少新 helper 的 runtime 会拒绝打包，避免更新源码却重新发布旧实现。

## 更新和重新生成（Windows）

先正常备份自己的存档和 settings.ini。不要覆盖本地自定义源码。以下命令在仓库根目录 PowerShell 中执行；沿用已经能够构建本项目的 DevEco、SDL、Python 和自备镜像环境。

```powershell
$PY = ".\build\venv\Scripts\python.exe"
# 首次从0008升级时，旧patched checkout的身份不会被静默覆盖。
# 先检查其中有没有自己的修改；保留整目录而非删除。
Rename-Item .\third_party\saturn-recomp-pal saturn-recomp-pal.before-0009
& $PY tools/prepare_linux_runtime.py
& $PY -m pip install -e third_party/saturn-recomp-pal
& $PY tools/winbuild.py build --recompile
& $PY tools/ohosbuild.py --skip-learn --build-mode release --device YOUR_DEVICE_ID --launch
```

若没有旧 `saturn-recomp-pal` 就不执行 Rename-Item；若备份名称已经存在，换一个唯一名称，不能覆盖旧备份。不要重命名或修改用于解析的干净 `third_party/saturn-recomp`。新代码还保留上游 pin 和完整补丁身份校验。

`--skip-learn` 只跳过学习，不代表允许旧代码。若提示 source/version、helper、manifest 改变，请先重新生成，而不是删掉守卫或手改哈希。`build --recompile` 明确执行重新生成；`learn --recompile` 不是这一步的替代命令。

HAP 默认仍不包含原镜像、素材或 BIOS。资源与存档路径沿用 `P4_HARMONYOS.md`，本次不迁移或删除它们。不改签名设置，不需要把密钥交给其他人。

如果 hvigor 输出完全没有变化，候选脚本会拒绝把旧包当本轮产物。先核查构建输出和构建模式，必要时在 DevEco 中做干净重建，不要随意安装目录里的另一份旧 signed 包。只有文件名符合 signed 并不构成独立签名审计，安装器仍须验证签名。

## 音频最小复测

1. 记录手机/平板型号、系统、SDL Git revision，以及实际 C++ 编译参数。`buildMode=release` 本身不能证明生成代码最后用了 `-O2` 或 `-O3`。
2. 启动后保持前台、不打开中途设置、不切应用，运行约 90 秒；听是否仍周期性断续。最后通过菜单 Quit 正常退出。
3. 退出后采集：

```powershell
& $PY tools/ohosbuild.py --logs --device YOUR_DEVICE_ID > audio-after-quit.txt
```

`--logs` 不构建、不安装、不启动、不清日志。日志可能包含多次运行，按本次启动和退出段匹配；若系统环形日志已覆盖旧记录，需重新短跑采集。原来的 `--launch` 只在启动约六秒后取一次快照，不能自动包含之后 Quit 的统计。

请提供本次 `audio: device`、`audio: driver`、`audio stream`、`audio diagnostics` 行及前后 FATAL/错误。不要只用现有 `vblanks / seconds` 判断真实帧率：默认非 `--realtime` 的机器统计使用虚拟时间。本批不打开 `--realtime`，不改 CPU、CDDA 或全局速度。

4096 帧 / 44100 Hz 约 93 ms；现有 100 ms lead 只比它多约 7 ms，不能仅凭这个数断言不再饿。输入队列 empty、SDL 下游已有数据、真正硬件欠载应区分。后续是否改 FAST/NORMAL 或具体回调量，须依据当前设备实际后端和日志做 A/B；本批不盲改 SDL 的模式。

## 触控/显示复测

- 同场景测试短按、长按、快速转向、多指确认，松开所有手指后不应残留方向。
- 进 ☰ 暂停菜单，依次测试明确关闭、系统返回、翻页、透明度和大小拖动、旋转后返回游戏；再重启核配置保留。
- Picture 的 Fit 应保持比例并尽量占满可用输出；Fill 会变形，按个人喜好选择；TV 保留旧电视边框。
- 本批处理的是运行中 ☰ 的 SDL 暂停菜单。`advanced.txt` 打开的 ImGui launcher 设置是另一条路径，尚未取得故障截图，不能称其返回问题已修。
- 本地矩阵使用零 safe-area inset，实际刘海、系统导航条、窗口布局、SDL OHOS 的真实密度和 Back 事件仍需设备确认。逻辑净宽小于 320 或净高小于 120 时不承诺 48 单位布局。自定义按钮位置和一键重置界面尚未实现。

## 已完成的本地证据

- 触控公式/纯布局 1328 项，0008 基线 15 项失败、候选 0 项失败。
- 实际 host.cpp 的分页/触控/viewport 路径以 OS/渲染桩测试：3037 断言通过。
- Desktop / Harmony 缺省配置各 84 项持久化和迁移测试通过。
- 实际 host 音频路径以 SDL 桩和 UBSan 验证：22 场景、79 断言通过，含 PCM 原字节保持、容量、错误计数、重开和退出时刻。
- 打包身份守卫的独立合成测试：8 项通过；有效包只读验证，旧版本、缺失/篡改 helper、输出变化和越界软链接均拒绝。
- 构建脚本 39 项 mock 测试通过，覆盖新包选择、设备歧义、日志及旧 runtime 拒绝；不等于真实 hvigor、hdc 或 HAP 测试。
- 这批没有通关进度变化，没有新增游戏资源，也没有替换已有 Release 附件。
