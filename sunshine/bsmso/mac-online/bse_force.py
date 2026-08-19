"""Generate (and install) the BSE "force framerate" Gecko codes for any rate.

WHY GECKO AND NOT A MEMORY POKE
-------------------------------
set_bse_fps.py pokes BSE's Setting ints over ReadProcessMemory, which works but
only after the game has booted -- and BSE cold-boots at 30fps / 4:3 on EVERY
launch, so there is always a window where the game runs FPS/30 times too fast.
Gecko `04` (32-bit write) codes are applied by the code handler from the first
frame and re-applied every frame, so the settings are correct from boot with no
tooling attached at all.  This is the same trick as the old `$BSE Force 120 FPS`
(`0451E528 00000002`), generalized.

WHAT GETS WRITTEN
-----------------
  mFPSValue          <- FPSSetting::Kind enum (0=30 .. 5=320)
  gAspectRatioSetting<- 0=4:3, 2=16:10, 3=16:9, 4=21:9
  0x804167B8         <- FPS/60    ) the two stock timestep globals BSE's
  0x80414904         <- FPS/3000  ) updateFPS() writes, per patches/fps.cpp

The last two matter because updateFPS(TMarDirector*) is a GAMEPLAY callback --
it never runs on the title screen or file select.  Pinning the globals from boot
makes menus correctly paced too, and in-stage BSE writes the identical values,
so the Gecko and BSE agree rather than fight.

ADDRESS DISCOVERY
-----------------
mFPSValue is NOT at a fixed address across kxe builds: the high-fps fork
relocated the module data section, moving it from 0x8051E528 (stock kxe) to
0x8051EBA8 (fork).  Hardcoding it is what silently broke the old codes.  So with
a game running this discovers the live addresses by BSE's own Setting *name*
strings; --addr-fps / --addr-aspect override, and the fork values are the
fallback.

Usage:
    python bse_force.py --fps 240                  # print codes (discovers if running)
    python bse_force.py --fps 240 --install        # install into GMSE01.ini
    python bse_force.py --discover                 # just report live addresses
"""
import argparse
import struct
import subprocess
import sys
import os

# FPSSetting::Kind, widened by the fork (src/p_settings.hxx: mValueRange {0,5,1}).
FPS_ENUM = {30: 0, 60: 1, 120: 2, 240: 3, 280: 4, 320: 5}

# Stock timestep globals written by BetterSMS updateFPS() (src/patches/fps.cpp).
ADDR_FRAME_GLOBAL = 0x804167B8   # = FPS / 60
ADDR_TIMESTEP     = 0x80414904   # = FPS / 3000

# Fork-kxe defaults (verified live across multiple launches).  Only used when a
# running game is not available to discover from.
FORK_ADDR_FPS    = 0x8051EBA8
FORK_ADDR_ASPECT = 0x8051EB58


def f32_be(value: float) -> int:
    """IEEE754 float32 as the big-endian word a Gecko 04 code writes."""
    return struct.unpack(">I", struct.pack(">f", value))[0]


def discover_addresses():
    """Find live mFPSValue / aspect addresses from a running Dolphin.

    Returns (fps_addr, aspect_addr, note).  Falls back to the fork constants if
    no game is running or the scan fails.
    """
    try:
        import winmem
        import bridge
    except ImportError as exc:
        return FORK_ADDR_FPS, FORK_ADDR_ASPECT, f"fork defaults (import failed: {exc})"

    pid = winmem.find_dolphin_pid()
    if pid is None:
        return FORK_ADDR_FPS, FORK_ADDR_ASPECT, "fork defaults (Dolphin not running)"
    try:
        mem = winmem.DolphinMem(pid)
    except PermissionError as exc:
        return FORK_ADDR_FPS, FORK_ADDR_ASPECT, f"fork defaults ({exc})"

    try:
        views = [(b, s) for b, s in mem._regions()
                 if s >= winmem._MEM1_MIN_SIZE and mem._raw_read(b, 6) == b"GMSE01"]
        if not views:
            return FORK_ADDR_FPS, FORK_ADDR_ASPECT, "fork defaults (no game booted)"
        mem._mem1_host_base = views[0][0]
        fps_addr    = bridge._scan_settings_by_name(mem, bridge.BSE_FPS_NAME)
        aspect_addr = bridge._scan_settings_by_name(mem, bridge.BSE_ASPECT_NAME)
        if fps_addr is None or aspect_addr is None:
            return (fps_addr or FORK_ADDR_FPS, aspect_addr or FORK_ADDR_ASPECT,
                    "partial discovery (BSE settings may not be registered yet)")
        return fps_addr, aspect_addr, "discovered from live MEM1"
    finally:
        mem.close()


