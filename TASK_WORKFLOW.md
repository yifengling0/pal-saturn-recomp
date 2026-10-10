# TASK_WORKFLOW — Windows 阶段执行规程

本文件是上一提交 `validation/TASK_WORKFLOW.md` 在 Windows 上的续用版：阶段划分、Gate 判据与
"先取证再改代码"的约束不变；这里只补本轮实测确认过的 Windows 专有事项。

## 铁律（本轮每一条都用上了）

1. **先取证再改代码。** 没有镜像时只搭骨架 —— 本轮镜像到位后才开始真盘分析。
2. 每项结论标注 **已验证 / 待验证 / 假设**，并附复现命令与日志文件名。
   `docs/P0_DISC_ANALYSIS.md` §6 的地址表就是按这个格式写的。
3. `game.toml` 的地址必须来自反汇编、内存日志或运行时行为。本轮的 `PROG.BIN = 0x06020000`
   是先有 `--find-base` 候选（标注"仅候选"），再等到运行时 `call to 06020040 / r6=06020000` 才启用。
4. **不把"编译成功"当"游戏已运行"**，也不把"跑起来了"当"能玩了"。本轮画面仍是全黑，报告照实写。
5. 不预设根因。走路问题的五类成因在拿到地图内采样前一律"待测"。
6. 修改优先落在游戏层（`src/pal_game/` + `[[hook]]` + `SATURN_EXTRA`），**上游 checkout 保持干净**；
   只有真正的平台/硬件缺口才动上游，且要单独说明。
7. 原版模式与增强模式必须可切换；移动补丁不得绕过碰撞、NPC 同步、场景触发。
8. 每过一个 Gate 交一份报告并更新 `PROGRESS.md`；阻塞要写"已排除项 + 下一步候选"，不能只写"失败了"。
9. 增量构建优先：改 hook 只触发一次 recompile + 11 秒 ninja，不要无目的全量重来。
10. 产出含可运行测试、日志与失败边界。

## Windows 专有事项（本轮实测）

| 事项 | 要求 |
|---|---|
| 上游 checkout | `core.autocrlf=false`，否则 `disc.py` 的已审查 SHA-256 不匹配，`validation` 直接判失败 |
| 链接方式 | 必须 `-static`（`tools/winbuild.py` 已内置）；否则 Git 的 `libstdc++-6.dll` 抢解析，产物加载即 0xC0000139 |
| 构建入口 | 用 `tools/winbuild.py`，不要用 `python -m saturnrecomp.build/learn`（上游 `prereqs` 会因平台标签拒绝） |
| CMake 缓存 | 改过 flags 先删 `build/check` / `build/recomp-build`，否则 ninja 报依赖缺失 |
| 传给编译器的路径 | 用 `pwd -W` 的 `C:/...` 形式；MSYS 的 `/c/...` g++ 打不开 |
| 子进程输出解码 | 中文系统默认 GBK，`text=True` 会抛 `UnicodeDecodeError`；驱动里统一 UTF-8 + `errors="replace"` |
| 自动化通道 | `saturnrecomp.agent` 在 Windows 不可用（`pass_fds`）；测量走 `--input/--watch/--peek/--shot/--state-*` 与游戏层 hook |
| 存档隔离 | 测试一律 `--save -` 或专用文件，避免写 `%APPDATA%\saturn-recomp\T-37401H_V1.000\backup.bin` |

## 阶段与命令

```bat
:: P0 输入与光盘分析
build\venv\Scripts\python.exe -m saturnrecomp.disc disc\pal_t37401h_13tr.cue --info
build\venv\Scripts\python.exe -m saturnrecomp.disc disc\pal_t37401h_13tr.cue --list
build\venv\Scripts\python.exe -m saturnrecomp.sh2 build\disc-extract\0 --find-base
cd validation && ..\build\venv\Scripts\python.exe -m pal_validate prepare --image ..\disc\pal_t37401h_13tr.cue ^
  --toolchain ..\third_party\saturn-recomp --run-upstream --out ..\build\win-input-00X

:: P0/P1 工具链自检（等价上游 tools/check.sh）
bash tools\check_windows.sh

:: P1 重编译与推进
build\venv\Scripts\python.exe tools\winbuild.py build --recompile
build\venv\Scripts\python.exe tools\winbuild.py learn --out build\learn-00X --limit 25 -- ^
  --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 3000

:: 定位（游戏层 hook）
set PAL_HOOKS=06004164,06004334,06004364,06004950,06004EB0&& set PAL_DUMP=r14:24&& ^
  build\recomp-build\saturn.exe --out build\run\diag-00X --cue disc\pal_t37401h_13tr.cue --headless --save - --vblanks 900
```

Gate 判据沿用实施方案 §5；当前状态见 `PROGRESS.md`。
