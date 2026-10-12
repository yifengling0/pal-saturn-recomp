import { common, bundleManager } from '@kit.AbilityKit';
import { fileIo as fs, fileUri, picker } from '@kit.CoreFileKit';
import { BusinessError } from '@kit.BasicServicesKit';

export interface ImportSavePlan {
  homes: string[];
  requiresChoice: boolean;
  unavailable: boolean;
  newSave: boolean;
}

export interface DiscLocation {
  root: string;
  cue: string;
  home: string;
}

// DOWNLOAD grants its returned application directory persistently. It does not
// grant arbitrary access to public Download or require the PC-only permission.
export class PalStorage {
  readonly downloadRoot: string;
  private readonly statePath: string;
  private readonly sandboxRoot: string;
  private readonly filesDir: string;

  private readonly context: common.UIAbilityContext;

  constructor(context: common.UIAbilityContext) {
    this.context = context;
    const bundle = bundleManager.getBundleInfoForSelfSync(
      bundleManager.BundleFlag.GET_BUNDLE_INFO_WITH_APPLICATION).name;
    this.downloadRoot = new fileUri.FileUri(
      'file://docs/storage/Users/currentUser/Download/' + bundle).path;
    this.filesDir = context.getApplicationContext().filesDir;
    this.sandboxRoot = this.filesDir + '/' + bundle;
    this.statePath = this.filesDir + '/pal-launch-paths.txt';
  }

  static errorCode(error: Object): string {
    const code = (error as BusinessError).code;
    return code === undefined ? '' : '（错误 ' + code.toString() + '）';
  }

  private isDirectory(path: string): boolean {
    try { return fs.statSync(path).isDirectory(); } catch (_) { return false; }
  }

  private isFile(path: string): boolean {
    try { return fs.statSync(path).isFile(); } catch (_) { return false; }
  }

  // One level at a time: recursive mkdir cannot provision the provider's
  // first-level application directory. Never create or inspect its siblings.
  private ensureDirectory(path: string): void {
    if (this.isDirectory(path)) return;
    try { fs.mkdirSync(path); } catch (error) {
      if (!this.isDirectory(path)) throw new Error('目录创建失败' + PalStorage.errorCode(error));
    }
    if (!this.isDirectory(path)) throw new Error('路径不是目录');
  }

  private verifyWritable(path: string): void {
    // An exclusively created temporary directory avoids truncating a user's
    // file with a predictable probe name, even when multiple launches overlap.
    const temporary = fs.mkdtempSync(path + '/.pal-check-XXXXXX');
    const probe = temporary + '/write';
    try {
      const output = fs.openSync(probe, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY);
      try { fs.writeSync(output.fd, 'PAL'); } finally { fs.closeSync(output); }
      fs.unlinkSync(probe);
    } finally { fs.rmdirSync(temporary); }
  }

  prepareDownload(): void {
    this.ensureDirectory(this.downloadRoot);
    this.ensureDirectory(this.downloadRoot + '/disc');
    fs.listFileSync(this.downloadRoot + '/disc');
    this.verifyWritable(this.downloadRoot + '/disc');
  }

  async provisionDownload(): Promise<void> {
    const options = new picker.DocumentSaveOptions();
    options.pickerMode = picker.DocumentPickerMode.DOWNLOAD;
    const uris = await new picker.DocumentViewPicker(this.context).save(options);
    if (uris.length !== 1 || !uris[0]) throw new Error('系统未返回下载目录');
    const selected = new fileUri.FileUri(uris[0]).path.replace(/\/+$/, '');
    if (selected !== this.downloadRoot.replace(/\/+$/, '')) {
      throw new Error('系统返回了不匹配的应用目录');
    }
    this.prepareDownload();
  }

  private findDisc(root: string): string {
    for (const directory of [root + '/disc', root]) {
      let names: string[] = [];
      try { names = fs.listFileSync(directory).sort(); } catch (_) { continue; }
      for (const extension of ['.cue']) {
        for (const name of names) {
          if (!name.toLowerCase().endsWith(extension)) continue;
          // The native loader requires a CUE track table, not a standalone BIN.
          const path = directory + '/' + name;
          if (!this.isFile(path)) continue;
          try {
            const input = fs.openSync(path, fs.OpenMode.READ_ONLY);
            fs.closeSync(input);
            if (extension === '.cue') this.validateCue(path, names);
            return path;
          } catch (_) { /* A visible name alone does not prove read access. */ }
        }
      }
    }
    return '';
  }

  private savedSelection(): DiscLocation | undefined {
    try {
      const lines = fs.readTextSync(this.statePath).split('\n');
      const roots = [this.downloadRoot, this.sandboxRoot, this.filesDir];
      if (lines.length === 5 && lines[0] === 'PAL1' && roots.indexOf(lines[1]) >= 0 &&
          lines[2].startsWith(lines[1] + '/') && !/[\r\x00]/.test(lines[2]) &&
          !lines[2].includes('/../') && !lines[2].includes('/./') &&
          roots.indexOf(lines[3]) >= 0) {
        return { root: lines[1], cue: lines[2], home: lines[3] };
      }
    } catch (_) { /* Missing or stale selection: inspect only known roots. */ }
    return undefined;
  }

