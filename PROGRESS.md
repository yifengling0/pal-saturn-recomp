# PROGRESS —《仙剑奇侠传》土星版 Recomp，Windows 阶段

更新：2026-10-10（Windows 实测）。上一提交（Linux 准备包，`PAL_Saturn_Linux_Prepared_PENDING_20261010.zip`）
的状态是 `actual_pal_image: MISSING`、`upstream_execution: PENDING_AUTHORIZATION_NOT_RUN`。
**本次两项都被推翻**：真盘已在工程目录内，上游源码已在本机审查后固定提交执行，且真盘已在本机码上启动。

## 阶段结果

| 阶段 | 状态 | 关键事实 |
|---|---|---|
| P0-A 镜像取证 | **已验证** | MDF = 243,793 个 RAW 2352 扇区；数据 131,988 + 音频 111,805；IP.BIN `T-37401H V1.000 19981101 areas JT`；SHA-256 全记录 |
| P0-B Windows 工具链 | **已验证** | 上游指令自测 775 函数/9300 向量/0 失败；运行时单测 44/0（含 GPL VDP1 变体）；200 通过 + 6 项 Windows 平台缺陷（已定位并给出处置） |
| P0-C 真盘光盘分析 | **已验证** | 41 文件 + IP.BIN 提取；12 条 CD-DA 记录；`/0`→0x06004000、`PROG.BIN`→0x06020000 与入口 0x06020040 **由运行时行为证明** |
| P1 可运行性 | **部分通过 / Gate 未过** | 本机码连续 13000 VBlank（≈217 s）无 FATAL；**已进入俯视角地图并看到人物**（最小按键序列 `START@1500, START@2500, A@2600` → VB2700 出地图，`build/run/dump-map/shot-2700.png`）；同址换入链 PROG→TRUE→PROG 跑通。原以为卡住的"影片幕全黑"经离线复刻证伪——那一幕 runtime 画对了。当前阻塞 `PAL-P1-009` 已六度收窄：地图幕（VB2700）与洞穴幕（VB4400）**都画得完好**，输入/精灵/VDP2 单元与位图模式均正常；停滞发生在 VB4707 换到 P0 state 8 之后 —— PROG 的**模式 4 主循环按机器码设计就不返回**（其收口 `0x06026F72` 在 PROG.BIN 全模块内零引用，已逐条解码 `bra/bsr/bt/bf/bt/s/bf/s` 证实），而"把场景脚本装上"那一步从未发生（游标 `[0x060768E8]/[0x060768EA]` 全程只有 `0x0000`/`0xFFFF` 两种值），PROG 也从不装自己的任务（`[gbr+972]` 的唯一写点只写空桩 `0x06060394`）。结果：背景位图不上传、VDP2 CRAM 零写，人物浮在黑底上一直到 VB30000
| P2 走路基线 | **未开始测量** | 协议与采集通道已就绪（`docs/P0_MOVEMENT_BASELINE.md`）；无数据、无常数、无根因 |
| P3 Windows 成品体验 | 未开始 | 依赖 P1 |
| P4 HarmonyOS | 未开始 | 依赖 P1/P3；上游生成器只对 `ANDROID` 出 shared library，OHOS 需自行处理 |

## 阻塞清单

**PAL-P1-001（已解决 2026-10-10）** 根因在上游光盘模型，不在游戏层，也不是 SMPC/68000：
`runtime/src/machine/cdrom.cpp` 的 `CueFile` 只有一个 `audio` 标志，却在每一条 `TRACK` 行都被覆写，
本盘"单 BIN 13 轨（1 数据 + 12 音）"因此被整盘判为音轨 → `cd_tick()` 走音频分支 →
`deliver_sector()` 从不调用 → `Get Part Size`(0x51) 恒 0 → 装载器无限轮询 → 返回 -8。
修复 `patches/0001-cdrom-is-audio-per-track.patch`（20 行，按轨判定；对一轨一文件的 CUE 行为不变）。
验证：修复前后 `--trace` 对照（`evidence/p1-trace-cd-001.log` vs `build/cd60.log`）、
`evidence/p1-boot-003/004.log`、回归 `evidence/p1-check-after-cuefix.log`（SCRIPT_EXIT=0，200/6、775/0、44/0）。
详见 `docs/P1_RECOMP_REPORT.md` §4。

