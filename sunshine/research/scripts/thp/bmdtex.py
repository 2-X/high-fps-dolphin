"""Extract and decode TEX1 textures from a J3D BMD/BDL file to PNG."""
import struct, sys, os, zlib

def write_png(path, w, h, rgba):
    raw = b"".join(b"\0" + rgba[y*w*4:(y+1)*w*4] for y in range(h))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)

def s3tc_color(c):
    r = (c >> 11) & 0x1F; g = (c >> 5) & 0x3F; b = c & 0x1F
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))

def decode(fmt, w, h, data):
    px = bytearray(w * h * 4)
    def put(x, y, r, g, b, a):
        if x < w and y < h:
            i = (y * w + x) * 4
            px[i:i+4] = bytes((r, g, b, a))
    bw, bh = {0:(8,8),1:(8,4),2:(8,4),3:(4,4),4:(4,4),5:(4,4),6:(4,4),14:(8,8)}[fmt]
    sp = 0
    for by in range(0, h, bh):
        for bx in range(0, w, bw):
            if fmt == 0:    # I4
                for yy in range(bh):
                    for xx in range(0, bw, 2):
                        v = data[sp]; sp += 1
                        for k, n in ((0, v >> 4), (1, v & 0xF)):
                            i = n * 17
                            put(bx+xx+k, by+yy, i, i, i, 255)
            elif fmt == 1:  # I8
                for yy in range(bh):
                    for xx in range(bw):
                        i = data[sp]; sp += 1
                        put(bx+xx, by+yy, i, i, i, 255)
            elif fmt == 2:  # IA4
                for yy in range(bh):
                    for xx in range(bw):
                        v = data[sp]; sp += 1
                        a = (v >> 4) * 17; i = (v & 0xF) * 17
                        put(bx+xx, by+yy, i, i, i, a)
            elif fmt == 3:  # IA8
                for yy in range(bh):
                    for xx in range(bw):
                        a, i = data[sp], data[sp+1]; sp += 2
                        put(bx+xx, by+yy, i, i, i, a)
            elif fmt == 4:  # RGB565
                for yy in range(bh):
                    for xx in range(bw):
                        c = struct.unpack(">H", data[sp:sp+2])[0]; sp += 2
                        r, g, b = s3tc_color(c)
                        put(bx+xx, by+yy, r, g, b, 255)
            elif fmt == 5:  # RGB5A3
                for yy in range(bh):
                    for xx in range(bw):
                        c = struct.unpack(">H", data[sp:sp+2])[0]; sp += 2
                        if c & 0x8000:
                            r = (c >> 10) & 0x1F; g = (c >> 5) & 0x1F; b = c & 0x1F
                            put(bx+xx, by+yy, (r<<3)|(r>>2), (g<<3)|(g>>2), (b<<3)|(b>>2), 255)
                        else:
                            a = (c >> 12) & 7; r = (c >> 8) & 0xF; g = (c >> 4) & 0xF; b = c & 0xF
                            put(bx+xx, by+yy, r*17, g*17, b*17, a*36+(a>>1))
            elif fmt == 6:  # RGBA32
                ar = data[sp:sp+32]; gb = data[sp+32:sp+64]; sp += 64
                for yy in range(4):
                    for xx in range(4):
                        o = (yy*4+xx)*2
                        put(bx+xx, by+yy, ar[o+1], gb[o], gb[o+1], ar[o])
            elif fmt == 14:  # CMPR
                for sy in range(0, 8, 4):
                    for sx in range(0, 8, 4):
                        c0, c1, bits = struct.unpack(">HHI", data[sp:sp+8]); sp += 8
                        p0, p1 = s3tc_color(c0), s3tc_color(c1)
                        if c0 > c1:
                            pal = [p0+(255,), p1+(255,),
                                   tuple((2*p0[i]+p1[i])//3 for i in range(3))+(255,),
                                   tuple((p0[i]+2*p1[i])//3 for i in range(3))+(255,)]
                        else:
                            pal = [p0+(255,), p1+(255,),
                                   tuple((p0[i]+p1[i])//2 for i in range(3))+(255,),
                                   (0, 0, 0, 0)]
                        for yy in range(4):
                            for xx in range(4):
                                idx = (bits >> (30 - 2*(yy*4+xx))) & 3
                                r, g, b, a = pal[idx]
                                put(bx+sx+xx, by+sy+yy, r, g, b, a)
    return bytes(px)

FMT = {0:"I4",1:"I8",2:"IA4",3:"IA8",4:"RGB565",5:"RGB5A3",6:"RGBA32",
       8:"C4",9:"C8",10:"C14X2",14:"CMPR"}

def main(path, outdir):
    data = open(path, "rb").read()
    assert data[:4] == b"J3D2", data[:8]
    nsec = struct.unpack(">I", data[0x0C:0x10])[0]
    off = 0x20
    tex1 = None
    for _ in range(nsec):
        tag = data[off:off+4]; size = struct.unpack(">I", data[off+4:off+8])[0]
        if tag == b"TEX1":
            tex1 = off
        off += size
    assert tex1 is not None
    count = struct.unpack(">H", data[tex1+8:tex1+10])[0]
    hdrs = tex1 + struct.unpack(">I", data[tex1+0x0C:tex1+0x10])[0]
    strt = tex1 + struct.unpack(">I", data[tex1+0x10:tex1+0x14])[0]
    nstr = struct.unpack(">H", data[strt:strt+2])[0]
    names = []
    for i in range(nstr):
        so = struct.unpack(">H", data[strt+4+i*4+2:strt+4+i*4+4])[0]
        names.append(data[strt+so:data.index(b"\0", strt+so)].decode("shift-jis", "replace"))
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    for i in range(count):
        h = hdrs + i*0x20
        fmt = data[h]
        w, hh = struct.unpack(">HH", data[h+2:h+6])
        mips = data[h+0x18]
        doff = struct.unpack(">I", data[h+0x1C:h+0x20])[0]
        nm = names[i] if i < len(names) else f"tex{i}"
        print(f"{base}: [{i}] {nm!r} {w}x{hh} fmt={FMT.get(fmt,fmt)} mips={mips} dataoff=0x{doff:X}")
        if fmt in (0,1,2,3,4,5,6,14):
            rgba = decode(fmt, w, hh, data[h+doff:])
            write_png(os.path.join(outdir, f"{base}_{i}_{nm}.png"), w, hh, rgba)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