  findExisting(): DiscLocation | undefined {
    const previous = this.savedSelection();
    // Preserve the original launcher's priority and all existing save roots.
    for (const root of [this.downloadRoot, this.sandboxRoot, this.filesDir]) {
      const cue = this.findDisc(root);
      if (cue) {
        let home = root;
        if (previous && previous.root === root && previous.cue === cue) home = previous.home;
        else if (!this.saveExists(root) && this.saveExists(this.filesDir)) home = this.filesDir;
        return { root: root, cue: cue, home: home };
      }
    }
    // Imported files live inside our sandbox. Picker permissions need not
    // survive the copy; arbitrary public URIs are never cached for import.
    if (previous && previous.root === this.filesDir &&
        previous.cue.startsWith(this.filesDir + '/imports/')) {
      try {
        const directory = previous.cue.substring(0, previous.cue.lastIndexOf('/'));
        this.validateCue(previous.cue, fs.listFileSync(directory));
        return previous;
      } catch (_) { /* A removed or unreadable BIN returns to setup. */ }
    }
    return undefined;
  }

  private saveExists(home: string): boolean {
    try {
      const entry = fs.statSync(home + '/saves/pal-saturn.bup');
      if (!entry.isFile()) throw new Error('存档路径不是文件');
      return true;
    } catch (error) {
      // Only ENOENT proves no previous save exists. Denied/revoked access and
      // provider failures are not permission to silently start a different save.
      if ((error as BusinessError).code === 13900002) return false;
      throw new Error('无法检查原存档，请恢复目录访问权限后重试');
    }
  }

  private prepareHome(location: DiscLocation, allowFallback: boolean = true): string {
    let home = location.home;
    try {
      this.ensureDirectory(home + '/saves');
      this.verifyWritable(home + '/saves');
      this.verifyWritable(home);
      return home;
    } catch (_) {
      if (!allowFallback) throw new Error('选定的存档位置不可写，请恢复访问后重试');
      // Never silently shadow an existing save after a permission is revoked.
      const previous = this.savedSelection();
      if (this.saveExists(home) || (previous !== undefined && previous.home === home)) {
        throw new Error('原存档目录不可写，请恢复该目录访问权限后重试；原存档未改动');
      }
      home = this.filesDir;
      this.ensureDirectory(home + '/saves');
      this.verifyWritable(home + '/saves');
      this.verifyWritable(home);
      return home;
    }
  }

  commitLaunch(location: DiscLocation, allowFallback: boolean = true): void {
    const home = this.prepareHome(location, allowFallback);
    const paths = [location.root, location.cue, home];
    for (const path of paths) {
      if (!path.startsWith('/') || /[\r\n\x00]/.test(path)) throw new Error('无效路径');
    }
    // Publish only a complete launch selection, never a partially copied disc.
    const temporary = fs.mkdtempSync(this.filesDir + '/.pal-launch-XXXXXX');
    const pending = temporary + '/paths';
    try {
      const output = fs.openSync(pending, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY);
      const contents = 'PAL1\n' + paths.join('\n') + '\n';
      try { fs.writeSync(output.fd, contents); }
      finally { fs.closeSync(output); }
      if (fs.readTextSync(pending) !== contents) throw new Error('启动路径写入不完整');
      fs.renameSync(pending, this.statePath);
    } finally { fs.rmdirSync(temporary); }
  }

  private safeName(name: string): boolean {
    return name.length > 0 && name !== '.' && name !== '..' && !/[\\/\r\n\x00]/.test(name);
  }

