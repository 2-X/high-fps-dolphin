"""Freeze #7 probe (Bianco Ep.2, 240 offline): full context + guard cave check
+ drawbuffer discovery + TWO-LEVEL packet walk with explicit cycle reporting at
BOTH the mat-chain (bucket) level and the shape-chain level."""
import sys, struct
sys.path.insert(0, r"C:\code\high-fps-dolphin\sunshine\research\scripts")
from gcmem import Dolphin, find_dolphin_pid

DOL = r"C:\code\high-fps-dolphin\sunshine\research\main.dol"
d = Dolphin(find_dolphin_pid(), DOL)
PTR = lambda v: v is not None and 0x80003000 <= v < 0x81800000 and (v & 3) == 0

# ---- full thread context ----
head = d.u32(0x800000DC)
ctx = d.read(head, 0x1A0)
regs = struct.unpack(">32I", ctx[:0x80])
cr, lr, ctr = struct.unpack(">3I", ctx[0x80:0x8C])
srr0 = struct.unpack(">I", ctx[0x198:0x19C])[0]
print(f"thread {head:#x}  srr0={srr0:#010x} lr={lr:#010x} ctr={ctr:#010x}")
for i in range(0, 32, 8):
    print("  r%-2d:" % i, " ".join(f"{regs[i+j]:08x}" for j in range(8)))

# ---- guard sites: decode branch targets, dump cave heads ----
print("\nguard sites & caves:")
for a in (0x802EDC18, 0x802ED914, 0x802EFA80, 0x802EFAA0):
    w = d.u32(a)
    assert w >> 26 == 18, f"{a:#x} not a branch: {w:08x}"
    li = w & 0x03FFFFFC
    if li & 0x02000000: li -= 0x04000000
    tgt = (a + li) & 0xFFFFFFFF
    cave = d.read(tgt, 0x100)
    if cave is None:
        print(f"  {a:#010x} -> {tgt:#010x}  (cave UNREADABLE via MEM1 window)")
        continue
    cw = struct.unpack(">64I", cave)
    has_rlwinm = 0x558B463E in cw
    print(f"  {a:#010x} -> {tgt:#010x}  v2.1-rlwinm(558B463E) present: {has_rlwinm}")
    print("     head:", " ".join(f"{x:08x}" for x in cw[:8]))

# ---- stack dump (raw words for the innermost frames) ----
sp = regs[1]
print(f"\nstack from r1={sp:#x}:")
frames = []
cur = sp
for fi in range(12):
    if not (0x80000000 <= cur < 0x81800000): break
    nxt, slr = d.u32(cur), d.u32(cur + 4)
    words = struct.unpack(">8I", d.read(cur, 32))
    print(f"  frame@{cur:#010x} next={nxt:08x} lr={slr:08x} | " +
          " ".join(f"{x:08x}" for x in words[2:8]))
    frames.append((cur, slr))
    if not nxt or nxt <= cur or nxt - cur > 0x10000: break
    cur = nxt

# ---- drawbuffer discovery ----
def looks_like_drawbuffer(v):
    if not PTR(v): return None
    a0, c = d.u32(v), d.u32(v + 4)
    if not (PTR(a0) and c and c <= 1024): return None
    ok = 0
    for i in range(min(c, 16)):
        e = d.u32(a0 + 4 * i)
        if e == 0 or PTR(e): ok += 1
    return (a0, c) if ok >= min(c, 16) - 1 else None

cands = {0x81377720}
cands.update(regs)
for base, _ in frames[:6]:
    ws = struct.unpack(">16I", d.read(base, 64))
    cands.update(ws)
bufs = {}
for v in sorted(cands):
    r = looks_like_drawbuffer(v)
    if r: bufs[v] = r
print("\ndrawbuffer candidates:", {hex(k): (hex(v[0]), v[1]) for k, v in bufs.items()})

# ---- two-level walk ----
def walk_chain(start, nexto):
    """returns (members list, cycle_entry_index or None)"""
    seen, chain = {}, []
    p = start
    while PTR(p):
        if p in seen: return chain, seen[p]
        seen[p] = len(chain)
        chain.append(p)
        if len(chain) > 2000: return chain, -1
        p = d.u32(p + nexto)
    return chain, None

for bv, (arr, cnt) in bufs.items():
    print(f"\n=== drawbuffer {bv:#010x} arr={arr:#010x} cnt={cnt} ===")
    for i in range(min(cnt, 1024)):
        mp0 = d.u32(arr + 4 * i)
        if not PTR(mp0): continue
        mats, mcyc = walk_chain(mp0, 4)
        tag = ""
        if mcyc == -1: tag = " MAT-CHAIN >2000 (runaway)"
        elif mcyc is not None:
            tag = f" MAT-CYCLE entry@idx {mcyc} len {len(mats) - mcyc}"
        if tag:
            print(f" bucket {i}: mat chain len {len(mats)}{tag}")
            lo = max(0, (0 if mcyc == -1 else mcyc) - 2)
            for m in mats[lo:lo + 12]:
                w = struct.unpack(">16I", d.read(m, 64))
                print(f"   mat {m:#010x}: vt={w[0]:08x} next={w[1]:08x} "
                      f"+14={w[5]:08x} +34(shape-head)={w[13]:08x}")
        # shape chains under each mat (only walk unique mats)
        for m in mats:
            sh = d.u32(m + 0x34)
            if not PTR(sh): continue
            shapes, scyc = walk_chain(sh, 4)
            if scyc is not None:
                stag = ">2000 runaway" if scyc == -1 else f"CYCLE entry@idx {scyc} len {len(shapes) - scyc}"
                print(f" bucket {i} mat {m:#010x}: shape chain len {len(shapes)} {stag}")
                lo = max(0, (0 if scyc == -1 else scyc) - 2)
                for s in shapes[lo:lo + 12]:
                    w = struct.unpack(">16I", d.read(s, 64))
                    print(f"   shp {s:#010x}: vt={w[0]:08x} next={w[1]:08x} +14={w[5]:08x}")
        if not tag and mats and i < 64:
            print(f" bucket {i}: mats {len(mats)} ok "
                  f"(shapes: {[len(walk_chain(d.u32(m+0x34),4)[0]) for m in mats[:8]]})")
