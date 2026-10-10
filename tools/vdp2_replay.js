// 离线复刻 runtime 的 VDP2 合成（vdp2.cpp 的 setup_nbg/nbg_pixel/dot/back），从 --dump 文件重建画面，
// 用来判断"地图能显示、影片幕全黑"到底出自哪条取数路径；并可切换假设（字符步长、名称表单位）做对照。
// 用法: node tools/vdp2_replay.js <dump.bin> <out.png> [chrShift=5] [nameUnit=0x4000]
const fs = require('fs'), zlib = require('zlib');
const buf = fs.readFileSync(process.argv[2]);
const regs = buf.subarray(buf.length - 0x200);
const cram = buf.subarray(buf.length - 0x200 - 0x1000, buf.length - 0x200);
const vram = buf.subarray(buf.length - 0x200 - 0x1000 - 0x80000, buf.length - 0x200 - 0x1000);
const r = (o) => (regs[o] << 8 | regs[o + 1]) & 0xFFFF;
const vw = (a) => { a &= 0x7FFFE; return (vram[a] << 8 | vram[a + 1]) & 0xFFFF; };
const vb = (a) => vram[a & 0x7FFFF];
const rgb555 = (v) => ((v & 0x1F) << 3) << 16 | ((v >> 5 & 0x1F) << 3) << 8 | ((v >> 10 & 0x1F) << 3);
const cramMode = r(0x0E) >> 12 & 3;
function cramAt(i) {
  if (cramMode === 2) { const a = (i & 0x3FF) * 4; const v = cram[a] << 24 | cram[a + 1] << 16 | cram[a + 2] << 8 | cram[a + 3]; return (v & 0xFF) << 16 | (v & 0xFF00) | (v >> 16 & 0xFF); }
  const a = (i & (cramMode === 1 ? 0x7FF : 0x3FF)) * 2;
  return rgb555((cram[a] << 8 | cram[a + 1]) & 0xFFFF);
}
const chrShift = +(process.argv[4] ?? 5);          // runtime 用 chr*0x20，即 shift 5
const nameUnit = +(process.argv[5] ?? 0x4000);     // runtime 用 page_bytes 作名称表地址单位

const W = [320, 352, 640, 704][r(0x00) & 7], H = (r(0x00) >> 4 & 3) === 1 ? 240 : 224;
const px = new Uint32Array(W * H);
const stats = [];
const bk = ((r(0xAC) & 7) << 16 | r(0xAE)) * 2;
const back = rgb555(vw(bk));
for (let i = 0; i < W * H; i++) px[i] = back;