  private validateCue(path: string, names: string[]): void {
    if (fs.statSync(path).size > 1024 * 1024) throw new Error('CUE 文件过大');
    const text = fs.readTextSync(path);
    let references = 0;
    let track = 0;
    let indexed = true;
    let indices = 0;
    // Match the native parser's uppercase, quoted grammar. In particular a
    // TRACK before FILE would otherwise dereference an empty native vector.
    for (const line of text.split(/\r?\n/)) {
      if (/^\s*FILE\b/i.test(line)) {
        const match = /^[ \t]*FILE[ \t]+"([^"]+)"[ \t]+BINARY[ \t]*$/.exec(line);
        if (!match || !indexed) throw new Error('CUE FILE 格式或轨道顺序无效');
        const name = match[1];
        if (!this.safeName(name) || !name.toLowerCase().endsWith('.bin') || names.indexOf(name) < 0) {
          throw new Error('请同时选择 CUE 引用的全部 BIN，文件名和大小写须一致；不支持子目录引用');
        }
        const directory = path.substring(0, path.lastIndexOf('/'));
        const referenced = directory + '/' + name;
        if (!this.isFile(referenced) || fs.statSync(referenced).size <= 0) throw new Error('BIN 不存在或为空');
        const input = fs.openSync(referenced, fs.OpenMode.READ_ONLY);
        fs.closeSync(input);
        references++;
      } else if (/^\s*TRACK\b/i.test(line)) {
        const match = /^[ \t]*TRACK[ \t]+(\d{1,2})[ \t]+(MODE1\/2352|MODE1\/2048|AUDIO)[ \t]*$/.exec(line);
        if (!match || references === 0 || !indexed || Number(match[1]) !== track + 1) {
          throw new Error('CUE TRACK 格式或顺序无效');
        }
        track = Number(match[1]);
        indexed = false;
      } else if (/^\s*INDEX\b/i.test(line)) {
        const match = /^[ \t]*INDEX[ \t]+(00|01)[ \t]+(\d{2,3}):([0-5]\d):([0-7]\d)[ \t]*$/.exec(line);
        if (!match || track === 0 || indexed || Number(match[4]) >= 75) {
          throw new Error('CUE INDEX 格式或顺序无效');
        }
        if (match[1] === '01') { indexed = true; indices++; }
      }
    }
    if (references === 0 || indices === 0 || !indexed) throw new Error('CUE 缺少完整 FILE、TRACK 或 INDEX 01');
  }

  saveHomeLabel(home: string): string {
    if (home === this.downloadRoot) return 'Download 存档位置';
    if (home === this.sandboxRoot) return '应用内旧版包目录存档位置';
    return '应用内存档位置';
  }

  importSavePlan(): ImportSavePlan {
    // A missing/revoked disc is precisely why the player may need to import.
    // Keep the previously committed save choice independently of disc access.
    const previous = this.savedSelection();
    if (previous && this.saveExists(previous.home)) {
      // Fail closed on revoked/unknown access; a positive current save wins
      // over stale backups elsewhere even when the original disc was deleted.
      return { homes: [previous.home], requiresChoice: false, unavailable: false, newSave: false };
    }
    const homes: string[] = [];
    let unavailable = false;
    let sandboxEmpty = false;
    for (const home of [this.downloadRoot, this.sandboxRoot, this.filesDir]) {
      try {
        const exists = this.saveExists(home);
        if (exists) homes.push(home);
        if (home === this.filesDir && !exists) sandboxEmpty = true;
      } catch (_) { unavailable = true; }
    }
    // Legacy installs may have no handoff record. One accessible existing save
    // is unambiguous only when all other known roots were positively checked.
    // Multiple saves/unknown roots require an explicit UI choice, never a guess.
    const newSave = homes.length === 0;
    if (newSave) {
      if (!previous && !sandboxEmpty) throw new Error('无法检查应用内存档');
      homes.push(previous ? previous.home : this.filesDir);
    }
    return { homes: homes, requiresChoice: unavailable || homes.length > 1 ||
      (previous !== undefined && homes.indexOf(previous.home) < 0),
      unavailable: unavailable, newSave: newSave };
  }

  async importDisc(requestedHome: string = ''): Promise<DiscLocation | undefined> {
    const plan = this.importSavePlan();
    if ((plan.requiresChoice && !requestedHome) ||
        (requestedHome && plan.homes.indexOf(requestedHome) < 0)) {
      throw new Error('请先明确选择要继续的存档位置');
    }
    const home = requestedHome || plan.homes[0];
    // Validate the selected existing save before presenting the disc picker or
    // copying a large image. Known/committed homes may never silently relocate.
    this.prepareHome({ root: this.filesDir, cue: '', home: home }, false);

    const options = new picker.DocumentSelectOptions();
    options.maxSelectNumber = 32;
    options.fileSuffixFilters = ['光盘镜像|.cue,.bin'];
    const uris = await new picker.DocumentViewPicker(this.context).select(options);
    if (uris.length === 0) return undefined;
    const names: string[] = [];
    for (const uri of uris) {
      const name = new fileUri.FileUri(uri).name;
      if (!this.safeName(name) || !/\.(cue|bin)$/i.test(name) || names.indexOf(name) >= 0) {
        throw new Error('请选择同一套镜像的 CUE 和 BIN，不能包含重名或其他文件');
      }
      names.push(name);
    }
    const cues = names.filter((name: string) => name.toLowerCase().endsWith('.cue'));
    if (cues.length !== 1) throw new Error('请同时选择一份 CUE 和它引用的全部 BIN');
    const imports = this.filesDir + '/imports';
    this.ensureDirectory(imports);
    const staging = fs.mkdtempSync(imports + '/disc-XXXXXX');
    let complete = false;
    try {
      for (let i = 0; i < uris.length; i++) {
        // Open the selected URI, not a reconstructed public filesystem path.
        const input = await fs.open(uris[i], fs.OpenMode.READ_ONLY);
        try { await fs.copyFile(input.fd, staging + '/' + names[i]); }
        finally { await fs.close(input); }
      }
      this.validateCue(staging + '/' + cues[0], names);
      const result: DiscLocation = { root: this.filesDir, cue: staging + '/' + cues[0], home: home };
      this.commitLaunch(result, false);
      complete = true;
      return result;
    } finally {
      // rmdir is recursive in CoreFileKit. Only remove this attempt's newly
      // allocated sandbox directory; never touch an existing disc or save.
      if (!complete) { try { fs.rmdirSync(staging); } catch (_) {} }
    }
  }
}
