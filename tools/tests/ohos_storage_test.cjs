// Executes the shipped ArkTS service logic with a filesystem-backed platform
// adapter. HAP compilation separately checks the real SDK signatures/types.
const assert = require('node:assert/strict');
const nodefs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
const source = nodefs.readFileSync(process.argv[2], 'utf8').replace(/^import .*;\n/gm, '');
const code = stripTypeScriptTypes(source, { mode: 'transform' }).replace('export class', 'class');
let passed = 0;
const fixture = () => {
  // A device only ever hands out POSIX paths and the service refuses to publish a launch
  // selection for anything else, so keep the temp root in that shape. Node maps a leading
  // '/Users/...' back onto the current drive, so the same files are still real.
  const tmp = nodefs.mkdtempSync(path.join(os.tmpdir(), 'pal-storage-')).replace(/^[A-Za-z]:/, '').replace(/\\/g, '/');
  const files = tmp + '/files';
  const dl = tmp + '/Download/com.palhero.palsaturn';
  nodefs.mkdirSync(files);
  nodefs.mkdirSync(path.dirname(dl));
  let saved = [], selected = [], saveError, copyFailure = false, blockedPrefix = '', writeBlockedPrefix = '', selectAction = () => {};
  const check = p => { if (typeof p === 'string' && blockedPrefix && p.startsWith(blockedPrefix)) throw Object.assign(new Error('denied'), {code: 201}); };
  const io = {
    OpenMode: { READ_ONLY: 0, WRITE_ONLY: 1, CREATE: 64 },
    statSync: p => { check(p); try { return nodefs.statSync(p); } catch (e) { if (e.code === 'ENOENT') e.code = 13900002; throw e; } },
    mkdirSync: p => { check(p); nodefs.mkdirSync(p); },
    listFileSync: p => { check(p); return nodefs.readdirSync(p); },
    mkdtempSync: p => { check(p); if (writeBlockedPrefix && p.startsWith(writeBlockedPrefix)) throw {code:201}; return nodefs.mkdtempSync(p.replace(/XXXXXX$/, '')); },
    // The shipped code passes an OHOS mask. 64 is O_CREAT on the Linux runner but _O_TEMPORARY
    // on Windows, so name the bits instead of handing the number to node.
    openSync: (p, flags) => { check(p); const node = ((flags & 64) ? nodefs.constants.O_CREAT : 0) | ((flags & 512) ? nodefs.constants.O_TRUNC : 0) | ((flags & 128) ? nodefs.constants.O_EXCL : 0) | ((flags & 1024) ? nodefs.constants.O_APPEND : 0) | ((flags & 2) ? nodefs.constants.O_RDWR : ((flags & 1) ? nodefs.constants.O_WRONLY : nodefs.constants.O_RDONLY)); return { fd: nodefs.openSync(p.replace(/^file:\/\//, ''), node) }; },
    closeSync: f => nodefs.closeSync(typeof f === 'number' ? f : f.fd),
    writeSync: (fd, text) => nodefs.writeSync(fd, text),
    unlinkSync: p => nodefs.unlinkSync(p),
    rmdirSync: p => nodefs.rmSync(p, {recursive: true}),
    readTextSync: p => { check(p); return nodefs.readFileSync(p, 'utf8'); },
    renameSync: (a,b) => nodefs.renameSync(a,b),
    open: async (p, flags) => io.openSync(p,flags),
    close: async f => io.closeSync(f),
    copyFile: async (fd, out) => { if (copyFailure) throw Object.assign(new Error('full'), {code: 13900028}); nodefs.writeFileSync(out, nodefs.readFileSync(fd)); }
  };
  class FileUri {
    constructor(uri) { this.path = uri.startsWith('file://docs/') ? dl : uri.replace(/^file:\/\//, ''); this.name = path.basename(this.path); }
  }
  class DocumentViewPicker {
    async save(options) {
      assert.equal(options.pickerMode, 1);
      if (saveError) throw saveError;
      if (saved[0] === 'file://docs/storage/Users/currentUser/Download/com.palhero.palsaturn') nodefs.mkdirSync(dl, {recursive:true});
      return saved;
    }
    async select(options) { assert.equal(options.maxSelectNumber, 32); selectAction(); return selected; }
  }
  const sandbox = {fs: io, fileUri: {FileUri}, picker: {DocumentViewPicker, DocumentSaveOptions: class {}, DocumentSelectOptions: class {}, DocumentPickerMode:{DOWNLOAD:1}}, bundleManager: {BundleFlag:{GET_BUNDLE_INFO_WITH_APPLICATION:1}, getBundleInfoForSelfSync:()=>({name:'com.palhero.palsaturn'})}};
  vm.createContext(sandbox);
  vm.runInContext(code + '\nthis.Service = PalStorage;', sandbox);
  return {tmp, files, dl, storage: new sandbox.Service({filesDir:files+'/haps/entry/files', getApplicationContext:()=>({filesDir:files})}),
    saved: v => saved=v, selected: v => selected=v, onSelect: v => selectAction=v, saveError: v => saveError=v,
    copyFailure: v => copyFailure=v, blockWrites: v => writeBlockedPrefix=v, block: v => blockedPrefix=v,
    writeDisc: directory => { nodefs.writeFileSync(directory+'/game.cue','FILE \"game.bin\" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n'); nodefs.writeFileSync(directory+'/game.bin','bin'); },
    cleanup: () => nodefs.rmSync(tmp,{recursive:true,force:true})};
};
async function test(name, fn) { const f=fixture(); try { await fn(f); passed++; console.log('PASS '+name); } finally { f.cleanup(); } }
(async()=>{
  await test('missing app directory and disc are created, no sibling scan', f=>{
    f.storage.prepareDownload(); assert(nodefs.statSync(f.dl+'/disc').isDirectory());
    assert.deepEqual(nodefs.readdirSync(f.dl+'/disc'), []);
  });
  await test('existing files survive writable probe',f=>{
    f.storage.prepareDownload(); nodefs.writeFileSync(f.dl+'/disc/.pal-probe','keep');
    f.storage.prepareDownload(); assert.equal(nodefs.readFileSync(f.dl+'/disc/.pal-probe','utf8'),'keep');
  });
  await test('DOWNLOAD provider creates app root then app creates disc',async f=>{
    f.saved(['file://docs/storage/Users/currentUser/Download/com.palhero.palsaturn']);
    await f.storage.provisionDownload(); assert(nodefs.statSync(f.dl+'/disc').isDirectory());
  });
  await test('empty/cancelled provider result is rejected',async f=>{ await assert.rejects(f.storage.provisionDownload()); });
  await test('unexpected provider URI rejected before create',async f=>{
    f.saved(['file://'+f.files]); await assert.rejects(f.storage.provisionDownload());
    assert(!nodefs.existsSync(f.files+'/disc'));
  });
  await test('denied and unsupported provider are actionable failures',async f=>{
    f.saveError({code:801}); await assert.rejects(f.storage.provisionDownload());
    f.saveError({code:201}); await assert.rejects(f.storage.provisionDownload());
  });
  await test('legacy download/disc priority is preserved',f=>{
    f.storage.prepareDownload(); f.writeDisc(f.dl+'/disc'); nodefs.writeFileSync(f.dl+'/game.cue','cue');
    assert.equal(f.storage.findExisting().cue,f.dl+'/disc/game.cue');
  });
  await test('legacy sandbox bundle and files roots are supported',f=>{
    nodefs.mkdirSync(f.files+'/com.palhero.palsaturn'); f.writeDisc(f.files+'/com.palhero.palsaturn');
    f.writeDisc(f.files);
    assert.equal(f.storage.findExisting().root,f.files+'/com.palhero.palsaturn');
  });
  await test('native launch selection records exact disc and unchanged save root',f=>{
    f.storage.prepareDownload(); nodefs.writeFileSync(f.dl+'/disc/game.cue','FILE \"game.bin\" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n'); f.writeDisc(f.dl+'/disc');
    nodefs.mkdirSync(f.dl+'/saves'); nodefs.writeFileSync(f.dl+'/saves/pal-saturn.bup','save');
    f.storage.commitLaunch(f.storage.findExisting());
    assert.equal(nodefs.readFileSync(f.files+'/pal-launch-paths.txt','utf8'),'PAL1\n'+f.dl+'\n'+f.dl+'/disc/game.cue\n'+f.dl+'\n');
    assert.equal(nodefs.readFileSync(f.dl+'/saves/pal-saturn.bup','utf8'),'save');
  });
  await test('incomplete existing CUE stays in setup instead of raw BIN fallback', f=>{
    f.storage.prepareDownload(); nodefs.writeFileSync(f.dl+'/disc/game.cue','FILE "one.bin" BINARY\nFILE "two.bin" BINARY\n');
    nodefs.writeFileSync(f.dl+'/disc/one.bin','bin'); assert.equal(f.storage.findExisting(),undefined);
  });
  await test('old fallback save stays selected when Download becomes writable', f=>{
    f.storage.prepareDownload(); f.writeDisc(f.dl+'/disc');
    nodefs.mkdirSync(f.files+'/saves'); nodefs.writeFileSync(f.files+'/saves/pal-saturn.bup','old');
    const location=f.storage.findExisting(); assert.equal(location.home,f.files);
    f.storage.commitLaunch(location); assert.equal(f.storage.findExisting().home,f.files);
    assert(!nodefs.existsSync(f.dl+'/saves/pal-saturn.bup'));
  });
  await test('previous home survives even before its first save is created', f=>{
    f.storage.prepareDownload(); f.writeDisc(f.dl+'/disc');
    f.storage.commitLaunch({root:f.dl,cue:f.dl+'/disc/game.cue',home:f.files});
    assert.equal(f.storage.findExisting().home,f.files);
  });
  await test('read-only existing save fails without silent relocation', f=>{
    f.storage.prepareDownload(); f.writeDisc(f.dl+'/disc');
    nodefs.mkdirSync(f.dl+'/saves'); nodefs.writeFileSync(f.dl+'/saves/pal-saturn.bup','old');
    f.blockWrites(f.dl); assert.throws(()=>f.storage.commitLaunch(f.storage.findExisting()));
    assert(!nodefs.existsSync(f.files+'/saves/pal-saturn.bup'));
    assert.equal(nodefs.readFileSync(f.dl+'/saves/pal-saturn.bup','utf8'),'old');
  });
  await test('revoked save read access never becomes an empty fallback save', f=>{
    f.storage.prepareDownload(); f.writeDisc(f.dl+'/disc');
    nodefs.mkdirSync(f.dl+'/saves'); nodefs.writeFileSync(f.dl+'/saves/pal-saturn.bup','old');
    f.storage.commitLaunch(f.storage.findExisting());
    const previous=nodefs.readFileSync(f.files+'/pal-launch-paths.txt','utf8');
    f.block(f.dl+'/saves'); assert.throws(()=>f.storage.commitLaunch(f.storage.findExisting()));
    assert.equal(nodefs.readFileSync(f.files+'/pal-launch-paths.txt','utf8'),previous);
    assert(!nodefs.existsSync(f.files+'/saves/pal-saturn.bup'));
  });
  await test('standalone BIN waits for its CUE track table', f=>{
    f.storage.prepareDownload(); nodefs.writeFileSync(f.dl+'/disc/only.bin','bin');
    assert.equal(f.storage.findExisting(),undefined);
  });
  const selectDisc=(f,cue='FILE "game.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n', includeBin=true)=>{
    const src=f.tmp+'/selected'; nodefs.mkdirSync(src);
    nodefs.writeFileSync(src+'/game.cue',cue); nodefs.writeFileSync(src+'/game.bin','image');
    f.selected([src+'/game.cue',...(includeBin?[src+'/game.bin']:[])]);
  };
  const putSave=(home,value)=>{ nodefs.mkdirSync(home+'/saves',{recursive:true}); nodefs.writeFileSync(home+'/saves/pal-saturn.bup',value); };
  await test('legacy Download save survives import when its original disc is missing',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'download progress'); selectDisc(f);
    const result=await f.storage.importDisc(); assert.equal(result.home,f.dl);
    assert.equal(f.storage.findExisting().home,f.dl);
    assert.equal(nodefs.readFileSync(f.dl+'/saves/pal-saturn.bup','utf8'),'download progress');
    assert(!nodefs.existsSync(f.files+'/saves/pal-saturn.bup'));
  });
  await test('deleted previous cue does not discard committed Download home',async f=>{
    f.storage.prepareDownload(); f.writeDisc(f.dl+'/disc'); putSave(f.dl,'current');
    f.storage.commitLaunch(f.storage.findExisting()); nodefs.unlinkSync(f.dl+'/disc/game.cue');
    selectDisc(f); assert.equal(f.storage.importSavePlan().homes[0],f.dl);
    const result=await f.storage.importDisc(); assert.equal(result.home,f.dl);
    assert.equal(nodefs.readFileSync(f.dl+'/saves/pal-saturn.bup','utf8'),'current');
  });
  await test('revoked committed Download home blocks import before copying',async f=>{
    f.storage.prepareDownload(); f.writeDisc(f.dl+'/disc'); putSave(f.dl,'protected');
    f.storage.commitLaunch(f.storage.findExisting()); nodefs.unlinkSync(f.dl+'/disc/game.cue');
    const previous=nodefs.readFileSync(f.files+'/pal-launch-paths.txt','utf8'); selectDisc(f); f.block(f.dl+'/saves');
    await assert.rejects(f.storage.importDisc()); await assert.rejects(f.storage.importDisc(f.files));
    assert.equal(nodefs.readFileSync(f.files+'/pal-launch-paths.txt','utf8'),previous);
    assert(!nodefs.existsSync(f.files+'/imports')); assert(!nodefs.existsSync(f.files+'/saves/pal-saturn.bup'));
  });
  await test('unknown legacy Download save requires explicit fresh-start choice',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'hidden old'); selectDisc(f); f.block(f.dl+'/saves');
    const plan=f.storage.importSavePlan(); assert(plan.requiresChoice); assert(plan.unavailable); assert(plan.newSave);
    await assert.rejects(f.storage.importDisc()); assert(!nodefs.existsSync(f.files+'/imports'));
    const result=await f.storage.importDisc(f.files); assert.equal(result.home,f.files);
    assert.equal(nodefs.readFileSync(f.dl+'/saves/pal-saturn.bup','utf8'),'hidden old');
  });
  await test('mixed legacy saves need a choice and never prefer stale sandbox backup',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'download current'); putSave(f.files+'/com.palhero.palsaturn','old bundle'); putSave(f.files,'old fallback'); selectDisc(f);
    const plan=f.storage.importSavePlan(); assert(plan.requiresChoice); assert.equal(plan.homes.length,3);
    await assert.rejects(f.storage.importDisc()); assert(!nodefs.existsSync(f.files+'/imports'));
    const result=await f.storage.importDisc(f.dl); assert.equal(result.home,f.dl);
    assert.equal(nodefs.readFileSync(f.files+'/saves/pal-saturn.bup','utf8'),'old fallback');
    assert.equal(nodefs.readFileSync(f.files+'/com.palhero.palsaturn/saves/pal-saturn.bup','utf8'),'old bundle');
  });
  await test('committed files home wins over stale bundle and Download backups on import',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'stale download'); putSave(f.files+'/com.palhero.palsaturn','stale bundle'); putSave(f.files,'current fallback');
    f.storage.commitLaunch({root:f.files,cue:f.files+'/removed.cue',home:f.files}); selectDisc(f);
    const plan=f.storage.importSavePlan(); assert(!plan.requiresChoice); assert.equal(plan.homes[0],f.files);
    const result=await f.storage.importDisc(); assert.equal(result.home,f.files);
    assert.equal(nodefs.readFileSync(result.home+'/saves/pal-saturn.bup','utf8'),'current fallback');
  });
  await test('committed Download home wins over accessible sandbox backups',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'current download'); putSave(f.files+'/com.palhero.palsaturn','stale bundle'); putSave(f.files,'stale fallback');
    f.storage.commitLaunch({root:f.dl,cue:f.dl+'/removed.cue',home:f.dl}); selectDisc(f);
    const result=await f.storage.importDisc(); assert.equal(result.home,f.dl);
    assert.equal(nodefs.readFileSync(result.home+'/saves/pal-saturn.bup','utf8'),'current download');
  });
  await test('missing committed save cannot silently start empty over an existing backup',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'current');
    f.storage.commitLaunch({root:f.dl,cue:f.dl+'/removed.cue',home:f.dl});
    nodefs.unlinkSync(f.dl+'/saves/pal-saturn.bup'); putSave(f.files,'available backup'); selectDisc(f);
    const plan=f.storage.importSavePlan(); assert(plan.requiresChoice); assert.equal(plan.homes[0],f.files);
    await assert.rejects(f.storage.importDisc()); assert(!nodefs.existsSync(f.files+'/imports'));
    const result=await f.storage.importDisc(f.files); assert.equal(result.home,f.files);
    assert.equal(nodefs.readFileSync(f.files+'/saves/pal-saturn.bup','utf8'),'available backup');
    assert(!nodefs.existsSync(f.dl+'/saves/pal-saturn.bup'));
  });
  await test('chosen save home cannot relocate if it changes while picker is open',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'current'); selectDisc(f);
    f.onSelect(()=>{ nodefs.unlinkSync(f.dl+'/saves/pal-saturn.bup'); f.blockWrites(f.dl); });
    await assert.rejects(f.storage.importDisc());
    assert(!nodefs.existsSync(f.files+'/pal-launch-paths.txt'));
    assert(!nodefs.existsSync(f.files+'/saves/pal-saturn.bup'));
    assert.deepEqual(nodefs.readdirSync(f.files+'/imports'),[]);
  });
  await test('read-only Download save blocks import without sandbox relocation',async f=>{
    f.storage.prepareDownload(); putSave(f.dl,'old'); selectDisc(f); f.blockWrites(f.dl);
    await assert.rejects(f.storage.importDisc()); assert(!nodefs.existsSync(f.files+'/imports'));
    assert.equal(nodefs.readFileSync(f.dl+'/saves/pal-saturn.bup','utf8'),'old');
  });
  await test('import copies selected URI data and survives restart lookup',async f=>{
    selectDisc(f); const result=await f.storage.importDisc();
    assert.equal(nodefs.readFileSync(result.cue,'utf8'),'FILE "game.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n');
    assert.equal(f.storage.findExisting().cue,result.cue); assert.equal(result.home,f.files);
    assert.equal(nodefs.readFileSync(f.tmp+'/selected/game.bin','utf8'),'image');
  });
  await test('import preserves old sandbox-bundle save home',async f=>{
    nodefs.mkdirSync(f.files+'/com.palhero.palsaturn/saves',{recursive:true});
    nodefs.writeFileSync(f.files+'/com.palhero.palsaturn/saves/pal-saturn.bup','old');
    selectDisc(f); const result=await f.storage.importDisc(); assert.equal(result.home,f.files+'/com.palhero.palsaturn');
    assert.equal(nodefs.readFileSync(result.home+'/saves/pal-saturn.bup','utf8'),'old');
  });
  await test('cancelled import never publishes selection',async f=>{
    assert.equal(await f.storage.importDisc(),undefined); assert(!nodefs.existsSync(f.files+'/pal-launch-paths.txt'));
  });
  for (const [name,cue,bin] of [['missing BIN','FILE "game.bin" BINARY\n',false],['case mismatch','FILE "GAME.BIN" BINARY\n',true],['path traversal','FILE "../game.bin" BINARY\n',true],['no references','TRACK 01 MODE1/2352\n',true],['BOM FILE','\ufeffFILE \"game.bin\" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n',true],['lowercase FILE','file \"game.bin\" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n',true],['unquoted FILE','FILE game.bin BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n',true],['missing INDEX','FILE \"game.bin\" BINARY\n TRACK 01 MODE1/2352\n',true],['TRACK before FILE','TRACK 01 MODE1/2352\n FILE \"game.bin\" BINARY\n INDEX 01 00:00:00\n',true]]) {
    await test('reject '+name+' and remove only new incomplete import',async f=>{
      selectDisc(f,cue,bin); await assert.rejects(f.storage.importDisc());
      assert.deepEqual(nodefs.readdirSync(f.files+'/imports'),[]); assert(nodefs.existsSync(f.tmp+'/selected/game.bin'));
    });
  }
  await test('copy failure preserves existing launch selection',async f=>{
    selectDisc(f); nodefs.writeFileSync(f.files+'/pal-launch-paths.txt','old'); f.copyFailure(true);
    await assert.rejects(f.storage.importDisc()); assert.equal(nodefs.readFileSync(f.files+'/pal-launch-paths.txt','utf8'),'old');
    assert.deepEqual(nodefs.readdirSync(f.files+'/imports'),[]);
  });
  await test('malformed persisted selection cannot escape sandbox', f=>{
    nodefs.writeFileSync(f.files+'/pal-launch-paths.txt','PAL1\n'+f.files+'\n/etc/passwd\n'+f.files+'\n');
    assert.equal(f.storage.findExisting(),undefined);
  });
  console.log(`${passed} storage scenarios passed`);
})().catch(error=>{console.error(error);process.exitCode=1;});
