# 实际进度（2026-10-10 UTC）

## 已完成

- 固定主路线：`callumjenkins/saturn-recomp`，提交 `086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`。
- 只读核验上游 `disc.py` 接口：`python -m saturnrecomp.disc IMAGE --info` / `--list` / `--extract DIR`。
- 完成此目录的 Python 标准库包装层、独立构建目录、输入前后 SHA-256、来源备注、路径检查和分阶段 JSON 报告。
- 完成 26 项自有测试，26/26 通过；包含缺输入、缺轨、路径/符号链接逃逸、目录复用、输入变动、不能以 BIN 扩展名证明 SH-2、走路指标与呈现频率独立等测试。
- 实跑缺盘命令：退出 2，报告明确 `input_inventory: blocked`。
- 实跑自写合成光盘的“只读文件盘点”：退出 0，输入哈希未变；未执行上游解析、提取或游戏。
- 实跑合成 walking CSV：得到每逻辑 tick 世界位移 2、自定义坐标单位的演示结果。这个数字只属于示例，不属于《仙剑》。

## 待完成或阻塞

- **上游代码执行尚待授权/实跑结果。** 上游源码、环境和自主夹具准备由并行验证任务负责；不得将准备好误写成构建/测试通过。
- **真实游戏 P0：缺输入。** 用户文件元数据与官方资源渠道核验未找到本轮可用的真实 Saturn《仙剑》镜像。需要合法 CUE 和全部轨道，或现有 CHD 待独立核验转换；需要台湾/日版及补丁情况。
- SH-2 模块/入口、游戏 `game.toml`、Linux 真游戏构建与启动、地图/输入、真实走路基线与修复、原生 OHOS：均未验证。

## 证据位置

- [wrapper-tests.log](evidence/wrapper-tests.log)：此工程自有测试，不是上游测试。
- [missing-input.report.json](evidence/missing-input.report.json)：缺盘负向路径。
- [synthetic-inventory.report.json](evidence/synthetic-inventory.report.json)：自写夹具只读盘点，所有游戏成功声明均 false。
- [walking-synthetic.report.json](evidence/walking-synthetic.report.json)：合成指标演示，不代表原版速度。
- [Linux 验证报告](docs/LINUX_VALIDATION_REPORT.md)：证据层级、风险、缺输入和下一步。

## 更新规则

只有拿到准确命令、环境、退出码及日志，才能把该步骤从 `pending/not_run` 改成 `passed/failed`。合成和上游自测结果只能更新 G0，不能更新真盘 G1～G5。以后真实镜像进入时创建新 run，不覆盖本轮报告。