**PAL-P1-006（已解决 2026-10-10）** 覆写 BIOS 服务向量区的不是别人，是**游戏在 0x06020000 处把 PROG.BIN
换入成 TRUE.BIN**，而 `game.toml` 只声明了 PROG，运行时继续跑 PROG 的本机码：PROG 的 `0605FD92`
把换入镜像头部的 `0x06040C40`（TRUE 的字段）当成自己那张 `{30, 指针}` DMA 记录表的长度，
从 `0x060C0000` 起连铺 2 万余条记录，铺过 WRAM 尾（`0x060FFFFF`）后按 1 MiB 镜像落到 `0x06100320`，
折叠进向量槽 `0x06000320..0x0600034C`，于是 `06059C3A` 的 `jsr @r1` 取到 `0x1E` 而 FATAL。
证据：`--watch`（打 0002 补丁后报**原始**地址，别名写不再漏）+ hook `06007E96` 打印的装载请求块
（目标 0x06020000、长度 0x21000、66 扇区）+ 盘上唯一吻合的文件是 TRUE.BIN(134,200 B)，
其 0x88/0x8C/0x90 三字节与 watch 抓到的写入值逐字节相同。日志 `evidence/p1-true-001..006`。
处置：**只改配置层**——`game.toml` 增加 `[[module]] TRUE`（base 0x06020000，seed 0x06020058 取自镜像头部
`[0x24]`，与 PROG 的 0x06020040 同源）。之后运行时打出 `program start 1: TRUE at 06020000`，
画面从全黑变成开场地球实机画面。

**PAL-P1-007（已解决 2026-10-10）** 上游把"调用模块基址"一律当成 program start：`core.cpp` 的
`is_base(addr)` 命中就 `sh2_program_start()` → 抛 `ProgramStart` 展开宿主栈。本作 P0 的装载循环是
`06004200 mov.l #0x06020000,r8 ; 06004202 jsr @r8`（**调用**并等返回，返回点在 `06004206`），
程序一 `rts` 就撞上 `the program at 06020000 returned` 而 FATAL——按键退出开场影片时必现。
修复 `patches/0003-call-into-swapped-module-returns.patch`（14 行）：基址处镜像能识别为已知模块
且该地址确有入口时，按**普通嵌套调用**处理（先 activate 再 call），否则保持原 program start 语义。
验证：同一输入序列下 `evidence/p1-map-001/p1-007-program-returned-fatal.log`（修复前 FATAL）→
修复后 P0 于 28.148 s 重新 `PROG activated by a call to 06020040` 并进入地图。
hook `P0:06004206` 就是"程序返回装载器"的实测探针（`evidence/p1-map-001/run-with-return-hook.log`，vb=1616 命中一次）。

**PAL-P1-008（判断已撤回 2026-10-10，见 PAL-P1-009）** 原判断"VB4000 之后的影片幕全黑是因为 VDP2 的 SCRCTL
（行滚动）没实现"是**错的**，用 `--dump` + 离线复刻合成（`tools/vdp2_replay.js`）当场证伪：
把 VB3900 的 VDP2 VRAM/CRAM/寄存器喂回一份独立复刻的合成器，渲出的正是**同一幅山峦云海**，
与运行时截图 `build/run/dump-movie/shot-3900.png` 一致 —— 这一幕 runtime 本来就画对了，
`SCRCTL` 那条 `is not done` 只是"某效果被忽略"的提示，不是黑屏原因。SCRCTL 仍属已知缺口（片头 logo 幕用到），
但**不是**当前阻塞，已降级到 PAL-P1-002 那一族里跟 RBG 缺口并列。

**PAL-P1-009（当前硬阻塞）** 停滞点不在影片幕，而在**片头放完、游戏把 PROG.BIN 换回 0x06020000 之后**。实测链条：

