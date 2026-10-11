# 开场影片问题包（给专家）：片头 AVI 只播了约四分之一就进入"片尾等按键"

日期 2026-10-11。平台 Windows（`build/recomp-build/saturn.exe`，SDL3 + direct3d11）。
镜像 `disc/pal_t37401h_13tr.cue`（T-37401H V1.000, areas JT）。上游 pin `086c372` + `patches/0001-0005`。

## 0. 先说结论：用户看到的"启动视频卡住"不是死机，但也不是完全正常

- **不是死机**：片尾静帧上按一次 START，约 250 VBlank 黑场后**自动**淡入标题画面，无需第二次按键；再按 START 进「新的故事」，地图、走路、镜头滚动、演出全部正常（见 §4）。
- **不正常之处**：片头 AVI 只播了它自己文件的大约四分之一就停了，然后进入"片尾等按键"。真机上这段应该播完。这是要交给专家的唯一真问题。
- **Windows 没有独立缺陷**：同一停滞点、同一帧哈希在 windowed / `SDL_AUDIODRIVER=dummy` / `--headless` 三种宿主下完全一致；读档回归的 PNG 与 Linux 基准哈希逐字节相同（§4）。

## 1. 现象时间线（无输入，`--headless`，PNG 哈希前 8 位）

| VBlank | 哈希 | 画面 |
| --- | --- | --- |
| 600–650 | `145b2133` | 引导帧 |
| 675 | `4a46dde0` | 黑 |
| 700–1150 | `03b43474` | **TrueMotion / The Duck Corporation 授权静帧**，持续 450 VBlank ≈ 7.5 s |
| 1175–1275 | `4a46dde0` | 黑 |
| 1300–1450 | 每 25 VBlank 一帧新画面 | 片头动画在动（密集采样 VB1290–1500 共 53 张、30 张互不相同 ≈ 8.5 fps） |
| 1475 → 4000+ | `d5054485` | **地球+陨星静帧，永久保持**（用户看到的"卡住"） |

产物：`build/run/moviefix/`、`build/run/moviedense/`、`build/run/avi2-head/`。

## 2. 关键数字：盘上 AVI 应有的时长 vs 实测

盘上六个 AVI 全部是 DUCK(Cinepak)，头部解析（`build/avihdr.js`，只读镜像）：

| 文件 | 帧数 | µs/帧 | 应有时长 | 大小 | 字节/帧 |
| --- | --- | --- | --- | --- | --- |
| A1.AVI | 265 | 66738 | **17.7 s** | 2,658,574 | 10,032 |
| A2.AVI | 930 | 66738 | 62.1 s | 13,442,844 | 14,455 |
| A3.AVI | 517 | 66667 | 34.5 s | 5,175,212 | 10,010 |
| A4.AVI | 201 | 66667 | 13.4 s | 2,016,828 | 10,034 |
| A5.AVI | 2294 | 66667 | 152.9 s | 30,645,980 | 13,359 |
| A6.AVI | 2197 | 66667 | 146.5 s | 27,049,084 | 12,312 |

实测真正在动的窗口只有 VB1300–1475 ≈ **2.9 s**、密集采样约 30 个不同帧。若片头是 A1（265 帧 / 17.7 s），我们只展示了约 30–44 帧。

**数据消费对账**：VB1200→1500 期间 CD 数据口 `0x25890000` 被读 183,054 次（`reg R 05818000 +183054`）；`runtime/src/machine/cdblock.cpp:542-544` 里 32 位读 = 两个 16 位字，即每次 4 字节 → **约 732 KB**。A1.AVI 全文 2,658,574 B，即**只消费了约 27.5%**（约 73 帧的数据量）。VB1500 之后 2500 帧内 CD 完全静默：0 条命令、0 次数据读。

=> 播放器**在文件中途停止取数**，却把自己当成"放完了"（START 能干净地进标题，见 §3）。这是要修的行为。

## 3. 停滞期的活动清单（证明是"等按键"而不是挂死）

`build/run/avi2-head/hw-log.txt`、`build/run/avistart/log.txt`：

