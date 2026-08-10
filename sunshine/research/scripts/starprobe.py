"""starprobe.py — live-watch TGCConsole2 (HUD) state to diagnose the perpetual
star-sparkle / never-hiding counters bug at 120fps.

Chain: gpMarDirector (USA 0x8040DB78) -> +0x74 TGCConsole2* -> fields per the
JP decomp layout (GC2D/GCConsole2.hpp).  Star emitters: unk124 (coin),
unk144 (shine/star), unk164 (blue coin 'd_'); JPABaseEmitter->mStatus @+0x11C,
bit0 = STOP_EMIT.

Usage:  SMS_DOL=.../main.dol python3 starprobe.py [interval_s] [count]
"""
import sys, time, struct
from gcmem import Dolphin, find_dolphin_pid
import os

GP_MARDIRECTOR = 0x8040E178  # lwz r3,-0x6048(r13), r13=0x804141C0

pid = find_dolphin_pid()
if not pid:
    raise SystemExit("Dolphin not running")
d = Dolphin(pid, os.environ["SMS_DOL"])

interval = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
count = int(sys.argv[2]) if len(sys.argv) > 2 else 10


def u8(va):
    b = d.read(va, 1)
    return b[0] if b else None


def u16(va):
    b = d.read(va, 2)
    return struct.unpack(">H", b)[0] if b else None


def emitter_info(p):
    if not p or not (0x80000000 <= p < 0x81800000):
        return "null"
    st = d.u32(p + 0x11C)
    return f"@{p:08x} status={st:02x}{'(STOP)' if st is not None and st & 1 else '(EMITTING)'}"


prev = None
for it in range(count):
    dir_ = d.u32(GP_MARDIRECTOR)
    con = d.u32(dir_ + 0x74) if dir_ else None
    if not con:
        print("no console yet"); time.sleep(interval); continue
    row = {
        "unk10": d.u32(con + 0x10),
        "unk14": d.u32(con + 0x14),
        "flags34": bytes(d.read(con + 0x34, 30)).hex(),
        "unk58": u8(con + 0x58),
        "unk59": u8(con + 0x59),
        "unk5A": u8(con + 0x5A),
        "unk78": u16(con + 0x78),
        "unk7C": u16(con + 0x7C),
        "unk84": u16(con + 0x84),
        "unk86": u16(con + 0x86),
        "unk88": u8(con + 0x88),
        "unk8A": u16(con + 0x8A),
        "unk98": u16(con + 0x98),
        "unk264": u16(con + 0x264),
        "unk266": u8(con + 0x266),
        "unk268": u16(con + 0x268),
        "unk26A": u16(con + 0x26A),
        "em_coin(124)": emitter_info(d.u32(con + 0x124)),
        "em_star(144)": emitter_info(d.u32(con + 0x144)),
        "em_dcoin(164)": emitter_info(d.u32(con + 0x164)),
        "dir_state(E4)": d.u32(dir_ + 0xE4),
        "dir_unk5C": d.u32(dir_ + 0x5C),
    }
    if it == 0:
        print(f"director={dir_:08x} console={con:08x}")
    changed = {k: v for k, v in row.items() if prev is None or prev.get(k) != v}
    ts = time.strftime("%H:%M:%S")
    if prev is None:
        for k, v in row.items():
            print(f"  {k:14s} = {v}")
    else:
        print(f"[{ts}] " + ("  ".join(f"{k}={v}" for k, v in changed.items()) or "(no change)"))
    prev = row
    time.sleep(interval)
