# Saturn《仙剑》Linux 重编译可行性：本轮证据报告

时间：2026-10-10 UTC。目标：以 Linux 为实际验证平台，准备可继续推进的真盘输入与测量链路；原生 HarmonyOS 为后续目标。这里的 PAL 是游戏简称。

## 结论

当前已经交付并实测的是“真盘准备与证据工具”，**尚未证明《仙剑》在 Linux 启动，更没有验证走路修复**。这不是一份假定游戏地址的空 `game.toml`：输入一旦到位，可以按固定、可审计步骤读取盘信息、目录和提取结果；未知项持续标为 unknown。

截至本报告，公开上游执行仍待授权，未运行；此目录的 26 个自有测试已经通过。即使随后上游合成测试全部通过，也只能证明工具链的一部分，仍不能代替游戏验证。

## 实际运行了什么

1. `python -m unittest discover -s tests -v`：26/26 通过。覆盖输入缺失、缺轨、CUE 相对路径范围、绝对/Windows/遍历/逃逸符号链接拒绝、空轨拒绝、显式 pregap 保留问题、只盘点模式不调用上游、目录不可复用、哈希一致性、BIN 不是已证实模块、逻辑 tick/地图边界与 FPS 独立性。
2. 无 `--image` 的 `prepare`：退出 2，写出机器可读缺输入报告。此失败是预期的负向测试。
3. 自写合成光盘 `prepare`（没有 `--run-upstream`）：退出 0，仅对 CUE/ISO 文件进行只读枚举、来源标记、SHA-256 和前后复核。
4. 自写合成 walking CSV：退出 0，产生世界/镜头/动画的每逻辑 tick 指标；样本有意与呈现次数解耦。示例中的世界步长 2、镜头步长 1 都是人工构造值。

完整日志在工程的 `evidence/`；正式链接见 [PROGRESS](../PROGRESS.md)。没有真实游戏画面、ROM、BIOS、已确认入口或真实角色坐标的证据。

## 上游版本和接口核验

主路线固定为 [`callumjenkins/saturn-recomp@086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`](https://github.com/callumjenkins/saturn-recomp/commit/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5)。[生成器源码](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/src/saturnrecomp/recomp/__main__.py) 可输出 SH-2 模块的 C++ 与构建工程；这提供了真实静态重编译验证路径。

[上游 disc.py](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/src/saturnrecomp/disc.py) 已按源码核验。文件 SHA-256：`3a63f6c444677e5fb44f172de8331b6697def3c17c0f2be13ba5e973de220b6e`。

包装层复用该解析器做轨道/IP.BIN/ISO 读取，不重新实现 Saturn 光盘格式。CUE 路径安全检查只负责禁止意外读取目录外的轨道。ISO 目录先校验目标路径、目录循环与覆盖冲突，然后执行已知 CLI；结果和 stderr 各自留档。

源码中显式 `PREGAP/POSTGAP` 没有对应解析分支，因此当前包装层直接报出限制，不能为通过测试而悄悄删除这些行。单独 BIN/ISO 的完整多轨信息也保留为未知。

上游 [官方检查脚本](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/tools/check.sh) 与 [CI](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/.github/workflows/check.yml) 提供不依赖商业游戏的检查入口；工具链准备包只包含自主夹具、脚本、版本和准备日志，`approval-status.txt` 明记 PENDING；没有实际构建通过结果。后续是否通过须另看实跑日志。本报告不会将上游 README 中其他游戏的成绩当成本轮成果。

## 真实镜像门槛

本轮审计搜索了用户上传文件元数据和官方渠道，没有找到可核实为 Saturn《仙剑》的可用镜像，也没有找到经确认授权的官方 Saturn 完整版/试玩下载。这个结论不表示用户没有光盘；未知名称的历史压缩包未全部解开检查。

需要的最小输入：

- 合法持有的 CUE + 所有引用轨道，保留文件名；或原 CHD 及来源，后续单独核验转换。
- 台湾/日版、原版/汉化或其他补丁、转储方式。
- 如要定位具体走路现象，补充场景、按键、录屏/存档有帮助，但不能取代原版可复现基线。

[Mednafen 官方 Saturn 文档](https://mednafen.github.io/documentation/ss.html) 列出的版本线索为台湾 `Xian Jian Qi Xia Zhuan` / `T-37401H`，日本 `Senken Kigyouden` / `T-37401G`。**它们是参考资料，不是本次从实盘读出的产品号、文件路径或校验值。** 两个版本应独立建模，不能共用猜测的地址。

## 缓存与自修改代码风险

Mednafen 官方资料将上述两个版本列为需要完整 SH-2 cache 模拟来修复对白截断。对固定上游源码的只读检查显示：缓存/直通 WRAM 最终落到同一 RAM、cache 地址数组和 purge 不具完整语义、CCR 主要存储写入值；这不等于完整缓存一致性模型。源码证据见 [core.cpp](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/runtime/src/core/core.cpp)、[mmio.cpp](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/runtime/src/machine/mmio.cpp) 和 [onchip.cpp](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/runtime/src/machine/onchip.cpp)。

据此推论：真盘阶段必须关注代码/数据可见性、overlay 与运行时指令修改。上游 [learn.py](https://github.com/callumjenkins/saturn-recomp/blob/086c372c67d9e0f94fcc64cedd6e6b63cc5542b5/src/saturnrecomp/learn.py) 通过未知入口学习种子，不能等同于完整 SMC 动态重翻译。需要记录真实执行区写入、缓存访问和控制流后才选择处理方式。

目前既未证明这个版本具体发生哪条 SMC 路径，也未证明上述风险造成走路异常。连续对白、切图、存读档应和方向输入一同纳入真盘回归。

## 走路验证和后续平台

[采集协议](WALKING_BASELINE.md) 将游戏逻辑 tick、世界坐标、动画、相机和宿主呈现次数分开。不同运行器的 BIOS/光盘加载时间会导致 VBlank 不对齐，因此用已证实逻辑计数器和场景状态作行为对照。平均 FPS 上升不能证明步速、动画或碰撞正确。

推进顺序：真实盘身份与 SH-2 入口 → Linux 编译/boot/标题与对白 → 可操作地图和输入回放 → 走路基线及有据修复 → 原生 HarmonyOS。

[SDL3 官方 HarmonyOS 说明](https://wiki.libsdl.org/SDL3/README-harmonyos) 提供原生集成路线，但现有 Recomp 工程的 Android 特判不自动构成 OHOS 支持。共享库/HAP、生命周期、输入、音频、文件授权和真机行为需要独立适配；本轮不宣称 HarmonyOS 已可运行。

## 可审计的下一步

在授权执行上游后，记录 Linux G0 的测试/构建结果；用户提供真实镜像后运行 README 中的完整准备命令。若缺任一前提，保持对应 Gate blocked，不为了推进文档而制造成功状态。所有媒体和提取内容留在本地，游戏存档使用专用测试路径；发布和分发另行授权。