- 时间线（最小序列 `START@1500, START@2500, A@2600`）：VB700 TTC 线框 logo 正常 → VB1400/3900 云海正常 →
  VB2700-3350 俯视地图正常（VB3350 地上还多出影子，说明场景在自走）→ **VB4886 `PROG activated by a call to 06020040`**
  （日志无 "its data differs from the image's" 后缀 = CRC 与镜像逐字节相符，换入是真的）→ 此后永久黑屏。
- 黑屏幕的 VDP2 寄存器就是 logo 那一套（`BGON=0x43`、`CHCTLA=0x1212`、`SCRCTL=0x0002`、`MPOFN=0x10`、`MPABN0=0x3B3B`），
  但 **VDP2 VRAM 只剩 640 / 524288 个非零字节**（VB3900 是 413646）→ 图元数据没了。
- **VB6000 与 VB12000 的 VDP1 VRAM / VDP1 FB / VDP2 VRAM / VDP2 CRAM 逐字节完全相同**（只有 VDP2 寄存器差 1 字节），
  而这段时间 hw-log 仍记着约 1405 次/帧的 VDP2 VRAM 写 → 写进去的是同一份空数据。
  两幕的存储占用正好互补：地图/影片 = VDP2 有内容、VDP1 几乎空（293 字节）；停滞幕 = VDP1 有内容（65697 字节、FB 72359 字节）、VDP2 空。
- ~~不是"在等某个键"~~ **这条口径本轮被推翻**：先前用 `build/mash-all.txt`（VB6000-9100 逐键按）对照得到的
  "三帧 MD5 一致"，实测是**按键时点不对**造成的假阴性。按正确时点重做（`build/holdup.txt`：
  `1500:START, 2500:START, 2600:A`，再 `6000:UP` 一直按住到 6500，`--shot 5950,6000,6100,6200,…`）：
  VB5950/6000 = `471770e4…`，**VB6100 变成 `be3ff755…`，VB6200 起再变成 `1f25ea67…`** ——
  人物在停滞幕里确实随方向键换姿势、换位（`build/run/holdup/shot-*.png`）。
  另一组对照 `build/press2.txt`（6000:START / 6100:A / 6200:B / 6300:UP / 6400:A）也在 6400 之后换帧。
  **所以"输入链路坏了"不成立**；反过来"每 40 VBlank 猛按 A 能从 6000 按到 12000"也没能让画面前进
  （`build/run/pressA/shot-*.png` 六帧 MD5 全 = `471770e4…`），说明它不是"再按一下就过"的界面。
- 不是光盘：`--trace` 全程无 FATAL、无未实现命令，cmd 61/06/62 读循环持续（2734 轮），
  FAD→BIN 偏移映射经实测校验（LBA16 扇区内第 17 字节正是 `CD001`）。
- 不是死锁：`last polls in` 99% 落在 `PROG:0605D68A`，但 `--watch 060FFC10:060FFC18` 证明那是 SEGA 声音驱动
  Tick 的**等下一帧空转** —— `gbr+19` 每 VBlank 由 `PROG:0605CECC` 递减（5→4→…→-1 后重装），CPU 一直在跑帧循环。
- 已排除的三个猜测（都留了实测）：游戏全程不碰 MPEG 卡寄存器（hw-log 无 `0588xxxx`，盘里的 `A1-A6.AVI` 与本幕无关）；
  不写 SCU 定时器（重编译码里没有 `0x05FE0090/94/98`）；SCSP→主 CPU 中断（`SOUND_REQ`/0x46）全程 0 次，
  而实测游戏根本不写 `MCIEB(0x42A)`、只写 `SCIEB(0x41E)=0x0088` → 声音中断不是这里的等待条件
  （runtime 的 SCSP 偏移表与 yabause wiki 的 `SCIEB=0x41E`/`MCIEB=0x42A` 一致，不是移植侧的映射错）。

**2026-10-10 第二次收窄（本轮实测，四项旧候选全部当场否掉）**

