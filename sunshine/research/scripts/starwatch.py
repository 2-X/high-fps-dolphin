"""starwatch.py — transition logger for the perpetual-HUD-stars bug (120fps).

Logs changes to: console cue mask (+0xC), director state, ConsoleStr banner
phase (unk2B8/unk2BC/unk18), star-emitter STOP_EMIT bits, shine-pane offsets,
console appear-cycle flags. Run in background while playing; every state
transition is timestamped.

  SMS_DOL=../main.dol python3 starwatch.py [duration_s] > starwatch.log
"""
import os, sys, time, struct
from gcmem import Dolphin, find_dolphin_pid

GP_MARDIRECTOR = 0x8040E178

d = Dolphin(find_dolphin_pid(), os.environ["SMS_DOL"])
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0


def u16(va):
    b = d.read(va, 2)
    return struct.unpack(">H", b)[0] if b else None


def sample():
    dir_ = d.u32(GP_MARDIRECTOR)
    if not dir_ or not (0x80000000 <= dir_ < 0x81800000):
        return {"dir": None}
    con = d.u32(dir_ + 0x74)
    if not con or not (0x80000000 <= con < 0x81800000):
        return {"dir": hex(dir_), "con": None}
    cstr = d.u32(con + 0x94)
    sp = d.u32(con + 0x140)
    row = {
        "con": hex(con),
        "mask": u16(con + 0xC),
        "mMap": d.read(dir_ + 0x7C, 1)[0],
        "mState": d.read(dir_ + 0x64, 1)[0],
        "d124": d.read(dir_ + 0x124, 1)[0],
        # -400 = ctor-virgin (block never ran); else bucket by 50 to avoid log spam
        "unk30": (lambda v: v if v < 0 else v // 50 * 50)(struct.unpack(">i", d.read(con + 0x30, 4))[0]),
        "csPhase": d.u32(cstr + 0x2B8) if cstr else None,
        "csSub": d.u32(cstr + 0x2BC) if cstr else None,
        "f34_0": d.read(con + 0x34, 1)[0],
        "f34_1": d.read(con + 0x35, 1)[0],
        "f34_5": d.read(con + 0x39, 1)[0],
        "spY": round(d.f32(sp + 0x18) or 0),
    }
    for name, offc in (("s144", 0x144), ("s164", 0x164), ("s124", 0x124)):
        em = d.u32(con + offc)
        row[name] = (d.u32(em + 0x11C) & 1) if em and 0x80000000 <= em < 0x81800000 else None
    # coarse ConsoleStr timer (bucketed so it only logs on phase-scale moves)
    if cstr:
        t = d.f32(cstr + 0x18)
        row["csT"] = int(t // 30) * 30 if t is not None and -1e6 < t < 1e6 else None
    return row


prev = None
t0 = time.time()
print(f"start {time.strftime('%H:%M:%S')}", flush=True)
while time.time() - t0 < dur:
    row = sample()
    if row != prev:
        delta = {k: v for k, v in row.items() if prev is None or prev.get(k) != v}
        print(f"{time.time()-t0:8.2f}s  " + "  ".join(f"{k}={v}" for k, v in delta.items()), flush=True)
        prev = row
    time.sleep(0.05)
print("done", flush=True)
