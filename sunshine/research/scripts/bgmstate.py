"""Dump live BGM state from a running Dolphin (SMS USA) — for the music bug.

Usage:
    python bgmstate.py <dolphin_pid>              one snapshot
    python bgmstate.py <dolphin_pid> --watch 10   sample 2x/s for 10s, report churn

Needs SMS_DOL env var (same as gcmem.py).

Reads MSBgm::smBgmInTrack[3] (0x803E9C80) and follows each entry:
  MSBgm* -> +0x14 JAISound* (+0x0 track slot byte, +0x8 sound id).
Also dumps gpMSound's flag block (+0x70..0xE0: fade handles unk7C/unk80,
unkA0/A4 counters, unkA8 enable bits, unkC8[5] state, unkCD..D1 flags).

Interpretation:
  slot empty                -> startBGM never fired or failed
  handle static across time -> sequencer started then STALLED
  handle/id churning        -> something is RETRIGGERING startBGM per frame
"""
import os, struct, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcmem import Dolphin

SM_BGM_IN_TRACK = 0x803E9C80   # MSBgm* [3]
SM_MAIN_VOLUME  = 0x8040C1C0   # f32, 0.75 stock
GP_MSOUND       = 0x8040D05C   # MSound*


def valid(p):
    return p is not None and 0x80000000 <= p < 0x81800000


def snapshot(d):
    """Return dict: {'msound': bytes, 'tracks': [(bgm_ptr, snd_ptr, snd_bytes|None)]}"""
    out = {"tracks": []}
    ms = d.u32(GP_MSOUND)
    out["msound_ptr"] = ms
    out["msound"] = d.read(ms + 0x70, 0x70) if valid(ms) else None
    for i in range(3):
        p = d.u32(SM_BGM_IN_TRACK + 4 * i)
        snd = d.u32(p + 0x14) if valid(p) else None
        b = d.read(snd, 0x40) if valid(snd) else None
        out["tracks"].append((p, snd, b))
    return out


def show(s):
    ms = s["msound_ptr"]
    print(f"gpMSound = {ms:08x}")
    if s["msound"]:
        w = struct.unpack(">28I", s["msound"])
        for row in range(0, 28, 4):
            off = 0x70 + row * 4
            print(f"  MSound+{off:02x}: " + " ".join(f"{x:08x}" for x in w[row:row + 4]))
    for i, (p, snd, b) in enumerate(s["tracks"]):
        if not valid(p):
            print(f"track[{i}]: empty")
            continue
        line = f"track[{i}]: MSBgm@{p:08x} JAISound={snd if snd is None else f'{snd:08x}'}"
        print(line)
        if b:
            w = struct.unpack(">16I", b)
            print("  snd[0:40]: " + " ".join(f"{x:08x}" for x in w))
            print(f"  -> slot={b[0]} soundId={w[2]:08x}")


def main():
    pid = int(sys.argv[1])
    d = Dolphin(pid, os.environ["SMS_DOL"])
    print(f"MEM1 host base {d.base:#x}  mainVol={d.f32(SM_MAIN_VOLUME)!r}")

    if "--watch" in sys.argv:
        secs = int(sys.argv[sys.argv.index("--watch") + 1])
        prev = None
        t0 = time.time()
        while time.time() - t0 < secs:
            s = snapshot(d)
            if prev is None:
                print(f"--- t=0.0s baseline ---")
                show(s)
            else:
                diffs = []
                for i in range(3):
                    if s["tracks"][i][:2] != prev["tracks"][i][:2]:
                        diffs.append(f"track[{i}] PTR CHANGED "
                                     f"{prev['tracks'][i][0]:#x}/{prev['tracks'][i][1] or 0:#x}"
                                     f" -> {s['tracks'][i][0]:#x}/{s['tracks'][i][1] or 0:#x}")
                    elif s["tracks"][i][2] != prev["tracks"][i][2]:
                        a, bb = prev["tracks"][i][2], s["tracks"][i][2]
                        if a and bb:
                            ch = [f"+{j*4:#x}" for j in range(16)
                                  if a[j*4:j*4+4] != bb[j*4:j*4+4]]
                            diffs.append(f"track[{i}] words changed: {' '.join(ch)}")
                    if s["msound"] != prev["msound"] and s["msound"] and prev["msound"]:
                        ch = [f"+{0x70+j*4:#x}" for j in range(28)
                              if s["msound"][j*4:j*4+4] != prev["msound"][j*4:j*4+4]]
                        if ch:
                            diffs.append(f"MSound changed: {' '.join(ch)}")
                t = time.time() - t0
                if diffs:
                    for x in dict.fromkeys(diffs):
                        print(f"t={t:4.1f}s {x}")
            prev = s
            time.sleep(0.5)
        print("--- final ---")
        show(snapshot(d))
    else:
        show(snapshot(d))


if __name__ == "__main__":
    main()
