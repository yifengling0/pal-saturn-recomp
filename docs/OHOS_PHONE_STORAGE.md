# 鸿蒙手机横屏与镜像目录修复（2026-10-12）

此说明对应 `v0.1.0-preview.2` 之后的源码修复，旧发行 HAP 不包含这些改动。

## 玩家操作

1. 启动应用后，手机主窗口使用双向横屏；系统旋转锁不限制左右横屏切换。平板、PC/2in1 的原有窗口策略不变。系统分屏/窗口限制可能仍使横屏请求失败，页面会给出提示。
2. 应用先检查自己的 `Download/com.palhero.palsaturn/`。尚未找到可用镜像且目录缺失或不可用时，调用系统 `DocumentViewPicker` 的 `DOWNLOAD` 模式，请系统建立应用专用目录，再逐级建立 `disc/` 并测试列举、实际写入/清理能力。不会扫描其他应用目录或创建公共 Download 根。
3. 在 `Download/com.palhero.palsaturn/disc/` 放入自己有权使用的完整 CUE + BIN，点“重新扫描”。有 CUE 时会检查它引用的 BIN 均存在且可读；不完整 CUE 不会被旁边的裸 BIN 掩盖。
4. 若系统能力不可用、授权失效或路径不可写，准备页面会保留重试按钮与“导入 CUE + BIN”。在系统文件选择器里同时选择一份 CUE 和它引用的全部 BIN。导入要求引用为同目录文件名，大小写一致；不支持 CUE 中的子目录或 `..` 路径。CUE 使用原生加载器支持的大写 FILE/TRACK/INDEX，FILE 文件名须加双引号，每轨须有 INDEX 01。最多选择 32 个文件。
5. 导入通过选中的 URI 打开原文件，复制到应用沙盒的新目录。复制或检查失败不会替换原镜像、原存档或上次成功的启动选择。请预留一份完整镜像的空间。应用内导入文件随卸载删除。

系统 `DOWNLOAD` 模式的标准行为是直接返回应用目录并赋予持久访问，不一定弹出文件选择界面。API/设备实现差异、目录被删除、授权撤销等仍可能失败，因此这里不承诺所有手机均可访问 Download。没有宽泛文件权限的导入流程仍只访问用户在系统 picker 中明确选择的文件。

## 存档与升级兼容

- 保留旧启动顺序：应用 Download 根 → 应用级 `files/<bundle>/` → 应用级 `files/`，每个根先 `disc/` 再本层；必须有可解析的 CUE 轨道表，单独 BIN 不会启动。
- 延续已记录的存档根，记录独立于旧镜像是否仍存在；重新导入镜像也继续使用原存档。旧版本曾回退到应用 `files/saves/` 的存档不会因 Download 恢复可写而被新空存档遮蔽。
- 没有启动记录的旧安装会检查 Download、旧包名沙盒和应用 files 的存档。只有唯一现有档且其余位置可明确检查时自动选择；有多份存档、其他目录无法检查，或原档已删除但发现另一位置的备份时，页面要求明确选要继续的存档，不猜哪份更新。
- 已记录的存档位置若权限撤销，导入会在复制镜像前停止，要求恢复访问。没有记录且有目录无法检查时，不会自动开始新档；必须明确点击“确认全新开始”才能使用页面标明的位置，其他旧档不删除、不覆盖。
- 对已有存档的目录，如果现在不能写，阻止启动并要求恢复访问，不自动迁移或覆盖它。
- ArkTS 使用 `context.getApplicationContext().filesDir`，与原生 `OH_AbilityRuntime_ApplicationContextGetFilesDir` 对齐。不能用模块级 `UIAbilityContext.filesDir`，两者路径不同。
- 准备完成后，在应用私有目录原子写入具体盘路径与存档根，然后才创建 XComponent。原生只读取这一份选择，不会再请求 PC/平板下载权限、扫描公共根或悄悄更换存档目录。
- 不改游戏、战斗、音频和存档格式。导入不复制或导出存档；已有 Download 存档仍由原路径保管。

