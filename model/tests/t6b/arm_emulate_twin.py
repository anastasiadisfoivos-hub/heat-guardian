#!/usr/bin/env python3
"""T6b: run the Body Twin save/load code FROM THE ACTUAL 09 ARM ELF (built by arduino-cli with the core's -Ofast) under the
Unicorn Cortex-M4F emulator: hg_twin_defaults + hg_twin_acc_init + hg_twin_pack + hg_twin_unpack, and also the glue's
hg_fw_twin_pack/hg_fw_twin_load path. No board needed; the instructions are the ones that would run on the band.
usage: arm_emulate_twin.py <09_guardian.ino.elf>"""
import struct, sys
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
elf = ELFFile(open(sys.argv[1], 'rb'))
sym = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4) if hasattr(uc, 'ctl_set_cpu_model') else None
uc.mem_map(0x0, 0x100000)            # flash
uc.mem_map(0x20000000, 0x40000)      # RAM
uc.mem_map(0xE000E000, 0x1000)       # SCB (CPACR)
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and seg['p_filesz']:
        a = seg['p_paddr'] if seg['p_vaddr'] >= 0x20000000 else seg['p_vaddr']
        uc.mem_write(seg['p_vaddr'] if seg['p_vaddr'] < 0x20000000 else seg['p_vaddr'], seg.data())
        if seg['p_vaddr'] != seg['p_paddr']: uc.mem_write(seg['p_paddr'], seg.data())
uc.mem_write(0xE000ED88, struct.pack('<I', 0xF << 20))   # CPACR: full access CP10/CP11 (FPU on)
RET = 0x000FFF00; uc.mem_write(RET, b'\x00\xbf\x00\xbf')  # nop; nop  (return target)
SP0 = 0x2003F000
def call(name, *args):
    a = sym[name]
    regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
    sp = SP0
    stack_args = list(args[4:])
    if stack_args:
        sp -= 4 * len(stack_args); sp &= ~7
        for i, v in enumerate(stack_args): uc.mem_write(sp + 4 * i, struct.pack('<I', v & 0xFFFFFFFF))
    for r, v in zip(regs, args[:4]): uc.reg_write(r, v & 0xFFFFFFFF)
    uc.reg_write(UC_ARM_REG_SP, sp); uc.reg_write(UC_ARM_REG_LR, RET | 1)
    uc.emu_start(a | 1, RET, timeout=20_000_000)
    r = uc.reg_read(UC_ARM_REG_R0); return r - (1 << 32) if r & 0x80000000 else r
TW, ACC, BUF, TW2, ACC2, RT, RLEN, SC = 0x20030000, 0x20031000, 0x20032000, 0x20033000, 0x20034000, 0x20035000, 0x20036000, 0x20036010
call('hg_twin_defaults', TW); call('hg_twin_acc_init', ACC)
n = call('hg_twin_pack', TW, ACC, 0, 0, 1, BUF, 900)
rc = call('hg_twin_unpack', BUF, n, TW2, ACC2, RT, 700, RLEN, SC)
print(f'ARM image {sys.argv[1].split("/")[-1]} fresh twin: hg_twin_pack -> {n} B, hg_twin_unpack -> rc {rc}  (0 = loads; < 0 = file rejected, defaults used)')
# same bytes through the host -O2 build's view: CRC is fine, so any rejection is a value check
nb = bytes(uc.mem_read(BUF, n)); print(f'packed file first bytes {nb[:8].hex()}  (unlearned t1_night_base hours are NaN by design)')
# a twin with every night-base hour learned (no NaN anywhere except the calm block)
t = bytearray(uc.mem_read(TW, 0x100))
