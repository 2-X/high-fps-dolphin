"""Live logger for the M-portal warp sequence — diagnoses the dots-vs-ripples
desync at 240/360fps ("ripples of Mario's atoms hitting the portal appear way
later than when the dots hit"; destination recompose lags Mario).

The one question this answers: at what WALL-CLOCK rate does Mario's
mStatusTimer tick during MARIO_STATUS_WARP_IN (0x1336) / WARP_OUT (0x1337)?

  * ~120/s  -> the status machine is substep-cadenced (rate-invariant, as the
               CUE_MOVE architecture predicts) and the desync must live in the
               JPA/callback/gate-reaction path instead.
  * ~60*G/s -> the warp autodemo ticks per RENDERED frame; the dot-push
               callback (v += mWarpInDir * unk468 * mStatusTimer * factor,
               TWarpInCallBack) ramps 2G x too hard, the dots slam in early,
               and every WarpIn*Time param (BallsDisp 6 / Balls 70 /
               Captured 120 ticks) fires early -> exactly the reported look.

Also logs every (mStatus, mStatusState) transition with wall-clock deltas, so
the warp phase durations can be compared against stock (state0 pull-in
= 120 ticks = 1.0s stock; state2 captured window = 120 ticks = 1.0s stock).

Self-arming: waits for Dolphin, resolves Mario via the gpMarioPos global
(0x8040E10C — handles both pointer-to-mPosition and inline-vec layouts), then
samples at ~1kHz. TMario fields: mStatus +0x7C (u32), mStatusState +0x84 (u16),
mStatusTimer +0x86 (u16), mPosition +0x10.

Usage:  python scripts/warplog.py            (finds Dolphin itself)
Log:    also appended to scripts/warplog.txt
Then:   enter an M portal once (and ride it to the destination).
"""
import os, sys, time, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SMS_DOL", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.dol"))
from gcmem import Dolphin, find_dolphin_pid

GP_MARIO_POS = 0x8040E10C
STATUS_NAMES = {0x1336: "WARP_IN", 0x1337: "WARP_OUT"}
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warplog.txt")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def u32(d, va):
    b = d.read(va, 4)
    return struct.unpack(">I", b)[0] if b else None


def u16(d, va):
    b = d.read(va, 2)
    return struct.unpack(">H", b)[0] if b else None


def _plausible_base(d, base):
    """TMario sanity: mPosition (+0x10) = 3 sane floats, mStatus (+0x7C) is a
    small flag word (every MarioStatus.hpp value < 0x40000000)."""
    b = d.read(base + 0x10, 12)
    if not b or len(b) != 12:
        return False
    x, y, z = struct.unpack(">3f", b)
    for v in (x, y, z):
        if v != v or abs(v) > 1e7 or (v != 0 and abs(v) < 1e-30):
            return False
    st = u32(d, base + 0x7C)
    return st is not None and st < 0x40000000


def mario_base(d):
    """The 0x8040E10C global is documented as gpMarioPos (= &mario->mPosition,
    so base = ptr - 0x10) but could plausibly be gpMarioOriginal (= base).
    Disambiguate at runtime by sanity-checking both candidates."""
    w = u32(d, GP_MARIO_POS)
    if w is None or not (0x80000000 <= w < 0x81800000):
        return None
    for cand in (w - 0x10, w):
        if _plausible_base(d, cand):
            return cand
    return None


def attach():
    """Wait for Dolphin AND a booted game. gcmem sys.exit()s when MEM1 is not
    mapped yet (process up, emulation not started) — catch SystemExit too and
    keep polling quietly."""
    announced = False
    while True:
        pid = find_dolphin_pid()
        if pid:
            try:
                d = Dolphin(pid, os.environ["SMS_DOL"])
                log(f"attached to Dolphin pid {pid}")
                return d
            except (Exception, SystemExit):
                if not announced:
                    log("Dolphin up, game not booted yet — polling until MEM1 appears")
                    announced = True
        time.sleep(2)


def main():
    log("=== warplog armed — waiting for Dolphin ===")
    d = attach()

    prev_status = prev_state = None
    prev_timer = None
    t_prev_change = time.time()
    # timer-rate window: (t0, timer0) reset on every status/state change
    win = None
    in_warp = False

    dead_since = None
    while True:
        base = mario_base(d)
        if base is None:
            now = time.time()
            if dead_since is None:
                dead_since = now
            elif now - dead_since > 10 and not find_dolphin_pid():
                log("Dolphin gone — re-arming")
                d = attach()
                dead_since = None
            time.sleep(0.5)
            continue
        dead_since = None
        status = u32(d, base + 0x7C)
        state = u16(d, base + 0x84)
        timer = u16(d, base + 0x86)
        if status is None or state is None or timer is None:
            time.sleep(0.5)
            continue
        now = time.time()
        warp = status in STATUS_NAMES

        if status != prev_status or state != prev_state:
            dt = now - t_prev_change
            name = STATUS_NAMES.get(status, f"{status:#x}")
            pname = STATUS_NAMES.get(prev_status, f"{prev_status:#x}" if prev_status is not None else "-")
            if warp or (prev_status in STATUS_NAMES):
                log(f"{pname}/s{prev_state} -> {name}/s{state}  (prev phase lasted {dt*1000:.0f}ms)")
            t_prev_change = now
            win = (now, timer)
            prev_status, prev_state = status, state

        if warp:
            if not in_warp:
                log(f"--- warp begins: {STATUS_NAMES[status]} state={state} timer={timer} ---")
                in_warp = True
                win = (now, timer)
                gate_prev = None
            # the holder gate's whirl/ripple machinery (TModelGate +0xC4 substate,
            # +0xB9 whirl phase 0..7, +0xBC phase tick) — the one subsystem known
            # to advance per RENDERED frame (documented 2Gx fast at 120)
            holder = u32(d, base + 0x68)
            if holder and 0x80000000 <= holder < 0x81800000:
                gb = d.read(holder + 0xB9, 1)
                gc = d.read(holder + 0xC4, 1)
                gt = u16(d, holder + 0xBC)
                if gb and gc and gt is not None:
                    gsig = (gc[0], gb[0])
                    if gsig != gate_prev:
                        log(f"    gate: substate={gc[0]} whirlphase={gb[0]} tick={gt}")
                        gate_prev = gsig
            # report the measured tick rate once per half second of ramp
            if win and now - win[0] >= 0.5:
                dtimer = (timer - win[1]) & 0xFFFF
                rate = dtimer / (now - win[0])
                log(f"{STATUS_NAMES[status]}/s{state}: timer {win[1]} -> {timer}  "
                    f"rate = {rate:.0f} ticks/s  "
                    f"({'substep-invariant ~120' if 100 <= rate <= 140 else 'RENDER-RATE CLASS' if rate > 160 else 'slow?'})")
                win = (now, timer)
        elif in_warp:
            log(f"--- warp over (status {STATUS_NAMES.get(status, hex(status))}) ---")
            in_warp = False

        prev_timer = timer
        time.sleep(0.001)


if __name__ == "__main__":
    main()