*光盘没饿着*：给 `cdblock.cpp` 加临时诊断（测完已 `git checkout --` 撤回，上游树回到"仅 3 处补丁"），
`--trace` 到 VB6200 的驱动器心跳是 `st=1(PAUSE) fad=5350 start=5334 end=5350 free=200 done=16 due=0` ——
最后一次 `cmd 10 (1080 14D6 0080 0010)` 要 16 扇区，16 扇区全部投递完并 `play ended`，游戏随后发了
`cmd 48`（Reset Selector）就**再没碰过 CD 直到 VB9000**。所以"在等光盘数据"不成立；
`cmd 51` 恒 0 只是"分区已读完并 delete"的正常终态（全程 81542 次轮询里 448 次拿到过 0xC8=200，说明这条答复通路本身是好的）。

*声音中断不是等待条件*：停滞全程主 CPU 对 SCSP 公共区只写过 **一个** 寄存器
（hw-log：`reg W 2 05B00400`＝MVOL，共 4 次），`MCIEB(0x42A)`/`SCIEB(0x41E)` 一次都没有 →
上一轮"唯一剩下的候选是 SCSP→主 CPU 中断"**作废**。

*主循环没卡死，是 6 VBlank 一周期的自走*：`--watch 060FFC12:060FFC13 --watch-vblanks 5700:6200` 抓到
`gbr+19` 每帧 `5→4→3→2→1→0→-1`，随后由 `PROG:0605CECC`（pr `0x06022354`）重装成 5、
由 `PROG:06026D84`（pr `0x06026E58`）把 `gbr+18` 置 6，VB5700-6200 共 668 次写入、周期严格 6 帧 →
`last polls in PROG:0605D68A ×4052` 是 Tick 的常规等待，**不是死锁**。
回调槽 `gbr+972 = 0x06060394`（`rts; nop` 空桩）在 VB55/59/67 的健康段也是同一个值，
它由驱动自己的初始化在 `0x0606036C-0x06060372` 装上去，**不是异常**。

*镜像与字面量池都排除了*：`disc/pal_t37401h_13tr.cue` 的 12 个音轨边界与原始
`仙剑奇侠传（中）.mds` TOC 里的 MSF **逐条吻合（CUE 位置 = TOC 绝对 MSF − 2 秒）**；
抽样扇区的 BCD MSF 与其位置一致（LBA 5184 → `01:11:09`）；全零段只有 150 扇区量级的引前空隙与常规填充，
不是转换打洞。`0x0605D77C` 这个被重编译期折成常量的池单元，镜像里、运行时 `--peek` 里都是 `0x21000000`，
且是装载器自己写的（`P0:06007E90`，VB35 与 VB1672 各一次）→ **不存在"池被运行期改写而常量过期"的错编**。

*两幕的存储占用互补，指向很干净*（`--dump` 分段非零字节）：
地图幕 VDP2 VRAM **413642**、VDP1 VRAM 293、VDP1 FB **0**；停滞幕 VDP2 VRAM **640**、
VDP1 VRAM **65697**、VDP1 FB **72359**，寄存器侧 `BGON=0x0043`（**RBG0 + RBG1 + NBG2**，
bit0/1/6 —— 早先记成"NBG0+NBG1+RBG2"是位序读错，已更正）、两层名称表全 0、
`PNCN0=0x800C`（bit15 **SPCL**＝特殊显示模式）、`SCRCTL=0x0002` + `LSTA0=0x12F2E07C`（行表）、
`CCCTL=0x0043`、`SPCTL=0x2122`。
即：**这一幕只有 VDP1 的人物在画，VDP2 的背景从未被填**（640 非零字节只够一张行表，像素一层都没有）。
顺带记一笔真缺口：`vdp2.cpp` 的 `note_unsupported()` 只测 `BGON & 0x30`（RBG0/RBG1），**RBG2/RBG3（bit6/7）被静默忽略**，
所以这一幕即便有数据也不会出图 —— 但它现在连数据都没有，两者要分开修，别混为一谈。

