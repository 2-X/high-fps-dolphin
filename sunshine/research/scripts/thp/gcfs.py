"""List / extract files from a GameCube ISO (GCM) filesystem."""
import struct, sys, os

ISO = sys.argv[1]
CMD = sys.argv[2] if len(sys.argv) > 2 else "list"   # list | extract <pattern> <outdir>

f = open(ISO, "rb")
f.seek(0x424)
fst_off, fst_size = struct.unpack(">II", f.read(8))
f.seek(fst_off)
fst = f.read(fst_size)

num_entries = struct.unpack(">I", fst[8:12])[0]
str_base = num_entries * 12

def name_of(i):
    off = struct.unpack(">I", fst[i*12:i*12+4])[0] & 0xFFFFFF
    s = fst[str_base+off:fst.index(b"\0", str_base+off)]
    return s.decode("shift-jis", "replace")

# walk
paths = {}   # index -> (is_dir, full_path, data_off, size)
stack = []   # (end_index, dirname)
cur = []
i = 1
while i < num_entries:
    flags = fst[i*12]
    a, b = struct.unpack(">II", fst[i*12+4:i*12+12])
    while stack and i >= stack[-1][0]:
        stack.pop(); cur.pop()
    nm = name_of(i)
    if flags == 1:
        stack.append((b, nm)); cur.append(nm)
        i += 1
    else:
        paths[i] = ("/".join(cur + [nm]), a, b)
        i += 1

if CMD == "list":
    for idx, (p, off, size) in sorted(paths.items(), key=lambda kv: kv[1][0]):
        print(f"{size:>10}  {p}")
elif CMD == "extract":
    import fnmatch
    pat, outdir = sys.argv[3], sys.argv[4]
    for idx, (p, off, size) in paths.items():
        if fnmatch.fnmatch(p.lower(), pat.lower()):
            dst = os.path.join(outdir, p.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            f.seek(off)
            with open(dst, "wb") as o:
                o.write(f.read(size))
            print("extracted", p, size)
