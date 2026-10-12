import { common } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { deviceInfo } from '@kit.BasicServicesKit';

// SDL replaces Ability lifecycle methods. Attach to the real main window,
// retaining it across system pickers, and unregister with the page lifecycle.
export class PhoneOrientation {
  private main: window.Window | undefined = undefined;
  private active: boolean = true;
  private binding: boolean = false;
  private listener = (event: window.WindowEventType): void => {
    if (event === window.WindowEventType.WINDOW_SHOWN || event === window.WindowEventType.WINDOW_ACTIVE) {
      this.apply();
    } else if (event === window.WindowEventType.WINDOW_DESTROYED) {
      this.detach();
    }
  };

  private readonly context: common.UIAbilityContext;
  private readonly report: (message: string) => void;

  constructor(context: common.UIAbilityContext, report: (message: string) => void) {
    this.context = context;
    this.report = report;
  }

  refresh(): void {
    if (!this.active || deviceInfo.deviceType !== 'phone') return;
    if (this.main) { this.apply(); return; }
    if (this.binding) return;
    this.binding = true;
    window.getLastWindow(this.context).then((main: window.Window): void => {
      if (!this.active) return;
      if (deviceInfo.sdkApiVersion >= 18 && main.getWindowProperties().type !== window.WindowType.TYPE_MAIN) {
        throw new Error('main window unavailable');
      }
      this.main = main;
      main.on('windowEvent', this.listener);
      this.apply();
    }).catch((): void => {
      if (this.active) this.report('暂时无法设置横屏，请切回应用重试');
    }).finally((): void => { this.binding = false; });
  }

  private apply(): void {
    if (!this.active || !this.main) return;
    this.main.setPreferredOrientation(window.Orientation.AUTO_ROTATION_LANDSCAPE)
      .then((): void => { if (this.active) this.report(''); })
      .catch((): void => {
        if (this.active) this.report('系统未允许横屏，请退出分屏或重新打开应用');
      });
  }

  private detach(): void {
    try { this.main?.off('windowEvent', this.listener); } catch (_) {}
    this.main = undefined;
  }

  stop(): void {
    this.active = false;
    this.detach();
  }
}
