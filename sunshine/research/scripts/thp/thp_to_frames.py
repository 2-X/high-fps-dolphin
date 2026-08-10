"""Decode a video-only THP into a directory of PNG frames.

Inverse of thp_from_frames.py. Reuses the THP->standard-JPEG de-stuffing from
thp_upscale.py (THP JPEGs carry no 0xFF stuffing bytes in the scan).

Usage: python thp_to_frames.py <in.thp> <out_dir>
Writes frame_00000.png ... in sorted order (matches thp_from_frames.py's reader).
"""
import struct, sys, io, os
from PIL import Image

src, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)

d = open(src, "rb").read()
(magic, version, bufSize, audioMax, fps, numFrames, firstFrameSize,
 movieDataSize, compOff, offsetsOff, firstOff, lastOff) = struct.unpack(">4sIIIfIIIIIII", d[:48])
assert magic == b"THP\0" and audioMax == 0
ncomp = struct.unpack(">I", d[compOff:compOff+4])[0]
assert ncomp == 1
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
    """Restuff a THP frame's scan back into a standard baseline JPEG."""
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


for n, fr in enumerate(walk_frames()):
    im = Image.open(io.BytesIO(thp2jpg(fr))).convert("RGB")
    im.save(os.path.join(outdir, f"frame_{n:05d}.png"))
    if n % 50 == 0:
        print("decoded frame", n)
print(f"wrote {numFrames} PNGs to {outdir}")
