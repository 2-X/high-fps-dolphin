"""Post-launch verification: prove the Gecko codes actually installed.

Run detached by launch() ~25s after boot (BSE modes) — or by play240.ps1 on
the PC. Attaches to the live Dolphin via the platform memory backend
(sunshine/bsmso/mac-online/gcmem.py: Mach memhelper on macOS, Win32
ReadProcessMemory on Windows), then checks, against the INI's [Gecko_Enabled]
set:

  * every enabled C2 hook site holds a branch (opcode 18) — i.e. the code
    handler processed that code (this is what catches the bracket-title bug,
    a relocation failure, or a stomped code list);
  * the framerate global reads the profile's rate (fps/60 as float) — i.e.
    the native BSE FPS poke landed (catches the 30fps "60fps-2x illusion");
  * every enabled 04 write reads back (warning only — the game may
    legitimately overwrite between handler runs).

Verdict goes to /tmp/sms-verify.log, one line per code, PASS/FAIL summary
last. Usage:  python3 -m smslaunch.verify --fps 120 [--delay 25]
"""
from __future__ import annotations

import argparse
import struct
import sys
import time

from . import config as C
from .inieditor import Ini, dolphin_name

sys.path.insert(0, str(C.MAC_ONLINE))
from gcmem import DolphinMem, find_dolphin_pid  # noqa: E402

FRAMERATE_GLOBAL = 0x804167B8   # SMS framerate float: 0.5=30fps, 2.0=120fps


def _dolphin_pid():
    return find_dolphin_pid()


def _locate(mem: DolphinMem) -> bool:
    """MEM1 host base: BSMSO comm anchor first (exists from boot on the BSE
    disc), then a GMSE01 disc-header signature scan as fallback."""
    try:
        if mem.locate_comm_buffer():
            return True
    except Exception:
        pass
    for base, size in mem._regions():
        if size < 0x1800000:            # MEM1 view is >= 24MB
            continue
        for hit in mem._scan_region(base, min(size, 0x4000000),
                                    b"GMSE01".hex()):
            chk = mem._raw_read(hit + 0x20, 4)
            if chk and struct.unpack(">I", chk)[0] == 0x0D15EA5E:
                mem._mem1_host_base = hit
                return True
    return mem._mem1_host_base is not None


def _enabled_bodies(ini: Ini) -> dict[str, list[str]]:
    """{dolphin-name: [hex-pair lines]} for every enabled code."""
    want = {dolphin_name(t) for t in ini.enabled()}
    out: dict[str, list[str]] = {}
    span = ini._span("Gecko")
    cur = None
    for ln in ini.text[span[0]:span[1]].splitlines():
        if ln.startswith("$"):
            name = dolphin_name(ln[1:])
            cur = name if name in want else None
            if cur is not None:
                out[cur] = []
        elif cur is not None and ln.strip() and not ln.startswith("*"):
            out[cur].append(ln.strip())
    return out


def _sites(body: list[str]):
    """(c2_addrs, writes04) parsed from a code body. C2 line counts are
    honored so embedded data words are never misread as opcodes."""
    c2, w04 = [], []
    i = 0
    while i < len(body):
        try:
            a, b = body[i].split()
            wa, wb = int(a, 16), int(b, 16)
        except ValueError:
            i += 1
            continue
        op = wa >> 24
        if op in (0xC2, 0xC3):
            c2.append(0x80000000 | (wa & 0x01FFFFFF))
            i += 1 + wb          # skip the cave payload lines
        elif op == 0x04:
            w04.append((0x80000000 | (wa & 0x01FFFFFF), wb))
            i += 1
        else:
            i += 1
    return c2, w04


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, required=True)
    ap.add_argument("--delay", type=int, default=25)
    args = ap.parse_args()
    print(f"[verify] waiting {args.delay}s for boot…", flush=True)
    time.sleep(args.delay)

    pid = None
    for _ in range(12):                      # up to +60s for a slow boot
        pid = _dolphin_pid()
        if pid:
            break
        time.sleep(5)
    if not pid:
        print("[verify] FAIL: no Dolphin process."); return 1

    mem = DolphinMem(pid)
    located = False
    for _ in range(6):
        if _locate(mem):
            located = True
            break
        time.sleep(5)
    if not located:
        print("[verify] FAIL: could not locate MEM1 (core not running?)")
        return 1

    def r32(a): return struct.unpack(">I", mem.read(a, 4))[0]

    failures, warnings = [], []

    # framerate global — retry: the poke/bridge may still be landing
    want_g = struct.unpack(">I", struct.pack(">f", args.fps / 60.0))[0]
    got = None
    for _ in range(8):
        got = r32(FRAMERATE_GLOBAL)
        if got == want_g:
            break
        time.sleep(5)
    if got == want_g:
        print(f"[verify] framerate global OK ({args.fps}fps)")
    else:
        gotf = struct.unpack(">f", struct.pack(">I", got))[0]
        failures.append(f"framerate global = {gotf} (native FPS poke has NOT "
                        f"landed — game is at {int(gotf*60)}fps, codes that "
                        "gate on the rate are dormant)")

    ini = Ini(C.LIVE_INI)
    for name, body in _enabled_bodies(ini).items():
        c2, w04 = _sites(body)
        dead = [a for a in c2 if (r32(a) >> 26) != 18]
        if dead:
            failures.append(f"${name}: {len(dead)}/{len(c2)} C2 hooks NOT "
                            "installed (" +
                            ", ".join(f"{a:08x}" for a in dead[:4]) + ")")
        else:
            stale = [a for a, v in w04 if r32(a) != v]
            if stale:
                warnings.append(f"${name}: {len(stale)}/{len(w04)} 04-writes "
                                "read back differently (may be benign)")
            print(f"[verify] ${name}: OK "
                  f"({len(c2)} C2 hooks, {len(w04)} writes)")

    for w in warnings:
        print(f"[verify] warn: {w}")
    if failures:
        print("[verify] ================ FAIL ================")
        for f in failures:
            print(f"[verify] FAIL: {f}")
        return 1
    print("[verify] ================ PASS ================ "
          "all enabled codes installed & active")
    return 0


if __name__ == "__main__":
    sys.exit(main())
