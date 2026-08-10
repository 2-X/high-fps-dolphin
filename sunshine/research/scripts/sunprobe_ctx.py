"""Disassemble context around each 0xC800 (EFB peek) site to identify the
sun getZBufValue loop vs the Mario occlusion probe."""
import struct, os
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32

DOL = os.environ["SMS_DOL"]
data = open(DOL, "rb").read()
th_off = struct.unpack(">7I", data[0x00:0x1C])
th_a   = struct.unpack(">7I", data[0x48:0x64])
th_s   = struct.unpack(">7I", data[0x90:0xAC])
SEGS = [(a, a+s, o) for o,a,s in zip(th_off, th_a, th_s) if s]

def a2o(addr):
    for a0,a1,o in SEGS:
        if a0 <= addr < a1: return o + (addr-a0)
    return None

md = Cs(CS_ARCH_PPC, CS_MODE_32)
SHOW = {"cmpwi","cmplwi","cmplw","cmpw","li","lis","addi","addis","lwz","lwzu",
        "stw","stwu","stb","lbz","bl","b","bc","bdz","bdnz","rlwinm","ori","or",
        "mr","mtctr","mfctr","mflr"}

for site in [0x800fb560, 0x804b2030, 0x80968b00, 0x80a0b360]:
    win_start = max(site - 24*4, 0x80000000)
    so = a2o(win_start)
    if so is None:
        print(f"\n===== 0x{site:08x}: not in any text segment =====")
        continue
    chunk = data[so:so + 52*4]
    print(f"\n===== 0x{site:08x} context =====")
    for ins in md.disasm(chunk, win_start):
        marker = " <<< EFB BASE" if ins.address==site else ""
        if ins.mnemonic in SHOW or marker:
            print(f"  {ins.address:08x}: {ins.mnemonic:8} {ins.op_str}{marker}")
