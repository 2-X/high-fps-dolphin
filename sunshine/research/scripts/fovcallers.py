#!/usr/bin/env python3
"""fovcallers.py — audit every `bl C_MTXPerspective (0x8034A404)` caller in USA main.dol.

For each call site, walk backward through the caller's instructions tracking the
last writer of f1 (the fovy argument) and classify it:
  - sdata2 constant via r2      -> resolved to the actual float value
  - sdata constant via r13      -> resolved to the actual float value
  - camera mFovy load (+0x48)   -> "camera fovy" (gameplay)
  - other object-field load     -> offset reported
  - stack reload                -> try to pair with a prior stfs of a known value
  - fmr / arithmetic            -> traced one level / reported raw

READ-ONLY. Usage:  python3 fovcallers.py [dolpath]
"""
import struct, sys

DOL = sys.argv[1] if len(sys.argv) > 1 else "/Users/kbrethower/code/high-fps-dolphin/sunshine/research/main.dol"
TARGET = 0x8034A404
R2_BASE = 0x80416B80


class Dol:
    def __init__(self, path):
        d = open(path, "rb").read()
        self.d = d
        th_off = struct.unpack(">7I", d[0x00:0x1C]); th_a = struct.unpack(">7I", d[0x48:0x64])
        th_s = struct.unpack(">7I", d[0x90:0xAC])
        da_off = struct.unpack(">11I", d[0x1C:0x48]); da_a = struct.unpack(">11I", d[0x64:0x90])
        da_s = struct.unpack(">11I", d[0xAC:0xD8])
        self.text = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]
        self.segs = self.text + [(a, a + s, o) for o, a, s in zip(da_off, da_a, da_s) if s]

    def u32(self, va):
        for a0, a1, o in self.text:
            if a0 <= va < a1:
                return struct.unpack(">I", self.d[o + va - a0:o + va - a0 + 4])[0]
        return None

    def read_f32(self, va):
        for a0, a1, o in self.segs:
            if a0 <= va < a1:
                return struct.unpack(">f", self.d[o + va - a0:o + va - a0 + 4])[0]
        return None

    def fstart(self, a, floor=0x80003100):
        while a > floor:
            w = self.u32(a - 4)
            if w == 0x4E800020:
                return a
            a -= 4
        return floor


def sext16(v):
    return v - 0x10000 if v & 0x8000 else v


def bl_target(w, a):
    if w is None or (w >> 26) != 18 or (w & 3) != 1:
        return None
    off = w & 0x03FFFFFC
    if off & 0x02000000:
        off -= 0x04000000
    return (a + off) & 0xFFFFFFFF


dol = Dol(DOL)

# ---- find r13 base (SDA) from __init_registers: lis r13,H / [ori|addi] r13,r13,L
R13_BASE = None
for a0, a1, o in dol.text:
    a = a0
    while a < a1 - 4:
        w = dol.u32(a)
        if w is not None and (w >> 26) == 15 and ((w >> 21) & 31) == 13 and ((w >> 16) & 31) == 0:  # lis r13
            hi = (w & 0xFFFF) << 16
            w2 = dol.u32(a + 4)
            if w2 is not None:
                if (w2 >> 26) == 24 and ((w2 >> 16) & 31) == 13 and ((w2 >> 21) & 31) == 13:  # ori
                    R13_BASE = hi | (w2 & 0xFFFF); break
                if (w2 >> 26) == 14 and ((w2 >> 16) & 31) == 13 and ((w2 >> 21) & 31) == 13:  # addi
                    R13_BASE = (hi + sext16(w2 & 0xFFFF)) & 0xFFFFFFFF; break
        a += 4
    if R13_BASE: break
print(f"r13 (SDA) base = {R13_BASE:#010x}" if R13_BASE else "r13 base NOT found")
print(f"r2  (SDA2) base = {R2_BASE:#010x} (known)")

# ---- find all bl sites
sites = []
for a0, a1, o in dol.text:
    seg = dol.d[o:o + (a1 - a0)]
    for j in range(0, len(seg) - 3, 4):
        w = struct.unpack(">I", seg[j:j + 4])[0]
        if bl_target(w, a0 + j) == TARGET:
            sites.append(a0 + j)
