#!/usr/bin/env python3
"""Patch the SMS game-heap constant (5MB -> 7MB) in main.dol INSIDE a GC ISO.

The HD-portal previews (AI-3x THP, ~1.2MB) don't fit in the stock 5MB
TApplication heap -> JKRHeap.cpp abort on Delfino load. The heap size is a
hardcoded constant in TApplication::initialize; a Gecko 04-write applies too
late (initialize runs at boot before the code handler), so it must be a DOL
patch baked into the disc.

USA sites (verified 0x3C600050 / 0x3C800050 = lis r3,0x50 / lis r4,0x50):
  0x802A74E8 -> lis r3,0x70   (0x3C600070)
  0x802A74FC -> lis r4,0x70   (0x3C800070)

Usage:  python3 iso_heappatch.py <game.iso>
"""
import struct, sys

SITES = {0x802A74E8: (0x3C600050, 0x3C600070),
         0x802A74FC: (0x3C800050, 0x3C800070)}

def main():
    iso = sys.argv[1]
    f = open(iso, "r+b")
    f.seek(0x420)
    dol_off = struct.unpack(">I", f.read(4))[0]              # boot DOL offset (ISO header 0x420)
    f.seek(dol_off)
    h = f.read(0xE4)
    t_off = struct.unpack(">7I",  h[0x00:0x1C]); t_a = struct.unpack(">7I",  h[0x48:0x64]); t_s = struct.unpack(">7I",  h[0x90:0xAC])
    d_off = struct.unpack(">11I", h[0x1C:0x48]); d_a = struct.unpack(">11I", h[0x64:0x90]); d_s = struct.unpack(">11I", h[0xAC:0xD8])
    segs = list(zip(t_off, t_a, t_s)) + list(zip(d_off, d_a, d_s))

    def va_to_iso(va):
        for o, a, s in segs:
            if s and a <= va < a + s:
                return dol_off + o + (va - a)
        raise SystemExit(f"{va:#x} not in DOL (dol_off={dol_off:#x})")

    changed = 0
    for va, (old, new) in SITES.items():
        pos = va_to_iso(va)
        f.seek(pos); cur = struct.unpack(">I", f.read(4))[0]
        if cur == new:
            print(f"  {va:#x}: already patched ({new:#010x})"); continue
        if cur != old:
            raise SystemExit(f"  {va:#x}: expected {old:#010x}, found {cur:#010x} — ABORT (wrong DOL/region?)")
        f.seek(pos); f.write(struct.pack(">I", new)); changed += 1
        print(f"  {va:#x}: {old:#010x} -> {new:#010x}  (iso offset {pos:#x})")
    f.close()
    print(f"heap patch done ({changed} word(s) written)")

if __name__ == "__main__":
    main()
