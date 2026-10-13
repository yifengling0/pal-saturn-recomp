# OHAudio 间歇静音：驱动名称回归（2026-10-13）

## 已确认的代码缺陷

`0010-harmony-audio-and-physical-gamepad.patch` 用大小写敏感的
`strcmp(driver, "ohaudio")` 选择鸿蒙音频策略。实际打包使用的 SDL revision
`930cd0dbf8d1b6fdc5b91711d8d71542c1df0960` 在
`src/audio/ohaudio/SDL_ohaudio.c` 注册的名字是 **`OHAudio`**。
`SDL_audio.c` 的 `SDL_GetCurrentAudioDriver()` 原样返回注册名字；SDL 自己选择驱动时
使用大小写不敏感的比较。仓内 `P4_HARMONYOS.md` §10 的真机日志也记录了
`audio: driver=OHAudio`。

因此，此前的修复虽在小写 mock 测试里通过，真正鸿蒙设备却不会进入这条路径：

- 源队列归零后仍反复插入一整份 4410 帧（100ms）静音。
- 不注册 input-request observer，相关诊断和生命周期观察重置也没有启用。
- 历史上的 4096 帧 / 44100Hz 回调不是本轮测量值，仍须对当前设备重查。

这是确定的代码/测试覆盖错误；它是否解释用户当前设备的全部听感问题，仍需真机复测。

## 最小修复

新增补丁 `0019-ohaudio-driver-identity.patch`，使用 SDL 自身的
`SDL_strcasecmp(driver, "OHAudio")`，并保留空指针检查。只完整匹配该驱动，不匹配
`OHAudio-extra`，其他后端行为不变。

沿用此前已实现的策略：初始预灌 50–100ms、总输入容量 250ms；OHAudio 不再仅凭
input queue empty 插入整份静音。菜单不清空/重新预灌队列，真实 PCM 正常提交。
`PAL_AUDIO_ADAPTIVE_LEAD` 继续默认关闭，不改变游戏速度、VBlank、CDDA、采样率或
设备回调配置。没有启用此前被拒绝的 200ms prime：它加上约93ms的拉取相位可能
撞上250ms总容量而丢真实PCM。单纯加大缓冲不能替代辨明此次分支选择错误。

## 验证

固定上游 `086c372c67d9e0f94fcc64cedd6e6b63cc5542b5` 完整应用补丁到0019，
重复 prepare 身份校验通过。精确重放 raw → precise → paired → keyboard/guard_host
阶段，旧五个 SHA 全部匹配已有 pins；新 SHA 见
`audit/harmony-audio/driver-identity-source-hashes.json`。
HAP 构建只接受新 mapping/accelerated host SHA，拒绝旧0018 host，避免 `--skip-learn`
误打包未修复的生成目录。桌面历史源码 allowlist 仍保留，未知源码未放行。

运行：

```sh
python audit/harmony-audio/run_audio_tests.py \
  --runtime third_party/saturn-recomp-pal/runtime \
  --sdl-prefix /path/to/native/SDL3 --build-dir build/audio-after
```

本轮完整工具回归378测试 / 201子项通过，零跳过。
本轮 UBSan：31 策略断言、36 actual-host 场景 / 510 断言通过。
新增名称矩阵在0018旧host上有12处断言失败，0019后全部通过；测试不会因 observer
为空崩溃来掩盖失败原因。包含：

- `OHAudio`、小写、大写、非鸿蒙、空字符串、空指针和相似前缀。
- 默认自适应关闭；20次4096帧无缺额拉取后源队列为零，不产生恢复静音。
- 五次菜单边界和生命周期信号，无重复预灌；其他后端保留原策略。
- **真实SDL流、无音频设备**：手动取出初始4410帧静音，再提交/拉取20份4096帧
  PCM，81920帧逐样本相同，21次真实stream callback，零short callback、零恢复
  静音、零丢弃/失败；其中穿插五次菜单音频边界。这里的device接口仍是mock，
  不是OHAudio调度/硬件或实际菜单UI测试。
- **真实SDL欠载后恢复**：空拉4096帧返回0；随后提交735帧即能取出735帧，
  未写出的buffer尾部保持哨兵值；再提交4096帧完整逐样本恢复。共记录两次真实
  stream缺额，累计接收86751帧，零额外静音/丢弃/失败。测试主动越过startup
  warmup，确认默认策略没有等待重新灌满阈值，也不会欠载后永久无声。

没有使用或打断正在进行的真实游戏GUI，也没有改动存档。
OHOS HAP 实编由整合版本统一执行；此报告不把上述本机测试当作HAP或真机通过。

## 真机验收仍待做

使用重新生成并实编/签名后的HAP，同一存档分别测试：冷启动稳态3–6分钟、游戏内
菜单五次、宿主设置菜单五次、切后台再回来、音频路由切换。记录听感及实际时长。
退出后保留会话完整日志，至少包含：

- `audio: driver=OHAudio`、设备Hz/quantum、SDL version/revision
- `audio input requests: observer=1 adaptive=0`（callback注册失败时记录错误）
- `initial_zeros` 只初始发生、`recovery_zeros=0`、`dropped_frames/failed_frames`
- `short_calls`、`additional_bytes_est`、`requested_bytes_est`、`max_request_bytes_est`
- `lifecycle_resets`、`pause_errors/resume_errors`、`max_push_gap_us`

empty 可以不为零；它不等于硬件欠载。若仍有卡顿，用缺额占比、真实PCM生产量/
有效播放时间、推送间隔与生命周期对照定位；不能只以empty次数断言音频已修好。
