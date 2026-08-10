"""Level-music coin-toss watcher — logs BGM slot state INCLUDING the empty/null
case, so a silent entry (slot never populates) can't be missed.

For each of the 3 BGM slots, logs every transition between empty and active,
with the global BGM volume. On a silent level entry we'll see either:
  * slot stays EMPTY at a time music should play  -> startBGM never completed
  * slot ACTIVE but vol~0                          -> volume/fade race

Usage:  /usr/bin/python3 scripts/bgmwatch.py   (self-arms; get-task-allow Dolphin)
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SMS_DOL", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.dol"))
from gcmem import Dolphin, find_dolphin_pid
import bgmlog2 as B

SLOTS = 0x803E9C80    # MSBgm::smBgmInTrack[3]
MAIN_VOL = 0x8040C1C0 # f32 global BGM volume, stock 0.75
GP_MSOUND = 0x8040D05C
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgmwatch.txt")

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    open(LOG, "a").write(line + "\n")

def slot(d, i):
    p = d.u32(SLOTS + 4 * i)
    snd = d.u32(p + 0x14) if B.valid(p) else None
    if not B.valid(snd):
        return None
    ts = B.track_state(d, snd)
    ts["snd"] = snd
    # per-track output/volume candidates (silent entry read these all 0.0)
    ts["vols"] = [d.f32(snd + o) for o in (0x40, 0x44, 0x48, 0x4c, 0x50, 0x54)]
    return ts

def main():
    open(LOG, "w").close()
    d = None
    log("bgmwatch v2 armed — enter/exit levels; empty AND active states are logged")
    prev = {}
    last_mv = None
    while True:
        if d is None:
            pid = find_dolphin_pid()
            try:
                d = Dolphin(pid, os.environ["SMS_DOL"]) if pid else None
                if d:
                    log(f"attached pid {pid}"); prev = {}; last_mv = None
            except SystemExit:
                d = None
            if d is None:
                time.sleep(3); continue
        try:
            mv = d.f32(MAIN_VOL)
            # MSound engine enable/fade state (documented transition suspects)
            ms = d.u32(GP_MSOUND)
            if B.valid(ms):
                a8 = d.u32(ms + 0xA8); f7c = d.u32(ms + 0x7C); f80 = d.u32(ms + 0x80)
                a0 = d.u32(ms + 0xA0); a4 = d.u32(ms + 0xA4)
                msk = (a8, f7c != 0, f80 != 0, a0, a4)
                if msk != prev.get("ms"):
                    log(f"        MSound +A8(enable)={a8:08x} +7C={f7c:08x} +80={f80:08x} "
                        f"+A0={a0:08x} +A4={a4:08x}")
                    prev["ms"] = msk
            for i in range(3):
                ts = slot(d, i)
                key = (ts is not None, ts and ts["trk"], ts and ts["active"])
                if key != prev.get(i):
                    if ts is None:
                        log(f"slot{i} -- EMPTY --                       vol={mv:.3f}")
                    else:
                        vv = " ".join(f"{v:.2f}" for v in ts["vols"])
                        log(f"slot{i} ACTIVE id={ts['trk']:08x} act={ts['active']} "
                            f"tempo={ts['tempo']} cur={ts['cur']:08x}  vol={mv:.3f}  trkVols[{vv}]")
                    prev[i] = key
            # log notable main-volume moves (the fade dips/recovers)
            if last_mv is None or abs((mv or 0) - (last_mv or 0)) >= 0.10:
                log(f"        mainVol -> {mv:.3f}")
                last_mv = mv
            time.sleep(0.05)
        except Exception as e:
            log(f"detached ({e}); re-arming"); d = None; time.sleep(3)

if __name__ == "__main__":
    main()
