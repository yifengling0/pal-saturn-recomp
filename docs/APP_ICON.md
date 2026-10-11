# 应用图标接入

使用用户批准的青玉底、金色土星环与仙剑生成图。未使用原盘图像素材；批准原图保留。

## Harmony

保持工程既有资源描述：AppScope/app.json5 的 app.icon 和 EntryAbility.icon 均引用 layered_image，两套同名媒体分别替换 foreground.png/background.png。JSON、包名和签名设置不改。EntryAbility.startWindowIcon 仍引用 startIcon，单独使用批准原图的 1024 全不透明版本。

1024 分层前景的非零 alpha 最大中心半径约483.614px，圆形mask剩余约5.5%半径；它没有预裁圆角。背景全不透明。工程 layered JSON 只有前景/背景引用，没有额外缩放。官方 ArkUI 非288资源分支按整画布适配，不能期待系统自动放大内部主体；旧过度留白的radius320导出已弃用。

参考：[OpenHarmony drawable_descriptor.cpp](https://github.com/openharmony/arkui_ace_engine/blob/master/interfaces/inner_api/drawable_descriptor/drawable_descriptor.cpp) 的 BlendForeground/CompositeIconAdaptive 路径。实际Launcher蒙版、桌面显示比例和启动窗口仍须真机核对，合成预览不是设备截图。

## Windows

用户图标包含16、24、32、48、64、128、256七档。游戏层CMake在WIN32才启用RC并把 app_icon/pal_app.rc 挂到实际程序target；OHOS/Linux不会调用Windows资源编译器。默认资源ID1，保留既有游戏兼容源。所核SDL Windows后端在没有显式icon hint时枚举首个RT_GROUP_ICON，故此资源同时是Explorer和默认窗口图标的来源；没有本轮Windows原生窗口验收。

本地GNU windres2.44交叉编译及带空格路径CMake小夹具通过，输出确实PE32+ x86-64。解析PE资源得到七个RT_ICON和一个RT_GROUP_ICON，所有图像payload与批准ICO逐字节一致。此夹具不是游戏exe，也不代替Windows运行测试。

正常重新构建后检查实际安装包/主程序；已有Release附件不会被本次源码更新替换。系统可能缓存旧图标，不要为了强制刷新而未经备份卸载游戏或删除应用数据。
