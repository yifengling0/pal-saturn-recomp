# P0 真盘分析报告 —《仙剑奇侠传》土星版（Windows 实测）

日期：2026-10-10 　平台：Windows 11 x64（10.0.26300）　上游锁定：`saturn-recomp` `086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`

本轮所有数值都来自对本地镜像的实际读取与上游工具的输出，日志在 `evidence/`。之前提交的 Linux 准备包记录的
`actual_pal_image: MISSING` 已被推翻：**本次输入就是土星版真盘镜像**。

---

## 1. 输入文件

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `../仙剑奇侠传（中）.mdf` | 573,401,136 | `4c76366e3178289c3e73264d8f3a0b9b8b3d78f7baa0862561ce48ce4199d4b5` |
| `../仙剑奇侠传（中）.mds` | 1,542 | `818eac0d35fdd320d9edf54bbdf38a30dec058686685be23a52cb787a821059b` |
| `../readme.txt` | 289 | `c31cb724493f16cfb7993662241d68a3eb2b9c1728932598f1ebd0bdc319d5b7` |
| 派生 `disc/pal_t37401h_v1000_jt.bin` | 573,401,136 | `4c76366e…4199d4b5`（与 MDF 逐字节相同） |
| 派生 `disc/pal_t37401h_13tr.cue` | 605 | `27b0f9fd3a6198a7c8369004188775a75b914a13d28ecf44e6494ffc1e8e7b7d` |

原始 MDF/MDS 全程只读：`validation`（上一提交附带的校验工具）在每次运行前后各算一次哈希，
`build/win-input-002/report.json` 的 `input_hashes_unchanged = true`。转换产物是**副本**，不改原盘文件。

`readme.txt`（GBK）自述：`《仙剑奇侠传》SS版（汉化）`，用法为"虚拟光驱载入 .mdf，用 SS 模拟器（Girigiri、SSF）游戏"。

## 2. MDF/MDS 的结构判定（为什么可以直接当 RAW BIN）

- `573,401,136 = 2352 × 243,793` 正好整除，且 `243,793 + 150 = 243,943` 与 MDS 头里的盘长 `0x3B8E7` 一致。
- 逐扇区扫描 243,793 个扇区的 12 字节同步字段与 4 字节头：
  - 扇区 0–131,987：同步为 `00 FF×10 00`，头字节 mode = `0x01`，MSF 地址从 `00:02:00` 起**连续递增无断裂**（LBA 0–131,987）。
  - 扇区 131,988–243,792：111,805 个扇区同步字段无效、mode 字节随机分布 → 无 Mode 1/2352 结构的 CD-DA 数据。
  - 坏同步计数 111,805 与音频区长度精确相等，没有第三种情况。
- MDF 无文件头、无压缩：偏移 0 即扇区 0。所以 **MDF 本体就是 RAW BIN**，复制一份即可作为 `FILE ... BINARY` 使用。
- 未解决项：MDS v3.1 的层/轨道描述表未被完整解码（`numTracks=2`，三条 `00 00 14 00` 记录的字段语义存疑），
  因此**音轨边界不取自 MDS**，改用盘内 ISO 记录（见下）。这不影响数据区判定。

## 3. IP.BIN（ sectors 0–15，6,144 字节）

`python -m saturnrecomp.disc disc/pal_t37401h_13tr.cue --info` 的输出（`evidence/p0-disc-001/disc_info.txt`）：

```
hardware   SEGA SEGASATURN
maker      SEGA TP T-374
product    T-37401H   version V1.000   date 19981101
device     CD-1/1
areas      JT  (Japan, Asia NTSC)
peripheral J   (control pad)
title      LEGEND OF SWORD AND FAIRY
IP size    0x1800
stacks     master 0x00000000  slave 0x00000000
1st read   at 0x06004000, size whole file
area block 0x0E04  'For JAPAN.'
volume     'LEGEND_OF_SWORD_AND_FAIRY'  system 'SEGA SEGASATURN'  243943 sectors
publisher  'SOFTSTAR'  preparer 'SOFTSTAR'
cpy/abs/bib 'SMP_CPY.TXT' 'SMP_ABS.TXT' 'SMP_BIB.TXT'  created 1998120410235800
1st read file /0 (53068 bytes, lba 25)
```

