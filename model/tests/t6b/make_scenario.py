#!/usr/bin/env python3
"""T6b: a deterministic SYNTHETIC 2-day scenario (not data) as the 1 Hz layer would hand it to hg_fw_second(), plus the
per-minute context. Writes sec.bin (52-B hg_fw_sec_t per second) and ctx.bin (u16 mod, i32 day, f32 vbat per minute).
Day 1 calm (26 C room); day 2 afternoon heat wave room (to 37 C) with HR rising; short PPG dropouts (motion) every 40 min."""
import struct, math, random, sys
random.seed(61)
out = sys.argv[1]
fs = open(out + '/sec.bin', 'wb'); fc = open(out + '/ctx.bin', 'wb')
N = 2 * 1440
for m in range(N):
    day, mod = 20000 + (600 + m) // 1440, (600 + m) % 1440
    hot = m >= 1440 + 180 and m < 1440 + 660
    hh = 0.0 if not hot else min(1.0, (m - 1620) / 240.0) * (1.0 if m < 1440 + 540 else max(0.0, (1440 + 660 - m) / 120.0))
    ta = 26.0 + 11.0 * hh; t1 = 33.6 + 2.6 * hh; t2 = t1 - 1.3 + 0.9 * hh; rh = 45 - 10 * hh
    hr_mean = 68 + 40 * hh
    night = mod < 420 or mod >= 1380
    drop = (m % 40) < 3
    for s in range(60):
        ppg_on = 1 if s < 30 or hh > 0.2 else 0
        q = 2 if (drop or s < 11) else 4
        hr = hr_mean + random.gauss(0, 1.5) if q == 4 else 0.0
        sd = 0.0008 if night else 0.025
        a_m2 = (sd * (0.7 + 0.6 * random.random())) ** 2 * 25
        z = (5.0 if night else 20.0 + 15 * random.random())
        fs.write(struct.pack('<fffffBBxxfIffHxxff', t1 + random.gauss(0, 0.02), t2 + random.gauss(0, 0.02), ta + random.gauss(0, 0.05),
                             rh + random.gauss(0, 0.3), hr if hr > 0 else float('nan'), q, ppg_on, 0.4 + 0.05 * random.random(),
                             110000, 1.0, a_m2, 25, 1.0 + 4 * sd, z))
    fc.write(struct.pack('<Hif', mod, day, 3.95))
print('wrote', N, 'minutes')
