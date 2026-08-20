"""Disassemble LIVE emulated memory (includes C2 patches) from a running
Dolphin. Usage:  python livedisasm.py 802EF6C0 802EFA60  [more lo hi pairs]

Reads through gcmem (so 0x81800000+ relocated-codelist caves work too when
the host mapping is contiguous). For pristine bytes use gcmem.dol_bytes."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcmem import Dolphin, find_dolphin_pid
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

DOL = os.environ.get("SMS_DOL",
    r"C:\code\high-fps-dolphin\sunshine\research\main.dol")
d = Dolphin(find_dolphin_pid(), DOL)
cs = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

args = [int(a, 16) for a in sys.argv[1:]]
if not args or len(args) % 2:
    raise SystemExit(__doc__)
for lo, hi in zip(args[::2], args[1::2]):
    print(f"===== {lo:#010x}..{hi:#010x} =====")
    blob = d.read(lo, hi - lo)
    if blob is None:
        print("  (unreadable)")
        continue
    a = lo
    for ins in cs.disasm(blob, lo):
        print(f"  {ins.address:08x}: {ins.bytes.hex()}  {ins.mnemonic:10s} {ins.op_str}")
        a = ins.address + 4
    if a < hi:
        print(f"  (capstone stopped at {a:#x}; raw words follow)")
        import struct
        rest = blob[a - lo:]
        for i in range(0, len(rest) - 3, 4):
            print(f"  {a + i:08x}: {struct.unpack('>I', rest[i:i+4])[0]:08x}")
