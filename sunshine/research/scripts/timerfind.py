#!/usr/bin/env python3
"""timerfind.py — locate the SMS (USA GMSE01) game-timer machinery in main.dol.

The HUD race/countdown timers are OS-tick STOPWATCH based (not frame counters):
  TMarDirector+0xE8 = OSStopwatch "イベント用ストップウォッチ" (event stopwatch)
  TGCConsole2::setTimer(-1)  : elapsed = OSTicksToMs(OSCheckStopwatch(sw)) - base
  TMarDirector::getRestTime(): unk120 - OSTicksToMs(OSCheckStopwatch(sw))/10
At EmulationSpeed=2 the emulated timebase runs 2x real -> all these run 2x fast.

This script finds (in the USA dol):
  1. the Shift-JIS stopwatch-name string
  2. OSInitStopwatch call site in TMarDirector ctor (-> stopwatch offset + funcs)
  3. OSCheckStopwatch + every bl caller of it
  4. TGCConsole2::setTimer via the 599999 (0x927BF) cap constant
"""
import struct, sys
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

DOL = "/Users/kbrethower/code/high-fps-dolphin/sunshine/research/main.dol"

def load_dol(path):
    data = open(path, "rb").read()
    text_off = struct.unpack(">7I", data[0x00:0x1C])
    data_off = struct.unpack(">11I", data[0x1C:0x48])
    text_addr = struct.unpack(">7I", data[0x48:0x64])
    data_addr = struct.unpack(">11I", data[0x64:0x90])
    text_size = struct.unpack(">7I", data[0x90:0xAC])
    data_size = struct.unpack(">11I", data[0xAC:0xD8])
    segs = []
    for o, a, s in zip(text_off, text_addr, text_size):
        if s: segs.append((a, a + s, o, s, "text"))
    for o, a, s in zip(data_off, data_addr, data_size):
        if s: segs.append((a, a + s, o, s, "data"))
    return data, segs

def addr_to_off(segs, addr):
    for a0, a1, o, s, k in segs:
        if a0 <= addr < a1:
            return o + (addr - a0), k
    return None, None

def off_to_addr(segs, off):
    for a0, a1, o, s, k in segs:
        if o <= off < o + s:
            return a0 + (off - o)
    return None

data, segs = load_dol(DOL)
md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

def disasm(addr, count, label=""):
    off, kind = addr_to_off(segs, addr)
    code = data[off:off + count * 4]
    print(f"--- {label} @ 0x{addr:08X} ---")
    for insn in md.disasm(code, addr):
        raw = struct.unpack(">I", data[off + (insn.address - addr):off + (insn.address - addr) + 4])[0]
        print(f"  0x{insn.address:08X}: {raw:08X}  {insn.mnemonic}\t{insn.op_str}")

# ---- 1. the stopwatch name string (Shift-JIS) ----
sjis = "イベント用ストップウォッチ".encode("shift-jis")
idx = data.find(sjis)
str_addr = off_to_addr(segs, idx) if idx >= 0 else None
print(f"[1] stopwatch-name string: {'0x%08X' % str_addr if str_addr else 'NOT FOUND'}")

# ---- 2. lis/addi (or lis/ori) reference to that string in text ----
refs = []
if str_addr:
    hi = (str_addr + 0x8000) >> 16          # ha16
    lo = str_addr & 0xFFFF
    for a0, a1, o, s, k in segs:
        if k != "text": continue
        for i in range(0, s - 4, 4):
            w = struct.unpack(">I", data[o + i:o + i + 4])[0]
            # addi rD,rA,lo16  (opcode 14) with simm == signed lo
            if (w >> 26) == 14 and (w & 0xFFFF) == lo:
                # scan back a few instrs for lis rA,hi
                for back in range(1, 8):
                    w2 = struct.unpack(">I", data[o + i - 4 * back:o + i - 4 * back + 4])[0]
                    if (w2 >> 26) == 15 and (w2 & 0xFFFF) == ((hi if lo < 0x8000 else hi) & 0xFFFF):
                        refs.append(a0 + i)
                        break
    for r in refs:
        print(f"[2] string ref (addi) at 0x{r:08X}")

# ---- 4. setTimer via 599999 = 0x927BF: lis rX,0x9 ; ori rX,rX,0x27BF ----
hits = []
for a0, a1, o, s, k in segs:
    if k != "text": continue
    for i in range(0, s - 8, 4):
        w1, w2 = struct.unpack(">II", data[o + i:o + i + 8])
        if (w1 >> 26) == 15 and (w1 & 0xFFFF) == 0x0009 and (w2 >> 26) == 24 and (w2 & 0xFFFF) == 0x27BF:
            hits.append(a0 + i)
print(f"[4] 599999-cap sites (setTimer candidates): {['0x%08X' % h for h in hits]}")
