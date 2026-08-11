#!/usr/bin/env python3
"""gcislot.py — inspect / transplant Super Mario Sunshine (GMSE01) save slots.

The .gci is a 0x40 GCI header + 7 x 0x2000 TCardSectors (decomp CardManager.cpp):
  sector 0          option block (game settings; no file directory)
  sectors 1+2       in-game file A   (double-buffered: higher mWriteCount wins)
  sectors 3+4       in-game file B
  sectors 5+6       in-game file C
Each sector: [0x00] u32 mWriteCount, [0x04..] header+data, [0x1FFC] u32 mCheckSum
= CalcCheckSum over the first 0x1FFC bytes (u16 sum << 16 | u16 ~sum, big-endian).
Slots are self-contained, so a slot transplant is a verbatim copy of its two
sectors. Dolphin must NOT be running when writing (it holds/flushes the card).

Usage:
  gcislot.py info CARD.gci
  gcislot.py transplant SRC.gci DST.gci SLOT     # SLOT = A, B or C; backs up DST
"""
import shutil, struct, sys

GCI_HDR = 0x40
SECTOR = 0x2000
SLOTS = {"A": 1, "B": 3, "C": 5}


def checksum(sector_bytes):
    top = bottom = 0
    for (v,) in struct.iter_unpack(">H", sector_bytes[:0x1FFC]):
        top = (top + v) & 0xFFFFFFFF
        bottom = (bottom + (~v & 0xFFFF)) & 0xFFFFFFFF
    return ((top << 16) | (bottom & 0xFFFF)) & 0xFFFFFFFF


def sector(data, k):
    off = GCI_HDR + k * SECTOR
    return data[off:off + SECTOR]


def sector_info(data, k):
    s = sector(data, k)
    wc = struct.unpack(">I", s[:4])[0]
    stored = struct.unpack(">I", s[0x1FFC:0x2000])[0]
    calc = checksum(s)
    empty = all(b == 0 for b in s)
    return wc, stored == calc, empty


def info(path):
    data = open(path, "rb").read()
    if len(data) != GCI_HDR + 7 * SECTOR:
        sys.exit(f"{path}: unexpected size {len(data)}")
    print(path)
    for name, base in SLOTS.items():
        parts = []
        for k in (base, base + 1):
            wc, ok, empty = sector_info(data, k)
            parts.append(f"sector {k}: writeCount={wc} "
                         f"{'EMPTY' if empty else 'checksum ' + ('OK' if ok else 'BAD')}")
        live = max((sector_info(data, k)[0] for k in (base, base + 1)))
        used = any(not sector_info(data, k)[2] for k in (base, base + 1))
        print(f"  file {name}: {'IN USE' if used else 'empty':7} "
              f"(latest writeCount {live})   [{parts[0]} | {parts[1]}]")


def transplant(src_path, dst_path, slot):
    base = SLOTS[slot.upper()]
    src = open(src_path, "rb").read()
    dst = bytearray(open(dst_path, "rb").read())
    for p, d in ((src, "source"), (dst, "dest")):
        if len(p) != GCI_HDR + 7 * SECTOR:
            sys.exit(f"{d}: unexpected size {len(p)}")
    # source slot must hold at least one checksum-valid, non-empty sector
    good = [k for k in (base, base + 1)
            if sector_info(src, k)[1] and not sector_info(src, k)[2]]
    if not good:
        sys.exit(f"source file {slot}: no valid sector — refusing")
    bak = dst_path + ".bak-transplant"
    shutil.copyfile(dst_path, bak)
    off = GCI_HDR + base * SECTOR
    dst[off:off + 2 * SECTOR] = src[off:off + 2 * SECTOR]
    open(dst_path, "wb").write(dst)
    print(f"file {slot} copied {src_path} -> {dst_path} (backup: {bak})")
    info(dst_path)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "info":
        info(sys.argv[2])
    elif len(sys.argv) == 5 and sys.argv[1] == "transplant":
        transplant(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
