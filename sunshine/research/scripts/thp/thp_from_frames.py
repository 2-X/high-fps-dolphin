"""Assemble a THP from a directory of PNG frames, using an original THP as template.

Usage: python thp_from_frames.py <template.thp> <frames_dir> <out.thp> <W> <H> [quality]
Frames are read in sorted filename order and resized (Lanczos) to WxH if needed.
"""
import struct, sys, io, os
from PIL import Image

tmpl, framedir, dst, W, H = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
quality = int(sys.argv[6]) if len(sys.argv) > 6 else 85

d = open(tmpl, "rb").read()
(magic, version, bufSize, audioMax, fps, numFrames, firstFrameSize,
 movieDataSize, compOff, offsetsOff, firstOff, lastOff) = struct.unpack(">4sIIIfIIIIIII", d[:48])
assert magic == b"THP\0" and audioMax == 0
assert W <= 1024 and H <= 1024 and W % 16 == 0 and H % 16 == 0

files = sorted(f for f in os.listdir(framedir) if f.lower().endswith(".png"))
assert len(files) == numFrames, (len(files), numFrames)

def normalize(j):
    dqt, dht, sof, sos_seg = b"", b"", None, None
    i = 2
    while i < len(j) - 1:
        assert j[i] == 0xFF
        m = j[i+1]
        ln = struct.unpack(">H", j[i+2:i+4])[0]
        payload = j[i+4:i+2+ln]
        if m == 0xDB: dqt += payload
        elif m == 0xC4: dht += payload
        elif m == 0xC0: sof = payload
        elif m == 0xDA:
            sos_seg = j[i:]; break
        elif m == 0xC2: raise ValueError("progressive JPEG")
        i += 2 + ln
    def seg(m, p):
        return bytes((0xFF, m)) + struct.pack(">H", len(p) + 2) + p
    return b"\xff\xd8" + seg(0xDB, dqt) + seg(0xC0, sof) + seg(0xC4, dht) + sos_seg

def destuff(j):
    sos = j.find(b"\xff\xda")
    hl = struct.unpack(">H", j[sos+2:sos+4])[0]
    split = sos + 2 + hl
    out = bytearray(j[:split])
    scan = j[split:]
    i = 0
    while i < len(scan):
        b = scan[i]
        out.append(b)
        if b == 0xFF and scan[i+1] == 0x00:
            i += 2; continue
        i += 1
    return bytes(out)

payloads = []
for n, fn in enumerate(files):
    im = Image.open(os.path.join(framedir, fn)).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, subsampling=2)
    payloads.append(destuff(normalize(buf.getvalue())))
    if n % 50 == 0:
        print("frame", n, len(payloads[-1]), "bytes")

sizes, bodies = [], []
for p in payloads:
    imgsz = (len(p) + 3) & ~3
    body = struct.pack(">I", imgsz) + p + b"\0" * (imgsz - len(p))
    total = (8 + len(body) + 31) & ~31
    bodies.append(body + b"\0" * (total - 8 - len(body)))
    sizes.append(total)

frames = b"".join(
    struct.pack(">II", sizes[(i+1) % numFrames], sizes[(i-1) % numFrames]) + bodies[i]
    for i in range(numFrames))

hdr = struct.pack(">4sIIIfIIIIIII", b"THP\0", version, max(sizes), 0, fps,
                  numFrames, sizes[0], len(frames), 0x30, 0,
                  0x50, 0x50 + sum(sizes[:-1]))
comp = bytearray(d[0x30:0x50])
struct.pack_into(">II", comp, 0x14, W, H)
open(dst, "wb").write(hdr + bytes(comp) + frames)
print(f"out: {W}x{H}, maxframe {max(sizes)}, ring10 {max(sizes)*10//1024}KB, "
      f"tex {3*(W*H + 2*(W//2)*(H//2))//1024}KB")