**2026-10-10 第四次收窄（详见 `docs/P1_RECOMP_REPORT.md` §4.10）** 上面"场景脚本在 VB5660 之后不再运行"
这条口径**作废**：给帧链 8 个 jsr 返回点下 hook 后实测，`f_06026D84 → f_06033654 → f_0603440C →
{f_06033DD8, f_060344A0 脚本 VM, f_06032C64, f_06034FA0, f_0602222C}` **每一帧都跑到头**
（VB4886 之后各 70-71 次，末次 VB6096）。同时当场否掉三条候选：
① `f_0605D68A` 不是卡死点，它是每帧 VSync 同步（`[19,gbr]` 由 `f_0605CECC` 每 VB 递减并 5→0→FF 回卷，
`[972,gbr]=0x06060394` 是一条 `rts` 空任务，属正常空档）；② 从机 SH-2 健康（`--watch 060FFC44:060FFC4B`
里主机每写一次队列游标，从机立刻跟到同值）；③ PROG.BIN 三次装载全部走完
（请求块 `+04=0x00062000`、`+18=0xC4`=196 扇区，VB4886 到 `+1C=0xC3` 末扇区）。
静态解码 `build/disc-extract/0` 偏移 0x138 的 13 项 P0 状态表后，真正的缺口是：
**状态 `[0x0601FA00]` 自 VB4707 起停在 8（→ 装载 PROG.BIN），而只有 PROG 自己把它推到 9/11/12，
P0 下一轮才会去装载 TRUE.BIN —— TRUE 才是画 VDP2 背景的模块**。
`--peek` 到 VB16000 仍是 `0008`，且 187 次连续按键（`build/mashlong.txt`）推不动，所以这一幕不是在等按键。
抓手：`f_06026D84` 里 `jsr f_06022D5C` 返回 0 走 `[18,gbr]=6` 那一支（VB4886 后 71/71 全走这支），
而 `f_06022D5C` 是 14 个操作码的命令解释器 —— 门在"这一帧没吃到该吃的命令"。
判据不变：同一最小序列下停滞幕 VDP2 VRAM 非零字节从 640 回到 40 万级并出背景。

**方向输入的状态（第二次更正）** 上一轮写的是"VB2700-3800 地图幕里 UP/RIGHT/不按键三组逐帧 MD5 相同，
但那一幕是自走脚本，不能当输入链路坏的证据"。本轮在**停滞幕**用正确时点重测（见上面 `build/holdup.txt` 那组）：
**方向键有响应、人物会换位换姿势**，所以"输入链路坏了"这个候选**正式作废**，不再作为任何根因。
仍未证明的是：人物能不能走到场景触发点（背景是黑的，触发点看不见），以及坐标/朝向单元在哪 —— 那属于 P2 的活。


**PAL-P1-002（硬件缺口，未触发）** `VDP2: RBG0/RBG1 (0013) is not done` 在旧路径出现，换入 TRUE 之后本路径没再打过；
它和已撤回的 PAL-P1-008 是同一族（VDP2 未实现的模式），但**不是**当前这幕（PAL-P1-009）的条目，不要混用。

**PAL-P1-005（已解决 2026-10-10）** `--watch` 的两处精度缺口：① 别名写看不见 →
`patches/0002-watch-fold-wram-mirrors.patch` 让区间比较走折叠地址、报告仍打印**原始**地址，
加上这一条才当场点出 `0x06100320` 这类别名写；② `in ?:%08X` 的归属由宿主函数入口上界查找得出，
会把确属 SH-2 指令的 store 打成 `?`，不得据此推断"是运行时内部写的"（②仍未改，属工具限制）。

**PAL-P1-003（平台自动化）** `saturnrecomp.agent` 在 Windows 不可用（`pass_fds`）；走路测量暂用
`--input/--watch/--peek/--shot/--state-*` + 游戏层 hook 通道，本轮全部实际用到。

**PAL-P1-004（风险跟踪）** Mednafen 对 `T-37401H` 要求完整 SH-2 cache 仿真以修复对白截断；
上游固定提交无完整 cache 模型。进入连续对白回归时必须实测；**不作为走路根因**。

