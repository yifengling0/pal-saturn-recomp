# 土星备份卡匣（BUP 设备 1）

## 为什么需要它

《仙剑奇侠传》土星版的读档/存档菜单有两处记忆：**本機進度**（内置备份内存）和
**卡匣進度一到四**（外接记忆卡）。此前 runtime 只模拟设备 0，`BupInit` 直接上报"无卡匣"，
所以那四格永远是空的——玩家只有一份进度可存，换进度只能换 `--save` 指向的文件。

取证（`--trace`，VB2720 停在读档菜单）：

```
BUP_Stat(00000001, 00006400, 0609EE20, 060FE994)   设备 1，每份 25600 字节
BUP_Dir(00000001, 06076AE9 / AF4 / AFF / B0A, 00000080, ...)   四格，名字缓冲间隔 11 字节
```

设备 0 只装得下一份 25600 字节（32 KiB 模型里占 402/512 块），四格确实只能落在卡匣上。

## 实现

`patches/0007-backup-cartridge.patch`（只碰 `bios.cpp`、`saturn.h`、`main.cpp`、`bup_test.cpp`，
与 0001-0005 无交集）：

- BUP 从单一 map 改为 `g_bup[2]`，每设备各挂一个文件、各自原子重写；
- 新增 `--cart FILE|-`。**不给 `--cart` 时行为与从前完全一致**（上报无卡匣），所以既有取证基准不受影响；
- `Stat/SelPart/Format/Write/Read/Delete/Dir/Verify` 按设备分派；卡匣容量模型取 512 KiB
  （四份 25600 字节加目录余量），`BupStat` 的"还能放几份"按该设备自己算；
- 状态转储：设备 0 的字段顺序不变，卡匣追加在其后。因此**旧 state dump 会被明确拒绝**
  （"a part is shorter than this build reads"），不会读错。

构建时补丁清单在 `tools/winbuild.py` 与 `tools/prepare_linux_runtime.py` 里都从
`range(1,6)` 改为 `(1,2,3,4,5,7)`；0006 仍归选项构建器专用。

## 验收（全部在本机 Windows 上实跑）

1. `tools/prepare_linux_runtime.py` 重放 0001-0005+0007，生成的树与我手工改的树
   `git diff HEAD` **逐字节相同**。
2. `runtime_tests.exe` 全绿，含新增用例 `cart_holds_the_saves_the_internal_memory_has_no_room_for`：
   四份写入 `cart.bin`、设备 0 文件未被创建、重跑读回、设备 0 读不到（返回 5）。
3. 基准未动：不带 `--cart`，用 `hidden-dragon-exit-rescue-complete` 工作副本 + `inputs/boot-load.txt`
   跑到 VB3401，PNG = `7f410a40b8ee582a9a9db9514d801ee03ad09f9f4cbc1ab25a1e53565598ff10`，
   与 Linux 基准一致；带 `--cart` 时同一帧哈希相同。
4. 端到端写入：进游戏 → `X` 开菜单 → 系统 → 「儲存進度」→ 目标列表出现
   「本機進度／卡匣進度一到四」→ 选卡匣一 → `BUP_Write(00000001, 06089D40, 00200000, 00000000)`，
   `cart.bup` 生成 25632 字节，记录名 `SDW_JPNV_00`（与设备 0 同名，故必须按设备分开存放）。
5. 端到端读回：标题「舊的回憶」→ 读档菜单选卡匣一 → `BUP_Read(00000001, 06076AE9, ...)`，
   画面回到竹篱笆村庄场景。

复现命令：

```bash
build/venv/Scripts/python.exe tools/prepare_linux_runtime.py
WININC="$(pwd -W)/tools/wincompat.h"
cmake -S third_party/saturn-recomp-pal/runtime/tests -B build/check/rt-tests-0007 -G Ninja \
      -DCMAKE_CXX_COMPILER=g++ -DSATURN_NO_SDL=ON -DCMAKE_EXE_LINKER_FLAGS=-static \
      "-DCMAKE_CXX_FLAGS=-static -include $WININC"
ninja -C build/check/rt-tests-0007 && ./build/check/rt-tests-0007/runtime_tests.exe

build/recomp-build/saturn.exe --cue disc/pal_t37401h_13tr.cue --save 工作副本.bup \
  --cart 卡匣.bup --settings - --clock 1998-11-01T12:00:00 --headless --trace \
  --input "1500:START,1512:,2500:DOWN,2512:,2600:START,2612:,2750:START,2912:,3600:X,3620:,\
3800:DOWN,3820:,3900:DOWN,3920:,4000:DOWN,4020:,4200:A,4220:,4800:A,4820:,5400:DOWN,5420:,5600:A,5620:" \
  --vblanks 6500 --shot 5500,5800,6100,6400 --out 输出目录 --log 输出目录/log.txt
```

## 分发包

`run.bat` 默认带 `--cart "%~dp0saves\pal-saturn-cart.bup"`，玩家双击即有四格；文件在第一次往
卡匣存盘时才创建。`SHA256SUMS.txt` 同时改为 LF，`sha256sum -c` 才能直接校验（此前是 CRLF，
Git Bash 下会把 `\r` 当成文件名的一部分）。

## 已知边界

- 卡匣容量是本 runtime 自己的模型（512 KiB / 64 字节块），不等于真机记忆卡的块表；
  游戏只按 `BupStat` 回报的"还能放几份"决定能否存，实测四格可用。
- `Format` 仍与上游一样是空操作（存档界面不会格式化），未随本次改动。
- 设备 0 与设备 1 可以同名（都是 `SDW_JPNV_00`），所以两份文件不能合并成一个。
