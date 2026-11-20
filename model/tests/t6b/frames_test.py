#!/usr/bin/env python3
"""T6b: drive frames_test (frozen hg_cmd_parse) with B4's vectors, the dashboard's frames (hg_ble.js run in node if present,
else re-implemented here byte for byte from hg_ble.js) and malformed frames. Prints PASS/FAIL lines."""
import json, random, subprocess, sys
R = '/home/claude/hg_ai'
BIN = sys.argv[1]
V = json.load(open(f'{R}/tomorrow/tests/ble_vectors.json'))
def crc8(b):
    c = 0
    for x in b:
        c ^= x
        for _ in range(8): c = ((c << 1) ^ 7) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c
seal = lambda b: bytes(b) + bytes([crc8(b)])
lines = []
for i, h in enumerate(V['forecast_chunks_hex']): lines.append((f'b4_fc{i}', h))
lines.append(('b4_safe', V['safe_hours_hex']))
# dashboard frames (hg_ble.js cmdTime / cmdFamilyAck / cmdDebug)
t = 1794470400
lines.append(('dash_time', seal([0x10, t & 255, (t >> 8) & 255, (t >> 16) & 255, (t >> 24) & 255, 8]).hex()))
lines.append(('dash_ack', seal([0x12, 1, 0x34, 0x12, 0, 0]).hex()))
lines.append(('dash_debug', seal([0x1F, 60]).hex()))
# 20-byte padded TIME (the B4 layout says EVERY CMD frame is 20 B with CRC at byte 19)
pad = [0x10, t & 255, (t >> 8) & 255, (t >> 16) & 255, (t >> 24) & 255, 8] + [0] * 13
lines.append(('time_20B_crc_at_19', seal(pad).hex()))
# malformed
good = bytes.fromhex(V['forecast_chunks_hex'][0])
random.seed(6)
for k in range(200):
    b = bytearray(good); i = random.randrange(20); b[i] ^= 1 << random.randrange(8); lines.append((f'flip{k}', b.hex()))
lines.append(('short_time', seal([0x10, 1, 2, 3]).hex()))
lines.append(('empty1', '10'))
lines.append(('unknown_op', seal([0x55, 1, 2, 3, 4, 5]).hex()))
lines.append(('ack_type0', seal([0x12, 0, 0, 0, 0, 0]).hex()))
lines.append(('ack_type9', seal([0x12, 9, 0, 0, 0, 0]).hex()))
import struct
nanb = list(struct.pack('<f', float('nan'))); infb = list(struct.pack('<f', float('inf')))
lines.append(('profile_nan', seal([0x13, 2] + nanb).hex()))
lines.append(('profile_inf', seal([0x13, 2] + infb).hex()))
lines.append(('time_zero', seal([0x10, 0, 0, 0, 0, 0]).hex()))
lines.append(('time_ffff', seal([0x10, 255, 255, 255, 255, 127]).hex()))
lines.append(('time_tz_m128', seal([0x10, t & 255, (t >> 8) & 255, (t >> 16) & 255, (t >> 24) & 255, 0x80]).hex()))
fcm = bytearray(good); fcm[6] = (fcm[6] & ~0x18) | (1 << 3); fcm[19] = crc8(fcm[:19]); lines.append(('fc_mixed_chunk', fcm.hex()))
# random garbage frames of 1..20 bytes: how many does the parser accept?
for k in range(5000):
    n = random.randint(1, 20); b = bytes([random.choice([0x10, 0x11, 0x12, 0x13, 0x14, 0x1F, random.randrange(256)])]) + bytes(random.randrange(256) for _ in range(n - 1))
    lines.append((f'rnd{k}', b.hex()))
out = subprocess.run([BIN], input='\n'.join(f'{a} {b}' for a, b in lines), capture_output=True, text=True).stdout.splitlines()
res = {l.split()[0]: l for l in out if not l.startswith('FC')}
fcl = [l for l in out if l.startswith('FC')][0]
def ok(c, msg): print(('PASS  ' if c else 'FAIL  ') + msg)
ok(all(' rc=17 ' in res[f'b4_fc{i}'] + ' ' for i in range(4)) and 'complete=1' in res['b4_fc3'], 'B4 forecast chunks 0-3 parse, buffer complete')
# compare decoded hours
fch = [tuple(int(x) for x in s.split('/')) for s in fcl.split()[1:]]
bad = 0
for h, d in enumerate(V['decoded_hours']):
    t_in, rh, fl = fch[h]
    if t_in != d['t_in'] or rh != d['rh_in'] or bool(fl & 1) != d['heat_day'] or bool(fl & 2) != d['night_heat'] or bool(fl & 4) != d['safe']: bad += 1
ok(bad == 0, f'24 decoded forecast hours == ble_vectors decoded_hours ({bad} mismatches)')
s = res['b4_safe']
ok(f"bitmap={V['safe_hours_bitmap']}" in s and f"plan={V['plan_id']}" in s and V['tag'] in s, f'SAFE_HOURS == vectors: {s}')
ok(' rc=16 ' in res['dash_time'] + ' ' and 'tz_q=8' in res['dash_time'], 'dashboard TIME frame accepted: ' + res['dash_time'])
ok(' rc=18 ' in res['dash_ack'] + ' ', 'dashboard FAMILY_ACK accepted')
ok(' rc=31' in res['dash_debug'], 'dashboard DEBUG accepted')
print('INFO  20-byte TIME with CRC at byte 19 (B4 "every frame is 20 B" rule): ' + res['time_20B_crc_at_19'])
flips = [res[f'flip{k}'] for k in range(200)]
ok(all(' rc=-' in f for f in flips), f'200 single-bit flips of a valid FORECAST frame all rejected ({sum(" rc=-" in f for f in flips)}/200)')
for k in ['short_time', 'empty1', 'unknown_op', 'ack_type0', 'ack_type9', 'profile_nan', 'fc_mixed_chunk']:
    ok(' rc=-' in res[k], f'{k} rejected: {res[k]}')
for k in ['profile_inf', 'time_zero', 'time_ffff', 'time_tz_m128']:
    print(f'INFO  {k}: {res[k]}')
acc = [l for k, l in res.items() if k.startswith('rnd') and ' rc=-' not in l]
print(f'INFO  random frames accepted: {len(acc)}/5000 (CRC-8 chance acceptance ~1/256 of well-formed-length ones)')
for l in acc[:8]: print('      ' + l)