- 每帧轮询 FRC `0xFFFFFE12/13` ×11、`0xFFFFFF9C` ×2、SMPC 手柄 `0x00100061/5F/3D`。
- `last polls in: TRUE:06021E18 x2562`；`master pr 0602A10C, sr 100`。
- 加输入立刻恢复：`1600:START` → VB1620–1850 黑 → VB1900 起恒为 `9abeb31b`（标题：仙劍奇俠傳 + 葫芦剑 +「新的故事／舊的回憶」+ © 1998 SOFTSTAR）。**只按这一次键即可**，标题是自动淡入的（`build/run/skiponly/`）。
- 旁证：Linux 侧私有包 `pal-private-checkpoints-20261010-v11` 的 `inputs/boot-load.txt` 开头同样是 `1500:START`——参考平台也在同一位置等按键。

## 4. 已排除项（别再查这些）

1. **Windows 宿主/音频**：windowed ≡ `SDL_AUDIODRIVER=dummy` ≡ `--headless`，帧哈希相同。实机窗口会话 26,670 VBlank（444.9 s）正常关闭，`audio stream: 0 times empty, 0 chunks dropped`，19.6 M 采样中 10.8 M 非静音——Windows 音频在出声且无欠载。
2. **读档/渲染与 Linux 的差异**：按私有包说明跑读档回归，VB3401 的 PNG = `7f410a40b8ee582a9a9db9514d801ee03ad09f9f4cbc1ab25a1e53565598ff10`，与包内 README 记录的 Linux 基准 load PNG **完全相同**（`build/run/bootload/`；VB2700 是「本機進度／卡匣進度一…四」读档菜单）。
3. **走路/演出**：`build/run/walk1/`（VB2500–3200 交替 DOWN/RIGHT/UP/LEFT）VB2300→3900 每帧互不相同，角色朝向随输入变化、镜头跟随滚动，VB3600 切洞窟、VB3900 角色躺地演出帧。收尾 `master pr 06034F06`、`TRUE:06034EDA x2202`。
4. **DMA 短拷**：已由 `patches/0005` 修复并有实盘证据（`docs/DMA_BURST_FIX.md`），本包现象与它无关。

复现命令（全部 `--save -`，不碰存档）：

```
./build/recomp-build/saturn.exe --cue disc/pal_t37401h_13tr.cue --headless --vblanks 2600 --save - --settings - \
  --clock 1998-11-01T12:00:00 --shot 1500,1700,1900,2100,2300,2600 --out build/run/avistart \
  --input "1600:START,1612:,1800:A,1812:,2000:START,2012:"
```

## 5. 给专家的候选方向（按可能性排序，均未证实）

1. **AVI 播放器的取数/丢帧逻辑**：消费约 27.5% 文件后停止请求。播放器按 FRC（`0xFFFFFE12/13`，停滞期每帧轮询 11 次）计时；若 FRC 速率或"追帧丢弃"判定与真机不符，会在几秒内把预算烧完并提前进入片尾。请核对 `onchip.cpp` 的 FRC 递增率与播放器 `f_0602xxxx` 的帧调度。
2. **DMAC 外部请求模式不传输**：`runtime/src/machine/onchip.cpp:167`（`if (!(chcr >> 9 & 1)) { … waits for an external request … return; }`）。若影片解码用外部请求型 DMA 搬数据，会表现为"取到一部分就停"。
3. **DMA 结束中断未模拟**：`onchip.cpp:188` 对 end-interrupt 是 `sat_fatal` 而非模拟；本路径未触发，但同族缺口。
4. 顺带登记的渲染缺口（与本片头无关，别混进本问题）：`vdp2.cpp:349` RBG0/RBG1 旋转未实现（片头期间报 `0013`）、`vdp2.cpp:350` SCRCTL 行/纵向单元滚动未实现（读档后的场景首次报 `0002`，仙剑的彩虹/水面靠它）。

## 6. 其它待办（独立于本包）

- `tools/synthetic_check.py` 在 Windows 上 native selftest 以 `0xC0000409` 中止（任务 #8）。
- `tools/disc_ls.js` 我本轮改过（修好卷名与 PVD 基址 16），但目录遍历仍有缺陷（flags/名字长度偏移不对，会递归爆栈）；可用清单在 `evidence/p0-disc-001/disc_list.txt`，本包 §2 的 LBA/大小取自该文件并已用原始扇区复核。
