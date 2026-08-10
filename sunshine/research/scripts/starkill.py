"""starkill.py — interactive kill-test for the stuck-stars bug.

Enumerates every ACTIVE emitter (walking group lists of every JPAEmitterManager
found via known globals + heap scan), prints them, and stops them in batches so
the user can say when the visible stars disappear.

  SMS_DOL=../main.dol python3 starkill.py list          # show all active emitters
  SMS_DOL=../main.dol python3 starkill.py stop2d        # stop all 2D-manager emitters
  SMS_DOL=../main.dol python3 starkill.py stopall       # stop every emitter everywhere
  SMS_DOL=../main.dol python3 starkill.py stop ADDR...  # stop specific emitters
"""
import os, sys, ctypes, struct
from gcmem import Dolphin, find_dolphin_pid, _libc

GP_EM4D2 = 0x8040E1E4          # gpEmitterManager4D2 ([r13-0x5fdc])
GP_MARDIRECTOR = 0x8040E178

d = Dolphin(find_dolphin_pid(), os.environ["SMS_DOL"])
_libc.mach_vm_write.argtypes = [ctypes.c_uint, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint]
_libc.mach_vm_write.restype = ctypes.c_int


def wr32(va, val):
    buf = ctypes.create_string_buffer(struct.pack(">I", val))
    return _libc.mach_vm_write(d._be.task, d.base + (va - 0x80000000), ctypes.addressof(buf), 4)


def walk_group_lists(mgr):
    """Yield active emitters from mgr->unk44[0..7] JSULists.
    JSULink layout observed: [obj, list, next, prev]? walk defensively via
    head/tail/count and link-word candidates."""
    out = []
    for gid in range(8):
        head, tail, n = struct.unpack(">3I", d.read(mgr + 0x44 + 12 * gid, 12))
        if not n or not (0x80000000 <= head < 0x81800000):
            continue
        ln = head
        seen = set()
        for _ in range(n + 4):
            if not ln or not (0x80000000 <= ln < 0x81800000) or ln in seen:
                break
            seen.add(ln)
            w = struct.unpack(">4I", d.read(ln, 16))
            # try to identify the emitter object: candidates w[0] or ln itself
            obj = w[0] if 0x80000000 <= w[0] < 0x81800000 else ln
            out.append(obj)
            # next link: try each word that looks like a pointer and isn't obj/list
            nxt = 0
            for cand in (w[2], w[1], w[3]):
                if cand != ln and 0x80000000 <= cand < 0x81800000 and cand not in seen:
                    # heuristic: a link points at another emitter whose +0x10C mgr matches
                    m2 = d.u32(cand + 0x10C)
                    if m2 == mgr:
                        nxt = cand
                        break
            ln = nxt
    return out


def heap_actives(mgr):
    """Fallback: scan heap for emitters with mManager==mgr and un-stopped status,
    NOT distinguishing free-list ghosts (caller beware)."""
    out = []
    for lo, hi in ((0x80900000, 0x80B00000),):
        blob = d.read(lo, hi - lo)
        if not blob:
            continue
        for off in range(0x10C, len(blob) - 0x220, 4):
            if struct.unpack(">I", blob[off:off + 4])[0] == mgr:
                base = lo + off - 0x10C
                st = struct.unpack(">I", blob[off + 0x10:off + 0x14])[0]
                if st < 0x100 and not (st & 1):
                    out.append(base)
    return out


def describe(em):
    st = d.u32(em + 0x11C)
    age = d.f32(em + 0x10)
    maxf = struct.unpack(">i", d.read(em + 0x1E8, 4))[0]
    n1, n2 = d.u32(em + 0xFC), d.u32(em + 0x108)
    pos = struct.unpack(">3f", d.read(em + 0x160, 12))
    return (f"{em:08x} st={st:#04x} maxF={maxf} age={age:.0f} particles={n1}+{n2} "
            f"pos=({pos[0]:.0f},{pos[1]:.0f},{pos[2]:.0f})")


def managers():
    ms = {"2D(4D2)": d.u32(GP_EM4D2)}
    # other managers via heap: collect distinct mManager values of emitter-shaped objs
    lo, hi = 0x80900000, 0x80B00000
    blob = d.read(lo, hi - lo)
    seen = {}
    for off in range(0x10C, len(blob) - 0x220, 4):
        m = struct.unpack(">I", blob[off:off + 4])[0]
        if 0x80900000 <= m < 0x80B00000:
            st = struct.unpack(">I", blob[off + 0x10:off + 0x14])[0]
            if st < 0x100:
                seen[m] = seen.get(m, 0) + 1
    for m, cnt in sorted(seen.items()):
        if cnt >= 2 and m not in ms.values():
            ms[f"mgr_{m:08x}"] = m
    return ms


cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

if cmd == "list":
    for name, mgr in managers().items():
        if not mgr:
            continue
        ems = walk_group_lists(mgr)
        if ems:
            print(f"[{name}] manager {mgr:#x}: {len(ems)} in group lists")
            for em in ems:
                print("   ", describe(em))
elif cmd == "stop2d":
    mgr = d.u32(GP_EM4D2)
    ems = walk_group_lists(mgr) or heap_actives(mgr)
    for em in ems:
        st = d.u32(em + 0x11C)
        if not st & 1:
            wr32(em + 0x11C, st | 1)
            print("stopped", describe(em))
elif cmd == "stopall":
    for name, mgr in managers().items():
        if not mgr:
            continue
        for em in walk_group_lists(mgr):
            st = d.u32(em + 0x11C)
            if st is not None and not st & 1:
                wr32(em + 0x11C, st | 1)
                print(f"stopped [{name}]", describe(em))
elif cmd == "stop":
    for a in sys.argv[2:]:
        em = int(a, 16)
        st = d.u32(em + 0x11C)
        wr32(em + 0x11C, st | 1)
        print("stopped", describe(em))
