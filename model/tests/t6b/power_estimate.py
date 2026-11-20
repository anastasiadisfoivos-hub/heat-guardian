#!/usr/bin/env python3
"""T6b: ESTIMATE (no board) of 09_guardian's average current, from R4 A6's table with every row re-derived from what the 09
source actually configures. Rows marked [R4] are taken unchanged from research/R4 A6; rows marked [09] are recomputed."""
rows = [
 ("XIAO floor, QSPI deep power-down [R4]", 0.005),
 ("CPU: loop wakes 100 Hz (delay(10)) ~30 us each x 3.3 mA [09 est]", 100 * 30e-6 * 3.3),
 ("CPU: IMU 25 Hz, 7-byte TWIM read @100 kHz busy-polled ~0.8 ms x 3.3 mA [09]", 25 * 0.8e-3 * 3.3),
 ("CPU: PPG FIFO every 100 ms, 10 samples x 6 B (SpO2 mode) @100 kHz ~5.5 ms x 3.3 mA x duty 0.5 [09]", 10 * 5.5e-3 * 3.3 * 0.5),
 ("MAX30102 IR LED 6.2 mA x 411 us x 400 sps (SPO2_CONFIG 0x2F) = 16.4 % duty, x PPG duty 0.5 [09]", 6.2 * 411e-6 * 400 * 0.5),
 ("MAX30102 red LED same PA, 1 s in 4, x PPG duty 0.5 [09]", 6.2 * 411e-6 * 400 * 0.25 * 0.5),
 ("MAX30102 AFE 0.6 + module LDO 0.08 mA, x PPG duty 0.5 [R4 values, 09 duty]", 0.68 * 0.5),
 ("ICM-20649 accel-only LP 25 Hz [R4]", 0.05),
 ("TMP117 x2 one-shot 8x avg every 5 s (135 uA x 125 ms / 5 s x 2) + SHTC3 [09]", 2 * 0.135 * 0.125 / 5 + 0.001),
 ("BLE connected 990 ms / adv 1022.5 ms [R4]", 0.015),
 ("Screen 15 min/day at 60 % (15 mA) + panel SLPIN 0.05 mA [R4]", 15 * 15 / 1440 + 0.05),
 ("Haptics 2 min/day at 80 mA + DRV standby [R4]", 0.12),
 ("Battery divider [R4]", 0.002),
 ("Breakout regulators and pull-ups [R4 estimate]", 0.20),
]
tot = sum(v for _, v in rows)
for k, v in rows: print(f"{v:7.3f} mA  {k}")
print(f"{tot:7.3f} mA  SUM;  +20 % margin -> {tot*1.2:.2f} mA")
cap = 250 * 0.85
for name, extra in [("calm day (above)", 0.0),
                    ("a tier on all day (PPG continuous: LEDs + AFE + FIFO CPU x2)", 6.2*411e-6*400*1.25*0.5 + 0.68*0.5 + 10*5.5e-3*3.3*0.5),
                    ("HELP latched with no phone ack: screen on at 100 % (~25 mA) + PPG continuous", 25.0 + 6.2*411e-6*400*1.25*0.5 + 0.68*0.5)]:
    i = (tot + extra) * 1.2
    print(f"ESTIMATE {name}: {i:.2f} mA -> {cap / i:.0f} h = {cap / i / 24:.1f} days on 250 mAh x 0.85")
print("R4 A6 assumed 100 sps x 411 us (4.1 % LED duty) and 25 % PPG duty: 0.23 mA for the PPG; 09 runs 400 sps (avg 4) and 50 % duty.")
