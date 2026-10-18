// Exact upstream algorithm, MIT license; no game bytes. Source commit 38a153d273f448ad1953d0b89497470443fd590e
/*
MIT License

Copyright (c) 2026 thezerodivide

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
'use strict';
// Core of the 1440-slot spellbook patch for the RoF2 eqgame.exe. No file or console I/O here.
// build() checks every spot it will change BEFORE changing anything, and throws Refusal if anything is off.
const BASE = 0x400000;

class Refusal extends Error {}

function parsePe(buf) {
  if (buf.length < 0x400 || buf[0] !== 0x4d || buf[1] !== 0x5a) throw new Refusal('This is not a Windows program file.');
  const peo = buf.readUInt32LE(0x3c);
  if (peo + 24 > buf.length || buf.toString('latin1', peo, peo + 2) !== 'PE') throw new Refusal('This is not a Windows program file.');
  const nsec = buf.readUInt16LE(peo + 6);
  const optsz = buf.readUInt16LE(peo + 20);
  const opt = peo + 24;
  const secTab = opt + optsz;
  const sec = [];
  for (let i = 0; i < nsec; i++) {
    const o = secTab + i * 40;
    sec.push({
      o, name: buf.toString('latin1', o, o + 8).replace(/\0/g, ''),
      vs: buf.readUInt32LE(o + 8), va: buf.readUInt32LE(o + 12),
      rs: buf.readUInt32LE(o + 16), raw: buf.readUInt32LE(o + 20),
    });
  }
  const text = sec.find(s => s.name === '.text');
  const reloc = sec.find(s => s.name === '.reloc');
  if (!text || !reloc) throw new Refusal('This does not look like the RoF2 eqgame.exe (missing code sections).');
  return { peo, nsec, opt, secTab, sec, text, reloc };
}

const hasLaa = buf => { const p = parsePe(buf); return (buf.readUInt16LE(p.peo + 22) & 0x20) !== 0; };
const hasSpellbookSection = buf => parsePe(buf).sec.some(s => s.name === '.sbook');

// table: [{va, expect, replace}] (hex strings). setLaa: also set the 4GB flag. Returns the patched Buffer.
function build(buf, table, setLaa) {
  const pe = parsePe(buf);
  const { peo, nsec, opt, secTab, sec, text, reloc } = pe;
  if (sec.some(s => s.name === '.sbook')) throw new Refusal('This exe already has the spellbook patch (it has a .sbook section).');
  const va2off = va => {
    const r = va - BASE;
    if (r < text.va || r >= text.va + text.rs) throw new Refusal('Internal error: address outside the code section.');
    return r - text.va + text.raw;
  };
  const hex = s => Buffer.from(s, 'hex');
  const u32 = v => { const b = Buffer.alloc(4); b.writeUInt32LE(v >>> 0); return b; };
  const rel32 = (from, to) => u32((to - from) >>> 0);
  const out = Buffer.from(buf);
  const ORIG_READ = 0x57b600;

  // ---- 1. check everything first
  let bad = 0, firstBad = '';
  for (const p of table) {
    const o = va2off(parseInt(p.va, 16)), e = hex(p.expect);
    if (e.length !== hex(p.replace).length) throw new Refusal('Internal error: patch table length mismatch at ' + p.va);
    if (!buf.subarray(o, o + e.length).equals(e)) { bad++; if (!firstBad) firstBad = p.va; }
  }
  if (bad) throw new Refusal(bad + ' of ' + table.length + ' spots (first at ' + firstBad + ') do not hold what this patch expects. This is not the RoF2 eqgame.exe the patch was made for, or it has other changes in the same places.');
  const site1 = 0x57cbd1, site2 = 0x578fd6;
  const exp1 = Buffer.concat([hex('68d0020000' + '8d97bc1a0000' + '52' + '8bce' + 'e8'), rel32(0x57cbe4, ORIG_READ)]);
  if (!buf.subarray(va2off(site1), va2off(site1) + exp1.length).equals(exp1)) throw new Refusal('The profile-reading code is not what this patch expects (hook 1).');
  if (!buf.subarray(va2off(site2), va2off(site2) + 7).equals(hex('8bbcb3bc1a0000'))) throw new Refusal('The spellbook copy code is not what this patch expects (hook 2).');

  // ---- 2. in-place byte patches
  for (const p of table) hex(p.replace).copy(out, va2off(parseInt(p.va, 16)));

  // ---- 3. new section .sbook: caves + the profile staging array
  const sizeOfImage = buf.readUInt32LE(opt + 56);
  const newRVA = sizeOfImage;
  const SEC_VS = 0x2000, CAVE_RAW = 0x200;
  const BG_OFF = 0x200, BG_BYTES = 1440 * 4, FLAG_OFF = BG_OFF + BG_BYTES;
  const abs = off => BASE + newRVA + off;
  const BG = abs(BG_OFF), FLAG = abs(FLAG_OFF);
  const cave = Buffer.alloc(CAVE_RAW, 0xCC);
  const relocs = [];
  function emit(off, parts) {
    let p = off;
    for (const x of parts) {
      if (typeof x === 'string') { const b = hex(x); b.copy(cave, p); p += b.length; }
      else if (x.abs !== undefined) { u32(x.abs).copy(cave, p); relocs.push(p); p += 4; }
      else { rel32(abs(p) + 4, x.call || x.jmp).copy(cave, p); p += 4; }
    }
    return p;
  }
  const H1440 = u32(1440).toString('hex');
  emit(0x00, [
    '50', '51', '57', 'bf', { abs: BG }, 'b9' + H1440, '83c8ff', 'fc', 'f3ab', '5f', '59', '58',
    '68' + H1440, '68', { abs: BG }, '8bce', 'e8', { call: ORIG_READ },
    'c705', { abs: FLAG }, '01000000', '56', '57', 'be', { abs: BG }, '8dbfbc1a0000',
    'b9d0020000', 'fc', 'f3a5', '5f', '5e', 'c3',
  ]);
  const COPY_BACK = 0x578fdd;
  emit(0x80, [
    '81fed0020000', '730c', '8bbcb3bc1a0000', 'e9', { jmp: COPY_BACK },
    '833d', { abs: FLAG }, '00', 'bfffffffff', '7407', '8b3cb5', { abs: BG }, 'e9', { jmp: COPY_BACK },
  ]);
  { const b = Buffer.alloc(19, 0x90); b[0] = 0xe8; rel32(site1 + 5, abs(0x00)).copy(b, 1); b.copy(out, va2off(site1)); }
  { const b = Buffer.alloc(7, 0x90); b[0] = 0xe9; rel32(site2 + 5, abs(0x80)).copy(b, 1); b.copy(out, va2off(site2)); }

  // ---- 4. PE edits
  const hdrEnd = secTab + nsec * 40;
  const firstRaw = Math.min(...sec.map(s => s.raw));
  if (hdrEnd + 40 > firstRaw) throw new Refusal('No room in the file header for another section.');
  if (!buf.subarray(hdrEnd, hdrEnd + 40).every(b => b === 0)) throw new Refusal('The section header slot is not empty.');
  for (const r of relocs) if (r >= 0x1000) throw new Refusal('Internal error: fixup beyond first page.');
  const entries = relocs.map(r => 0x3000 | r);
  if (entries.length % 2) entries.push(0);
  const blk = Buffer.alloc(8 + entries.length * 2);
  blk.writeUInt32LE(newRVA, 0); blk.writeUInt32LE(blk.length, 4);
  entries.forEach((e, i) => blk.writeUInt16LE(e, 8 + i * 2));
  const dd5 = opt + 96 + 5 * 8;
  if (buf.readUInt32LE(dd5) !== reloc.va) throw new Refusal('The relocation directory is not where this patch expects.');
  const dirSize = buf.readUInt32LE(dd5 + 4);
  if (reloc.rs - dirSize < blk.length) throw new Refusal('Not enough room at the end of the relocation section.');
  blk.copy(out, reloc.raw + dirSize);
  out.writeUInt32LE(dirSize + blk.length, dd5 + 4);
  if (reloc.vs < dirSize + blk.length) out.writeUInt32LE(dirSize + blk.length, reloc.o + 8);

  const raw = Buffer.concat([out, cave]);
  raw.write('.sbook\0\0', hdrEnd, 'latin1');
  raw.writeUInt32LE(SEC_VS, hdrEnd + 8);
  raw.writeUInt32LE(newRVA, hdrEnd + 12);
  raw.writeUInt32LE(CAVE_RAW, hdrEnd + 16);
  raw.writeUInt32LE(out.length, hdrEnd + 20);
  raw.writeUInt32LE(0xE0000060, hdrEnd + 36);
  raw.writeUInt16LE(nsec + 1, peo + 6);
  raw.writeUInt32LE(sizeOfImage + SEC_VS, opt + 56);
  if (setLaa) raw.writeUInt16LE(raw.readUInt16LE(peo + 22) | 0x20, peo + 22);
  raw.writeUInt32LE(0, opt + 64);
  let sum = 0;
  const n = raw.length;
  for (let i = 0; i < n; i += 2) {
    sum += (i + 1 < n ? raw.readUInt16LE(i) : raw[i]);
    sum = (sum & 0xffff) + (sum >>> 16);
  }
  sum = (sum & 0xffff) + (sum >>> 16);
  raw.writeUInt32LE(((sum & 0xffff) + n) >>> 0, opt + 64);
  return raw;
}

module.exports = { build, hasLaa, hasSpellbookSection, Refusal };
