"""Replace a file inside a GameCube ISO by appending data and rewriting its FST entry.

Usage: python isopatch.py <src.iso> <dst.iso> <fst_path> <new_file>
"""
import struct, sys, shutil, os

src, dst, target, newfile = sys.argv[1:5]

if os.path.abspath(src) != os.path.abspath(dst):
    print("copying iso...")
    shutil.copyfile(src, dst)

f = open(dst, "r+b")
f.seek(0x424)
fst_off, fst_size = struct.unpack(">II", f.read(8))
f.seek(fst_off)
fst = bytearray(f.read(fst_size))
num = struct.unpack(">I", fst[8:12])[0]
str_base = num * 12

def name_of(i):
    off = struct.unpack(">I", fst[i*12:i*12+4])[0] & 0xFFFFFF
    return fst[str_base+off:fst.index(b"\0", str_base+off)].decode("shift-jis", "replace")

# resolve full paths like gcfs.py
found = None
stack, cur = [], []
i = 1
while i < num:
    flags = fst[i*12]
    a, b = struct.unpack(">II", fst[i*12+4:i*12+12])
    while stack and i >= stack[-1]:
        stack.pop(); cur.pop()
    nm = name_of(i)
    if flags == 1:
        stack.append(b); cur.append(nm)
    else:
        if "/".join(cur + [nm]).lower() == target.lower():
            found = i
    i += 1
assert found is not None, f"{target} not in FST"

old_off, old_size = struct.unpack(">II", fst[found*12+4:found*12+12])
data = open(newfile, "rb").read()

end = os.path.getsize(dst)
new_off = (end + 0x7FFF) & ~0x7FFF          # 32KiB align
f.seek(new_off)
f.write(data)

struct.pack_into(">II", fst, found*12+4, new_off, len(data))
f.seek(fst_off)
f.write(fst)
f.close()
print(f"{target}: 0x{old_off:X}({old_size}) -> 0x{new_off:X}({len(data)})")
