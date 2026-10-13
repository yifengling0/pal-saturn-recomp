import { common } from '@kit.AbilityKit';
import { PhoneOrientation } from '../services/PhoneOrientation';
import { PalStorage } from '../services/PalStorage';

@Entry
@Component
struct Index {
  @State private ready: boolean = false;
  @State private busy: boolean = true;
  @State private status: string = '正在准备光盘目录…';
  @State private orientationStatus: string = '';
  @State private importHomes: string[] = [];
  @State private importNewSave: boolean = false;
  private storage: PalStorage | undefined = undefined;
  private orientation: PhoneOrientation | undefined = undefined;
  private alive: boolean = false;

  aboutToAppear(): void {
    this.alive = true;
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.orientation = new PhoneOrientation(context, (message: string): void => {
      if (this.alive) this.orientationStatus = message;
    });
    this.orientation.refresh();
    try {
      // Explicit developer --selftest builds must reach SDL without a disc.
      const flag = context.resourceManager.getRawFileContentSync('pal-selftest.txt');
      if (flag.length === 3 && flag[0] === 111 && flag[1] === 110 && flag[2] === 10) {
        this.ready = true;
        this.busy = false;
        return;
      }
      this.storage = new PalStorage(context);
      this.prepare(true);
    } catch (error) {
      this.status = '目录初始化失败' + PalStorage.errorCode(error) + '，请关闭后重新打开应用';
      this.busy = false;
    }
  }

  onPageShow(): void { this.orientation?.refresh(); }

  aboutToDisappear(): void {
    this.alive = false;
    this.orientation?.stop();
    this.orientation = undefined;
  }

  private async prepare(provision: boolean): Promise<void> {
    if (!this.storage) return;
    this.busy = true;
    try {
      let downloadReady = false;
      try { this.storage.prepareDownload(); downloadReady = true; } catch (_) {}
      // Recover existing discs/saves before asking the provider for anything.
      let disc = this.storage.findExisting();
      if (!disc && !downloadReady && provision) {
        try { await this.storage.provisionDownload(); downloadReady = true; } catch (error) {
          this.status = '系统下载目录暂不可用' + PalStorage.errorCode(error) + '。可重试，或点“导入 CUE + BIN”复制到应用内';
        }
        disc = this.storage.findExisting();
      }
      if (!this.alive) return;
      if (disc) {
        this.storage.commitLaunch(disc);
        this.ready = true;
      } else if (downloadReady) {
        this.status = '已准备 Download/com.palhero.palsaturn/disc。放入自己的完整 CUE + BIN 后点“重新扫描”，也可直接导入';
      }
    } catch (error) {
      this.status = '无法准备光盘或存档目录' + PalStorage.errorCode(error) + '。请确认目录可读写后重试；原文件未改动';
    } finally { if (this.alive) this.busy = false; }
  }

  private async importDisc(selectedHome: string = ''): Promise<void> {
    if (this.busy || !this.storage) return;
    this.busy = true;
    try {
      try {
        const plan = this.storage.importSavePlan();
        if (plan.requiresChoice && !selectedHome) {
          this.importHomes = plan.homes;
          this.importNewSave = plan.newSave;
          this.status = plan.unavailable ?
            '有旧存档目录暂时无法检查。请先恢复权限，或明确选择下面的存档位置；不会迁移或覆盖其他目录的进度' :
            '发现其他或多处已有存档，请明确选择要继续的一份；其他存档保持原样';
          return;
        }
      } catch (_) {
        this.status = '无法访问上次使用的存档目录，请恢复该目录权限后重试。未切换存档，也未创建新档';
        return;
      }
      this.importHomes = [];
      this.status = '请选择同一套镜像的一份 CUE 和全部 BIN；复制期间请保持应用打开';
      const disc = await this.storage.importDisc(selectedHome);
      if (!this.alive) return;
      if (disc) this.ready = true;
      else this.status = '已取消导入。原文件未改动，可以重新选择';
    } catch (error) {
      this.status = '导入失败' + PalStorage.errorCode(error) + '。未切换原存档。请恢复存档目录权限、检查空间，并同时选择完整 CUE + BIN（文件名大小写须一致，无子目录）';
    } finally { if (this.alive) this.busy = false; }
  }

  build() {
    Stack() {
      if (this.ready) {
        // SDL only ever sees a key press if the surface itself holds focus: the native
        // side registers OH_NativeXComponent_RegisterKeyEventCallback, and ArkUI routes
        // hardware-key events to the focused component, not to the page.
        XComponent({ id: 'SDL_XComponent', type: XComponentType.SURFACE, libraryname: 'SDL3' }).id('SDL_XComponent')
          .focusable(true).defaultFocus(true)
      } else {
        Scroll() {
          Column({ space: 16 }) {
            Text('仙剑奇侠传 · 土星版').fontSize(24).fontColor(Color.White)
            Text(this.status).fontSize(16).fontColor('#eeeeee')
            Button('重新扫描 / 准备下载目录').enabled(!this.busy)
              .onClick((): void => { if (!this.busy) this.prepare(true); })
            Button('导入 CUE + BIN').enabled(!this.busy).onClick((): void => { this.importDisc(); })
            if (this.importHomes.length > 0) {
              if (this.importNewSave) {
                Text('下方操作会在所选位置全新开始。其他旧存档不会被删除，但本次不会读取它。').fontColor('#ffcc88')
              }
              ForEach(this.importHomes, (home: string) => {
                Button((this.importNewSave ? '确认全新开始：' : '') +
                  (this.storage?.saveHomeLabel(home) || '选择此存档'))
                  .enabled(!this.busy).onClick((): void => { this.importDisc(home); })
              })
              Button('取消选择').enabled(!this.busy).onClick((): void => {
                this.importHomes = [];
                this.status = '已取消选择，原存档未改动。可恢复目录访问后重试';
              })
            }
            Text('导入仅复制所选镜像到应用内，不覆盖已有镜像或存档。卸载应用会删除应用内文件。').fontSize(13).fontColor('#aaaaaa')
          }.padding(24).width('100%')
        }.width('100%').height('100%')
      }
      if (this.orientationStatus) {
        Text(this.orientationStatus).fontColor(Color.White).backgroundColor('#bb222222').padding(8)
      }
    }.width('100%').height('100%').backgroundColor('#121722')
  }
}