for (let n = 0; n < 4; n++) {
  const bgon = r(0x20);
  if (!(bgon >> n & 1)) continue;
  const chctl = n < 2 ? r(0x28) >> (n * 8) & 0xFF : r(0x2A) >> ((n - 2) * 4) & 0xF;
  const colors = n < 2 ? chctl >> 4 & 7 : chctl >> 1 & 1;
  const bitmap = n < 2 ? chctl >> 1 & 1 : 0;
  const cell2x2 = chctl & 1;
  const pncn = r(0x30 + n * 2);
  const word1 = pncn >> 15 & 1, cnsm = pncn >> 14 & 1, supp = pncn & 0x3FF;
  const plsz = r(0x3A) >> (n * 2) & 3;
  const plane_w = plsz === 0 ? 1 : 2, plane_h = plsz === 3 ? 2 : 1;
  const mpof = r(0x3C) >> (n * 4) & 7;
  const page_bytes = (cell2x2 ? 0x800 : 0x2000) * (word1 ? 1 : 2);
  const mask = plane_w * plane_h - 1;
  const plane = [0, 1, 2, 3].map((i) => (((mpof << 6 | r(0x40 + n * 4 + (i / 2 | 0) * 2) >> ((i & 1) * 8) & 0x3F) & ~mask)) * (n === 0 ? nameUnit : page_bytes));
  const b = n < 2 ? 0x70 + n * 0x10 : 0x90 + (n - 2) * 4;
  const sx0 = n < 2 ? ((r(b) & 0x7FF) << 8 | r(b + 2) >> 8) : (r(b) & 0x7FF) << 8;
  const sy0 = n < 2 ? ((r(b + 4) & 0x7FF) << 8 | r(b + 6) >> 8) : (r(b + 2) & 0x7FF) << 8;
  const dx = n < 2 ? ((r(b + 8) & 7) << 8 | r(b + 10) >> 8) : 0x100;
  const dy = n < 2 ? ((r(b + 12) & 7) << 8 | r(b + 14) >> 8) : 0x100;
  const prio = r(0xF8 + (n / 2 | 0) * 2) >> ((n & 1) * 8) & 7;
  const caos = (r(0xE4) >> (n * 4) & 7) << 8;
  const opaque = bgon >> (8 + n) & 1;
  if (!prio) { stats.push(`NBG${n} prio=0 -> runtime 跳过`); continue; }
  let drawn = 0, trGB = 0, trZero = 0, minP = 1e9, maxP = 0, minB = 1e9, maxB = 0;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    let sx = ((sx0 + x * dx) >> 8) & (plane_w * 512 * 2 - 1);
    let sy = ((sy0 + y * dy) >> 8) & (plane_h * 512 * 2 - 1);
    const pl = (sy >= plane_h * 512 ? 2 : 0) + (sx >= plane_w * 512 ? 1 : 0);
    const ix = sx % (plane_w * 512), iy = sy % (plane_h * 512);
    const cs = cell2x2 ? 16 : 8;
    const page = ((iy / 512) | 0) * plane_w + ((ix / 512) | 0);
    const cx = (ix % 512) / cs | 0, cy = (iy % 512) / cs | 0, cpr = 512 / cs;
    let rgb = null;
    if (bitmap) {
      const bm_addr = mpof * 0x20000;
      const bw = (r(0x28) >> (n * 8) & 0xFF) >> 2 & 3;
      const w = bw & 2 ? 1024 : 512, h = bw & 1 ? 512 : 256;
      const i = ((iy & (h - 1)) * w + (ix & (w - 1))) | 0;
      minP = Math.min(minP, bm_addr + i * 4); maxP = Math.max(maxP, bm_addr + i * 4);
      const v = vw(bm_addr + i * 4) << 16 | vw(bm_addr + i * 4 + 2);
      if (v & 0x80000000) rgb = (v & 0xFF) << 16 | (v & 0xFF00) | (v >> 16 & 0xFF); else trGB++;
    } else {
      const pnd = (plane[pl] + page * page_bytes + (cy * cpr + cx) * (word1 ? 2 : 4)) | 0;
      minP = Math.min(minP, pnd & 0x7FFFE); maxP = Math.max(maxP, pnd & 0x7FFFE);
      let chr, pal, hf, vf;
      if (word1) {
        const w = vw(pnd);
        pal = colors === 0 ? (w >> 12 & 0xF) | (supp >> 1 & 0x70) : (w >> 8 & 0x70);
        hf = w & 0x400; vf = w & 0x800;
        chr = cell2x2 ? ((w & 0x3FF) << 2 | supp & 3 | (supp & 0x1C) << 10) : (w & 0x3FF | (supp & 0x1F) << 10);
      } else {
        const w0 = vw(pnd), w1 = vw(pnd + 2);
        hf = w0 & 0x4000; vf = w0 & 0x8000; pal = w0 & 0x7F; chr = w1 & 0x7FFF;
      }
      let pxx = ix % cs, pyy = iy % cs;
      if (hf) pxx = cs - 1 - pxx;
      if (vf) pyy = cs - 1 - pyy;
      let base = chr << chrShift;
      if (cell2x2) base += ((pyy >> 3) * 2 + (pxx >> 3)) * [32, 64, 128, 128, 256][colors];
      const i = ((pyy & 7) * 8 + (pxx & 7)) | 0;
      minB = Math.min(minB, base + i * 4); maxB = Math.max(maxB, base + i * 4);
      if (colors === 4 || colors === 3) {
        const v = colors === 4 ? (vw(base + i * 4) << 16 | vw(base + i * 4 + 2)) : vw(base + i * 2);
        const on = colors === 4 ? v & 0x80000000 : v & 0x8000;
        if (on) rgb = colors === 4 ? (v & 0xFF) << 16 | (v & 0xFF00) | (v >> 16 & 0xFF) : rgb555(v);
        else trGB++;
      } else {
        const v = colors === 0 ? ((vb(base + (i >> 1)) >> (i & 1 ? 0 : 4)) & 0xF) : colors === 1 ? vb(base + i) : vw(base + i * 2) & 0x7FF;
        if (v === 0) trZero++; else rgb = cramAt((colors === 0 ? pal * 16 : (pal & 0x70) * 16) + v + caos);
      }
    }
    if (rgb !== null) { px[y * W + x] = rgb; drawn++; }
  }
  stats.push(`NBG${n} colors=${colors} bitmap=${bitmap} 2x2=${cell2x2} word1=${word1} plane=${plane.map((p) => '0x' + (p & 0x7ffff).toString(16)).join('/')} 画出=${drawn} 因display位透明=${trGB} 因0号色透明=${trZero} 名称表读址 0x${minP.toString(16)}..0x${maxP.toString(16)} 图案读址 0x${minB.toString(16)}..0x${maxB.toString(16)}`);
}

// 写 PNG（filter 0）
const raw = Buffer.alloc(W * (H * 3 + 1));
for (let y = 0; y < H; y++) { raw[y * (W * 3 + 1)] = 0; for (let x = 0; x < W; x++) { const c = px[y * W + x], o = y * (W * 3 + 1) + 1 + x * 3; raw[o] = c >> 16 & 0xFF; raw[o + 1] = c >> 8 & 0xFF; raw[o + 2] = c & 0xFF; } }
const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const body = Buffer.concat([Buffer.from(type), data]); const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(body) >>> 0); return Buffer.concat([len, body, crc]); };
let T = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; T[n] = c >>> 0; }
function crc32(b) { let c = 0xFFFFFFFF; for (const x of b) c = T[(c ^ x) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4); ihdr[8] = 8; ihdr[9] = 2;
fs.writeFileSync(process.argv[3], Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]));
console.log(`${W}x${H} CRAM模式=${cramMode} 背屏色=0x${back.toString(16)}`);
for (const s of stats) console.log(' ', s);