print(f"\n{len(sites)} call sites of C_MTXPerspective ({TARGET:#x}):\n")


def describe_fpr_writer(site, fpr, depth=0):
    """walk backward from `site` (exclusive) to find last writer of fpr; return desc str."""
    fs = dol.fstart(site)
    a = site - 4
    stack_slots = {}  # d(r1) -> desc of stored fpr, filled lazily below
    while a >= fs and site - a <= 4 * 120:
        w = dol.u32(a)
        if w is None:
            break
        op = w >> 26
        # lfs frD, d(rA)
        if op == 48 and ((w >> 21) & 31) == fpr:
            rA = (w >> 16) & 31
            d = sext16(w & 0xFFFF)
            if rA == 2:
                va = (R2_BASE + d) & 0xFFFFFFFF
                v = dol.read_f32(va)
                return f"lfs f{fpr},{d:#x}(r2) @ {a:#x} = sdata2[{va:#x}] = {v!r}"
            if rA == 13 and R13_BASE:
                va = (R13_BASE + d) & 0xFFFFFFFF
                v = dol.read_f32(va)
                return f"lfs f{fpr},{d:#x}(r13) @ {a:#x} = sdata[{va:#x}] = {v!r}"
            if rA == 1:
                # stack reload: look further back for stfs frS, same d(r1)
                b = a - 4
                while b >= fs:
                    w2 = dol.u32(b)
                    if w2 is not None and (w2 >> 26) == 52 and ((w2 >> 16) & 31) == 1 and sext16(w2 & 0xFFFF) == d:
                        src = (w2 >> 21) & 31
                        if depth < 3:
                            inner = describe_fpr_writer(b, src, depth + 1)
                            return f"lfs f{fpr},{d:#x}(r1) @ {a:#x} <- stfs f{src} @ {b:#x} <- [{inner}]"
                        return f"lfs f{fpr},{d:#x}(r1) @ {a:#x} <- stfs f{src} @ {b:#x}"
                    b -= 4
                return f"lfs f{fpr},{d:#x}(r1) @ {a:#x} (stack, store not found in fn)"
            if d == 0x48:
                return f"lfs f{fpr},0x48(r{rA}) @ {a:#x} = CAMERA mFovy"
            return f"lfs f{fpr},{d:#x}(r{rA}) @ {a:#x} = object field +{d:#x}"
        # fmr
        if op == 63 and ((w >> 1) & 0x3FF) == 72 and ((w >> 21) & 31) == fpr:
            src = (w >> 11) & 31
            if depth < 3:
                inner = describe_fpr_writer(a, src, depth + 1)
                return f"fmr f{fpr},f{src} @ {a:#x} <- [{inner}]"
            return f"fmr f{fpr},f{src} @ {a:#x}"
        # fp arithmetic writing fpr (op 59 or 63 non-fmr)
        if op in (59, 63) and ((w >> 21) & 31) == fpr and ((w >> 1) & 0x3FF) != 72:
            xo5 = (w >> 1) & 0x1F
            names = {21: "fadds", 20: "fsubs", 25: "fmuls", 18: "fdivs", 24: "fres",
                     29: "fmadds", 28: "fmsubs", 12: "frsp"}
            nm = names.get(xo5, f"fop{op}.{xo5}")
            frA = (w >> 16) & 31; frB = (w >> 11) & 31; frC = (w >> 6) & 31
            return f"{nm} f{fpr},f{frA},f{frB}(,f{frC}) @ {a:#x} = ARITHMETIC"
        # lfd
        if op == 50 and ((w >> 21) & 31) == fpr:
            rA = (w >> 16) & 31; d = sext16(w & 0xFFFF)
            return f"lfd f{fpr},{d:#x}(r{rA}) @ {a:#x}"
        # bl (function call clobbers f1 as return? f1 is return reg)
        if (w >> 26) == 18 and (w & 3) == 1 and fpr == 1:
            t = bl_target(w, a)
            return f"bl {t:#x} @ {a:#x} (f1 = call result)"
        a -= 4
    return f"writer not found within window (fn start {fs:#x})"


for s in sorted(sites):
    fs = dol.fstart(s)
    desc = describe_fpr_writer(s, 1)
    print(f"caller {s:#010x} (fn {fs:#010x}): f1 <- {desc}")