## 本轮新增的可复用资产

- `patches/0001-cdrom-is-audio-per-track.patch`、`0002-watch-fold-wram-mirrors.patch`、
  `0003-call-into-swapped-module-returns.patch` — 上游改动全部以补丁入库，子模块固定提交保持可校验、可回退；
  三处都对应上游的测试盲区（单文件多轨混合模式 CUE、`--watch` 的 WRAM 别名、装载器 jsr 进程序后返回）。
  回归 `evidence/p1-check-after-3patches.log`：200 通过 / 6 项已知 Windows 平台缺陷（与打补丁前完全一致）、
  指令自测 775 函数 9300 向量 0 失败、运行时单测 44/0（含 GPL VDP1 变体 44/0）。
- `tools/winbuild.py` — Windows 构建/learn/run 驱动：以实测结论替换上游的平台标签，静态链接，UTF-8 安全。
- `tools/check_windows.sh` — 上游 `tools/check.sh` 的 Windows 等价套件（本轮 SCRIPT_EXIT=0）。
- `tools/wincompat.h` — 仅测试构建使用的 `setenv` 垫片（同时设 `%APPDATA%`）。
- `src/pal_game/pal_diag.cpp` + `game.toml [[hook]]` — 游戏层诊断通道（`PAL_HOOKS/PAL_DUMP/PAL_LIMIT`），
  现有 20 个 hook 点，含 P0 装载链与 PROG 的启动路径；阻塞点就是靠它逐层定位的。
  实测约束：**hook 必须先在 `game.toml` 声明**才会生成 `sh2_hook` 调用，且不能落在分支或延迟槽上。
- `tools/vdp2_inspect.js` / `tools/vdp2_replay.js` — 读 `--dump` 尾部的 VDP2 VRAM/CRAM/寄存器：前者按上游
  `src/saturnrecomp/hw.py` 的名表解寄存器并列出每层的名称表/图案读址；后者**独立复刻** runtime 的合成路径
  （setup_nbg/nbg_pixel/dot/back）把 dump 重画成 PNG。本轮就是靠它证伪了 PAL-P1-008，也是"改 VDP2 之前先离线验证假设"的通用手段。
- `tools/disc_ls.js` — 从 MODE1/2352 镜像读 ISO9660（数据在扇区内第 17 字节），可把 CD Block 日志里的 FAD 反查成文件。
- `build/p0_full.asm`、`build/prog_full.asm` — 两个模块的整文件线性反汇编（取证用，构建产物目录，不入库）。
- `disc/pal_t37401h_13tr.cue` — 13 轨盘定义（1 数据 + 12 音轨）。本轮**独立校验过**：与原始
  `仙剑奇侠传（中）.mds` TOC 里 12 条音轨的 MSF 逐条吻合（CUE 的 INDEX 位置 = TOC 绝对 MSF − 2 秒），
  抽样扇区的 BCD MSF 与位置一致，全零段只有引前空隙量级（150 扇区）→ 镜像与轨表不是任何阻塞的成因。
- `build/min3.txt`（到地图+片头的最小序列）、`build/holdup.txt` / `build/press2.txt` / `build/pressA.txt`
  （停滞幕的输入对照：按住 UP / 逐键按 / 每 40 帧猛按 A）—— 判"认不认键"必须用**停滞幕时点**的脚本，
  早先 `mash-all.txt` 那种时点会给出假阴性。
- `validation/` — 上一提交的只读校验工具，在 Windows 上 26 项自测通过，并对真盘产出分阶段 JSON 证据
  （`build/win-input-002/report.json`，`input_hashes_unchanged = true`）。

## 下一步（顺序固定，别跳）

