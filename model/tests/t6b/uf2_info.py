#!/usr/bin/env python3
"""T6b: decode a UF2: block count, family id, address range, flags; and compare payload with an Intel hex."""
import struct, sys
d = open(sys.argv[1], 'rb').read()
n = len(d) // 512; fam = set(); addrs = []; flags = set(); payload = {}
for i in range(n):
    b = d[i*512:(i+1)*512]
    m0, m1, fl, addr, size, bno, nblk, fid = struct.unpack('<8I', b[:32])
    assert m0 == 0x0A324655 and m1 == 0x9E5D5157 and struct.unpack('<I', b[508:512])[0] == 0x0AB16F30, 'magic'
    assert bno == i and nblk == n, 'block numbering'
    fam.add(hex(fid)); flags.add(hex(fl)); addrs.append(addr)
    for k in range(size): payload[addr+k] = b[32+k]
print(f'blocks {n}  family {fam}  flags {flags}  start 0x{min(addrs):08x}  end 0x{max(addrs)+256:08x}  bytes {len(payload)}')
if len(sys.argv) > 2:
    hx = {}; base = 0
    for line in open(sys.argv[2]):
        line = line.strip(); r = bytes.fromhex(line[1:]); ln, a, t = r[0], (r[1] << 8) | r[2], r[3]
        if t == 0: 
            for k in range(ln): hx[base + a + k] = r[4+k]
        elif t == 4: base = ((r[4] << 8) | r[5]) << 16
        elif t == 2: base = ((r[4] << 8) | r[5]) << 4
    diff = [a for a in hx if payload.get(a) != hx[a]]
    print(f'hex bytes {len(hx)}  hex range 0x{min(hx):08x}-0x{max(hx)+1:08x}  mismatches vs uf2 {len(diff)}  uf2-only bytes {len(set(payload)-set(hx))}')
