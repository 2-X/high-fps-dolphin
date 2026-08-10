"""Show the instructions immediately around each EFB site (aligned), and hunt
for the getZBufValue loop specifically: a function containing BOTH 'cmplwi ?,0xffffff'
AND 'bl <GXPeekZ>' inside a back-branch loop."""
import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

data = open("sunshine/research/main.dol", "rb").read()
T1_A, T1_O = 0x80005600, 0x2540
def a2o(addr): return T1_O + (addr - T1_A)

md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

# 1) Show window around each site
for site in [0x80042dd8, 0x8013088c, 0x8025e340]:
    start = site - 8*4
    so = a2o(start)
    chunk = data[so:so + 24*4]
    print(f"\n===== around 0x{site:08x} =====")
    for ins in md.disasm(chunk, start):
        m = " <<< EFB BASE (lis r3,0xC800)" if ins.address == site else ""
        print(f"  {ins.address:08x}: {ins.mnemonic:8} {ins.op_str}{m}")

# 2) Find getZBufValue: scan ALL functions for one containing cmplwi ?,0xffffff
#    within ~40 instrs of a bdnz/bc back-branch (loop) AND a bl.
print("\n\n===== Hunting getZBufValue (loop + cmplwi 0xffffff + bl) =====")
entries = []
for off in range(T1_O, T1_O + 0x36dac0, 4):
    if struct.unpack(">I", data[off:off+4])[0] == 0x7C0802A6:
        entries.append(T1_A + (off - T1_O))

def fn_range(start):
    # function = from this entry to the next entry (rough)
    idx = entries.index(start) if start in entries else -1
    nxt = entries[idx+1] if idx+1 < len(entries) else start + 0x1000
    return nxt

for i, e in enumerate(entries):
    nxt = entries[i+1] if i+1 < len(entries) else e + 0x200
    if nxt - e > 0x200:  # getZBufValue is 0x9C bytes
        continue
    so = a2o(e)
    chunk = data[so:so + (nxt - e)]
    insns = list(md.disasm(chunk, e))
    has_ffffff = any(x.mnemonic == "cmplwi" and "0xffffff" in x.op_str for x in insns)
    has_loop = any(x.mnemonic == "bdnz" for x in insns)
    has_bl = any(x.mnemonic == "bl" for x in insns)
    if has_ffffff and has_loop and has_bl:
        print(f"\n*** MATCH: fn 0x{e:08x} (size ~0x{nxt-e:x}) ***")
        for x in insns:
            flag = ""
            if x.mnemonic == "cmplwi" and "0xffffff" in x.op_str: flag = "  <== DEPTH"
            if x.mnemonic == "bdnz": flag += "  <== LOOP"
            if x.mnemonic == "bl": flag += "  <== bl"
            print(f"  {x.address:08x}: {x.mnemonic:8} {x.op_str}{flag}")
