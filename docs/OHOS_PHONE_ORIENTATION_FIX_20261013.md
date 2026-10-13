# Phone/tablet main-window lifecycle repair (2026-10-13)

## Evidence and limits

The reported phone ran 7.0.0.109 SP6C00E105. Cold launch retained the sensor's
`auto_rotation_restricted`; resuming through `aa start` retained a 1280x2832 main
window. The visible message came from the old acquisition/binding catch, not the
`setPreferredOrientation` catch. The old catch discarded the error, so the
available evidence does **not** distinguish getLastWindow failure, property/type
validation failure, and window-listener registration failure.

At inspection, the private remote branch was still
`6670c6c79d6952508d1026aff631b84d3e131e92`. Its PhoneOrientation blob matched the
local source. `docs/OHOS_PHONE_EVIDENCE_20261013.md` was not available at that ref
(404); this note uses the supplied device observations, not a claimed read of
that missing report.

## Repair

- Register an ApplicationContext `abilityLifecycle` observer before SDL startup.
  SDL's native-injected Ability methods are left untouched. SDL's actual
  `onWindowStageCreate` already obtains the main window and loads Index.
- Obtain the main window from the observed WindowStage's `getMainWindow()`.
  Never use the topmost-window API, which may return a child/picker window.
- Keep the policy alive for the Ability, independently of page show/disappear.
  The page subscribes only to status text. Stage-active and Ability-foreground
  notifications retry even if the initial window listener could not be bound.
- Retry transient acquisition/listener/orientation failures after 250, 750 and
  1500 ms, then wait for the next real lifecycle/page event. No endless polling.
- Remove listeners and timers on destruction. Generation checks prevent an old
  stage's pending Promise from installing a stale main window or resetting the
  new stage's state.
- Log the exact step, error code/message, SDK version, device type, acquired
  window type/dimensions, listener installation, and orientation request result
  under `PAL/ORIENTATION`. A successful API request is not proof of rotation.
- Updated to the user's latest requirement: phone and tablet use one landscape
  policy. The official SDK names the tablet device type `tablet` (not `pad`).
  PC/2in1, TV and unknown devices do not install the runtime observer.
- The launch orientation uses `$string:pal_start_orientation`: `phone` and
  `tablet` resource qualifiers both select `auto_rotation_landscape`, matching
  the runtime request. The base resource retains `auto_rotation_restricted` for
  desktop/other devices, preserving their previous startup behavior.

## API verification

The installed official 26.0.0.851 SDK declares `WindowType.TYPE_MAIN = 32`, since
API 18; the previous enum constant was not shown to be incorrect. `getMainWindow`
is available since API 9 and returns the stage's main window directly, so type
is now diagnostic rather than a guess at window identity.

References:
- https://gitcode.com/openharmony/docs/blob/494dc0d00ad8d84f3d7f016ba53cbc95f598aaa4/en/application-dev/reference/apis-arkui/js-apis-window.md
- SDK `@ohos.window.d.ts`, `@ohos.app.ability.AbilityLifecycleCallback.d.ts`,
  and `application/ApplicationContext.d.ts`.

## One device verification pass still required

Use the newly integrated, signed HAP; do not uninstall or clear storage.
1. Cold-launch on the phone, including with the system rotation lock enabled.
   Save PAL/ORIENTATION logs and the main-window rectangle/orientation.
2. Go Home, physically rotate, and resume via icon and `aa start`. Confirm the
   game fills a landscape window, not a narrow strip in a portrait window.
3. Open/cancel the disc picker and return. Confirm it never becomes the window
   receiving the game orientation policy; no disc/save writes are required.
4. Repeat cold launch and Home/resume on the tablet: expect the same landscape
   request and logs as phone. PC/2in1 must still skip the runtime policy and use
   the original base startup orientation.
5. If still failing, return the `PAL/ORIENTATION` sequence (including error code,
   SDK/type/size) and system main-window dump. Distinguish missing lifecycle
   callbacks, failed acquisition/listener, rejected orientation, and successful
   request with unchanged geometry before choosing another fix.

No phone was accessible in this task. Host regression and ArkTS compilation
results must not be described as a successful real-phone rotation test.

## Local validation

`python tools/tests/test_ohos_phone.py`: 7 tests passed, including executing the
actual service through Node's TypeScript stripping adapter. Scenarios include
startup before stage notification, unrelated Ability, non-TYPE_MAIN diagnostic
value, window events, page unsubscribe, bounded failure retries, foreground
recovery, stale stage/destroy, tablet launch/resume, PC/TV/unknown skips, and synchronous/asynchronous
unregistration failures.

`git diff --check`: passed. Real ArkTS validation is pending the integrated
`assembleHap`: this installed Hvigor CLI did not export a separately invokable
CompileArkTS task, so direct task attempts did not reach the compiler. No
standalone HAP was built for this patch.

### Updated device scope and startup resources

This supersedes the earlier phone-only requirement following the user's explicit
request to apply the same setting on the tablet. Official SDK `DeviceTypes`
declares `TYPE_TABLET = 'tablet'`. The installed module schema accepts an
orientation string resource; device-qualified resources preserve PC behavior.

References:
- https://developer.huawei.com/consumer/cn/doc/best-practices/bpta-landscape-and-portrait-development
- https://gitee.com/openharmony/docs/blob/6c4995a2bb86624aa86bbb350951f13f51dd5f96/zh-cn/application-dev/quick-start/resource-categories-and-access.md
