# Harmony 音频、实体手柄与 PC 战斗快捷键：本轮复测

本轮接在 AVI 构建修复 `bee32d8` 后。候选已在 Linux 实际 SDL 和受控接口测试；没有本轮 Harmony SDK/HAP 编译、蓝牙/USB 实体手柄或可听真机验收。请保留自己的 `docs/P4_HARMONYOS.md` 本地改动；本文件不替换它。

## 更新后必须重新生成

补丁流水线新增 `0010-harmony-audio-and-physical-gamepad.patch`，顺序为 1–5、7–10；0006 仍属于可选增强路径。请先备份自己的源码、BUP 与设置。保留旧 patched checkout，勿强制覆盖：

```powershell
$PY = ".\build\venv\Scripts\python.exe"
# 名称必须未存在；先确认旧目录没有需要合并的自定义代码。
Rename-Item .\third_party\saturn-recomp-pal saturn-recomp-pal.before-0010
& $PY tools/prepare_linux_runtime.py
& $PY -m pip install -e third_party/saturn-recomp-pal
& $PY tools/winbuild.py build --recompile
& $PY tools/ohosbuild.py --skip-learn --build-mode release --device YOUR_DEVICE_ID --launch
```

无旧 patched 目录则跳过重命名；不要改解析镜像用的干净上游目录。使用增强构建的用户仍沿用此前 `--pal-options` 配置，但必须新生成，旧 manifest/helper 被拒绝是保护，不能手改哈希绕过。`--skip-learn` 只可在本轮重新生成成功以后用；不能把旧生成代码打进新 HAP。AVI 的 `movie-cache-v1` 启动及实际刷新日志仍保留。

## 音频：停止把源队列见底直接当作需要再塞 100ms 静音

仅对实际 OHAudio 驱动改变恢复策略。SDL 输入源队列为零时，下游可能刚好接走完整一个回调的数据；这不证明设备已欠载。旧路径此时再插入一整份 lead 的零样本。受控真实 SDL 反例中，4096 帧原始 PCM 已完整被消费、回调缺额为零，旧路径却仍插入 4410 帧静音。

本轮保留初始 50–100ms 预灌与 250ms 总容量上限，正常送入原始 PCM，不再仅因源队列零就反复补整份静音。菜单暂停/恢复与前后台生命周期重置观测窗口；不清空已有队列，也不每次重灌静音。不改 CPU、VBlank、CDDA 或游戏速度。其他音频驱动保留已有策略。

新增 SDL stream 需求观察、回调线程及生命周期诊断。`source queue empty`、回调 `additional_amount` 估计缺额和真实硬件 underrun 是不同指标；日志不能证明声音已经完全不卡。可选 `PAL_AUDIO_ADAPTIVE_LEAD` 默认关闭，本轮先不启用。曾试过直接抬到 200ms，在原 250ms 容量下会丢真实 PCM，已拒绝该做法。

复测建议：同一存档启动稳态 60–90 秒，分别反复开关游戏内菜单、宿主 ☰ 设置各五次，再做一次切后台/恢复。记录听感和实际墙钟，退出后采集：

```powershell
& $PY tools/ohosbuild.py --logs --device YOUR_DEVICE_ID > audio-after-quit.txt
```

保留 `audio: device`、driver、SDL version/revision、`audio input requests`、`audio diagnostics`、`audio stream` 及错误行。`--logs` 不清系统日志，多次会话需按启动/退出段区分。Linux 实际 SDL dummy 三组生命周期实验保留全部 132300 帧原始 PCM、零丢弃/失败/恢复静音；其中两组仍观察到小额需求缺口，不能宣称设备零欠载。

## 实体手柄：API 21 原生桥接到 SDL

先前记录的 OHOS SDL 配置只有 dummy/virtual joystick，普通 `SDL_INIT_GAMEPAD` 并不能创造实体设备。新桥接使用官方 Game Controller Kit C API 21 的设备枚举/监视、按钮和轴回调，复制事件到有界队列，在实际 SDL 主线程创建/更新虚拟 gamepad，再走已有 Saturn 按键链路。不会在 SDK 回调线程调用 SDL。

官方来源：

