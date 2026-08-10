"""hoverlog.py — live sampler for TMario during FLUDD hover, for the pachinko
red-coin "suction to middle" bug at 120fps.

Auto-locates the TMario instance by scanning MEM1 for a pointer whose target
mPosition (@+0x10) equals gpMarioPos (0x8040E10C). Then polls state at a fixed
wall-clock rate and logs per-tick deltas.

Fields sampled (from ~/code/sms Player/Mario.hpp offsets):
  +0x10  mPosition          vec3f      (inherited via TPlacement)
  +0x74  mInput             u32
  +0x7C  mStatus            u32
  +0x84  mStatusState       u16
  +0x8C  mIntendedMag       f32
  +0x90  mIntendedYaw       s16
  +0x94  mFaceAngle         vec3s16
  +0xA4  mVel               vec3f
  +0xB0  mForwardVel        f32
  +0xB4  mSlideVelX         f32
  +0xB8  mSlideVelZ         f32
  +0x3E4 mWaterGun*         -> +0x1C84 mCurrentNozzle (u8; Hover=4)

MARIO_STATUS_ROCKET (hover state) = 0x0A000000 in the type/id mask.

Usage:
  # foreground, 60 Hz sample, 20 seconds:
  sudo SMS_DOL=../main.dol python3 hoverlog.py 60 20 > hoverlog.txt
  # background:
  sudo SMS_DOL=../main.dol python3 hoverlog.py 120 30 --only-hover \
      > hoverlog-120fps.txt &

Flags:
  <hz>           samples per second (wall clock; not tied to emu rate)
  <duration_s>   how long to run
  --only-hover   suppress rows where mCurrentNozzle != Hover(4)
  --raw          print every sample, not just changes
"""
import os, sys, time, struct, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault(
    "SMS_DOL",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.dol"),
)
from gcmem import Dolphin, find_dolphin_pid


GP_MARIO_POS = 0x8040E10C  # gpMarioPos (mirror of TMario::mPosition, USA)
MEM1_LO = 0x80000000
MEM1_HI = 0x81800000

HOVER_NOZZLE = 4  # TWaterGun::Hover

# offsets on TMario
O_POS         = 0x10
O_INPUT       = 0x74
O_STATUS      = 0x7C
O_STATUS_ST   = 0x84
O_STATUS_TMR  = 0x86
O_INT_MAG     = 0x8C
O_INT_YAW     = 0x90
O_FACE_ANG_Y  = 0x94 + 0x2  # TVec3<s16> {x,y,z}, want yaw = .y at +2
O_VEL         = 0xA4
O_FWD_VEL     = 0xB0
O_SLIDE_X     = 0xB4
O_SLIDE_Z     = 0xB8
O_WATER_GUN   = 0x3E4

O_WG_CURNOZ   = 0x1C84


def vec3f(d, va):
    b = d.read(va, 12)
    return struct.unpack(">3f", b) if b else None


def f32(d, va):
    return d.f32(va)


def u32(d, va):
    return d.u32(va)


def u16(d, va):
    b = d.read(va, 2)
    return struct.unpack(">H", b)[0] if b else None


def s16(d, va):
    b = d.read(va, 2)
    return struct.unpack(">h", b)[0] if b else None


def u8(d, va):
    b = d.read(va, 1)
    return b[0] if b else None


def find_mario_ptr(d, log=print):
    """Find TMario* by scanning MEM1 for a pointer whose target +0x10 equals
    gpMarioPos. Verifies with mForwardVel + mCurrentNozzle sanity checks."""
    tgt = d.read(GP_MARIO_POS, 12)
    if not tgt:
        log("gpMarioPos unreadable — is the game booted past intro?")
        return None
    px, py, pz = struct.unpack(">3f", tgt)
    if not (math.isfinite(px) and math.isfinite(py) and math.isfinite(pz)):
        log(f"gpMarioPos non-finite: {px} {py} {pz}")
        return None

    # scan MEM1 for candidate pointers whose target starts at some P with
    # mem[P+0x10:P+0x1C] == gpMarioPos bytes.
    want_pos = tgt  # 12 raw bytes to match
    CHUNK = 0x100000
    candidates = []
    for base in range(MEM1_LO, MEM1_HI, CHUNK):
        raw = d.read(base, CHUNK)
        if not raw:
            continue
        off = 0
        while True:
            i = raw.find(want_pos, off)
            if i < 0:
                break
            # candidate TMario is at (base + i - O_POS)
            cand = base + i - O_POS
            if MEM1_LO <= cand < MEM1_HI:
                candidates.append(cand)
            off = i + 1

    if not candidates:
        log("no MEM1 hits for gpMarioPos vec — Mario may be in cutscene / freeze")
        return None

    # sanity-filter: TMario has a valid vptr (in .data range), and mForwardVel
    # is a finite float in a reasonable magnitude. Prefer whichever has a
    # non-null mWaterGun pointer into MEM1.
    scored = []
    for cand in candidates:
        vptr = u32(d, cand)
        if vptr is None or not (MEM1_LO <= vptr < MEM1_HI):
            continue
        fv = f32(d, cand + O_FWD_VEL)
        if fv is None or not math.isfinite(fv) or abs(fv) > 500:
            continue
        wg = u32(d, cand + O_WATER_GUN)
        wg_ok = wg is not None and MEM1_LO <= wg < MEM1_HI
        scored.append((wg_ok, cand, vptr, wg))

    if not scored:
        log(f"{len(candidates)} raw hits, none passed the vptr/vel sanity check")
        return None
    scored.sort(reverse=True)  # wg_ok=True first
    _, cand, vptr, wg = scored[0]
    log(f"TMario @ {cand:#010x}  vptr={vptr:#010x}  waterGun={wg:#010x}  "
        f"(from {len(candidates)} raw / {len(scored)} sane hits)")
    return cand


