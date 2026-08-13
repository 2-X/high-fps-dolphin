#!/usr/bin/env python3
"""Diff two Super Mario Sunshine main.dol files for Gecko-hook collisions.

Usage: doldiff.py <original main.dol> <patched main.dol> <hook-addresses.txt>

Reports:
  1. Section-table differences (added/moved/resized sections, entry point, BSS).
  2. For every hook address: bytes in original vs patched (COLLISION if different,
     or if the address maps to a section that exists only in one DOL).
  3. Global map of changed byte-ranges within sections common to both DOLs.
"""
import struct
import sys


def parse_dol(path):
    d = open(path, "rb").read()
    hdr = struct.unpack(">18I18I18I3I", d[:0xE4])
    offs, addrs, sizes = hdr[0:18], hdr[18:36], hdr[36:54]
    bss_addr, bss_size, entry = hdr[54], hdr[55], hdr[56]
    secs = []
    for i in range(18):
        if sizes[i]:
            kind = "text" if i < 7 else "data"
            secs.append((kind, i, offs[i], addrs[i], sizes[i]))
    return d, secs, bss_addr, bss_size, entry


def vaddr_to_off(secs, va):
    for kind, i, off, addr, size in secs:
        if addr <= va < addr + size:
            return off + (va - addr), (kind, i)
    return None, None


def main(orig_path, patch_path, addr_path):
    od, osecs, obss, obsz, oent = parse_dol(orig_path)
    pd, psecs, pbss, pbsz, pent = parse_dol(patch_path)

    print("== SECTION TABLES ==")
    print(f"{'':14}{'ORIGINAL':34}{'PATCHED'}")
    fmt = lambda s: f"{s[0]}{s[1]:<2} off={s[2]:08X} va={s[3]:08X} sz={s[4]:X}"
    omap = {(s[0], s[1]): s for s in osecs}
    pmap = {(s[0], s[1]): s for s in psecs}
    for key in sorted(set(omap) | set(pmap), key=lambda k: (k[0], k[1])):
        o = fmt(omap[key]) if key in omap else "(absent)"
        p = fmt(pmap[key]) if key in pmap else "(absent)"
        mark = "" if omap.get(key) == pmap.get(key) else "   <-- DIFFERS"
        print(f"  {o:44} | {p}{mark}")
    print(f"  entry: {oent:08X} -> {pent:08X}{'   <-- DIFFERS' if oent != pent else ''}")
    print(f"  bss:   {obss:08X}+{obsz:X} -> {pbss:08X}+{pbsz:X}"
          f"{'   <-- DIFFERS' if (obss, obsz) != (pbss, pbsz) else ''}")

    print("\n== HOOK ADDRESSES ==")
    collisions = 0
    for line in open(addr_path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        va = int(line, 16)
        ooff, osec = vaddr_to_off(osecs, va)
        poff, psec = vaddr_to_off(psecs, va)
        ob = od[ooff:ooff + 4].hex() if ooff is not None else "----"
        pb = pd[poff:poff + 4].hex() if poff is not None else "----"
        if ooff is None and poff is None:
            status = "not in either DOL (runtime/scratch addr)"
        elif ooff is None or poff is None:
            status = "SECTION MISMATCH — present in only one DOL"
            collisions += 1
        elif ob != pb:
            status = f"COLLISION  {ob} -> {pb}"
            collisions += 1
        else:
            status = f"ok ({ob})"
        print(f"  {va:08X}  {status}")
    print(f"\n  hook collisions: {collisions}")

    print("\n== CHANGED RANGES (sections present in both, same va) ==")
    for key in sorted(set(omap) & set(pmap), key=lambda k: (k[0], k[1])):
        ks, ki, ooff, ova, osz = omap[key]
        _, _, poff, pva, psz = pmap[key]
        if ova != pva:
            print(f"  {ks}{ki}: va moved {ova:08X}->{pva:08X}, skipping byte diff")
            continue
        n = min(osz, psz)
        a, b = od[ooff:ooff + n], pd[poff:poff + n]
        i, ranges = 0, []
        while i < n:
            if a[i] != b[i]:
                j = i
                while j < n and (a[j] != b[j] or (j - i < 8 and any(
                        a[k] != b[k] for k in range(j, min(j + 8, n))))):
                    j += 1
                ranges.append((i, j))
                i = j
            else:
                i += 1
        if osz != psz:
            print(f"  {ks}{ki}: size {osz:X} -> {psz:X} (tail {'grown' if psz > osz else 'shrunk'})")
        for i, j in ranges:
            print(f"  {ks}{ki}: {ova + i:08X}..{ova + j:08X} ({j - i} bytes)")
        if not ranges and osz == psz:
            print(f"  {ks}{ki}: identical")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:4])
