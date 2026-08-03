#!/usr/bin/env python3
import struct, sys
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

DOL = "/Users/kbrethower/code/high-fps-dolphin/work/disc/sys/main.dol"

def load_dol(path):
    data = open(path, "rb").read()
    # DOL header: 7 text + 11 data sections
    text_off = struct.unpack(">7I", data[0x00:0x1C])
    data_off = struct.unpack(">11I", data[0x1C:0x48])
    text_addr = struct.unpack(">7I", data[0x48:0x64])
    data_addr = struct.unpack(">11I", data[0x64:0x90])
    text_size = struct.unpack(">7I", data[0x90:0xAC])
    data_size = struct.unpack(">11I", data[0xAC:0xD8])
    segs = []
    for o,a,s in zip(text_off, text_addr, text_size):
        if s: segs.append((a, a+s, o, s, "text"))
    for o,a,s in zip(data_off, data_addr, data_size):
        if s: segs.append((a, a+s, o, s, "data"))
    return data, segs

def addr_to_off(segs, addr):
    for a0,a1,o,s,k in segs:
        if a0 <= addr < a1:
            return o + (addr - a0), k
    return None, None

def read_u32(data, segs, addr):
    off,_ = addr_to_off(segs, addr)
    if off is None: return None
    return struct.unpack(">I", data[off:off+4])[0]

def disasm(data, segs, addr, count, label=""):
    off,kind = addr_to_off(segs, addr)
    if off is None:
        print(f"  [addr 0x{addr:08X} not in any segment]")
        return
    code = data[off:off+count*4]
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    print(f"--- {label} @ 0x{addr:08X} (seg {kind}) ---")
    for insn in md.disasm(code, addr):
        raw = struct.unpack(">I", data[off + (insn.address-addr): off + (insn.address-addr)+4])[0]
        print(f"  0x{insn.address:08X}: {raw:08X}  {insn.mnemonic}\t{insn.op_str}")

data, segs = load_dol(DOL)
print("Segments (addr range -> file off):")
for a0,a1,o,s,k in segs:
    print(f"  {k}: 0x{a0:08X}-0x{a1:08X}  size 0x{s:X}")
print()

# Hook sites from the Gecko codes (USA):
# 0x800066EC  C2 asm insert (lfs f22,val; fmuls f1,f1,f22; fmr f22,f1)
# 0x802FCB24  NOP'd instruction (04 code) -- what did it originally do?
# 0x804167B8  the value slot (2.0f)  -> data
# 0x80414904  0.02f constant slot    -> data

def find_func_start(data, segs, addr, maxback=0x400):
    # scan backwards for a prologue: stwu r1,-x(r1) = 0x9421xxxx
    a = addr
    for _ in range(maxback//4):
        v = read_u32(data, segs, a)
        if v is not None and (v & 0xFFFF0000) == 0x94210000:
            return a
        a -= 4
    return None

fs = find_func_start(data, segs, 0x800066EC)
print(f"Function containing hook starts at: 0x{fs:08X}" if fs else "prologue not found")
disasm(data, segs, fs if fs else 0x80006600, 80, "FULL hook function")
print()
fs2 = find_func_start(data, segs, 0x802FCB24)
print(f"Function containing NOP starts at: 0x{fs2:08X}" if fs2 else "prologue not found")
print()
disasm(data, segs, 0x8034F684, 20, "NOP'd call target 0x8034F684")
print()
for a in (0x804167B8, 0x80414904):
    v = read_u32(data, segs, a)
    if v is None:
        print(f"value @ 0x{a:08X}: not in a stored segment (likely .bss)")
    else:
        f = struct.unpack(">f", struct.pack(">I", v))[0]
        print(f"value @ 0x{a:08X}: 0x{v:08X}  = {f}")
