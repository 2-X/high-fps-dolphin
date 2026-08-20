"""Live BSE runtime-hook collision check.

For every address our Gecko stack hooks (hook-addresses.txt) plus the pollution
system's entry points, compare the LIVE instruction word in the running Dolphin
against the stock DOL and the BSE-release DOL. Decode branches to see where
they land:
  - branch to 0x818xxxxx  -> our Gecko C2 cave (relocated codelist, expected for
    every ENABLED code)
  - branch anywhere else / other mutation not in either DOL -> Kuribo/BSE
    RUNTIME trampoline  <- the collision candidate doldiff could not see
Also dumps the low-arena scratch block 0x800016C0..0x8000173F and key globals.
"""
import os, struct, sys

sys.path.insert(0, r"C:\code\high-fps-dolphin\sunshine\research\scripts")
import gcmem

STOCK = r"C:\code\high-fps-dolphin\sunshine\research\main.dol"
BSE   = r"C:\code\high-fps-dolphin\sunshine\bsmso\bse-release\BetterSunshineEngine_RELEASE\main.dol"
HOOKS = r"C:\code\high-fps-dolphin\sunshine\bsmso\hook-addresses.txt"

def dolw(path, va):
    try:
        return struct.unpack(">I", gcmem.dol_bytes(path, va, 4))[0]
    except SystemExit:
        return None

def br_target(va, w):
    """Decode b/bl (opcode 18) absolute target, else None."""
    if w is None or (w >> 26) != 18 or (w & 2):   # skip AA-form
        return None
    off = w & 0x03FFFFFC
    if off & 0x02000000:
        off -= 0x04000000
    return (va + off) & 0xFFFFFFFF

pid = gcmem.find_dolphin_pid()
if not pid:
    raise SystemExit("no Dolphin process")
d = gcmem.Dolphin(pid, STOCK)
print(f"pid {pid}  MEM1 base {d.base:#x}")

addrs = sorted({int(l, 16) for l in open(HOOKS) if l.strip()} |
               {0x8019D8C8, 0x8019B120, 0x8019B16C, 0x8019CA18,
                0x8019B3A0, 0x8019B334, 0x8019D8D0, 0x8019D8F8,
                0x8019D900, 0x8019D940})

print(f"\n{'addr':10} {'live':>8} {'stock':>8} {'bsedol':>8}  verdict")
n_stock = n_gecko = n_runtime = 0
for va in addrs:
    live = d.u32(va)
    s, b = dolw(STOCK, va), dolw(BSE, va)
    if live is None:
        print(f"{va:#010x}  <unreadable>")
        continue
    if s is None:            # not in DOL (low arena / bss) -> data, show raw
        print(f"{va:#010x} {live:08x} {'-':>8} {'-':>8}  DATA (not in DOL text)")
        continue
    if live == s:
        n_stock += 1
        continue             # untouched, don't spam
    t = br_target(va, live)
    if t is not None and 0x81700000 <= t <= 0x81FFFFFF:
        n_gecko += 1
        tag = "our Gecko C2 (enabled)"
    elif live == b:
        tag = "BSE DOL-level patch"
    else:
        n_runtime += 1
        tag = "*** RUNTIME HOOK (not stock, not BSE-DOL, not Gecko cave) ***"
    tstr = f"-> {t:#010x}" if t is not None else ""
    print(f"{va:#010x} {live:08x} {s:08x} {(b if b is not None else 0):08x}  {tag} {tstr}")

print(f"\nsummary: {len(addrs)} checked, {n_stock} pristine-stock, "
      f"{n_gecko} gecko-cave branches, {n_runtime} runtime hooks")

print("\nlow arena 0x800016C0..0x8000173F:")
for base in range(0x800016C0, 0x80001740, 0x10):
    row = " ".join(f"{d.u32(base+i*4):08x}" for i in range(4))
    print(f"  {base:#010x}: {row}")

print("\nglobals:")
print(f"  framerate 0x804167B8 = {d.f32(0x804167B8)!r}")
print(f"  mFPSValue 0x8051EBA8 = {d.u32(0x8051EBA8):#010x}  (fork kxe addr)")
print(f"  old mFPS  0x8051E528 = {d.u32(0x8051E528):#010x}  (stock kxe addr)")
