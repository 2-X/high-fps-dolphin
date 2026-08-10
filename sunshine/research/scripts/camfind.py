#!/usr/bin/env python3
"""Locate CPolarSubCamera camera-pitch functions in the USA (GMSE01) main.dol.

Decomp (JP/PAL) ground truth, offsets identical across regions (same class layout):
  rotateX_ByStickY_(f32):  bl SMS_IsMarioOpeningDoor early-out, then
      lwz   rP, 0x68(r3)        # mCurrentParams
      lfs   f?, 0x1C(rP)        # mXRotRatioManualSpeed
      fmuls ...
      lfs/stfs f?, 0xA8(r3)     # mCurrentTarget.unk28 (X-rot ratio)
      clamp: either [0,1] (L-button modes) or [unk268, unk26C] = 0x268/0x26C(r3)
  size 0xC4 in JP/PAL, preceded by rotateY_ByStickX_ (0x90) which shares the
  same bl target + a lha 0xA6(r3) (mYaw) store.

  calcSlopeAngleX_(s16*): big (0x2F8); tail does
      lha   r?, 0x28C(r3)       # unk28C slope chase
      subf  ...                 # *param -= unk28C
      clamp vs mSaveEx->mSLLimitMinAngleX/Max (param loads via ptr)
  Distinctive: only function with both lha 0x28C(r3) and sth to param reg,
  plus earlier float const 10.0f and calls to matan.
"""
import struct, sys
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

DOL = sys.argv[1] if len(sys.argv) > 1 else "/Users/kbrethower/code/high-fps-dolphin/sunshine/research/main.dol"
data = open(DOL, "rb").read()
t_off = struct.unpack(">7I", data[0x00:0x1C])
t_addr = struct.unpack(">7I", data[0x48:0x64])
t_size = struct.unpack(">7I", data[0x90:0xAC])
SEGS = [(a, a + s, o) for o, a, s in zip(t_off, t_addr, t_size) if s]

def words(a0, a1, off):
    n = (a1 - a0) // 4
    return struct.unpack(f">{n}I", data[off:off + (a1 - a0)])

def opcd(w): return w >> 26
def rD(w): return (w >> 21) & 31
def rA(w): return (w >> 16) & 31
def d16(w): return w & 0xFFFF

LFS, STFS, LWZ, LHA, STH = 48, 52, 32, 42, 44

for a0, a1, off in SEGS:
    ws = words(a0, a1, off)
    for i, w in enumerate(ws):
        # anchor: stfs fX, 0xA8(r3)
        if opcd(w) == STFS and rA(w) == 3 and d16(w) == 0xA8:
            lo = max(0, i - 24); hi = min(len(ws), i + 24)
            win = ws[lo:hi]
            has_speed = any(opcd(x) == LFS and d16(x) == 0x1C for x in win)
            has_268 = any(opcd(x) == LFS and rA(x) == 3 and d16(x) == 0x268 for x in win)
            has_26c = any(opcd(x) == LFS and rA(x) == 3 and d16(x) == 0x26C for x in win)
            if has_speed or (has_268 and has_26c):
                print(f"ratio-store candidate @ {a0 + i*4:08X}  speed={has_speed} 268={has_268} 26c={has_26c}")
        # anchor: lha rX, 0x28C(r3)
        if opcd(w) == LHA and rA(w) == 3 and d16(w) == 0x28C:
            print(f"unk28C load @ {a0 + i*4:08X}")