def snap(d, mario):
    """One state snapshot."""
    wg = u32(d, mario + O_WATER_GUN)
    return {
        "pos":  vec3f(d, mario + O_POS),
        "vel":  vec3f(d, mario + O_VEL),
        "fv":   f32(d, mario + O_FWD_VEL),
        "svx":  f32(d, mario + O_SLIDE_X),
        "svz":  f32(d, mario + O_SLIDE_Z),
        "yaw":  s16(d, mario + O_FACE_ANG_Y),
        "iyaw": s16(d, mario + O_INT_YAW),
        "imag": f32(d, mario + O_INT_MAG),
        "sts":  u32(d, mario + O_STATUS),
        "stst": u16(d, mario + O_STATUS_ST),
        "sttm": u16(d, mario + O_STATUS_TMR),
        "inp":  u32(d, mario + O_INPUT),
        "noz":  u8(d, wg + O_WG_CURNOZ) if wg else None,
    }


def is_hover(s):
    return s and s.get("noz") == HOVER_NOZZLE


def fmt_row(t, s, prev):
    def d3(a, b):
        return tuple(round(x - y, 3) for x, y in zip(a, b)) if a and b else None
    pos = s["pos"]
    vel = s["vel"]
    dp = d3(pos, prev["pos"]) if prev and prev.get("pos") else None
    dv = d3(vel, prev["vel"]) if prev and prev.get("vel") else None
    return (
        f"t={t:6.3f} "
        f"noz={s['noz']} sts={s['sts']:#010x} stst={s['stst']} sttm={s['sttm']} "
        f"pos=({pos[0]:8.2f},{pos[1]:8.2f},{pos[2]:8.2f}) "
        f"vel=({vel[0]:6.2f},{vel[1]:6.2f},{vel[2]:6.2f}) "
        f"fv={s['fv']:6.2f} svx={s['svx']:6.2f} svz={s['svz']:6.2f} "
        f"yaw={s['yaw']:6d} iyaw={s['iyaw']:6d} imag={s['imag']:.3f} "
        f"inp={s['inp']:#010x} "
        f"dp={dp} dv={dv}"
    )


def main():
    hz  = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    only_hover = "--only-hover" in sys.argv
    raw_mode   = "--raw" in sys.argv

    pid = find_dolphin_pid()
    if not pid:
        raise SystemExit("Dolphin not running")
    d = Dolphin(pid, os.environ["SMS_DOL"])
    print(f"# pid={pid} MEM1 base={d.base:#x}  {hz}Hz for {dur}s"
          f"{'  (only hover)' if only_hover else ''}"
          f"{'  (raw)' if raw_mode else ''}", flush=True)

    # keep re-searching for TMario until we find it (level not loaded yet, etc.)
    mario = None
    t0 = time.time()
    while mario is None and (time.time() - t0) < dur:
        mario = find_mario_ptr(d)
        if mario is None:
            time.sleep(0.5)
    if mario is None:
        raise SystemExit("could not locate TMario within duration")

    dt   = 1.0 / hz
    prev = None
    hover_samples = 0
    total_samples = 0
    t_start = time.time()
    next_t  = t_start
    while (time.time() - t_start) < dur:
        s = snap(d, mario)
        total_samples += 1
        if s and s.get("pos"):
            if is_hover(s):
                hover_samples += 1
            show = raw_mode or (prev is None) or any(
                s.get(k) != prev.get(k)
                for k in ("noz", "sts", "stst", "fv", "svx", "svz", "yaw")
            )
            if show and (not only_hover or is_hover(s)):
                print(fmt_row(time.time() - t_start, s, prev), flush=True)
            prev = s
        else:
            # Mario got freed (scene change)? try to re-find.
            new = find_mario_ptr(d)
            if new and new != mario:
                mario = new
                prev = None
        next_t += dt
        slack = next_t - time.time()
        if slack > 0:
            time.sleep(slack)
        else:
            next_t = time.time()  # fell behind; realign

    print(f"# done: {total_samples} samples, {hover_samples} in hover"
          f" ({100.0*hover_samples/max(total_samples,1):.1f}%)", flush=True)


if __name__ == "__main__":
    main()
