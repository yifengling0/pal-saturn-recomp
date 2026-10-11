# Windows 本地验证：输入与施法选项

这份步骤面向现有 Windows / MinGW-w64 `g++` 环境。Windows 实机运行、声卡和
该机器的编译器/SDL3 DLL 尚未在本轮云端验证；Linux 的编译、回放和 mock 测试
不代替 Windows 通过。请保留旧可用构建和存档，用独立目录测试。

## 包含什么

- 上游固定 `086c372c67d9e0f94fcc64cedd6e6b63cc5542b5`，顺序应用 `0001` 至
  `0005`。其中 `0005` 修正 SH-2 burst DMA 短拷贝；旧版黑背景由此恢复。
- `--pal-options` 将精准输入 v4 和快速施法 v3 同时编入独立 executable。
  **两项运行行为默认关闭**，环境变量缺省/`0` 使用原时序。
- `PAL_RESPONSIVE_INPUT=1`：短按意图一次消费，按住重复受控，转身和踏步合并。
  保留原碰撞检查。菜单/场景/战斗边界有限定回归；不声称物理键盘到屏幕
  延迟已完全消除。
- `PAL_SHORT_EFFECT_PREP=1`：只缩短已识别的 bank7 施法准备等待，保留已测特效帧
  与帧间隔。治疗、御剑术和气剑指各有有限闭环；减少战斗 tick/RNG 机会，
  **随机轨迹可能不同**，不是逐状态等价修复。
- `PAL_RESPONSIVE_ALIGN` / `PAL_RESPONSIVE_WAKE` 默认 `0`。二者为额外实验时序
  改动，会增加 NPC/脚本/RNG 执行机会，不是推荐的精准输入基本档。
- 已弃用的仅切 VDP1 buffer 早显原型不在此构建中。

## 一次搭建（PowerShell，从仓库根目录）

需要 Git、Python 3.11+、C++20 MinGW-w64 g++，以及与编译器匹配的 SDL3 开发包。
沿用你已工作的编译器和 SDL3；不要把不同架构或不同工具链的 DLL 混在一起。
这里仍沿用项目历史 MinGW 静态 C++ runtime 链接方式，不宣称支持 MSVC 参数。

```powershell
py -3 -m venv build\venv-windows
$py = (Resolve-Path build\venv-windows\Scripts\python.exe).Path
& $py -m pip install -r tools\requirements-linux.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
# 此锁文件中的 Python 构建工具跨平台；名称保留以兼容旧流程。

git -c core.autocrlf=false clone https://github.com/callumjenkins/saturn-recomp third_party/saturn-recomp
git -C third_party/saturn-recomp checkout 086c372c67d9e0f94fcc64cedd6e6b63cc5542b5
& $py tools\prepare_linux_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime provenance check failed; preserve existing files' }
# 上一脚本虽保留 Linux 名称，但为平台无关 Python；严格保留 clean parser checkout。
& $py -m pip install --no-build-isolation -e third_party\saturn-recomp-pal
```

已有正确 checkout 不要重新 clone。准备脚本遇到修改过的 checkout/补丁清单会
拒绝覆盖，先保留你的修改；不要删 marker 或伪造 pin 来绕过校验。

镜像只使用你自己提供的台湾版 T-37401H V1.000 JT，13-track CUE 与所有引用文件
必须完整。沿用已验证的 `build/disc-extract/0`、`PROG.BIN`、`TRUE.BIN` 即可。
首次提取走 `validation` 的正常 `pal_validate prepare --image ... --toolchain
../third_party/saturn-recomp --run-upstream --out ../build/input-windows-001`，先核
report 的产品/version/hash，再把这三个模块复制到 `build/disc-extract`。
不要把模块、BIN/CUE、生成的游戏 C++ 或存档上传 GitHub。

```powershell
$env:CXX = 'g++'
$sdl = 'C:\实际SDL3开发包\lib\cmake\SDL3' # 必须直接含 SDL3Config.cmake
& $py tools\winbuild.py check --pal-options --sdl-dir $sdl
if ($LASTEXITCODE -ne 0) { throw 'Build prerequisites failed' }
& $py tools\winbuild.py build --pal-options --sdl-dir $sdl --recompile --jobs 2
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
& $py -m pytest tools\tests -q
```

