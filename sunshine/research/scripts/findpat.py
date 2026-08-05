"""Scan the DOL .text for JUTGamePad::CButton::update's edge-computation.

    mTrigger = buttons & (buttons ^ mButton)
    mRelease = mButton  & (buttons ^ mButton)
    mButton  = buttons

compiles to an `xor` followed closely by two `and`s. Very rare in this binary.
"""
import struct, os, sys

DOL = os.environ["SMS_DOL"]
data = open(DOL, "rb").read()
th_off = struct.unpack(">7I", data[0x00:0x1C]); th_a = struct.unpack(">7I", data[0x48:0x64]); th_s = struct.unpack(">7I", data[0x90:0xAC])
TEXT = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]

def is_xreg(w, ext):
    return (w >> 26) == 31 and ((w >> 1) & 0x3FF) == ext

XOR, AND = 316, 28

for a0, a1, off in TEXT:
    words = [struct.unpack(">I", data[off+i:off+i+4])[0] for i in range(0, a1-a0, 4)]
    for i, w in enumerate(words):
        if not is_xreg(w, XOR):
            continue
        window = words[i+1:i+5]
        if sum(1 for x in window if is_xreg(x, AND)) >= 2:
            print(f"{a0 + i*4:08x}  xor + 2x and")
