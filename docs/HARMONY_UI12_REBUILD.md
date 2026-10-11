# 找不到“移动按键”：UI12 更新与构建身份

本批修复两个可独立验证的问题：旧布局配置曾隐藏位置编辑入口；OHOS 构建校验原先允许一套完整、自洽但较旧的 generated runtime。后者意味着“哈希校验通过”不等于正在使用最新触控界面。用户截图中的英文旧双栏既无间距也无重置触控，不能仅用 layout_version=1 解释；未取得其实际命令/已装 HAP 身份前，不认定用户没有更新代码。

## 进入位置编辑

1. 点游戏宿主菜单键，或桌面 F10。
2. 标题应能看到 **UI12**。普通手机/平板布局中，“移动按键 / Move controls”紧接“继续游戏 / Resume”，在第一页；极矮窗口每页仅一行时，点右上“下一页 / Next”进入第二页。
3. 旧 layout_version=1 会先询问是否启用可编辑布局。确认只是预览草稿，按键几何可能变化；大小、透明度、配色、间距和已有位置值保留。拖动后点“完成”才保存版本和位置；取消、返回不会修改旧配置。
4. 如磁盘保存失败，会回滚内存设置、保留编辑草稿并记录失败。可重试或取消，不会假装已保存。

不要删除 settings.ini 来试图找入口。已有自定义菜单位置也可能保留在顶部，不能单凭位置判断版本。UI12 中下一页按钮带文字和页码，左上 X 是关闭/返回，不是上一页。

## 安全重建（Windows / DevEco）

先合并本分支，并保护自己的未提交修改。尤其本地 `docs/P4_HARMONYOS.md` 的 fe29d2e 内容不能被覆盖。本批没有修改该文档。

在仓库根目录 PowerShell：

```powershell
$PY = '.\build\venv\Scripts\python.exe'
# 先检查 third_party\saturn-recomp-pal 内是否有自己的修改。
# 把这个旧 patched 目录改名备份为未占用的新名字，例如 before-0012；
# 不覆盖同名备份，不动干净 parser checkout 或游戏资源/存档。
& $PY tools/prepare_linux_runtime.py
& $PY -m pip install -e third_party/saturn-recomp-pal
& $PY tools/winbuild.py build --recompile
& $PY tools/ohosbuild.py --skip-learn --build-mode release --launch
```

第一次升级必须重新生成。之后只有本轮已经生成、通过完整校验的 runtime 才能使用 `--skip-learn`。若已启用原有 PAL 增强选项，沿原先配置重新生成，不要手工复制 host.cpp 或修改白名单。

出现 stale native CMake cache 报错时，按错误提供的选中路径检查 DevEco 的构建缓存；保留源码和原有参数后重新配置本项目。不要把其它目录的 runtime 塞进 SATURN_RUNTIME。API21 GameControllerKit 编译 SDK 条件仍与前批一致。

## 识别实际运行包

- 构建阶段：OHOS 专用校验要求批准的 UI12 host 源及完整 helper/字体组合。旧0010、旧0011及仅贴新版本常量的旧代码均应拒绝。
- CMake：核实际 `saturn_host` 目标拥有的 host.cpp 路径，打印 source_bytes_sha256。
- 运行阶段：实际 host object 提供强符号，OHOS entry 读取并打印 UI12 与 source_bytes_sha256；shared library 显式拒绝未解析符号，防旧 host 被错误链接。
- Python 的 normalized_lf_sha256 用于跨平台源码身份；CMake/运行日志的 source_bytes_sha256 是编译输入原字节。Windows CRLF 可使这两种哈希不同，必须按同一种口径比对。
- 菜单标题 UI12 是低成本可见标识。若仍是旧菜单，请保存实际命令、上述构建/启动行和截图，再查安装目标；不要盲删存档或设置。

Linux 的 C++/SDL 受控测试、真实游戏回放与 CMake/shared-library 链接夹具不等于 OHOS SDK/HAP 或设备验收。本批没有宣称已在用户设备验证。

## 本批验证记录

- 实际 C++/SDL 触控、保存/取消、旧配置转换与文字布局：91,191 个 portable 断言通过；另 host()/settings() 中间变换的 PC98/F10 专项 12,167 个断言通过，未把它冒充最终 guarded 层测试。
- 完整普通/增强 planner：140 项精确身份、幂等、混装、篡改等检查通过；50 次真实 SDL3/C++20 语法检查与 78 项键位单测通过。完整旧桌面 variants 保留；OHOS 本轮另行要求 UI12。
- 真实 Linux 增量程序 SHA256：221fe459970bcc7dfee61766e6329d6a9103bf6655e0a38a997ff48dfe7ccc90。无输入片头6700VB五张、棺前加载及 F/R 回放5803VB七张 PNG 与前版逐字节一致，两进程退出0，测试 BUP 不变。
- patch0012 对现存真实 pinned pipeline（0001–0005、0007–0011）先 check 再 apply，全部 raw 文件与冻结候选一致；setup保护相关8项通过。
- shared-library 夹具启用 --no-undefined，旧 host 缺强符号、仅有版本缺源哈希符号均拒链接。新双符号可从真实共享库读取。实际 OHOS SDK 最终链接和设备行为仍待本地复测。

正式普通 PC98 host 源的 LF 标准化 SHA256：a8a0235eea76af85618d9482240cb9582eebf408966c8396b478e5e9de324147。raw d388ef17… 或仅执行 host() 的中间态 388a8b90… 均不是这个正式产物。
