"""Disassemble a GX FIFO stream dump (fifodump.bin) to find a vertex-count desync.

Usage: python3 gxdisasm.py /tmp/fifodump.bin <start_phys> [end_phys]

Tracks CP VCD/VAT registers from the stream itself to compute vertex sizes.
Draw commands print prim/vat/count/vsize; BP token writes (0x61 47/48xxxxxx)
are flagged since SMS's DrawSyncManager tokens are unambiguous landmarks.
"""
import struct, sys

DUMP_BASE = 0x00440000

CP_SIZES_POSNRM = {0: 0, 1: None, 2: 1, 3: 2}  # none/direct/idx8/idx16 (direct computed)

def u8(b, i): return b[i]
def u16(b, i): return struct.unpack(">H", b[i:i+2])[0]
def u32(b, i): return struct.unpack(">I", b[i:i+4])[0]

COMP_SIZE = [1, 1, 2, 2, 4]  # u8,s8,u16,s16,f32

def pos_size(vat_a):
    fmt = (vat_a >> 1) & 7
    cnt = 2 + (vat_a & 1)          # xy / xyz
    return COMP_SIZE[fmt] * cnt

def nrm_size(vat_a):
    fmt = (vat_a >> 10) & 7
    cnt3 = (vat_a >> 9) & 1        # 0: 3 comps, 1: 9 comps (NBT)
    return COMP_SIZE[fmt] * (9 if cnt3 else 3)

def clr_size(vat, shift):
    fmt = (vat >> (shift + 1)) & 7
    return {0: 2, 1: 3, 2: 4, 3: 2, 4: 3, 5: 4}.get(fmt, 4)

def tex_size(vat_b_or_c, shift):
    fmt = (vat_b_or_c >> (shift + 1)) & 7
    cnt = (vat_b_or_c >> shift) & 1  # s / st
    return COMP_SIZE[fmt] * (1 + cnt)

class VtxState:
    def __init__(self):
        self.cp = {}
    def vcd(self):
        lo = self.cp.get(0x50, 0)
        hi = self.cp.get(0x60, 0)
        return lo, hi
    def vertex_size(self, vat):
        lo, hi = self.vcd()
        a = self.cp.get(0x70 + vat, 0)
        b = self.cp.get(0x80 + vat, 0)
        c = self.cp.get(0x90 + vat, 0)
        sz = 0
        # pnmtxidx + texmtxidx 0-7: 1 byte each if enabled (bits 0..8 of vcd_lo)
        for bit in range(9):
            if (lo >> bit) & 1:
                sz += 1
        # position bits 9-10
        mode = (lo >> 9) & 3
        if mode == 1: sz += pos_size(a)
        elif mode == 2: sz += 1
        elif mode == 3: sz += 2
        # normal bits 11-12
        mode = (lo >> 11) & 3
        if mode == 1: sz += nrm_size(a)
        elif mode == 2: sz += 1
        elif mode == 3: sz += 2
        # colors bits 13-14, 15-16
        for k, shift in ((0, 13), (1, 15)):
            mode = (lo >> shift) & 3
            if mode == 1: sz += clr_size(a, 13 if k == 0 else 17) if False else clr_size_direct(a, k)
            elif mode == 2: sz += 1
            elif mode == 3: sz += 2
        # tex coords 0-7: 2 bits each in vcd_hi
        for t in range(8):
            mode = (hi >> (t * 2)) & 3
            if mode == 1:
                if t == 0: sz += tex_size(a, 21) if False else tex0_size(a)
                elif t < 4: sz += tex_n_size(b, t)
                else: sz += tex_n_size_c(c, t)
            elif mode == 2: sz += 1
            elif mode == 3: sz += 2
        return sz

def clr_size_direct(vat_a, idx):
    # VAT_A: col0 bits 13-16 (cnt bit13? fmt 14-16), col1 bits 17-20
    shift = 13 if idx == 0 else 17
    fmt = (vat_a >> (shift + 1)) & 7
    return {0: 2, 1: 3, 2: 4, 3: 2, 4: 3, 5: 4}.get(fmt, 4)

def tex0_size(vat_a):
    # VAT_A tex0: cnt bit21, fmt bits 22-24
    fmt = (vat_a >> 22) & 7
    cnt = (vat_a >> 21) & 1
    return COMP_SIZE[fmt] * (1 + cnt)