**盘身份与上一提交 `RESOURCE_AUDIT.md` 引用的 Mednafen 兼容表精确对上**：
`Xian Jian Qi Xia Zhuan (Taiwan)`，ID **T-37401H**，该项要求 SH-2 完整 cache 仿真以修复对白截断。
→ 缓存敏感路径（对白/文本）必须在后续真机行为回归中专门覆盖。这是风险项，**不是**走路异常的根因证据。

`ip_sha1 = ac4596b35b6962acaa04b92ab0342ff7c21772b9`（`--manifest`），可作为"是否同一张盘"的复核凭据。

## 4. 轨道布局与 CUE 的还原依据

盘内 ISO 记录给出每条音轨自己的 LBA 与大小（`--list`，见 §5），据此还原：

```
TRACK 01 MODE1/2352  INDEX 01 00:00:00          lba        0  frames 132138
TRACK 02 AUDIO       INDEX 01 29:21:63          lba   132138  frames  11898
TRACK 03 AUDIO       INDEX 01 32:00:36          lba   144036  frames  10243
…                                                …
TRACK 13 AUDIO       INDEX 01 52:18:42          lba   235392  frames   8401
```

- 数据区实测结束于 LBA 131,987，`/02.WAV` 记录起于 132,138，中间 150 帧（2 秒）是首轨 lead-in gap。
- **未声明 `INDEX 00`/`PREGAP`**：该固定版本上游把 INDEX 00 计入相邻轨道的长度算术（实测会让每条音轨算出 `0 frames`），
  因此这里把 gap 归入前一条轨道。上游不解释显式 `PREGAP`，与本包一致。
- 轨道总数与 `--info` 的 `243943 sectors` 自洽（131,988 数据 + 111,805 音频 + 150）。
- 待验证：真实 TOC 的每轨控制/地址字节（MDS 未解出）；`--audio` 导出 WAV 的轨号是否需与播放器一致。

## 5. ISO 9660 与文件清单

PVD 在 LBA 16（扇区内数据偏移 0x10，`CD001` 位于 LBA 16 的 +1 ✓ 与标准一致），根目录 extent = LBA 4096、大小 0x100000。
上游 `--extract` 得到 **41 个文件 + IP.BIN**，12 条 CD-DA 记录不提取。

可执行程序候选（其余为资源）：

| 文件 | 字节 | LBA | 判定依据 |
|---|---:|---:|---|
| `/0` | 53,068 | 25 | IP.BIN 声明的 1st read 文件，装载地址 **0x06004000** |
| `PROG.BIN` | 399,984 | 51 | `/0` 内含名字串；装载地址由运行时证明（§6） |
| `TRUE.BIN` | 134,200 | 247 | `/0` 内含名字串；装载地址**未证明** |

资源分类（供后续适配层参考，名称/大小/LBA 全部实测）：影像 `A1..A6.AVI`；音乐 `02..13.WAV`（CD-DA）；
图型/关卡 `ABC.J FFF.J MGO.J MGO.NEW MGOP.JOE MAPIC.JOE MDAIF.JOE PPAIF.JOE RGM.JOE BALL.NEW FBP.PX RNG.AV RNG.PAL FIREN.AV`；
文字/字形 `CM.SEC CM.IDX CM.MSG CM.FNT CM.NOR`；脚本/数据 `AIF.NEW AIV.NEW ALLDAT.NEW FB.NEW LOG1.PX LOG2.PX ASCFONT.15`；
样本 `SMP_CPY/ABS/BIB.TXT`、`CERROR.TXT`。

## 6. SH-2 模块与装载地址（证据分级）

