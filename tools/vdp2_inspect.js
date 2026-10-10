// 解析 --dump 尾部的 VDP2 状态。寄存器偏移表取自上游 src/saturnrecomp/hw.py 的 VDP2 名表（每 2 字节一项）。
// 用法: node tools/vdp2_inspect.js <dump.bin> [vramHexAddr] [words]
const fs = require('fs');
const NAMES = `TVMD EXTEN TVSTAT VRSIZE HCNT VCNT - RAMCTL CYCA0L CYCA0U CYCA1L CYCA1U CYCB0L
CYCB0U CYCB1L CYCB1U BGON MZCTL SFSEL SFCODE CHCTLA CHCTLB BMPNA BMPNB PNCN0
PNCN1 PNCN2 PNCN3 PNCR PLSZ MPOFN MPOFR MPABN0 MPCDN0 MPABN1 MPCDN1 MPABN2
MPCDN2 MPABN3 MPCDN3 MPABRA MPCDRA MPEFRA MPGHRA MPIJRA MPKLRA MPMNRA MPOPRA
MPABRB MPCDRB MPEFRB MPGHRB MPIJRB MPKLRB MPMNRB MPOPRB SCXIN0 SCXDN0 SCYIN0
SCYDN0 ZMXIN0 ZMXDN0 ZMYIN0 ZMYDN0 SCXIN1 SCXDN1 SCYIN1 SCYDN1 ZMXIN1 ZMXDN1
ZMYIN1 ZMYDN1 SCXN2 SCYN2 SCXN3 SCYN3 ZMCTL SCRCTL VCSTAU VCSTAL LSTA0U LSTA0L
LSTA1U LSTA1L LCTAU LCTAL BKTAU BKTAL RPMD RPRCTL KTCTL KTAOF OVPNRA OVPNRB
RPTAU RPTAL WPSX0 WPSY0 WPEX0 WPEY0 WPSX1 WPSY1 WPEX1 WPEY1 WCTLA WCTLB WCTLC
WCTLD LWTA0U LWTA0L LWTA1U LWTA1L SPCTL SDCTL CRAOFA CRAOFB LNCLEN SFPRMD CCCTL
SFCCMD PRISA PRISB PRISC PRISD PRINA PRINB PRIR - CCRSA CCRSB CCRSC CCRSD CCRNA
CCRNB CCRR CCRLB CLOFEN CLOFSL COAR COAG COAB COBR COBG COBB`.split(/\s+/).filter(Boolean);

const buf = fs.readFileSync(process.argv[2]);
const regs = buf.subarray(buf.length - 0x200);
const cram = buf.subarray(buf.length - 0x200 - 0x1000, buf.length - 0x200);
const vram = buf.subarray(buf.length - 0x200 - 0x1000 - 0x80000, buf.length - 0x200 - 0x1000);
const r = (o) => (regs[o] << 8 | regs[o + 1]) & 0xFFFF;
const vw = (a) => (vram[(a & 0x7FFFE)] << 8 | vram[(a & 0x7FFFE) + 1]) & 0xFFFF;
const vb = (a) => vram[a & 0x7FFFF];
const hex = (v, n = 4) => '0x' + v.toString(16).padStart(n, '0');

console.log('== 非零寄存器 ==');
for (let i = 0; i < 0x120; i += 2) {
  const v = r(i);
  if (v) console.log((NAMES[i / 2] || '?').padEnd(8), hex(i), hex(v), v.toString(2).padStart(16, '0'));
}
let nzV = 0; for (const b of vram) if (b) nzV++;
let nzC = 0; for (const b of cram) if (b) nzC++;
console.log('== 非零字节 vram', nzV, '/ 524288   cram', nzC, '/ 4096 ==');

const bgon = r(0x20);
console.log('BGON =', hex(bgon), 'NBG0-3 =', [0, 1, 2, 3].map((n) => bgon >> n & 1).join(''),
  'RBG0/1/2/3 =', [4, 5, 6, 7].map((b) => bgon >> b & 1).join(''), 'SPB0/1 =', [8, 9].map((b) => bgon >> b & 1).join(''));
for (let n = 0; n < 4; n++) {
  const on = bgon >> n & 1;
  const chctl = n < 2 ? r(0x28) >> (n * 8) & 0xFF : r(0x2A) >> ((n - 2) * 4) & 0xF;
  const colors = n < 2 ? chctl >> 4 & 7 : chctl >> 1 & 1;
  const bitmap = n < 2 ? chctl >> 1 & 1 : 0;
  const cell2x2 = chctl & 1;
  const pncn = r(0x30 + n * 2);
  const word1 = pncn >> 15 & 1, cnsm = pncn >> 14 & 1, supp = pncn & 0x3FF;
  const plsz = r(0x3A) >> (n * 2) & 3;
  const pw = plsz == 0 ? 1 : 2, ph = plsz == 3 ? 2 : 1;
  const mpof = r(0x3C) >> (n * 4) & 7;
  const page = (cell2x2 ? 0x800 : 0x2000) * (word1 ? 1 : 2);
  const mask = pw * ph - 1;
  const planes = [0, 1, 2, 3].map((i) => ((mpof << 6 | r(0x40 + n * 4 + (i / 2 | 0) * 2) >> ((i & 1) * 8) & 0x3F) & ~mask) * page);
  const prio = r(0xF8 + (n / 2 | 0) * 2) >> ((n & 1) * 8) & 7;
  const b = n < 2 ? 0x70 + n * 0x10 : 0x90 + (n - 2) * 4;
  const sx = n < 2 ? (r(b) & 0x7FF) << 8 | r(b + 2) >> 8 : (r(b) & 0x7FF) << 8;
  const sy = n < 2 ? (r(b + 4) & 0x7FF) << 8 | r(b + 6) >> 8 : (r(b + 2) & 0x7FF) << 8;
  console.log(`NBG${n} on=${on} prio=${prio} colors=${colors} bitmap=${bitmap} 2x2=${cell2x2} word1=${word1} cnsm=${cnsm} supp=${hex(supp)} plane=${hex(page)} planes=${planes.map((p) => hex(p, 5)).join(' ')} scroll=(${sx / 256},${sy / 256}) opaque=${bgon >> (8 + n) & 1}`);
  if (!on) continue;
  const a = planes[0];
  const words = [];
  for (let o = 0; o < 24; o += 2) words.push(hex(vw(a + o)));
  console.log(`   名称表 @${hex(a, 5)}:`, words.join(' '));
  let used = 0; for (let o = 0; o < page; o += 2) if (vw(a + o)) used++;
  console.log(`   该页 512 项中非零项: ${used}`);
}
const spr = [0, 1, 2, 3].map((i) => r(0xF0 + (i / 2 | 0) * 2) >> ((i & 1) * 8) & 7);
console.log('SPRISA..D (sprite prio 0-3) =', spr.join(','), ' SPCTL =', hex(r(0xE0)));
if (process.argv[3]) {
  const base = parseInt(process.argv[3], 16), words = +(process.argv[4] || 32);
  let s = '';
  for (let o = 0; o < words * 2; o += 2) s += hex(vw(base + o)) + ' ';
  console.log('VRAM', process.argv[3] + ':', s);
}
