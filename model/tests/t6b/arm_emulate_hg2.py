#!/usr/bin/env python3
"""T6b: run hg2_init + hg2_step_aux(aux=NULL, = hg2_step; hg2_step itself is not linked) FROM THE ACTUAL 09 ARM ELF (arduino-cli build, core flag -Ofast) under Unicorn (Cortex-M4F)
on the same SYNTHETIC inputs as hg2_trace_host.c (frozen sources, guardian/c Makefile flags = the sealed-exam golden), and
compare every output field. Also runs hg2_check_crc() from the ELF.
usage: arm_emulate_hg2.py <elf> <in.bin> <out_host.bin>"""
import struct, sys, math
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
elf = ELFFile(open(sys.argv[1], 'rb'))
sym = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
uc.mem_map(0x0, 0x100000); uc.mem_map(0x20000000, 0x40000); uc.mem_map(0xE000E000, 0x1000)
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and seg['p_filesz']:
        uc.mem_write(seg['p_vaddr'], seg.data())
        if seg['p_vaddr'] != seg['p_paddr']: uc.mem_write(seg['p_paddr'], seg.data())
uc.mem_write(0xE000ED88, struct.pack('<I', 0xF << 20))
RET = 0x000FFF00; uc.mem_write(RET, b'\x00\xbf\x00\xbf'); SP0 = 0x2003F000
def call(name, *args):
    for rg, v in zip([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3], args): uc.reg_write(rg, v & 0xFFFFFFFF)
    uc.reg_write(UC_ARM_REG_SP, SP0); uc.reg_write(UC_ARM_REG_LR, RET | 1)
    uc.emu_start(sym[name] | 1, RET, timeout=50_000_000)
    r = uc.reg_read(UC_ARM_REG_R0); return r - (1 << 32) if r & 0x80000000 else r
print('hg2_check_crc() on the ARM image:', call('hg2_check_crc'))
ST, PR, TW, IN, OUT = 0x20030000, 0x20031000, 0x20031100, 0x20031200, 0x20031300
uc.mem_write(PR, struct.pack('<fffB3x', 75.0, 0.0, 26.0, 0))
call('hg_twin_defaults', TW); call('hg2_init', ST, PR, TW)
inb = open(sys.argv[2], 'rb').read(); outb = open(sys.argv[3], 'rb').read()
N = len(inb) // 36
names = ['core_now','core_20','core_30','sd_now','sd_20','sd_30','f20_eff','f30_eff','logit_p38','logit_p385','strain','kf','core_flux']
maxd = {k: 0.0 for k in names}; nanmis = {k: 0 for k in names}; flagmis = 0; first = None
for i in range(N):
    uc.mem_write(IN, inb[36*i:36*i+36]); call('hg2_step_aux', ST, IN, OUT, 0)
    a = struct.unpack('<13f4B', bytes(uc.mem_read(OUT, 56))); h = struct.unpack('<13f4B', outb[56*i:56*i+56])
    for k, x, y in zip(names, a[:13], h[:13]):
        if math.isnan(x) != math.isnan(y): nanmis[k] += 1; first = first or (i, k, x, y)
        elif not math.isnan(x): maxd[k] = max(maxd[k], abs(x - y))
    if a[13:] != h[13:]: flagmis += 1; first = first or (i, 'flags', a[13:], h[13:])
print(f'{N} minutes, ARM image {sys.argv[1].split("/")[-1]} vs host golden flags (-O2 -fsingle-precision-constant -ffp-contract=off):')
for k in names: print(f'  {k:11s} max |diff| {maxd[k]:.3e}   NaN-pattern mismatches {nanmis[k]}')
print(f'  flux_valid/hr_valid/valid/why mismatching minutes: {flagmis}')
print('  first mismatch:', first)