| 项 | 结论 | 证据 | 分级 |
|---|---|---|---|
| `/0` 装载地址 | 0x06004000 | IP.BIN 声明 + `sh2 /0 --find-base` 首位候选 252 次序言命中 + 运行时 `boot: P0 at 06004000` | **已验证** |
| `/0` 入口 | 0x06004040 | 自身引导桩 `mov.l @(… 06004024),r4 ; jmp @r4`（`evidence/p0-disc-001/disasm_0_head.txt`）；运行时确实从该地址开始执行 | **已验证** |
| PROG.BIN 装载地址 | 0x06020000 | 运行时 FATAL `call to 06020040 … (from pr 06004180)`，现场 `r6=06020000 r8=06020040`（`evidence/p1-boot-002.log`）；装载器 native 码 `06004152` 处 `r2=06020000, r1=06004094("PROG.BIN")` | **已验证** |
| PROG.BIN 入口 | 0x06020040 | 同上（+0x40 = 桩跳转目标） | **已验证** |
| TRUE.BIN 装载地址/入口 | 未知 | 仅有 `--find-base` 候选 0x06020000（与 PROG 冲突，显然不可同时成立）与其自身桩 | **待验证** |
| 引导桩家族 | `/0`、`PROG.BIN`、`TRUE.BIN` 前 16 字节相同，池内栈指针各异（06010B80 / 060663D0 / 06039520），GBR 均为 0x060FFC00 | 三个文件的头 48 字节对照 | 已观察（入口仍未证） |
| 库版本 | SGL 2.12（`$GFS_SGL Version 2.12 1996-12-04`，出现在三个模块中） | 字符串扫描 | 已验证（版本串存在） |

`--find-base` 的高分**只作候选**，不作为证明；上表把声明、启发式候选与运行时行为分开列出。
机器可读的模块证据见 `evidence/module_evidence.p0_prog.json`（沿用上一提交包内的模板）。

## 7. 尚不确定 / 下一步需要的证据

1. TRUE.BIN 的装载地址与生命周期（是否覆盖 PROG 区域、是否覆盖装载后执行）。
2. MDS 原始 TOC 的每轨控制字节（当前音轨边界来自盘内 ISO 记录，非 TOC 直读）。
3. 盘上 0x100 起的安全码/区域码块与本盘 `areas=JT` 在运行时是否需要额外处理（上游 HLE 已识别区域块 `0x0E04 'For JAPAN.'`）。
4. 缓存敏感行为：Mednafen 对 T-37401H 要求完整 SH-2 cache 仿真，上游固定提交未实现完整模型 → 进入对白/地图回归阶段必须实测比对。
5. **走路异常基线仍未测量**：本报告不含任何位移常数或根因判断（见 `P0_MOVEMENT_BASELINE.md`）。

## 8. 复现命令（Windows）

```bat
cd PAL-Saturn-Recomp
build\venv\Scripts\python.exe -m saturnrecomp.disc disc\pal_t37401h_13tr.cue --info
build\venv\Scripts\python.exe -m saturnrecomp.disc disc\pal_t37401h_13tr.cue --list
build\venv\Scripts\python.exe -m saturnrecomp.disc disc\pal_t37401h_13tr.cue --manifest evidence\p0-disc-001\disc_manifest.json
build\venv\Scripts\python.exe -m saturnrecomp.disc disc\pal_t37401h_13tr.cue --extract build\disc-extract
build\venv\Scripts\python.exe -m saturnrecomp.sh2 build\disc-extract\0 --find-base
build\venv\Scripts\python.exe -m saturnrecomp.sh2 build\disc-extract\0 --base 06004000 --at 06004000 --count 40
:: 上一提交带来的只读校验工具，对真盘产生分阶段 JSON 证据
cd validation && ..\build\venv\Scripts\python.exe -m pal_validate prepare --image ..\disc\pal_t37401h_13tr.cue ^
  --toolchain ..\third_party\saturn-recomp --run-upstream --out ..\build\win-input-002
```
