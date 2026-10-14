import { display, window } from '@kit.ArkUI';
import { deviceInfo } from '@kit.BasicServicesKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import palDisplay from 'libpal_display.so';

// Keep the SDL surface alive. Only geometry changes across fold/display events.
export class FoldLayout {
  private main: window.Window | undefined = undefined;
  private timer: number = -1;
  private foldListening: boolean = false;
  private modeListening: boolean = false;
  private displayListening: boolean = false;
  private sizeListening: boolean = false;
  private half: boolean = false;
  private orientation: number = 0;
  private orientationListening: boolean = false;
  private surfaceX: number = 0;
  private surfaceY: number = 0;
  private surfaceWidth: number = 0;
  private surfaceHeight: number = 0;
  private last: string = '';
  private onPosture: (() => void) | undefined = undefined;
  private orientationChange = (value: number): void => {
    this.orientation = value;
    this.onPosture?.();
  };
  private foldChange = (_status: display.FoldStatus): void => { this.refresh(); };
  private modeChange = (_mode: display.FoldDisplayMode): void => { this.refresh(); };
  private displayChange = (_id: number): void => { this.refresh(); };
  private sizeChange = (_size: window.Size): void => {
    // onAreaChange will supply the matching new surface bounds.
    this.surfaceWidth = 0;
    this.publish(false, []);
    this.refresh();
  };

  preferredOrientation(): window.Orientation {
    if (this.orientation === 1) return window.Orientation.AUTO_ROTATION_PORTRAIT;
    if (this.orientation === 2) return window.Orientation.AUTO_ROTATION;
    return window.Orientation.AUTO_ROTATION_LANDSCAPE;
  }

  bind(main: window.Window, onPosture: () => void): void {
    this.stop();
    this.main = main;
    this.onPosture = onPosture;
    try {
      palDisplay.onOrientationChange(this.orientationChange);
      this.orientationListening = true;
    } catch (_) { hilog.info(0x0000, 'PAL/FOLD', 'Orientation notifications unavailable; keeping landscape'); }
    try {
      if (display.isFoldable()) {
        display.on('foldStatusChange', this.foldChange); this.foldListening = true;
        display.on('foldDisplayModeChange', this.modeChange); this.modeListening = true;
        display.on('change', this.displayChange); this.displayListening = true;
      }
      main.on('windowSizeChange', this.sizeChange); this.sizeListening = true;
    } catch (_) { hilog.info(0x0000, 'PAL/FOLD', 'Fold notifications unavailable; manual layout remains available'); }
    this.refresh();
  }

  setSurface(x: number, y: number, width: number, height: number): void {
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(width) || !Number.isFinite(height) ||
      width <= 0 || height <= 0) {
      this.surfaceWidth = 0;
      this.publish(false, []);
      return;
    }
    this.surfaceX = x; this.surfaceY = y;
    this.surfaceWidth = width; this.surfaceHeight = height;
    this.refresh();
  }

  refresh(): void {
    if (!this.main) return;
    if (this.timer !== -1) clearTimeout(this.timer);
    this.timer = setTimeout((): void => { this.timer = -1; this.sample(); }, 80);
  }

  private publish(half: boolean, rectangles: number[]): void {
    const key = half.toString() + ':' + rectangles.join(',');
    if (key === this.last) return;
    palDisplay.update(half, rectangles);
    this.last = key;
    hilog.info(0x0000, 'PAL/FOLD', 'half=%{public}s creases=%{public}d', half.toString(), rectangles.length / 4);
  }

  private sample(): void {
    if (!this.main) return;
    let half = false;
    const rectangles: number[] = [];
    try {
      if (display.isFoldable()) {
        const status: number = display.getFoldStatus();
        half = status === 3 || status === 13 || status === 21 || status === 22 || status === 23;
        if (half) {
          const properties = this.main.getWindowProperties();
          const screen = properties.displayId === undefined ? display.getDefaultDisplaySync() :
            display.getDisplayByIdSync(properties.displayId);
          // API 20 returns creases in the current display orientation. The older API
          // does not promise rotated coordinates: use it only at rotation zero.
          const region = deviceInfo.sdkApiVersion >= 20 ? screen.getLiveCreaseRegion() :
            screen.rotation === 0 ? display.getCurrentFoldCreaseRegion() : undefined;
          if (region && region.displayId === screen.id && this.surfaceWidth > 0 && this.surfaceHeight > 0) {
            const sx = properties.windowRect.left + this.surfaceX;
            const sy = properties.windowRect.top + this.surfaceY;
            for (let i = 0; i < Math.min(4, region.creaseRects.length); i++) {
              const crease = region.creaseRects[i];
              const left = Math.max(sx, crease.left), top = Math.max(sy, crease.top);
              const right = Math.min(sx + this.surfaceWidth, crease.left + crease.width);
              const bottom = Math.min(sy + this.surfaceHeight, crease.top + crease.height);
              if (right < left || bottom < top) continue;
              rectangles.push((left - sx) / this.surfaceWidth, (top - sy) / this.surfaceHeight,
                (right - left) / this.surfaceWidth, (bottom - top) / this.surfaceHeight);
            }
          }
        }
      }
    } catch (_) { half = false; }
    if (half !== this.half) {
      this.half = half;
      this.onPosture?.();
    }
    this.publish(half, rectangles);
  }

  stop(): void {
    if (this.timer !== -1) clearTimeout(this.timer);
    this.timer = -1;
    try { if (this.orientationListening) palDisplay.onOrientationChange(undefined); } catch (_) {}
    this.orientationListening = false;
    try { if (this.foldListening) display.off('foldStatusChange', this.foldChange); } catch (_) {}
    try { if (this.modeListening) display.off('foldDisplayModeChange', this.modeChange); } catch (_) {}
    try { if (this.displayListening) display.off('change', this.displayChange); } catch (_) {}
    try { if (this.sizeListening) this.main?.off('windowSizeChange', this.sizeChange); } catch (_) {}
    this.foldListening = false; this.modeListening = false; this.displayListening = false; this.sizeListening = false;
    this.main = undefined; this.onPosture = undefined;
    this.half = false;
    this.publish(false, []);
  }
}