1. `PAL-P1-009`：**只查一件事——停滞幕的 VDP2 背景数据为什么没被写入**。已排除的不要再碰：
   光盘投递（16 扇区全部到位、`play ended`、之后游戏自己不再读盘）、声音中断（`MCIEB` 从不写）、
   主循环死锁（`gbr+19` 严格 6 帧一周地递减/重装）、镜像与轨表（与 MDS TOC 逐条吻合）、
   字面量池过期（`0x0605D77C` 镜像/运行期同为 `0x21000000`）、输入链路（停滞幕按 UP 人物会动）。
   **停滞 100 帧的状态普查（`--watch 060FFC00:060FFDFF --watch-vblanks 6000:6100`，40945 次写入）**：
变化的全部是驱动记账单元，没有一个是场景状态 —— 最热的是 `gbr+169=0x10`（`PROG:06065DC8`，5627 次）
与 `gbr+115=0x01`（`PROG:06060870`，5627 次，同一热循环），加上 6 帧一周的 `gbr+18/19`、
每 6 帧翻一次的 `gbr+166/168/188`（`gbr+188` 在 0x0E/0x08 之间交替，pr 为 `0xFFFFFFE8` 中断上下文）。
**100 帧里没有任何一个场景状态单元被写过**，这就是"脚本被门住"的直接证据，而不是"画面画错了"。

抓手：对主循环的两个返回点 `0x06022354`、`0x06026E58` 下 hook 打印脚本步序号与 `gbr+160..200`，
   落点已收敛（`docs/P1_RECOMP_REPORT.md` §4.10 ⑨⑩）：PROG 的 mode-4 常驻循环每帧都在调 P0 的状态服务
   `P0:06010A80`（pr `0x06022EFA`），但从未拿"切到 9/11/12"的参数去调它。要查的是
   `f_06022D5C`/`f_06022B8C` 那张 14 操作码表里**哪一条**会带状态值调 `06010A80`，以及这一幕脚本为何走不到它。
   **不要再查"记录分配器 `PROG:060235B8` 为什么没被调"**：它的门是 `[r14]==1`，而 `f_06026D84` 里
   `[r14]` 只有两处写、都写 0，在 PROG 下这条分支按设计就不可达 —— 装配场景的是 TRUE，不是 PROG。
   判据不变：VDP2 VRAM 非零字节从 640 回到 40 万级、同一最小序列下这一幕出背景。
   **RBG2/RBG3 的渲染缺口（`note_unsupported` 只测 `BGON & 0x30`）是另一件事**：数据填进去之后这一幕
   仍可能因为 RBG2 不画而缺一层，届时先用 `tools/vdp2_replay.js` 离线验证再动上游，
   上游改动继续以 `patches/0004…` 入库并跑 `tools/check_windows.sh` 回归。
2. 走到真正交给玩家操作的那一幕，用同一套 `--peek 06000000:262144` 差值法（不按键 / UP / LEFT 三组对照）
   **先证明方向输入确实改变状态**，再定位人物坐标与朝向单元。
3. 按 `docs/P0_MOVEMENT_BASELINE.md` §1 采集、填 §3 表格。**测到基线之前不写任何走路常量。**
4. 走路异常的修复只走游戏层（`game.toml [[hook]]` + `src/pal_game/`），不得绕过碰撞、NPC 同步与场景触发。
5. 继续在地图/战斗里推进并跑 `learn`，把新暴露的入口学进 `tools/seeds.json`；
   同址换入的新模块按 PAL-P1-006 的办法从镜像头部取入口，不猜。
6. Gate P1 未正式判过之前，不启动 HarmonyOS 移植，不产出可分发构建包。

## 2026-10-13 — 彩依战暴露的绘图跨层返回

已从 CPU fatal 与原 ROM 指令确认：06060870 的拒绝路径主动弹出上一层 PR，
静态生成代码却仍要求返回局部 continuation。新增五条精确调用边 lowering，
覆盖 PROG 三边和 TRUE 两边；保留原指令、delay slot、poll 和全局严格返回检查。
ROM 与八个完整函数均有身份断言，普通及 literal-probe 生成均独立校验。
CMake 对实际链接的生成代码拒绝旧、篡改或重复函数，包含 OHOS skip-learn。