def build_codes(fps: int, aspect: int, fps_addr: int, aspect_addr: int):
    """Return [(title, [code lines])] for the requested rate."""
    out = []
    out.append((
        f"BSE Force {fps} FPS (fork kxe)",
        [
            # mFPSValue = enum  -- BSE's own setting, which it does not clobber.
            f"04{fps_addr & 0x01FFFFFF:06X} {FPS_ENUM[fps]:08X}",
            # The two stock globals, so menus are paced right before any stage
            # loads (updateFPS only runs in gameplay).
            f"04{ADDR_FRAME_GLOBAL & 0x01FFFFFF:06X} {f32_be(fps / 60.0):08X}",
            f"04{ADDR_TIMESTEP & 0x01FFFFFF:06X} {f32_be(fps / 3000.0):08X}",
        ],
    ))
    if aspect >= 0:
        label = {0: "4:3", 2: "16:10", 3: "16:9 WIDE", 4: "21:9", 5: "32:9"}.get(aspect, str(aspect))
        out.append((
            f"BSE Force {label} (fork kxe)",
            [f"04{aspect_addr & 0x01FFFFFF:06X} {aspect:08X}"],
        ))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fps", type=int, choices=sorted(FPS_ENUM), default=240)
    ap.add_argument("--aspect", type=int, default=3,
                    help="BSE aspect enum: 0=4:3, 2=16:10, 3=16:9, 4=21:9; -1 to skip")
    ap.add_argument("--addr-fps", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--addr-aspect", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--discover", action="store_true", help="report live addresses and exit")
    ap.add_argument("--install", action="store_true",
                    help="install into the Dolphin per-game INI (Dolphin must be closed)")
    args = ap.parse_args()

    fps_addr, aspect_addr, note = discover_addresses()
    if args.addr_fps is not None:
        fps_addr, note = args.addr_fps, "overridden on the command line"
    if args.addr_aspect is not None:
        aspect_addr = args.addr_aspect

    print(f"[bse_force] mFPSValue @0x{fps_addr:08X}  aspect @0x{aspect_addr:08X}  ({note})")
    if args.discover:
        return 0

    codes = build_codes(args.fps, args.aspect, fps_addr, aspect_addr)
    print(f"[bse_force] {args.fps}fps -> mFPSValue={FPS_ENUM[args.fps]}, "
          f"0x804167B8={args.fps / 60.0:g}, 0x80414904={args.fps / 3000.0:g}")
    print()
    for title, lines in codes:
        print(f"${title}")
        for ln in lines:
            print(ln)
    print()

    if not args.install:
        print("[bse_force] re-run with --install to write these into GMSE01.ini")
        return 0

    here = os.path.dirname(os.path.abspath(__file__))
    gecko = os.path.abspath(os.path.join(
        here, "..", "..", "..", ".claude", "skills", "dolphin-gecko", "scripts", "gecko.py"))
    if not os.path.isfile(gecko):
        print(f"[bse_force] ERROR: gecko.py not found at {gecko}")
        return 1

    for title, lines in codes:
        # gecko.py is idempotent: re-adding a title replaces the old block, so
        # switching rates cleanly supersedes the previous force code.
        res = subprocess.run(
            [sys.executable, gecko, "add", "--title", title,
             "--code", "\n".join(lines), "--enable"],
            capture_output=True, text=True)
        sys.stdout.write(res.stdout)
        sys.stderr.write(res.stderr)
        if res.returncode != 0:
            print("[bse_force] install FAILED (is Dolphin still running?)")
            return res.returncode

    print("[bse_force] installed + enabled. Relaunch Dolphin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
