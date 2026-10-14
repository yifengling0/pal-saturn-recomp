import { AbilityLifecycleCallback, UIAbility } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { BusinessError, deviceInfo } from '@kit.BasicServicesKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { PalStorage } from './PalStorage';
import { FoldLayout } from './FoldLayout';

// Observe the lifecycle independently: SDL installs its own UIAbility methods.
// The WindowStage owns the main window; getLastWindow may return a picker/dialog.
export class PhoneOrientation {
  private static current: PhoneOrientation | undefined = undefined;
  private stage: window.WindowStage | undefined = undefined;
  private main: window.Window | undefined = undefined;
  private active: boolean = true;
  private epoch: number = 0;
  private binding: boolean = false;
  private listening: boolean = false;
  private applying: boolean = false;
  private callbackId: number = -1;
  private timer: number = -1;
  private retries: number = 0;
  private message: string = '';
  private report: ((message: string) => void) | undefined = undefined;
  private readonly ability: UIAbility;
  private readonly fold: FoldLayout = new FoldLayout();
  private listener = (event: window.WindowEventType): void => {
    if (event === window.WindowEventType.WINDOW_SHOWN || event === window.WindowEventType.WINDOW_ACTIVE) {
      this.refresh();
    } else if (event === window.WindowEventType.WINDOW_DESTROYED) {
      this.resetWindow();
    }
  };

  private constructor(ability: UIAbility) { this.ability = ability; }

  static install(ability: UIAbility): void {
    // Official deviceType uses 'tablet', not the colloquial 'pad'.
    if (deviceInfo.deviceType !== 'phone' && deviceInfo.deviceType !== 'tablet') return;
    PhoneOrientation.current?.stop();
    const policy = new PhoneOrientation(ability);
    PhoneOrientation.current = policy;
    try {
      // The SDK declares this callback contract as a class, not an interface.
      // A typed callback object avoids inheriting a platform runtime constructor.
      const callback: AbilityLifecycleCallback = {
        onAbilityCreate: (owner: UIAbility): void => { policy.onAbilityCreate(owner); },
        onWindowStageCreate: (owner: UIAbility, stage: window.WindowStage): void => { policy.onWindowStageCreate(owner, stage); },
        onWindowStageActive: (owner: UIAbility, stage: window.WindowStage): void => { policy.onWindowStageActive(owner, stage); },
        onWindowStageInactive: (owner: UIAbility, stage: window.WindowStage): void => { policy.onWindowStageInactive(owner, stage); },
        onWindowStageDestroy: (owner: UIAbility, stage: window.WindowStage): void => { policy.onWindowStageDestroy(owner, stage); },
        onAbilityForeground: (owner: UIAbility): void => { policy.onAbilityForeground(owner); },
        onAbilityBackground: (owner: UIAbility): void => { policy.onAbilityBackground(owner); },
        onAbilityDestroy: (owner: UIAbility): void => { policy.onAbilityDestroy(owner); },
        onAbilityContinue: (owner: UIAbility): void => { policy.onAbilityContinue(owner); }
      };
      policy.callbackId = ability.context.getApplicationContext().on('abilityLifecycle', callback);
      policy.log('lifecycle registered');
    } catch (error) { policy.failure('register lifecycle', error); }
  }

  static getCurrent(): PhoneOrientation | undefined { return PhoneOrientation.current; }

  setSurface(x: number, y: number, width: number, height: number): void {
    this.fold.setSurface(x, y, width, height);
  }

  setReporter(report: ((message: string) => void) | undefined): void {
    this.report = report;
    report?.(this.message);
  }

  private log(step: string): void {
    hilog.info(0x0000, 'PAL/ORIENTATION', '%{public}s',
      step + ' sdk=' + deviceInfo.sdkApiVersion.toString() + ' device=' + deviceInfo.deviceType);
  }

  private failure(step: string, error: Object): void {
    this.log(step + ' failed' + PalStorage.errorCode(error) + ' message=' + (error as BusinessError).message);
    this.message = '屏幕方向设置暂未完成（' + step + '）' + PalStorage.errorCode(error);
    this.report?.(this.message);
  }

  refresh(): void {
    if (!this.active) return;
    this.cancelRetry();
    this.retries = 0;
    this.bind();
    this.fold.refresh();
  }

  private retry(): void {
    if (!this.active || !this.stage || this.timer !== -1 || this.retries >= 3) return;
    const delay = [250, 750, 1500][this.retries++];
    this.timer = setTimeout((): void => { this.timer = -1; this.bind(); }, delay);
  }

