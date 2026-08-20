"""Dump the self-linked mat packet, its vtable, drawbuffer state, and the
entry-function prologues (to pin which entry path created the 1-cycle)."""
import sys, struct
sys.path.insert(0, r"C:\code\high-fps-dolphin\sunshine\research\scripts")
from gcmem import Dolphin, find_dolphin_pid
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

DOL = r"C:\code\high-fps-dolphin\sunshine\research\main.dol"
d = Dolphin(find_dolphin_pid(), DOL)
cs = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

PKT = 0x813AD984
b = d.read(PKT, 0x60)
w = struct.unpack(">24I", b)
print(f"mat packet {PKT:#x}:")
for i in range(0, 24, 4):
    print("  +%02x:" % (i * 4), " ".join(f"{w[i+j]:08x}" for j in range(4)))
print("  +3C word:", f"{w[0xF]:08x}", " top bit:", (w[0xF] >> 31) & 1)
print("  +44 word:", f"{w[0x11]:08x}")

vt = w[0]
vtw = struct.unpack(">12I", d.read(vt, 48))
print(f"\nvtable {vt:#x}:", " ".join(f"{x:08x}" for x in vtw))

# shape packet at +0x34
sh = w[13]
if 0x80000000 <= sh < 0x81800000:
    sw = struct.unpack(">16I", d.read(sh, 64))
    print(f"\nshape pkt {sh:#x} vt={sw[0]:08x} next={sw[1]:08x} +14={sw[5]:08x}")

# drawbuffer 0x81317040 full state
arr, cnt = d.u32(0x81317040), d.u32(0x81317044)
print(f"\ndrawbuffer 0x81317040: arr={arr:#x} cnt={cnt}")
ents = struct.unpack(f">{cnt}I", d.read(arr, 4 * cnt))
print("  buckets:", " ".join(f"{e:08x}" for e in ents))

# entry prologues
for lo, hi, note in ((0x802EF680, 0x802EF6D0, "func A entry (0x802EF6A4?)"),
                     (0x802EF5C0, 0x802EF680, "func before / 0x802EF5F8 ctx")):
    print(f"\n===== {lo:#010x}..{hi:#010x} {note} =====")
    blob = d.read(lo, hi - lo)
    for ins in cs.disasm(blob, lo):
        print(f"  {ins.address:08x}: {ins.mnemonic:10s} {ins.op_str}")
