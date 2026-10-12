# S/W/Q：真实 SDL 键盘回归与 OHOS Linux 构建

2026-10-12。基于用户提交 `5c6d50c42e77d7fd41637548e8987dc7f26eec8f`，保留其快捷键语义。

## 已找到并修复

原 `MenuWalk` 每次 `read_pads()` 都消耗一个 hold/gap 单位。启用 field-input 后，同一 VBlank 可能由呈现与游戏读键各调用一次；这些调用次数不是帧数。

真实 SDL 按 S 的无行为改变探针显示：边界一直为 4，菜单 epoch 一直为 2；X 在 VB3411 的第二次读取才开始，VB3415 结束，游戏下一次实际采样在 VB3417。因此游戏只收到 B，完全漏掉 X。这不是窗口焦点或键盘权限失败。运行中的 S 按住 200ms 也复现，普通 Esc 按住 400ms 则正常开菜单。

修复：
- 按真实 `sat_vblanks()` 推进；同一 VB 额外读取保持同一输出，不重复提交 intent。
- B/X/A 各保持七个 VBlank，间隔七个 VBlank，覆盖已测六 VB 采样周期及释放边沿。
- 仍须等待游戏自己的菜单 epoch 才确认；240 个实际 VB 超时。失焦、场景/宿主菜单取消逻辑保留。
- 通用列表仅在实际 cursor 指针等于 `0x060768DA` 时消费/应答 field intent；目标在该列表绘制之前写入，其他列表不会误应答。
- 不改变行走速率、CPU/音频时钟或 NPC/RNG 的推进。

## 实际验证

Linux 原生 SDL3 3.4.18 窗口，真正桌面键盘事件，`PAL_FIELD_INPUT=1`，新 PC98 设置。正常 BUP 副本通过启动输入载入，`--resume 3401` 后交还宿主键盘；没有测试用的任意 guest 内存写入。

- 原版 S/W/Q 全部复现 B 后不打开目标页。
- 修复版 S 打开李逍遥状态页；W 打开物品下的「装备／使用」页；Q 打开「储存进度／读取进度」。cursor 分别 0/2/3。
- 状态页内 W 不动作；四项菜单内 S 不动作。
- Q 留下 cursor=3，正常返回地图后按 S，正确打开状态页且 cursor=0。
- 实际 Esc 返回可用；测试以退出码 0 结束，源存档及测试存档 SHA 均保持不变。
- 载入 VB3401 的 PNG 与旧稳定版逐字节相同：`c4730adefed25a186436172dbc2ffd3a6afcd4bad3089dbcba54614766c51201`。
- 本轮没有重新打战斗或进入有效对白来验证快捷键隔离；对应上下文有自动测试，不冒充真实战斗/对白测试。

最终工具回归：`tools/tests` pytest 322 tests 与 160 subtests 通过；OHOS 构建工具 77 tests 通过。

自动回归：MenuWalk 上下文 10,903 检查；独立 2,592 种三目标/六采样相位/额外读取/延迟应答组合，2,020,032 检查通过。旧 helper 在同一矩阵失败。Python helper 测试会自动编译并运行此矩阵。

最终 Linux exe：`708cc7eda75316315b021bee33a6bf29cda9745b8bce084491893dc8a3c713de`。
Instrumentation 清单：`85393da9350e6149e2651270c1b958fe06aae7bc478dedb4d77715c03f367e0c`。
版本后缀为 `keyboard-v1-10-menu-vblank`；mapping-only 为 `mapping-10-menu-vblank`。

## 本地更新与重建

保留自己的未提交改动和存档；先正常更新本分支。第一次必须再生成，不能直接沿用旧 exe 或旧生成目录。

Windows 示例（SDL 路径替换成自己的）：

```bat
build\venv\Scripts\python.exe tools\winbuild.py build --pal-options --recompile --sdl-dir C:\path\to\SDL3\lib\cmake\SDL3
```

Linux 同源示例：

```sh
build/venv/bin/python tools/winbuild.py build --pal-options --recompile --sdl-dir /path/to/SDL3/lib/cmake/SDL3 --jobs 2
```

使用本轮新生成后，OHOS 可运行：

```sh
build/venv/bin/python tools/ohosbuild.py --deveco /path/to/official-command-line-tools --skip-learn --speed accelerated --build-mode debug
```

Windows 把 Python 换成项目 `Scripts/python.exe`，DevEco 路径换成自己的即可。`--skip-learn` 只表示沿用已经重新生成并通过身份校验的输入，不会允许旧 host 混入。

普通 PC98 设置保留，已有自定义配置不会被覆盖；S/W/Q 只在地图操作上下文生效。W 复用土星物品装备入口，Q 是存读档，不是 PC 退出屏幕。战斗 A 当前仍是土星「最强」填充而非 PC 全员普通攻击，原有边界见 `PAL98_HOTKEY_PARITY.md`。

## OHOS 构建与限制

增加官方 Linux Command Line Tools 的 hvigor/node/ohpm 布局、宿主 Python/learner/hdc 名称支持。两个 host pin 由当前已审核 planner 从固定 runtime 重放推导，不是盲目接受 observed hash。旧 host 仍拒绝。

官方工具链 26.0.0.851 实际完成 ARM64+x86_64 debug HAP，32,516,852 bytes，SHA256：
`dbf0402cfac0f3d3f7ed9218649626b884fd419701be10a5273f1a811acb166e`。
离线 LLDB 在 libmain 中确认新的 `MenuWalk::tick(epoch,vblank)` 与实际生成源码。此 HAP 未签名、未安装到设备；网络不可达仍阻止实体调试。不能据此声称手机音频、手柄、触摸已重新实测。Linux 窗口本次无可打开的 ALSA 音频设备，也未验证听感。

额外探测：`--pal-options` 的独立 `selftest` 目标仍有链接缺口（PFQ/VDP2/增强运行时符号未进入 stub 链）。主 `saturn` 与 OHOS `libmain` 可正常链接；该 selftest 未运行，另列待修，不能宣称全部底层自测全绿。

打包 fail-closed 与已有用户目录保全见 `PACKAGING_SAFETY.md`。
