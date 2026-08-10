"""Locate TCardSave::initData and TCardSave::waitForSelect2 in USA main.dol.

Signatures:
- initData: materializes pane-name constants 'sm1a' 0x736d3161, 'sc1a' 0x73633161
- waitForSelect2: SE ids 0x481C/0x481E, message overrides 0x1C..0x20, input bits 0x2/0x4/0x20
Usage: SMS_DOL=../main.dol python3 savefind.py
"""
import struct, os

DOL = os.environ.get("SMS_DOL", "../main.dol")
data = open(DOL, "rb").read()
th_off = struct.unpack(">7I", data[0x00:0x1C]); th_a = struct.unpack(">7I", data[0x48:0x64]); th_s = struct.unpack(">7I", data[0x90:0xAC])
d_off  = struct.unpack(">11I", data[0x1C:0x48]); d_a = struct.unpack(">11I", data[0x64:0x90]); d_s = struct.unpack(">11I", data[0xAC:0xD8])
TEXT = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]

def scan_pairs(hi16, lo16s):
    """find lis rX,hi16 followed within 8 insns by addi/ori with lo16"""
    hits = []
    for a0, a1, off in TEXT:
        buf = data[off:off + (a1 - a0)]
        for i in range(0, len(buf) - 4, 4):
            w = struct.unpack(">I", buf[i:i+4])[0]
            # lis rX, hi16  => addis rX,0,hi16: opcode 15, rA=0
            if (w >> 26) == 15 and ((w >> 16) & 0x1F) == 0 and (w & 0xFFFF) == hi16:
                for j in range(i + 4, min(i + 4 + 8 * 4, len(buf) - 4), 4):
                    w2 = struct.unpack(">I", buf[j:j+4])[0]
                    op2 = w2 >> 26
                    if op2 in (14, 24) and (w2 & 0xFFFF) in lo16s:  # addi/ori
                        hits.append((a0 + i, a0 + j, w2 & 0xFFFF))
    return hits

print("== 'sm1a' 0x736d3161 sites (initData loop / textbox search) ==")
for lis_va, lo_va, lo in scan_pairs(0x736D, {0x3161, 0x3162}):
    print(f"  lis @{lis_va:#010x}  lo16={lo:#06x} @{lo_va:#010x}")
print("== 'sc1a' 0x73633161 sites ==")
for lis_va, lo_va, lo in scan_pairs(0x7363, {0x3161, 0x3162}):
    print(f"  lis @{lis_va:#010x}  lo16={lo:#06x} @{lo_va:#010x}")

# waitForSelect2: look for li rX,0x481C followed soon by li rX,0x481E within same fn range
print("== SE id 0x481C (li) sites ==")
for a0, a1, off in TEXT:
    buf = data[off:off + (a1 - a0)]
    for i in range(0, len(buf) - 4, 4):
        w = struct.unpack(">I", buf[i:i+4])[0]
        if (w >> 26) == 14 and ((w >> 16) & 0x1F) == 0 and (w & 0xFFFF) == 0x481C:
            print(f"  li @{a0+i:#010x}")
