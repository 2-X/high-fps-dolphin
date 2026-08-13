#!/usr/bin/env python3
"""Extract a .NET single-file bundle (Major version 2..6, i.e. .NET Core 3.x..8).

The bundle is appended data located via a 32-byte signature; the int64 at
(sig_offset - 8) is the bundle-manifest header offset. Deflate-compressed
entries (CompressedSize != 0) are raw-inflated.
"""
import struct
import sys
import zlib
from pathlib import Path

SIG = bytes([0x8b, 0x12, 0x02, 0xb9, 0x6a, 0x61, 0x20, 0x38,
             0x72, 0xe8, 0x32, 0x56, 0x87, 0x2d, 0x61, 0x68,
             0x4e, 0x0f, 0x84, 0x8e, 0x6a, 0x3a, 0x1e, 0x2f,
             0x25, 0x4d, 0xa7, 0x11, 0x0e, 0x14, 0x2f, 0x0f])


def read_7bit_str(d, pos):
    n = 0
    shift = 0
    while True:
        b = d[pos]
        pos += 1
        n |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    s = d[pos:pos + n].decode("utf-8")
    return s, pos + n


def main(exe_path, out_dir):
    d = Path(exe_path).read_bytes()
    sig_off = d.find(SIG[:16])  # prefix is stable across .NET versions
    if sig_off < 0:
        sys.exit("bundle signature not found")
    (hdr_off,) = struct.unpack_from("<q", d, sig_off - 8)
    print(f"signature @ {sig_off:#x}, manifest header @ {hdr_off:#x}")

    p = hdr_off
    major, minor, count = struct.unpack_from("<iii", d, p)
    p += 12
    print(f"bundle major={major} minor={minor} files={count}")
    bundle_id, p = read_7bit_str(d, p)
    if major >= 2:
        # DepsJson (off,size), RuntimeConfigJson (off,size), Flags
        p += 8 + 8 + 8 + 8 + 8
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for _ in range(count):
        offset, size, comp = struct.unpack_from("<qqq", d, p)
        p += 24
        ftype = d[p]
        p += 1
        rel, p = read_7bit_str(d, p)
        raw = d[offset:offset + (comp if comp else size)]
        data = zlib.decompress(raw, -15) if comp else raw
        dest = out / rel.replace("\\", "/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        manifest.append((rel, size, comp, ftype))

    manifest.sort(key=lambda r: -r[1])
    print(f"extracted {count} entries -> {out}")
    print("largest entries:")
    for rel, size, comp, ftype in manifest[:15]:
        print(f"  {size:>10}  comp={'y' if comp else 'n'} type={ftype}  {rel}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
