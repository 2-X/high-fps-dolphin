"""Disassemble a list of hand-assembled words at a given base address.

Usage: python verify.py <base_hex> <word> <word> ...
       python verify.py <base_hex> --file <path-with-8-hex-words-per-line>
"""
import sys, struct, re
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

def dec(w, a):
    ins = next(md.disasm(struct.pack(">I", w), a), None)
    if not ins:
        return f".word {w:08x}"
    t = f"{ins.mnemonic} {ins.op_str}"
    if (w >> 26) == 16:                       # bc-form: show absolute target
        bd = w & 0xFFFC
        if bd & 0x8000:
            bd -= 0x10000
        t += f"   -> {(a + bd) & 0xFFFFFFFF:#010x}"
    return t

base = int(sys.argv[1], 16)
if sys.argv[2] == "--file":
    txt = open(sys.argv[3]).read()
    words = [int(x, 16) for x in re.findall(r"\b[0-9A-Fa-f]{8}\b", txt)]
else:
    words = [int(x, 16) for x in sys.argv[2:]]

for i, w in enumerate(words):
    a = base + i * 4
    print(f"[{i:2d}] +{i*4:#04x}  {a:08x}: {w:08x}  {dec(w, a)}")
print(f"\n{len(words)} words = {len(words)/2} lines")
