"""One-shot dump of the GX FIFO ring (+ GP fifo struct) from the frozen Dolphin.

Usage:  sudo python3 fifodump.py [out.bin]

Dumps GC phys 0x00440000..0x004D0000 (the FIFO ring region seen in the BP logs)
plus __GXData's fifo pointers, to out.bin (default /tmp/fifodump.bin) and prints
the GXFifoObj pointers so the offline disassembler knows rd/wr positions.
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcmem import Dolphin, find_dolphin_pid

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fifodump.bin"
DOL = os.environ.get("SMS_DOL", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.dol"))

d = Dolphin(find_dolphin_pid(), DOL)

LO, HI = 0x80440000, 0x804D0000
blob = d.read(LO, HI - LO)
with open(OUT, "wb") as f:
    f.write(blob)
print(f"dumped {HI-LO:#x} bytes {LO:#x}..{HI:#x} -> {OUT}")

# __GXData / CPU fifo struct: GXInit stores the active GXFifoObj; on SMS (USA)
# the CPU fifo obj lives in .sdata — find via low-mem OSGetCurrentFifo? Instead
# read the CP MMIO mirror the game keeps: dump a few candidate globals.
# Simplest robust source: the game's GXFifoObj for the GP fifo is at 0x804167E8
# region-ish; rather than guess symbols, print dwords around the known FIFO
# bounds so the analyst can spot base/end/rd/wr pointers (values in 0x0044-0x004D
# phys range or 0x8044-0x804D VA range).
print("scan for plausible fifo-pointer dwords in 0x80416000..0x80418000:")
region = d.read(0x80416000, 0x2000)
for off in range(0, len(region) - 4, 4):
    v = struct.unpack(">I", region[off:off + 4])[0]
    if 0x00440000 <= (v & 0x7FFFFFFF) <= 0x004D0000:
        print(f"  0x{0x80416000+off:08x}: 0x{v:08x}")