  private cancelRetry(): void {
    if (this.timer !== -1) clearTimeout(this.timer);
    this.timer = -1;
  }

  private async bind(): Promise<void> {
    if (!this.active || !this.stage || this.binding) return;
    if (this.main && this.listening) { this.apply(); return; }
    const stage = this.stage;
    const epoch = this.epoch;
    this.binding = true;
    let step = 'getMainWindow';
    try {
      const main = await stage.getMainWindow();
      if (!this.active || epoch !== this.epoch) return;
      // Properties are diagnostic only. The stage API establishes main-window identity
      // on every supported SDK, including systems exposing a different legacy type.
      try {
        const properties = main.getWindowProperties();
        this.log('main acquired type=' + properties.type.toString() + ' size=' +
          properties.windowRect.width.toString() + 'x' + properties.windowRect.height.toString());
      } catch (error) { this.log('getWindowProperties failed' + PalStorage.errorCode(error)); }
      this.main = main;
      this.fold.bind(main, (): void => { this.apply(); });
      step = 'listen windowEvent';
      main.on('windowEvent', this.listener);
      this.listening = true;
      this.log('windowEvent registered');
      this.apply();
    } catch (error) {
      if (this.active && epoch === this.epoch) { this.failure(step, error); this.retry(); }
    } finally {
      if (epoch === this.epoch) this.binding = false;
    }
  }

  private async apply(): Promise<void> {
    if (!this.active || !this.main || this.applying) return;
    const main = this.main;
    const epoch = this.epoch;
    this.applying = true;
    const requested = this.fold.preferredOrientation();
    try {
      await main.setPreferredOrientation(requested);
      if (!this.active || epoch !== this.epoch) return;
      this.message = '';
      this.report?.('');
      this.log('orientation requested=' + requested.toString());
    } catch (error) {
      if (this.active && epoch === this.epoch) { this.failure('setPreferredOrientation', error); this.retry(); }
    } finally {
      if (epoch === this.epoch) {
        this.applying = false;
        // A posture event may arrive while the system orientation request is pending.
        if (this.active && requested !== this.fold.preferredOrientation()) this.apply();
      }
    }
  }

  private resetWindow(): void {
    this.fold.stop();
    this.epoch++;
    this.cancelRetry();
    if (this.listening) {
      try { this.main?.off('windowEvent', this.listener); }
      catch (error) { this.log('unlisten failed' + PalStorage.errorCode(error)); }
    }
    this.main = undefined;
    this.binding = false;
    this.listening = false;
    this.applying = false;
  }

  private acceptStage(ability: UIAbility, stage: window.WindowStage): void {
    if (!this.active || ability !== this.ability) return;
    this.log('stage available');
    if (this.stage !== stage) { this.resetWindow(); this.stage = stage; }
    this.refresh();
  }

  onWindowStageCreate(ability: UIAbility, stage: window.WindowStage): void { this.acceptStage(ability, stage); }
  onWindowStageActive(ability: UIAbility, stage: window.WindowStage): void { this.acceptStage(ability, stage); }
  onWindowStageDestroy(ability: UIAbility, stage: window.WindowStage): void {
    if (ability !== this.ability || stage !== this.stage) return;
    this.resetWindow();
    this.stage = undefined;
  }
  onAbilityForeground(ability: UIAbility): void {
    if (ability === this.ability) { this.log('ability foreground'); this.refresh(); }
  }
  onAbilityDestroy(ability: UIAbility): void { if (ability === this.ability) this.stop(); }
  onAbilityCreate(_ability: UIAbility): void {}
  onWindowStageInactive(_ability: UIAbility, _stage: window.WindowStage): void {}
  onAbilityBackground(_ability: UIAbility): void {}
  onAbilityContinue(_ability: UIAbility): void {}

  stop(): void {
    this.active = false;
    this.resetWindow();
    this.stage = undefined;
    this.report = undefined;
    const callbackId = this.callbackId;
    this.callbackId = -1;
    if (PhoneOrientation.current === this) PhoneOrientation.current = undefined;
    if (callbackId !== -1) {
      try {
        this.ability.context.getApplicationContext().off('abilityLifecycle', callbackId)
          .catch((error: Object): void => { this.log('unregister lifecycle failed' + PalStorage.errorCode(error)); });
      } catch (error) { this.log('unregister lifecycle failed' + PalStorage.errorCode(error)); }
    }
  }
}