## 横屏生命周期

SDL 当前 OHOS 后端没有执行横屏设置，而且初始化会替换 Ability 的生命周期方法。因此手机横屏策略由页面绑定实际主窗口，在初次显示、重新显示/激活、页面恢复时请求 `AUTO_ROTATION_LANDSCAPE`；窗口失效后允许重新获取，页面销毁时解除监听。非手机不调用这些设置。XComponent 一旦启动不会因目录状态或前后台切换被重建。

## 对照与 API 依据

对照了 VintagePomeloPro 的 `AppCatalogService.provisionGamesDirectory` 与 `WineEnvService.acquireZHome`：真实逻辑使用 `DocumentViewPicker.save` 的 `DOWNLOAD` 模式，再通过 `FileUri.path` 获得应用目录并创建子目录。本修复独立实现标准 API 流程，没有移植 VPP 的项目服务或授权组件。

- [系统 DOWNLOAD 模式：创建应用目录与持久访问](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/file-management/save-user-file.md#download模式保存文件)
- [Huawei 文件 picker API](https://developer.huawei.com/consumer/en/doc/harmonyos-references/js-apis-file-picker)：DOWNLOAD 为 API 12 起能力，支持 Phone；项目最低 API 16。
- [下载目录宽泛权限的设备限制](https://github.com/openharmony/docs/blob/master/en/application-dev/security/AccessToken/permissions-for-all-user.md#ohospermissionread_write_download_directory)：Phone 不在支持设备内，所以移除该权限依赖。
- [应用级与模块级沙盒路径区别](https://github.com/openharmony/docs/blob/master/en/application-dev/application-models/application-context-stage.md#obtaining-application-file-paths)
- [窗口方向 API](https://developer.huawei.com/consumer/en/doc/harmonyos-references/js-apis-window)：使用不受旋转锁限制的双向横屏；API 18 起核对 TYPE_MAIN，API 16–17 在页面初次显示时取得并保留窗口。

## 构建与验证

回归入口：

```sh
python -m unittest tools.tests.test_ohos_phone tools.tests.test_ohosbuild
python -m unittest discover -s tools/tests
```

新增测试执行实际服务逻辑的文件系统适配版本（Node 22.13+ 的 TypeScript 去类型工具），覆盖目录缺失、重复准备、取消、系统拒绝/不支持、错误 URI、旧沙盒路径、保存根沿用、缺 BIN、大小写/路径穿越、导入失败清理和重复窗口生命周期。另有真实宿主 C++ 解析器测试。它们不是鸿蒙文件提供器或真机替代品。

HAP 使用官方 CLI 26.0.0.851 / Hvigor 6.26.8 / SDK 26，保持最低 API 16、ARM64+x86_64、未签名 debug。Hvigor 直接调用 Ninja，若需要限制总并发为 2，本项目双 ABI 可使用 `CMAKE_BUILD_PARALLEL_LEVEL=1`，每 ABI 一个编译任务；CMake 显式建立编译池以使该限制生效。`--selftest on|off` 同步 native 与页面开关，生产包须为 off。

本次没有连接、安装或运行鸿蒙真机。安装、旋转锁下双向横屏、返回前台、首次目录建立、删除目录后恢复、picker 的设备具体表现、复制真实大镜像及原存档继续读写，仍需在签名后的手机/平板/PC 上验收。不能把交叉编译、模拟文件系统回归或旧平板记录称作本次手机通过。

本次云端最终结果：完整 `tools/tests` 为 **365 passed，201 subtests passed**；新增服务适配测试含 39 个存储场景、8 个窗口方向场景，C++ 交接解析器含 8 个输入案例。真实 ArkTS 编译、双 ABI 原生链接、HAP ZIP CRC 与包内 `selftest=off` 检查通过。产物仍为未签名 debug；上述结果不扩大为任何真机验收。
