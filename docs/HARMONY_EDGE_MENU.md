# UI13：可关闭的侧滑菜单入口

除了可见的菜单键，新增从左右侧空白区域向内滑动并松手打开暂停设置的补充入口。它不取代菜单键，也不进入启动 launcher。

## 使用

- Harmony 默认开启；桌面默认关闭。已有明确的 `[touch] edge_menu = true/false` 保留。
- 设置中“侧滑菜单 / Edge swipe”可开关；菜单标题应显示 **UI13**。
- 一根手指从画面左右侧缘没有虚拟按键的区域开始，快速向内水平滑动后松手。仅在松手时打开设置，避免这根手指误点刚出现的菜单。
- 从十字键、按钮、肩键、START 或菜单键的命中区域起滑，不触发这个入口。正在使用其他手指、短点、过慢/明显竖向或反向滑动也不作为菜单手势。
- 关闭全部虚拟按键时，可见菜单入口依然保留；侧滑不是恢复设置的唯一方法。

应用只有收到平台分发的触摸事件才能识别；不能保证被系统导航手势接管的最外缘仍可用。手机/平板实际安全区和系统边缘事件需本地复测。

## 输入安全

取消的原始侧滑触点尾部不会补发成游戏按键。后续新的手指可以正常操作游戏或 Resume，不需要把所有手指抬起才恢复。独立审阅发现过“取消后的手势吞掉后续触点”的候选错误，已修复且保留红→绿复现；该错误没有发布。

失焦、切后台、旋转、输出尺寸或密度变化会取消识别。菜单暂停/恢复、物理按键 held-release、音频生命周期沿既有路径，不额外推进游戏时钟。位置编辑、旧布局确认和保存失败回滚保持 UI12 行为。

## 更新与身份

本批新增0013补丁。与 UI12 更新步骤相同：保留旧 patched checkout 和本地修改，重新 setup、生成和编译，再打包安装 HAP。首次不能只拿旧 runtime 使用 `--skip-learn`。

```powershell
$PY = '.\build\venv\Scripts\python.exe'
# 先备份旧 third_party\saturn-recomp-pal 到未占用的新目录，不覆盖已有备份。
& $PY tools/prepare_linux_runtime.py
& $PY -m pip install -e third_party/saturn-recomp-pal
& $PY tools/winbuild.py build --recompile
& $PY tools/ohosbuild.py --skip-learn --build-mode release --launch
```

新版本菜单显示UI13，host启动日志包含 edge-swipe-v1。本批工具仅接受对应UI13的完整OHOS源身份；旧commit及其配套工具未改，仍可按旧版本自行构建。不要混用新工具和旧生成runtime，也不要改哈希绕过检查。

## 验证范围

最终候选纯手势529项、双平台实际host各219项、portable布局/字体92,246项软件断言通过；独立审阅另复跑28项恢复检查。补丁应用、111字字体重现逐字节一致。Linux真实程序重新编译后，片头和加载/F-R回放12张PNG与UI12一致，测试BUP不变。

这些是Linux/SDL及受控事件测试，没有本批OHOS SDK/HAP或真机系统边缘事件、音频硬件验收。建议本地依次核：正常Dpad多指、空白边缘滑入、超时取消后新指A/菜单、后台恢复、旋转、开关持久化。若系统边缘不分发事件，继续使用可见菜单键。

整合回归另通过160项普通/增强身份与变体测试、50次真实C++/SDL语法检查、78项键位单测和61项OHOS身份/CMake/共享库夹具。完整UI12可由它自己的旧工具构建；本批UI13工具会拒绝自洽旧UI12和伪改manifest的新旧混合体。

本次Linux原生程序SHA256：cab84213f92efe8562f0f2c6e328ffc2bcc909272e8801b0e703e7b1f489e4c0。
正式普通PC98 host的normalized_lf_sha256：b1ec42e25e59279b196d8105df85c4b335760ebc902cbe903396e3fca01dcca5。运行日志source_bytes_sha256仍按实际输入原字节记录，Windows CRLF口径与LF标准化值可能不同。
