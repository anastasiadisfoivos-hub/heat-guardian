#!/usr/bin/env python3
"""Run 08_logger's own record code FROM THE ARM IMAGE (Unicorn Cortex-M4F) with missing sensors (NaN) and check that
the record says "absent". It does not use the source: buildRecordBase() and astdField() are called in the .elf the
.uf2 is made from. The harness is the tests/t6b one (T6b); peripherals are plain zeroed RAM and SoftDevice SVCs return 0.
usage: emu_08_nan.py <08_logger.ino.elf> [<label>]     exit 1 on any failure"""
import struct, sys, math, re
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
elf = ELFFile(open(sys.argv[1], 'rb')); label = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
sym = {}
for s in elf.get_section_by_name('.symtab').iter_symbols():
    if s.name: sym.setdefault(s.name, s['st_value'])
def find(plain):   # C++ statics are mangled _ZL<len><name>...
    for k in (plain, '_ZL%d%s' % (len(plain), plain)):
        if k in sym: return sym[k]
    for k, v in sym.items():
        if re.match(r'_ZL%d%s' % (len(plain), plain), k): return v
    return None
uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
uc.mem_map(0x0, 0x100000); uc.mem_map(0x20000000, 0x40000); uc.mem_map(0xE000E000, 0x1000)
uc.mem_map(0x40000000, 0x100000); uc.mem_map(0x50000000, 0x1000)   # nRF peripherals + GPIO: zeroed RAM
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and seg['p_filesz']:
        uc.mem_write(seg['p_vaddr'], seg.data())
        if seg['p_vaddr'] != seg['p_paddr']: uc.mem_write(seg['p_paddr'], seg.data())
uc.mem_write(0xE000ED88, struct.pack('<I', 0xF << 20))   # CPACR: FPU on
def on_intr(u, intno, d): u.reg_write(UC_ARM_REG_R0, 0)    # SVC (SoftDevice call) -> NRF_SUCCESS, value 0
uc.hook_add(UC_HOOK_INTR, on_intr)
RET = 0x000FFF00; uc.mem_write(RET, b'\x00\xbf\x00\xbf'); SP0 = 0x2003FF00
def call(addr, r0=0, s0=None):
    uc.reg_write(UC_ARM_REG_R0, r0 & 0xFFFFFFFF)
    if s0 is not None: uc.reg_write(UC_ARM_REG_S0, struct.unpack('<I', struct.pack('<f', s0))[0])
    uc.reg_write(UC_ARM_REG_SP, SP0); uc.reg_write(UC_ARM_REG_LR, RET | 1)
    uc.emu_start(addr | 1, RET, timeout=50_000_000)
    return uc.reg_read(UC_ARM_REG_R0)
def wf(name, v): uc.mem_write(find(name), struct.pack('<f', v))
def wb(name, v): uc.mem_write(find(name), bytes([v]))
REC = 0x2003E000; ABS_T, ABS_RH = 0x7FFF, 255
fails = 0
def check(what, got, want):
    global fails
    ok = got == want; fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {what}: got {got:#x} want {want:#x}")
brb, asf = find('buildRecordBase'), find('astdField')
print(f"== {label}: 08 record code run from the ARM image")
if brb is None: print("  FAIL buildRecordBase not in the image"); sys.exit(1)
def rec(t1, t2, ta, rh, skin=1, ref=1, sht=1):
    wb('hasSkin', skin); wb('hasRef', ref); wb('hasSht', sht)
    wf('t1C', t1); wf('t2C', t2); wf('tairC', ta); wf('rhPct', rh)
    uc.mem_write(REC, b'\xAA' * 24); call(brb, REC)
    t_ms, a, b, c, rhb = struct.unpack('<Ihhhb', bytes(uc.mem_read(REC, 11)))
    return a & 0xFFFF, b & 0xFFFF, c & 0xFFFF, rhb & 0xFF
nan = float('nan')
a, b, c, r = rec(33.25, 31.5, 27.0, 45.4)
print("  sensors present: t1 33.25 t2 31.50 air 27.00 rh 45.4")
check('t1_c100', a, 3325); check('t2_c100', b, 3150); check('tair_c100', c, 2700); check('rh', r, 45)
a, b, c, r = rec(nan, nan, nan, nan)
print("  sensors fitted but the reading is NaN (failed read before the first good one)")
check('t1_c100', a, ABS_T); check('t2_c100', b, ABS_T); check('tair_c100', c, ABS_T); check('rh', r, ABS_RH)
a, b, c, r = rec(nan, nan, nan, nan, 0, 0, 0)
print("  sensors not fitted")
check('t1_c100', a, ABS_T); check('t2_c100', b, ABS_T); check('tair_c100', c, ABS_T); check('rh', r, ABS_RH)
if asf is None: print("  (astdField not in this image: older build)")
else:
    print("  IMU: a_std NaN (no samples this second) and 0.0123 g")
    check('astd_1e4(NaN)', call(asf, 0, nan) & 0xFFFF, 0xFFFF); check('astd_1e4(0.0123)', call(asf, 0, 0.0123) & 0xFFFF, 123)
print(f"EMU_08_NAN: {'PASS' if not fails else 'FAIL (%d)' % fails}")
sys.exit(1 if fails else 0)
