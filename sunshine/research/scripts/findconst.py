import struct, os, sys

DOL = os.environ["SMS_DOL"]
data = open(DOL, "rb").read()
th_off = struct.unpack(">7I", data[0x00:0x1C]); th_a = struct.unpack(">7I", data[0x48:0x64]); th_s = struct.unpack(">7I", data[0x90:0xAC])
d_off  = struct.unpack(">11I", data[0x1C:0x48]); d_a = struct.unpack(">11I", data[0x64:0x90]); d_s = struct.unpack(">11I", data[0xAC:0xD8])
ALL = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s] + \
      [(a, a + s, o) for o, a, s in zip(d_off, d_a, d_s) if s]

R2 = 0x80416BA0
LO, HI = R2 - 0x8000, R2 + 0x8000

def u32(va):
    for a0, a1, o in ALL:
        if a0 <= va < a1:
            return struct.unpack(">I", data[o + va - a0:o + va - a0 + 4])[0]
    return None

targets = {
    "1/3  (0.333333)": 1.0 / 3.0,
    "1/6  (0.166667)": 1.0 / 6.0,
    "0.25": 0.25,
    "1/12 (0.083333)": 1.0 / 12.0,
    "3.0": 3.0,
    "1.0": 1.0,
}

for name, want in targets.items():
    hits = []
    va = LO & ~3
    while va < HI:
        w = u32(va)
        if w is not None:
            f = struct.unpack(">f", struct.pack(">I", w))[0]
            if f == f and abs(f - want) < abs(want) * 1e-6:
                off = va - R2
                # lfs frD,off(r2)  = opcode 48
                enc = (48 << 26) | (0 << 21) | (2 << 16) | (off & 0xFFFF)
                hits.append((va, off, w, enc))
        va += 4
    print(f"=== {name} -> {len(hits)} hit(s)")
    for va, off, w, enc in hits[:4]:
        print(f"    {va:#010x}  off={off:#07x}({off})  raw={w:08x}  lfs f0,{off:#x}(r2) = {enc:08X}")
