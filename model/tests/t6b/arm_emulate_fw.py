#!/usr/bin/env python3
"""T6b: the whole 09 minute pipeline FROM THE ACTUAL ARM ELF (hg_fw_init, hg_fw_twin_load, hg_fw_second x60, hg_fw_minute)
under Unicorn Cortex-M4F, on make_scenario.py's SYNTHETIC seconds; compares every minute's guardian log record (state,
screen, core, f20, tiers, why, valid bits...) with fw_trace_host.c (sealed-exam golden flags).
usage: arm_emulate_fw.py <elf> <scenario dir>"""
import struct, sys, math
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
elf = ELFFile(open(sys.argv[1], 'rb')); D = sys.argv[2]
sym = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
uc.mem_map(0x0, 0x100000); uc.mem_map(0x20000000, 0x40000); uc.mem_map(0xE000E000, 0x1000)
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and seg['p_filesz']:
        uc.mem_write(seg['p_vaddr'], seg.data())
        if seg['p_vaddr'] != seg['p_paddr']: uc.mem_write(seg['p_paddr'], seg.data())
uc.mem_write(0xE000ED88, struct.pack('<I', 0xF << 20))
RET = 0x000FFF00; uc.mem_write(RET, b'\x00\xbf\x00\xbf'); SP0 = 0x2003FF00
def call(name, *args):
    sp = SP0
    if len(args) > 4:
        extra = args[4:]; sp -= 8 * ((len(extra) + 1) // 2)
        for i, v in enumerate(extra): uc.mem_write(sp + 4 * i, struct.pack('<I', v & 0xFFFFFFFF))
    for rg, v in zip([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3], args): uc.reg_write(rg, v & 0xFFFFFFFF)
    uc.reg_write(UC_ARM_REG_SP, sp); uc.reg_write(UC_ARM_REG_LR, RET | 1)
    uc.emu_start(sym[name] | 1, RET, timeout=100_000_000)
    r = uc.reg_read(UC_ARM_REG_R0); return r - (1 << 32) if r & 0x80000000 else r
# scratch RAM well above the image's .bss (the ELF's own statics are not used: we pass our own objects)
FW, G, TW, ACC, PR, SEC, CTX, ACT, SC = 0x20010000, 0x20020000, 0x20022000, 0x20022200, 0x20022400, 0x20022500, 0x20022600, 0x20022700, 0x20022800
for a, n in [(FW, 0x10000), (G, 0x2000)]: uc.mem_write(a, b'\0' * n)
uc.mem_write(PR, struct.pack('<fffB3x', 75.0, 0.0, 26.0, 0))
call('hg_fw_init', FW); call('hg_fw_twin_load', G, PR, TW, ACC, 0, 0, SC)
sec = open(D + '/sec.bin', 'rb').read(); ctx = open(D + '/ctx.bin', 'rb').read(); host = open(D + '/act_host.bin', 'rb').read()
N = len(ctx) // 10
ST = ['OK', 'DRINK', 'COOL', 'CHECK', 'DANGER', 'IMOK', 'NOT_WORN', 'BATTERY', 'HELP']
mis_state = mis_any = 0; maxcore = 0.0; first = []; cnt_a = {}; cnt_h = {}; v12 = []
for m in range(N):
    for s in range(60):
        uc.mem_write(SEC, sec[52 * (60 * m + s): 52 * (60 * m + s) + 52]); call('hg_fw_second', FW, SEC)
    mod, day, vb = struct.unpack('<Hif', ctx[10 * m: 10 * m + 10])
    # ARM hg_fw_ctx_t: u16 mod @0, i32 day @4, u8 charging @8, f32 vbat @12, i8 ble @16, ptr @20, u8 has_fc @24
    uc.mem_write(CTX, struct.pack('<H2xiB3xfb3xIB3x', mod, day, 0, vb, -1, 0, 0))
    call('hg_fw_minute', FW, G, TW, ACC, CTX, (60000 * m) & 0xFFFFFFFF, ACT)
    a = bytes(uc.mem_read(ACT, 51)); h = host[51 * m: 51 * m + 51]
    ga, gh = a[27:51], h[27:51]
    sa, sh = ga[9], gh[9]
    cnt_a[ST[sa]] = cnt_a.get(ST[sa], 0) + 1; cnt_h[ST[sh]] = cnt_h.get(ST[sh], 0) + 1
    ca, chh = struct.unpack('<H', ga[4:6])[0], struct.unpack('<H', gh[4:6])[0]
    if ca and chh: maxcore = max(maxcore, abs(ca - chh) / 100)
    if sa != sh: mis_state += 1
    if ga[4:23] != gh[4:23]: mis_any += 1
    if (sa != sh or ga[10] != gh[10]) and len(first) < 6:
        first.append(f'minute {m} (mod {mod} day {day - 20000}): ARM state {ST[sa]} tiers {ga[10] >> 4} f20 {struct.unpack("<H", ga[7:9])[0] / 100} | host state {ST[sh]} tiers {gh[10] >> 4} f20 {struct.unpack("<H", gh[7:9])[0] / 100}')
print(f'{N} minutes. State mismatches ARM vs host golden: {mis_state}; minutes with any guardian-record difference: {mis_any}; max |core| diff {maxcore:.2f} C')
print('state minutes ARM :', cnt_a); print('state minutes host:', cnt_h)
for f in first: print('  ' + f)