合成边界、完整生成函数红绿、正常路径寄存器/内存一致性和 CMake 拒绝测试已通过；
独立审查与 ASan/UBSan 通过；376 tests / 201 subtests 通过，额外启用的可选
键盘整合测试也通过。正式 driver 从空目录生成后，二进制 SHA 与候选完全相同。
正常存档实玩 session042 已过退场门：第六回合 VB48041 后无键推进至48641，
battle 65535→0，回到场景109(704,1456)，李/月如的生命灵力恢复，彩依/晋元离场
无 fatal。该结论仅是此处 Linux 实玩修复验收，不是全游戏或其它设备通关。
完整根因、可复现命令和当前验证范围见 `docs/RENDER_NONLOCAL_RETURN_FIX.md`。

## 2026-10-13 — battle E and scoped command taps

- Fixed PC98 E in the native battle command menu by mapping the configured item
  key through its own battle context to Saturn R; original item/target flow owns
  choices, actions and consumption. Q battle flee remains unbound.
- Reproduced same-pump E key-down/up loss on real SDL, then fixed E/W/D/F/R with
  one first-edge-wins pending command until the original menu reader acknowledges
  it. Input is retired at menu/actor/focus/overlay boundaries and projected after
  tap carry, with genuine input priority. Field walking/audio/chest unchanged.
- Independent review found and helped eliminate a multi-key pending deadlock
  before acceptance. Added compiled generated-host conflict/lifecycle regression
  tests and exact source guards for the single guest acknowledgement addition.
- 389 tests + 201 subtests passed with zero skips. Both Linux generation modes
  and release unsigned ARM64/x86_64 HAP passed. Actual SDL normal-save checks:
  E list/target cancellation; held/repeated E across actors; exactly one herb
  consumed; W throw preserved by A; D; F/R magic semantics. See
  `docs/PC_KEYBOARD.md` and `evidence/battle-items-20261013.json`.
- No physical Harmony device or native Windows runtime acceptance claimed.

## 2026-10-13 — mobile landscape and bounded audio phase headroom

- Integrated phone/tablet landscape resources and SDL-main-window lifecycle
  recovery on the published E-fix baseline; PC and proven walking retained.
- Corrected actual ArkTS callback-class incompatibility with a typed nine-method
  adapter; real CompileArkTS, resources and unsigned dual-ABI HAP passed.
- Added bounded OHAudio phase prime and five-second producer diagnostics with
  adaptation disabled. No assertion that physical speaker stutter is resolved.
- Final tools: 404 tests + 201 subtests, zero skips; 7 phone tests; final-host
  UBSan audio: 38 policy checks and 43 cases / 4613 checks. Both formal Linux
  modes passed; package identities and boundaries recorded in
  `docs/OHOS_MOBILE_INTEGRATION_20261013.md` and its linked evidence.

## 2026-10-26 — manual obstacle stop (local, not published)

- Verified original mover neighbour fallback as the cause of wall/object side
  slides. Added a guarded game-layer hook selecting the original stop branch
  for manual input only; script movement and all input/audio layers unchanged.
- Actual original-disc replay: original-mode 5/5 screenshots match pre-change;
  fixed mode stops at desk/chair instead of sidestepping. Live cloud SDL held
  wall test and facing/cabinet interaction yielded 止血草 successfully.
- Callback, linked-generation gates and generated mover scenario tests cover
  original/fixed/manual/script paths; see `docs/OBSTACLE_STOP.md` for commands,
  evidence boundaries and the explicit original-policy switch.
- Final full regression: 421 tests + 201 subtests, zero skips; 176 generated
  mover scenarios including bounds, no input and turning. Clean formal SDL build
  passed; final-build pickup replay matched all three earlier screenshots.
- This task does not publish commits, release binaries or private game assets.


## 2026-10-26 battle casting voice audit

Original/quick first Sword spell uses the same original Li Xiaoyao casting PCM and SCSP pitch. Ling'er Thunder and Yueru Qi Jian Zhi use their respective original samples. The reported female voice was **not reproduced**, so no voice substitution or pitch patch is included. See `docs/BATTLE_VOICE_AUDIT.md` for evidence and coverage limits.
