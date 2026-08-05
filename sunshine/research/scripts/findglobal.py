"""Find `gpMarDirector` by signature.

TMarDirector::mState lives at +0x64 and is read with `lbz`. Any site doing
    lwz  rX, disp(r13)      ; load a global pointer
    lbz  rY, 0x64(rX)       ; ->mState
is almost certainly gpMarDirector->mState. Report the r13 displacements found,
ranked by how often they appear.
"""
import struct, os, sys
from collections import Counter

DOL = os.environ["SMS_DOL"]
data = open(DOL, "rb").read()
th_off = struct.unpack(">7I", data[0x00:0x1C]); th_a = struct.unpack(">7I", data[0x48:0x64]); th_s = struct.unpack(">7I", data[0x90:0xAC])
TEXT = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]
R13 = 0x804141C0

# field offset -> how it is loaded (opcode)
PROBES = [(0x64, 34), (0x5C, 32), (0x4C, 40)]   # mState(lbz), unk5C(lwz), unk4C(lhz)

hits = Counter()
sites = {}
for a0, a1, off in TEXT:
    words = [struct.unpack(">I", data[off+i:off+i+4])[0] for i in range(0, a1-a0, 4)]
    for i in range(len(words) - 3):
        w = words[i]
        if (w >> 26) != 32 or ((w >> 16) & 0x1F) != 13:   # lwz rX, disp(r13)
            continue
        rX = (w >> 21) & 0x1F
        disp = w & 0xFFFF
        if disp & 0x8000:
            disp -= 0x10000
        for nxt in words[i+1:i+4]:
            for foff, opc in PROBES:
                if (nxt >> 26) == opc and ((nxt >> 16) & 0x1F) == rX and (nxt & 0xFFFF) == foff:
                    hits[disp] += 1
                    sites.setdefault(disp, []).append((a0 + i*4, foff))

for disp, n in hits.most_common(8):
    print(f"r13{disp:+#x} -> {(R13 + disp) & 0xFFFFFFFF:#010x}   {n} hit(s)")
    for va, foff in sites[disp][:4]:
        print(f"      {va:08x}  ->+{foff:#x}")
