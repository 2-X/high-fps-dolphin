"""Live logger for TPopo (the Poink) in Bianco 5 — diagnoses the short-launch bug at 180fps.

Self-arming: waits for Dolphin + game boot, scans MEM1 for TPopo instances
(vptr == 0x803BA558), then samples each live popo at ~30Hz and logs nerve
transitions plus fill/velocity/flight data. On a Fly-nerve launch it prints
launch speed, direction, per-second ground covered, and total distance at
explosion — everything needed to see which quantity diverges from stock.

Usage:  python scripts/popolog.py            (finds Dolphin itself)
        python scripts/popolog.py <pid>
Log:    also appended to scripts/popolog.txt
"""
import os, sys, time, struct, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SMS_DOL", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.dol"))
from gcmem import Dolphin, find_dolphin_pid

VT_POPO = 0x803BA558
NERVES = {
    0x803BA4F8: "Thrown",
    0x803BA508: "Wait",
    0x803BA518: "Explosion",
    0x803BA528: "Fly",
    0x803BA538: "Attack",
    0x803BA548: "PossessedNozzle",
}
MARIO_POS = 0x8040E10C  # gpMarioPos vec

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "popolog.txt")

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def scan_popos(d):
    """Scan MEM1 heap range for TPopo vptrs. Objects are 4-aligned."""
    hits = []
    CHUNK = 0x100000
    want = struct.pack(">I", VT_POPO)
    for base in range(0x80000000, 0x81800000, CHUNK):
        raw = d.read(base, CHUNK)
        if not raw:
            continue
        off = raw.find(want)
        while off != -1:
            if off % 4 == 0:
                hits.append(base + off)
            off = raw.find(want, off + 1)
    return hits

def vec(d, va):
    b = d.read(va, 12)
    return struct.unpack(">3f", b) if b else None

def popo_state(d, p):
    s = {}
    s["pos"]  = vec(d, p + 0x10)
    s["vel"]  = vec(d, p + 0xAC)
    s["fill"] = d.f32(p + 0x198)
    s["timer"]= d.u32(p + 0x19C)
    s["flags"]= d.u32(p + 0xF0)
    s["live"] = d.u32(p + 0x64)
    spine = d.u32(p + 0x8C)
    s["nerve"] = "?"
    if spine:
        cur = d.u32(spine + 0x14) or d.u32(spine + 0x1C)
        if cur:
            nvt = d.u32(cur)
            s["nerve"] = NERVES.get(nvt, f"vt:{nvt:08x}" if nvt else "?")
    prm = d.u32(p + 0x194)
    if prm:
        s["prm"] = (d.f32(prm + 0x3B4), d.u32(prm + 0x3DC), d.f32(prm + 0x404),
                    d.f32(prm + 0x42C), d.f32(prm + 0x440))
    return s

def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    log("popolog armed - waiting for Dolphin + SMS boot")
    d = None
    popos = []
    prev = {}
    launch = {}
    printed_params = False
    beats = 0
    while True:
        if d is None:
            p = pid or find_dolphin_pid()
            if not p:
                if beats % 5 == 0: log("no Dolphin process found yet — boot the game, then wait…")
                beats += 1; time.sleep(2); continue
            try:
                d = Dolphin(p, os.environ["SMS_DOL"])
                log(f"ATTACHED to Dolphin pid {p}, MEM1 @ {d.base:#x} — now enter Bianco 5 and latch a Poink")
                beats = 0
            except SystemExit as e:
                # surface the real reason instead of looping in silence
                log(f"attach failed (pid {p}): {e} — retrying in 3s")
                d = None; beats += 1; time.sleep(3); continue
        try:
            if not popos:
                popos = scan_popos(d)
                if popos:
                    log(f"found {len(popos)} TPopo instance(s): " + " ".join(f"{p:#x}" for p in popos))
                else:
                    if beats % 5 == 0: log("attached, no Poinks in memory yet — be in Bianco ep5 with a Poink on the nozzle")
                    beats += 1; time.sleep(2); continue
            mario = vec(d, MARIO_POS)
            for p in popos:
                if d.u32(p) != VT_POPO:      # scene unloaded / freed
                    popos = []; prev = {}; launch = {}; break
                s = popo_state(d, p)
                if s["fill"] is None:
                    continue
                if not printed_params and "prm" in s:
                    rs, fl, mx, pr, ll = s["prm"]
                    log(f"params: releaseSpeed={rs} flyLimit={fl} scaleMax={mx} pumpRate={pr:.6f} levelLimit={ll}")
                    printed_params = True
                pv = prev.get(p)
                if pv:
                    if s["nerve"] != pv["nerve"]:
                        log(f"popo {p:#x}: nerve {pv['nerve']} -> {s['nerve']}  fill={s['fill']:.3f} timer={s['timer']} pos=({s['pos'][0]:.0f},{s['pos'][1]:.0f},{s['pos'][2]:.0f})")
                        if s["nerve"] == "Fly":
                            spd = math.sqrt(sum(v*v for v in s["vel"]))
                            launch[p] = (time.time(), s["pos"], s["timer"])
                            log(f"  LAUNCH: vel=({s['vel'][0]:.2f},{s['vel'][1]:.2f},{s['vel'][2]:.2f}) |v|={spd:.2f} fill={s['fill']:.3f} marioDist={dist(s['pos'], mario):.0f}" if mario else f"  LAUNCH |v|={spd:.2f}")
                            # BURST: flight is ~0.07s (9 ticks) — 30Hz misses it. Sample this
                            # popo as fast as possible, logging each new flyTimer with the
                            # +0xF0 collision latch. Shows when bit0x80 clears AND whether a
                            # fix re-heals it (clr->SET) vs stays clr (fix not running).
                            bt0 = time.time(); seen_t = set()
                            while time.time() - bt0 < 0.5:
                                sp2 = d.u32(p + 0x8C); nvt2 = None
                                if sp2:
                                    cur2 = d.u32(sp2 + 0x14) or d.u32(sp2 + 0x1C)
                                    nvt2 = d.u32(cur2) if cur2 else None
                                nerve2 = NERVES.get(nvt2, f"vt:{nvt2:08x}" if nvt2 else "?")
                                tmr = d.u32(p + 0x19C); flg = d.u32(p + 0xF0)
                                if tmr is None or flg is None: break
                                if tmr not in seen_t:
                                    seen_t.add(tmr)
                                    b80 = "SET" if flg & 0x80 else "clr"
                                    log(f"    t={tmr} nerve={nerve2} +0xF0={flg:08x} bit0x80={b80}")
                                if nerve2 != "Fly":
                                    log(f"    >>> left Fly -> {nerve2} at t={tmr}")
                                    break
                        if pv["nerve"] == "Fly":
                            t0, p0, _ = launch.get(p, (None, None, None))
                            if p0:
                                log(f"  FLIGHT END after {time.time()-t0:.2f}s real, distance={dist(s['pos'], p0):.0f} units, end-timer={pv['timer']} -> {s['nerve']}")
                    elif s["nerve"] in ("PossessedNozzle", "Fly") and abs((s["fill"] or 0) - (pv["fill"] or 0)) > 0.02:
                        spd = math.sqrt(sum(v*v for v in s["vel"]))
                        log(f"popo {p:#x}: {s['nerve']} fill={s['fill']:.3f} timer={s['timer']} |v|={spd:.2f}")
                prev[p] = s
            time.sleep(0.033)
        except Exception as e:
            log(f"detached ({e}); re-arming")
            d = None; popos = []; prev = {}; launch = {}
            time.sleep(2)

if __name__ == "__main__":
    main()
