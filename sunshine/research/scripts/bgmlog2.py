"""BGM deep logger v2 — waits for SMS to boot, then logs BGM handle AND
JASystem sequencer state (seq cursor / tick rate / tempo) until the game quits.

Usage:  python bgmlog2.py <logfile>     (SMS_DOL env var required)

Per live BGM slot it follows:
  smBgmInTrack[i] -> MSBgm+0x14 JAISound -> +0x38 JAISeqParameter -> +0x0 rootIdx
  -> TrackMgr::sRootTrack[[0x8040E6C0]][idx] -> TTrack:
       +0x004 mSeqCtrl.mCurrentFilePtr   (the BMS read cursor — heartbeat)
       +0x008 mSeqCtrl.mWaitTimer
       +0x3AC tick accumulator (f32)
       +0x3B0 tick rate (f32)            <- 0.0 == sequencer frozen
       +0x3B8 tempo (u16) / +0x3BA timebase (u16)
       +0x3BD pause-ish / +0x3C4 active
Logs edge events: handle changes, cursor FROZEN/MOVING transitions, tempo/rate
changes. Cursor heartbeat every 5s.
"""
import os, struct, sys, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcmem import Dolphin

SM_BGM_IN_TRACK = 0x803E9C80
S_ROOT_TRACK    = 0x8040E6C0
S_ROOT_COUNT    = 0x8040E6C8


def valid(p):
    return p is not None and 0x80000000 <= p < 0x81800000


def find_game(dol):
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process Dolphin -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True).stdout.split()
    for pid in out:
        try:
            return Dolphin(int(pid), dol), int(pid)
        except SystemExit:
            pass
        except Exception:
            pass
    return None, None


def track_state(d, snd):
    """Follow JAISound -> root TTrack. Returns dict or None."""
    sp = d.u32(snd + 0x38)
    if not valid(sp):
        return None
    idx = d.u32(sp)
    if idx is None or idx > 15:
        return None
    arr = d.u32(S_ROOT_TRACK)
    if not valid(arr):
        return None
    trk = d.u32(arr + 4 * idx)
    if not valid(trk):
        return None
    b = d.read(trk + 0x3A8, 0x20)
    head = d.read(trk, 0x10)
    if not b or not head:
        return None
    raw, cur, wait, loopidx = struct.unpack(">4I", head)
    acc = struct.unpack(">f", b[4:8])[0]
    rate = struct.unpack(">f", b[8:12])[0]
    tempo, timebase = struct.unpack(">HH", b[16:20])
    b3bc, b3bd = b[20], b[21]
    active = d.read(trk + 0x3C4, 1)[0]
    return dict(trk=trk, idx=idx, raw=raw, cur=cur, wait=wait, acc=acc,
                rate=rate, tempo=tempo, timebase=timebase,
                b3bc=b3bc, b3bd=b3bd, active=active)


def main():
    logpath = sys.argv[1]
    dol = os.environ["SMS_DOL"]
    f = open(logpath, "a")

    def log(msg):
        f.write(msg + "\n")
        f.flush()

    log(f"=== bgmlog2 waiting for game {time.strftime('%H:%M:%S')} ===")
    d = None
    while d is None:
        d, pid = find_game(dol)
        if d is None:
            time.sleep(5)
    log(f"=== game up pid={pid} {time.strftime('%H:%M:%S')} ===")

    t0 = time.time()
    prev = {}       # slot -> (bgm, snd)
    prevts = {}     # slot -> track_state
    frozen = {}     # slot -> bool
    last_beat = 0
    while True:
        t = time.time() - t0
        try:
            slots = []
            for i in range(3):
                p = d.u32(SM_BGM_IN_TRACK + 4 * i)
                snd = d.u32(p + 0x14) if valid(p) else None
                slots.append((p if valid(p) else None, snd if valid(snd) else None))
        except Exception:
            log(f"t={t:7.1f} === game gone, rearming ===")
            d = None
            while d is None:
                d, pid = find_game(dol)
                if d is None:
                    time.sleep(5)
            log(f"=== game up pid={pid} ===")
            t0 = time.time(); prev = {}; prevts = {}; frozen = {}
            continue

        beat = t - last_beat > 5.0
        for i, (p, snd) in enumerate(slots):
            if prev.get(i) != (p, snd):
                sid = d.u32(snd + 8) if snd else 0
                log(f"t={t:7.1f} slot{i} handle={p and hex(p)} snd={snd and hex(snd)} id={sid:08x}")
                prev[i] = (p, snd)
                prevts.pop(i, None); frozen.pop(i, None)
            if not snd:
                continue
            ts = track_state(d, snd)
            if ts is None:
                if prevts.get(i) is not None:
                    log(f"t={t:7.1f} slot{i} TRACK UNRESOLVABLE")
                prevts[i] = None
                continue
            pts = prevts.get(i)
            if pts:
                moved = ts["cur"] != pts["cur"] or ts["wait"] != pts["wait"]
                if frozen.get(i) is None:
                    frozen[i] = not moved
                elif frozen[i] and moved:
                    frozen[i] = False
                    log(f"t={t:7.1f} slot{i} CURSOR MOVING again cur={ts['cur']:08x}")
                elif not frozen[i] and not moved:
                    frozen[i] = True
                    log(f"t={t:7.1f} slot{i} ** CURSOR FROZEN ** cur={ts['cur']:08x} wait={ts['wait']} "
                        f"acc={ts['acc']:.3f} rate={ts['rate']:.4f} tempo={ts['tempo']} tb={ts['timebase']} "
                        f"3bc={ts['b3bc']} 3bd={ts['b3bd']} act={ts['active']}")
                for k in ("rate", "tempo", "timebase", "active", "b3bd"):
                    if ts[k] != pts[k]:
                        log(f"t={t:7.1f} slot{i} {k}: {pts[k]} -> {ts[k]} (cur={ts['cur']:08x})")
            if beat:
                log(f"t={t:7.1f} slot{i} beat trk={ts['trk']:08x} idx={ts['idx']} cur={ts['cur']:08x} "
                    f"wait={ts['wait']} rate={ts['rate']:.4f} tempo={ts['tempo']} act={ts['active']}")
            prevts[i] = ts
        if beat:
            last_beat = t
        time.sleep(0.25)


if __name__ == "__main__":
    main()
