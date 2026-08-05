"""Yaz0-decompress an SZS and list/extract the RARC archive inside."""
import struct, sys, os

def yaz0_dec(src):
    assert src[:4] == b"Yaz0", src[:4]
    out_size = struct.unpack(">I", src[4:8])[0]
    out = bytearray(out_size)
    sp, dp = 16, 0
    code, bits = 0, 0
    while dp < out_size:
        if bits == 0:
            code = src[sp]; sp += 1; bits = 8
        if code & 0x80:
            out[dp] = src[sp]; sp += 1; dp += 1
        else:
            b1, b2 = src[sp], src[sp+1]; sp += 2
            dist = ((b1 & 0xF) << 8) | b2
            cp = dp - dist - 1
            n = b1 >> 4
            if n == 0:
                n = src[sp] + 0x12; sp += 1
            else:
                n += 2
            for _ in range(n):
                out[dp] = out[cp]; dp += 1; cp += 1
        code <<= 1; bits -= 1
    return bytes(out)

def rarc_walk(data):
    assert data[:4] == b"RARC", data[:4]
    # header
    hdr_size = struct.unpack(">I", data[8:12])[0]
    data_off = struct.unpack(">I", data[12:16])[0] + 0x20
    num_nodes = struct.unpack(">I", data[0x20:0x24])[0]
    node_off = struct.unpack(">I", data[0x24:0x28])[0] + 0x20
    num_ents = struct.unpack(">I", data[0x28:0x2c])[0]
    ent_off = struct.unpack(">I", data[0x2c:0x30])[0] + 0x20
    str_off = struct.unpack(">I", data[0x34:0x38])[0] + 0x20

    def cstr(off):
        end = data.index(b"\0", str_off + off)
        return data[str_off+off:end].decode("shift-jis", "replace")

    nodes = []
    for i in range(num_nodes):
        o = node_off + i*16
        name_off = struct.unpack(">I", data[o+4:o+8])[0]
        first, count = struct.unpack(">I", data[o+8:o+12])[0] & 0xFFFF, 0
        count = struct.unpack(">H", data[o+10:o+12])[0]
        first = struct.unpack(">I", data[o+12:o+16])[0]
        nodes.append((cstr(name_off), first, count))

    files = []
    def walk(node_idx, prefix):
        name, first, count = nodes[node_idx]
        for i in range(first, first+count):
            o = ent_off + i*20
            fid = struct.unpack(">H", data[o:o+2])[0]
            attr = data[o+4]
            name_off = struct.unpack(">I", data[o+4:o+8])[0] & 0xFFFFFF
            fdata_off, fsize = struct.unpack(">II", data[o+8:o+16])
            nm = cstr(name_off)
            if nm in (".", ".."):
                continue
            if attr & 0x02:  # dir
                walk(fdata_off, prefix + nm + "/")
            else:
                files.append((prefix + nm, data_off + fdata_off, fsize))
    walk(0, "")
    return files

if __name__ == "__main__":
    path, cmd = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "list")
    raw = open(path, "rb").read()
    if raw[:4] == b"Yaz0":
        raw = yaz0_dec(raw)
    files = rarc_walk(raw)
    if cmd == "list":
        for nm, off, size in files:
            print(f"{size:>9}  {nm}")
    else:  # extract pat outdir
        import fnmatch
        pat, outdir = sys.argv[3], sys.argv[4]
        for nm, off, size in files:
            if fnmatch.fnmatch(nm.lower(), pat.lower()):
                dst = os.path.join(outdir, nm.replace("/", os.sep))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, "wb").write(raw[off:off+size])
                print("extracted", nm, size)
