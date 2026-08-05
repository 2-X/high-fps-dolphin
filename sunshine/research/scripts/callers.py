import struct, os, sys

DOL = os.environ["SMS_DOL"]
data = open(DOL, "rb").read()
th_off = struct.unpack(">7I", data[0x00:0x1C]); th_a = struct.unpack(">7I", data[0x48:0x64]); th_s = struct.unpack(">7I", data[0x90:0xAC])
d_off  = struct.unpack(">11I", data[0x1C:0x48]); d_a = struct.unpack(">11I", data[0x64:0x90]); d_s = struct.unpack(">11I", data[0xAC:0xD8])
TEXT = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]

target = int(sys.argv[1], 16)

hits = []
for a0, a1, off in TEXT:
    n = a1 - a0
    for i in range(0, n, 4):
        w = struct.unpack(">I", data[off + i:off + i + 4])[0]
        if (w >> 26) != 18:          # not b-form
            continue
        if w & 2:                     # AA set (absolute)
            continue
        if not (w & 1):               # LK clear -> plain branch, not bl
            continue
        d = w & 0x03FFFFFC
        if d & 0x02000000:
            d -= 0x04000000
        va = a0 + i
        if ((va + d) & 0xFFFFFFFF) == target:
            hits.append(va)

print(f"bl {target:#x} -> {len(hits)} call site(s)")
for h in hits:
    print(f"  {h:08x}")