- [设备监听与枚举](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/game-controller/game-controller-monitor-device.md)
- [固定版本 C API 声明](https://github.com/openharmony/game_game_controller_framework/tree/5221a8e8117cebe9b82bc06f5a251be1884abb73/interfaces/kits/c)
- [ButtonHome 对应 SELECT 的定义](https://github.com/openharmony/game_game_controller_framework/blob/5221a8e8117cebe9b82bc06f5a251be1884abb73/frameworks/native/common/include/gamecontroller_client_model.h#L108-L115)

运行时 `dlopen("libohgame_controller.z.so")`，逐项验证 `OH_GameDevice_GetAllDeviceInfos`、`OH_GameDevice_RegisterDeviceMonitor`、对应释放/查询函数，以及 `OH_GamePad_<按钮名>_RegisterButtonInputMonitor` / Unregister、`OH_GamePad_<轴名>_RegisterAxisInputMonitor` / Unregister 与事件字段查询函数。完整符号列表在 `pal_ohos_gamepad.cpp` 的三个 API 宏中；任何缺项均记录具体符号并停止桥接，不带着空函数指针继续。二进制测试确认没有强制未定义 OH_Game* 导入或该库的 NEEDED 依赖。

应用原 API16 最低版本不提高，但实体桥接需要设备具备 API21 服务。旧系统/缺库/缺符号只回退触控和键盘，**不表示旧系统实体手柄已兼容**。编译需要官方 GameControllerKit 头文件和 SDL virtual joystick；缺少时明确失败。只有确实希望构建触控/键盘版本才显式关闭 `PAL_OHOS_GAMEPAD_BRIDGE`，不要为了让编译过而误以为手柄还在。

默认按实体位置命名，不以厂商字母推断：南键→Saturn A，东键→B，西键→X，北键→Y，右肩→C，左肩→Z，左/右扳机→L/R，Menu/Start→START；十字/左摇杆移动，Home/Select/Back 打开宿主菜单。GameControllerKit 的 ButtonC 也映射右肩/C。已有 `[gamepad]` 或 GUID 自定义绑定优先，未重置。Back 与系统 GUIDE 不混为同一物理键。

应逐层看到 `API 21 callbacks registered`、`enumerated=N`、`attached SDL id=...`、`first input reached SDL id=...`。仅注册成功不能证明设备事件已到。请测启动前已连接、热插拔、USB/蓝牙模式、所有按钮/轴、一直按住方向时切后台/恢复、按住时断开再重连、☰ 菜单返回及触摸同时按住/松开。平台若未把设备分类进 Game Controller Kit，仍可能需要进一步适配。

本地实际 host + 真实 SDL virtual + 模拟官方服务 146 项通过，含两设备、线程边界、乱序连接、队列溢出、安全清零、焦点释放、退出晚回调；ASan/UBSan 通过，环境限制未做 LeakSanitizer。8 个 CMake/link 夹具通过，两种主入口均含桥接。它们不是完整 SDK 或实体蓝牙/USB 测试。未来若 SDL 本身有原生实体后端，则优先原生避免重复；混合原生/仅桥接设备群当前不承诺。

## PC98 F / R：调用原版战斗命令

仅 PC98 键盘模式、角色四图标战斗主菜单生效：F 调用原 Saturn L 的“最强武功”选择，R 调用原 Saturn Z 的重复上次指令。从当前角色到队尾沿用原作处理；此前手动下达的角色指令保留。

“最强”沿用原作按已学会、攻击类别、MP 费用及随机评分的算法，不保证数学上最高伤害。重复也沿用原作对 MP、沉默、物品是否仍可用的校验及回退。普通地图、对白、法术列表/选目标和演出期间不积压 F/R；离开主命令菜单清理，长按不穿越到下一回合。原物理手柄和 Saturn 键盘模式不变。

`[keyboard pc98]` 的 `item=E`、`spell=F`、`strongest=F, A`、`repeat=R` 可自定义；已有普通按键、确认/取消和宿主快捷键优先，显式空值可关闭。同一个字母可以同时管场景页和战斗主菜单：两个闩各自只在自家上下文里放出那一下，对方上下文里按成 0，所以场景按住 F 不会在下一回合变成"最强"。土星 X 移到 V，被这几个字母接管的 Y/Z/L/R 默认留空。不会覆盖用户已有绑定。原版很短按键可能仍受游戏采样节奏限制，本项不声称解决所有输入延迟。

## 当前本地验证范围

- 干净固定上游顺序应用补丁，重复 setup 不改文件；缺失/变动运行时被身份守卫拒绝。
- 上游 Python 206 项、runtime 45 项通过。
- 本轮实际音频 host 27 场景/166 断言与 31 策略断言通过。
- 键盘规划/设置/上下文 78 测试和 31 子项通过，实际 SDL 键盘 F 实录为 VB4308 的 L、R 实录为 VB5684 的 Z：F 填入三人原作法术，完整回合三人 MP 160/244/124→142/236/106、Boss HP5000→4595；R 恢复同三招及目标，未改历史。同 VB 原生 L/Z 重放 43 条命令、29 组只读状态与六张图一致。此例 R 填指令后结束，未据此宣称该次 Boss 胜利。
- 增强构建 data-CD→precise/paired→PC98 完整规划、重复零写入及篡改拒绝 17 项通过；只追加精确版本哈希，没有放宽未知源码保护。
- 新组合原生 Linux SDL 程序完整无输入片头到 VB6700，五张关键图与稳定基线相同。

这些结果不等于 Windows 新补丁已实编或 Harmony 真机验收。触控自由位置、中文菜单和退出确认属于下一批，不在这批音频/手柄/F R 提交内。
