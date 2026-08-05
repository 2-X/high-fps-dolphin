"""Rebuild EX128x144_q0.thp at NxN resolution.

Pipeline: walk original THP frames -> re-stuff to standard JPEG -> PIL decode
-> Lanczos upscale (+mild unsharp) -> baseline 4:2:0 JPEG -> de-stuff back to
THP convention -> reassemble THP with updated header.

Usage: python thp_upscale.py <in.thp> <out.thp> <scale> [quality]
"""
import struct, sys, io
from PIL import Image, ImageFilter

src, dst, scale = sys.argv[1], sys.argv[2], int(sys.argv[3])
quality = int(sys.argv[4]) if len(sys.argv) > 4 else 90

d = open(src, "rb").read()
(magic, version, bufSize, audioMax, fps, numFrames, firstFrameSize,
 movieDataSize, compOff, offsetsOff, firstOff, lastOff) = struct.unpack(">4sIIIfIIIIIII", d[:48])
assert magic == b"THP\0" and audioMax == 0
ncomp = struct.unpack(">I", d[compOff:compOff+4])[0]
assert ncomp == 1  # video only
w, h = struct.unpack(">II", d[compOff+20:compOff+28])
print(f"in: {w}x{h}, {numFrames} frames, fps={fps:.3f}")

def walk_frames():
    off, size = firstOff, firstFrameSize
    for _ in range(numFrames):
        yield d[off:off+size]
        nxt = struct.unpack(">I", d[off:off+4])[0]
        off += size
        size = nxt

def thp2jpg(fr):
    imgsz = struct.unpack(">I", fr[8:12])[0]
    j = fr[12:12+imgsz]
    sos = j.find(b"\xff\xda")
    hl = struct.unpack(">H", j[sos+2:sos+4])[0]
    split = sos + 2 + hl
    out = bytearray(j[:split])
    scan = j[split:]
    i = 0
    while i < len(scan):
        b = scan[i]
        if b == 0xFF:
            if scan[i+1:i+2] == b"\xd9":
                out += b"\xff\xd9"; break
            out += b"\xff\x00"
        else:
            out.append(b)
        i += 1
    else:
        out += b"\xff\xd9"
    return bytes(out)

def normalize(j):
    """SOI + merged DQT + SOF0 + merged DHT + SOS/scan (matches THPConv layout)."""
    dqt, dht, sof, sos_seg = b"", b"", None, None
    i = 2
    while i < len(j) - 1:
        assert j[i] == 0xFF
        m = j[i+1]
        ln = struct.unpack(">H", j[i+2:i+4])[0]
        payload = j[i+4:i+2+ln]
        if m == 0xDB:
            dqt += payload
        elif m == 0xC4:
            dht += payload
        elif m == 0xC0:
            sof = payload
        elif m == 0xDA:
            sos_seg = j[i:]          # SOS marker through end of scan
            break
        elif m in (0xC2,):
            raise ValueError("progressive JPEG")
        i += 2 + ln
    def seg(m, p):
        return bytes((0xFF, m)) + struct.pack(">H", len(p) + 2) + p
    return (b"\xff\xd8" + seg(0xDB, dqt) + seg(0xC0, sof) + seg(0xC4, dht)
            + sos_seg)

def jpg2thp(j):
    j = normalize(j)
    sos = j.find(b"\xff\xda")
    hl = struct.unpack(">H", j[sos+2:sos+4])[0]
    split = sos + 2 + hl
    out = bytearray(j[:split])
    scan = j[split:]
    i = 0
    while i < len(scan):
        b = scan[i]
        out.append(b)
        if b == 0xFF:
            nb = scan[i+1]
            if nb == 0x00:
                i += 2; continue   # drop stuffing byte
            # real marker (EOI) — keep and continue normally
        i += 1
    return bytes(out)

W, H = w*scale, h*scale
assert W <= 1024 and H <= 1024 and W % 16 == 0 and H % 16 == 0

payloads = []
for n, fr in enumerate(walk_frames()):
    im = Image.open(io.BytesIO(thp2jpg(fr))).convert("RGB")
    im = im.resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=60, threshold=2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, subsampling=2)  # baseline 4:2:0
    payloads.append(jpg2thp(buf.getvalue()))
    if n % 50 == 0:
        print("frame", n, "encoded", len(payloads[-1]), "bytes")

def frame_blob(payload):
    imgsz = (len(payload) + 3) & ~3
    body = struct.pack(">I", imgsz) + payload + b"\0" * (imgsz - len(payload))
    return body  # next/prev prepended later

# assemble with next/prev sizes; frames 32-byte aligned
sizes = []
bodies = []
for p in payloads:
    body = frame_blob(p)
    total = 8 + len(body)                # + next,prev fields
    total_pad = (total + 31) & ~31
    bodies.append(body + b"\0" * (total_pad - total))
    sizes.append(total_pad)

frames = b"".join(
    struct.pack(">II", sizes[(i+1) % numFrames], sizes[(i-1) % numFrames]) + bodies[i]
    for i in range(numFrames))

first_off = 0x50
hdr = struct.pack(">4sIIIfIIIIIII", b"THP\0", version, max(sizes), 0, fps,
                  numFrames, sizes[0], len(frames), 0x30, 0,
                  first_off, first_off + sum(sizes[:-1]))
# copy original component block (0x30..0x50) and overwrite just width/height
comp = bytearray(d[0x30:first_off])
struct.pack_into(">II", comp, 0x14, W, H)
out = hdr + bytes(comp) + frames
open(dst, "wb").write(out)
print(f"out: {W}x{H}, {len(out)} bytes, maxframe {max(sizes)}")
