import struct, os, sys

DOL = os.environ["SMS_DOL"]
data = open(DOL, "rb").read()
th_off = struct.unpack(">7I", data[0x00:0x1C]); th_a = struct.unpack(">7I", data[0x48:0x64]); th_s = struct.unpack(">7I", data[0x90:0xAC])
d_off  = struct.unpack(">11I", data[0x1C:0x48]); d_a = struct.unpack(">11I", data[0x64:0x90]); d_s = struct.unpack(">11I", data[0xAC:0xD8])
TEXT = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]
ALL  = TEXT + [(a, a + s, o) for o, a, s in zip(d_off, d_a, d_s) if s]

R2, R13 = 0x80416BA0, 0x804141C0
target = int(sys.argv[1], 16)

MNEM = {32:"lwz",36:"stw",34:"lbz",38:"stb",40:"lhz",44:"sth",
        48:"lfs",52:"stfs",50:"lfd",54:"stfd"}

def val(va):
    for a0,a1,o in ALL:
        if a0 <= va < a1:
            w = struct.unpack(">I", data[o+va-a0:o+va-a0+4])[0]
            return w, struct.unpack(">f", struct.pack(">I", w))[0]
    return None, None

w, f = val(target)
print(f"{target:#x} raw={w:08x} float={f}")
for base, name in ((R2,"r2"), (R13,"r13")):
    d = target - base
    if -0x8000 <= d < 0x8000:
        print(f"  reachable as {d:#x}({name})  [{d}]")
print()

for base, rnum, rname in ((R2,2,"r2"), (R13,13,"r13")):
    disp = target - base
    if not (-0x8000 <= disp < 0x8000):
        continue
    d16 = disp & 0xFFFF
    hits = []
    for a0,a1,off in TEXT:
        for i in range(0, a1-a0, 4):
            w = struct.unpack(">I", data[off+i:off+i+4])[0]
            op = w >> 26
            if op in MNEM and ((w >> 16) & 0x1F) == rnum and (w & 0xFFFF) == d16:
                hits.append((a0+i, MNEM[op], (w>>21)&0x1F))
    print(f"=== refs via {rname}{disp:+#x}: {len(hits)}")
    for va, m, reg in hits:
        print(f"    {va:08x}  {m:5s} {'f' if m.startswith(('lf','stf')) else 'r'}{reg}, {disp:#x}({rname})")
