"""Identify the 3 EFB-peek call sites in USA GMSE01 by disassembling forward
from real instruction boundaries.

Strategy: each of the 3 'lis r3,0xC800' sites is inside a caller. Walk forward
from each site looking at the surrounding instructions. The 'getZBufValue' caller
is the one with: a loop (bdnz/bc back-branch), a 'cmplwi r?,0xffffff' depth test,
and a loop-count of 17. The Mario probe has neither loop nor depth test.

To stay instruction-aligned, find the nearest prologue by scanning the raw bytes
for the EXACT 'mflr r0 ; stw r0,imm(r1)' pair (2 specific words) which is the
SMS compiler's standard function header.
"""
import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

data = open("sunshine/research/main.dol", "rb").read()
T1_A, T1_O = 0x80005600, 0x2540
def a2o(addr): return T1_O + (addr - T1_A)
def o2a(off): return T1_A + (off - T1_O)

# Find all 'mflr r0' (0x7C0802A6) word-aligned positions in T1 — these are function entries
entries = []
for off in range(T1_O, T1_O + 0x36dac0, 4):
    w = struct.unpack(">I", data[off:off+4])[0]
    if w == 0x7C0802A6:
        entries.append(o2a(off))

def fn_start_before(addr):
    best = None
    for e in entries:
        if e <= addr:
            best = e
        else:
            break
    return best

md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
SITES = [0x80042dd8, 0x8013088c, 0x8025e340]
for site in SITES:
    fn = fn_start_before(site)
    # disassemble forward from the prologue (skip the mflr/stw header words themselves)
    start = fn + 4   # the word after mflr r0
    so = a2o(start)
    chunk = data[so:so + 0x140]
    print(f"\n===== site 0x{site:08x}  fn-entry 0x{fn:08x} =====")
    for ins in md.disasm(chunk, start):
        m = " <<< EFB" if ins.address == site else ""
        # Flag loop/depth-test markers
        flag = ""
        if ins.mnemonic == "cmplwi" and "0xffffff" in ins.op_str: flag = "  <== DEPTH TEST (0xffffff)"
        if ins.mnemonic in ("cmpwi","cmplwi") and ", 17" in ins.op_str.replace(" ","") or (ins.mnemonic=="cmpwi" and "0x11" in ins.op_str): flag += "  <== LOOP 17?"
        if ins.mnemonic == "bdnz": flag += "  <== LOOP BACK-BRANCH"
        print(f"  {ins.address:08x}: {ins.mnemonic:8} {ins.op_str}{m}{flag}")
        if ins.mnemonic == "blr" and ins.address > site + 4:
            break
