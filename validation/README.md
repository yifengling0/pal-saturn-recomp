# Saturn《仙剑奇侠传》Linux 验证工程

这里的 PAL 是《仙剑》项目简称，不是欧洲 PAL 制式。本工程先验证 Linux 重编译路线，再推进真盘启动、地图输入和走路测量；Windows 与原生 HarmonyOS 留到后续。

**当前不是已经完成的游戏移植。** 此目录是可运行的输入准备、分阶段证据和走路基线工具。没有打包游戏、BIOS、猜测的装载地址或假的 `game.toml`。真实游戏进度和上游构建结论见 [PROGRESS.md](PROGRESS.md)；全流程见 [TASK_WORKFLOW.md](TASK_WORKFLOW.md)。

## 本地运行

需要 Python 3.11+；本项目自身只用标准库。上游源码必须单独取得、固定并审查。

```bash
cd project
python -m unittest discover -s tests -v
python -m pal_validate --help

# 无盘也会留下明确 blocked 报告；退出码预期为 2。
python -m pal_validate prepare --out build/no-image-001

# 只读盘点。请换成自己的合法镜像路径，保留 CUE 引用文件名。
python -m pal_validate prepare \
  --image /your/disc/game.cue \
  --provenance-note '自己持有的光盘转储；填写台湾/日版、原版/补丁版' \
  --out build/input-001

# 准许运行经审查上游后，完整执行信息/目录/提取。
python -m pal_validate prepare \
  --image /your/disc/game.cue \
  --toolchain ../toolchain/src/saturn-recomp \
  --run-upstream \
  --provenance-note '填写真实来源和版本' \
  --out build/disc-001
```

每次使用新的输出目录，且不能放在镜像目录内。输入以读取方式访问；前后 SHA-256 对比用于发现变动，不是内核级只读沙箱。不要在运行期间修改或替换镜像。这个工具不会联网、上传镜像、下载 ROM 或启动游戏。

## 输入与输出

- 首选完整 CUE + 所有 BIN/音轨文件。CUE `FILE` 需为 `BINARY`、相对 POSIX 路径；子目录可以使用，但不允许 `..`、绝对路径和逃逸符号链接。
- 也可检查单独 `.bin` / `.iso`，但这不能证明音轨、pregap 与完整光盘布局没有丢失。
- CHD 不直接交给该解析器。先保留原 CHD 的哈希，再单独核验转换工具/命令及转换后布局；本轮尚未运行转换。
- 本固定版本上游未解释显式 `PREGAP` / `POSTGAP`。本工具拒绝这类 CUE，避免静默丢失语义；不要只删除行来“修复”。
- 输出含 `report.json`、逐命令 stdout/stderr、`disc_structure.json`、提取文件和 `extracted_inventory.json`。
- 装载地址只引用实盘 IP.BIN 声明；入口地址保留 `null`。`.BIN` 扩展名、文件提取成功及 `--find-base` 候选都不是 SH-2 模块/入口证明。
- 退出码：`0` 当前准备步骤成功；`2` 缺输入/输入不符合约束；`3` 上游、工具链验证或输入一致性失败。`0` 不代表后续 game boot / walking / OHOS 已通过。

上游固定为 [`086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`](https://github.com/callumjenkins/saturn-recomp/commit/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5)。包装层先检查提交、工作树及已核验的 `disc.py` 哈希，再复用上游解析器检查目录/轨道，最后按已核实 CLI 执行 `--info`、`--list`、`--extract`。升级上游时必须重新审查接口和更新 pin，不能仅改哈希绕过检查。

## 走路测量

```bash
python -m pal_validate walking \
  --csv examples/walking.synthetic.csv \
  --input-kind synthetic \
  --out build/walking-demo-001.json
```

示例完全合成，只证明计算逻辑。输出按游戏逻辑 tick 统计世界位移、镜头位移及动画变化，呈现次数单独记录。没有有效世界坐标时显示 `unavailable`，不会把屏幕像素当作世界坐标。真实采集要求见 [走路基线协议](docs/WALKING_BASELINE.md)。

## 交付结构

- `pal_validate/`：只读输入核验、上游 CLI 包装和 CSV 指标
- `tests/`：26 项自有回归测试，不需要商业镜像或执行上游
- `examples/`：合成 CSV、空模块证据模板
- `evidence/`：本轮实际运行结果；任何 `synthetic` 均不计入游戏可玩证据
- `docs/`：Linux 证据解释、真盘门槛、走路采集协议

下一步最小输入：合法持有的完整 CUE/BIN（或原始 CHD 供单独核验转换）以及台湾/日版、是否补丁版。缓存敏感的对白路径也必须纳入真盘回归，不能只看帧率或一次启动。