输出为 `build/windows-pal-options/recomp-build/saturn.exe`，并生成相邻
`pal-options-build.json`。后者记录 executable SHA256 与实际编入能力，启动器
会核对，不能拿旧 exe 配新 manifest。SDL3.dll 应来自同一开发包并放到 exe 旁。
缺 SDL3 会明确失败；`--headless` 只用于无窗口测试，不是用户画面/声音验收。
`--build-dir` 只允许仓库 build 下的新专用目录或本工具拥有的目录，避免覆盖旧
实验。更换编译器时选新的 build-dir，避免复用不兼容 CMake cache。

## 先基线，再分别开启

下面四次请用相同镜像、相同存档副本、相同短路线；每次用新输出目录。
首次启动可以用 `--save -`，不会改写个人存档。测试已有进度时先复制 `.bup`，
把副本路径传给 `--save`，不要直接使用唯一的原存档。

```powershell
$exe = (Resolve-Path build\windows-pal-options\recomp-build\saturn.exe).Path
$cue = 'C:\你的镜像\pal_t37401h_13tr.cue'
& $py tools\run_pal_profile.py original --exe $exe -- --cue $cue --save - --settings - --out build\win-original
& $py tools\run_pal_profile.py precise --exe $exe -- --cue $cue --save - --settings - --out build\win-precise
& $py tools\run_pal_profile.py original --quick-spell --exe $exe -- --cue $cue --save - --settings - --out build\win-quick-spell
& $py tools\run_pal_profile.py precise --quick-spell --exe $exe -- --cue $cue --save - --settings - --out build\win-combined
```

启动器会显式设置全部输入/施法档位，避免继承上一轮 shell 残留。先测单项再测
合开，才能区分收益和问题。观察短按一步、松开停止、迅速换向、菜单游标、
对话和切场后是否残留方向；战斗观察首次特效、完整动作、伤害、MP、回菜单。
连续行走速度和全局 VBlank/CPU 时钟没有整体降速。

## Windows 音频/卡顿日志

先按系统默认声卡跑原版 profile，不先指定 dummy。保留 exe 与 SDL3.dll 的
SHA256、编译器版本、SDL3版本、启动命令和问题发生位置。

```powershell
Get-FileHash $exe -Algorithm SHA256
Get-FileHash (Join-Path (Split-Path $exe) 'SDL3.dll') -Algorithm SHA256
& g++ --version
& $py tools\run_pal_profile.py original --exe $exe -- --cue $cue --save - --settings - --vblanks 9000 --out build\win-audio-default --log build\win-audio-default.log --wav build\win-audio-default.wav --record-input build\win-audio-default-input.txt 2>&1 | Tee-Object build\win-audio-default-console.txt
```

9000VB 约150秒，机器性能不足时实耗时更长。若卡住，记下音频是循环、断续还是
完全无声，保留最后几十行，尤其 SDL audio、STALL/FATAL 和 audio stream 统计。
WAV 是模拟声源输出，不证明系统声卡能正常播放，也不能单凭其有声音排除主机
音频调用阻塞。日志/WAV 留本地，不自动上传。

必要时另做单进程 dummy 对照，其他参数不变，换输出目录：

```powershell
$env:SDL_AUDIODRIVER = 'dummy'
# 重跑上面的 original 命令，所有 win-audio-default 名称改为 win-audio-dummy
Remove-Item Env:SDL_AUDIODRIVER
```

这只绕过真实音频设备；游戏 SCSP/CPU/时钟仍执行。不要把系统静音/音量0当作
禁用音频路径，也不要把 dummy 成功当作真实声卡通过。若报驱动不支持，保留
该错误，不算有效对照。本轮云桌面无可用物理声卡，Windows 原声卡问题仍待你
的本机结果定位。

## 本轮已经运行的接入检查

2026-10-11 云端 Linux：共用注入器对真实 PAL 生成源与既有 v4/v3 修改逐字等价
（局部 include 路径除外）；CRLF、路径含空格/非ASCII、重复注入幂等、错误锚点
拒绝、目录覆盖保护及 exe manifest 均有单测。

新组合构建成功后：默认档首战12/12图与最终BUP等原版；精准档94/94图及BUP等
既有v4；快速施法档44/44图及BUP等既有v3群攻闭环。最初精准档测试器把停止帧
设为3424但参考含3530，导致缺图失败；保留该失败，修正停止帧到3531后94图
全部匹配，没有更改游戏代码来迎合测试。

此外，实际执行新的 winbuild.py 完整生成/注入/CMake/静态链接链路在 Linux
成功（2283函数/209370指令）；重复 build 仅增量链接检查，不误报陈旧；SHA
能力manifest核验后的Python启动器冒烟通过。这仍不是Windows本机编译/音频
通过。证据位于私有build/windows-options-audit和cross-platform-options-001；
这些包含游戏生成物的目录不提交。
