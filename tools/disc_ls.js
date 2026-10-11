// 从 MODE1/2352 的 BIN 里读 ISO9660 根/子目录，列出文件与 LBA，并把 CD Block 追踪到的 FAD 反查成文件名。
// 用法: node tools/disc_ls.js [bin] [fad...]
const fs = require('fs');
const bin = process.argv[2] || 'disc/pal_t37401h_v1000_jt.bin';
const fd = fs.openSync(bin, 'r');
const S = 2352;
function sect(n) { const b = Buffer.alloc(S); const r = fs.readSync(fd, b, 0, S, n * S); if (r !== S) throw new Error('short read at LBA ' + n); return b; }
const le32 = (b, o) => b.readUInt32LE(o);

const pvd = sect(16);
if (pvd.subarray(17, 22).toString() !== 'CD001') throw new Error('不是 ISO9660 主卷描述符');
// 本镜像的扇区内数据区从第 16 字节开始（12 字节同步 + 4 字节表头，表头里没有模式字节），所以记录基址是 16 而不是 17。
const root = pvd.subarray(16 + 156, 16 + 190);
const rootLba = le32(root, 2), rootLen = le32(root, 10);
console.log('卷名:', pvd.subarray(16 + 40, 16 + 72).toString().trim(), ' 根目录 LBA', rootLba, '长度', rootLen);

const files = [];
function walk(lba, len, path) {
  const seen = new Set();
  let off = 0;
  while (off < len) {
    const s = (off / 2048) | 0, so = off % 2048;
    const d = sect(lba + s);
    const rec = 16 + so;
    const su = d[rec]; if (!su) { off = (s + 1) * 2048; continue; }
    const nameLen = d[rec + 32];
    let name = d.subarray(rec + 33, rec + 33 + nameLen).toString();
    const dataLba = le32(d, rec + 2), dataLen = le32(d, rec + 10);
    const flags = d[rec + 25];
    name = name.replace(/;1$/, '').replace(/\.$/, '');
    off += su;
    // 本镜像里 '.' 和 '..' 记成单字节 0x00 / 0x01，不跳掉会自己递归自己
    if (nameLen === 1 && name.charCodeAt(0) <= 1) continue;
    if (name === '.' || name === '..') continue;
    if (flags & 2) { if (!seen.has(name)) { seen.add(name); walk(dataLba, dataLen, path + name + '/'); } }
    else files.push({ name: path + name, lba: dataLba, size: dataLen });
  }
}
walk(rootLba, rootLen, '');
files.sort((a, b) => a.lba - b.lba);
console.log(`共 ${files.length} 个文件`);
for (const f of files) console.log('  ', f.name.padEnd(28), 'LBA', f.lba, '大小', f.size, '扇区', Math.ceil(f.size / 2048));
console.log('\n== FAD 反查（LBA = FAD-1）==');
for (const a of process.argv.slice(3)) {
  const fad = +a, lba = fad - 1;
  const hit = files.filter((f) => lba >= f.lba && lba < f.lba + Math.ceil(f.size / 2048)).pop();
  console.log(`FAD ${fad} (LBA ${lba}) ->`, hit ? `${hit.name} (起始 LBA ${hit.lba}, 文件内第 ${lba - hit.lba} 扇区)` : '不在任何文件内（可能是音轨或空隙）');
}