def tex_n_size(vat_b, t):
    # VAT_B: tex1 cnt bit0 fmt1-3, tex2 cnt9 fmt10-12, tex3 cnt18 fmt19-21 (9 bits per tex)
    shift = (t - 1) * 9
    fmt = (vat_b >> (shift + 1)) & 7
    cnt = (vat_b >> shift) & 1
    return COMP_SIZE[fmt] * (1 + cnt)

def tex_n_size_c(vat_c, t):
    shift = (t - 4) * 9 + 5   # VAT_C: tex4 starts at bit 5? (tex4 cnt bit5? not exact)
    fmt = (vat_c >> (shift + 1)) & 7
    cnt = (vat_c >> shift) & 1
    return COMP_SIZE[fmt] * (1 + cnt)

PRIMS = {0x80: "QUADS", 0x88: "QUADS2", 0x90: "TRIS", 0x98: "TRISTRIP",
         0xA0: "TRIFAN", 0xA8: "LINES", 0xB0: "LINESTRIP", 0xB8: "POINTS"}

def main():
    path, start = sys.argv[1], int(sys.argv[2], 16)
    end = int(sys.argv[3], 16) if len(sys.argv) > 3 else None
    b = open(path, "rb").read()
    i = start - DUMP_BASE
    lim = (end - DUMP_BASE) if end else len(b)
    st = VtxState()
    zeros = 0
    while i < lim:
        op = b[i]
        pos_phys = DUMP_BASE + i
        if op == 0x00:
            zeros += 1
            i += 1
            continue
        if zeros:
            print(f"  ({zeros} NOP bytes)")
            zeros = 0
        if op == 0x61:
            v = u32(b, i + 1)
            reg = v >> 24
            tag = ""
            if reg == 0x47: tag = f"  <<< DRAWSYNC TOKEN(lo?) {v & 0xFFFF:#06x}"
            if reg == 0x48: tag = f"  <<< DRAWSYNC TOKEN INT {v & 0xFFFF:#06x}"
            if reg == 0x45: tag = "  <<< SETDRAWDONE"
            if reg in (0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f, 0x52):
                tag = "  (efb copy reg)"
            print(f"{pos_phys:08x}: BP  {v:08x}{tag}")
            i += 5
        elif op == 0x08:
            reg = b[i + 1]
            v = u32(b, i + 2)
            st.cp[reg] = v
            name = {0x50: "VCD_LO", 0x60: "VCD_HI"}.get(reg, f"CP{reg:02x}")
            print(f"{pos_phys:08x}: CP  {name} = {v:08x}")
            i += 6
        elif op == 0x10:
            v = u32(b, i + 1)
            n = ((v >> 16) & 0xFFFF) + 1
            addr = v & 0xFFFF
            print(f"{pos_phys:08x}: XF  addr={addr:04x} n={n}")
            i += 5 + n * 4
        elif op in (0x20, 0x28, 0x30, 0x38):
            print(f"{pos_phys:08x}: XF-indexed {op:02x}")
            i += 5
        elif op == 0x40:
            addr, size = u32(b, i + 1), u32(b, i + 5)
            print(f"{pos_phys:08x}: CALL DL addr={addr:08x} size={size:#x}")
            i += 9
        elif op == 0x48:
            print(f"{pos_phys:08x}: INVL VTX CACHE")
            i += 1
        elif (op & 0x80) and (op & 0xF8) in PRIMS:
            vat = op & 7
            cnt = u16(b, i + 1)
            vsz = st.vertex_size(vat)
            total = cnt * vsz
            print(f"{pos_phys:08x}: DRAW {PRIMS[op & 0xF8]} vat={vat} count={cnt} "
                  f"vsize={vsz} bytes={total:#x}"
                  + ("   <<<<<< HUGE" if cnt > 10000 else ""))
            i += 3 + total
        else:
            print(f"{pos_phys:08x}: ?? opcode {op:02x} — decoder lost, next 32 bytes:")
            print("   " + b[i:i+32].hex(" "))
            # try to resync at next known opcode
            i += 1
    if zeros:
        print(f"  ({zeros} NOP bytes)")

main()
