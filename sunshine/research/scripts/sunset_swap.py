#!/usr/bin/env python3
"""
sunset_swap.py -- Day/Night hard-swap for Super Mario Sunshine <-> Super Mario Sunset.

Flow (matches the manual-save design):
  1. You play the "day" ISO (base SMS).
  2. When you're ready to flip to dusk, save in-game at a save box.
  3. This script -- already armed -- watches the memory-card .gci, detects the
     save the instant it commits, waits for it to stabilize (debounce),
  4. gracefully closes Dolphin (in GCI-folder mode the save is already on disk),
  5. copies the save across ONLY if Sunset writes a different .gci name,
  6. boots the other ISO into Dolphin.

Because Dolphin is in GCI-folder mode and the two games share the same USA
Card A folder AND the same save-data format, the carry-over is automatic when
both write the same .gci filename. See SUNSET_GCI below.

Usage:
  python sunset_swap.py            # arm, wait for save, then boot NIGHT (Sunset)
  python sunset_swap.py --to day   # ... then boot DAY (base) instead
  python sunset_swap.py --confirm  # ask y/n after detecting the save, before closing
  python sunset_swap.py --dry-run  # detect + report, but don't close/launch

Tested target: Windows, custom Dolphin at dolphin-src\Binary\x64\Dolphin.exe.
"""
import argparse
import os
import subprocess
import sys
import time

# ======================= CONFIG -- edit these ========================
DOLPHIN = r"C:\code\high-fps-dolphin\dolphin-src\Binary\x64\Dolphin.exe"

# GCI-folder save location (confirmed on this machine):
CARD_DIR = os.path.expandvars(r"%APPDATA%\Dolphin Emulator\GC\USA\Card A")

# The .gci the BASE game writes (confirmed on this machine):
BASE_GCI = "01-GMSE-super_mario_sunshine.gci"

# The .gci SUNSET writes. Leave None if Sunset reuses the SAME name as BASE_GCI
# (the usual case for a pure asset-flip whose DOL is unchanged) -> no copy needed.
# Set it (e.g. "11-GMSE-super_mario_sunshine.gci") only if the 2-min test shows
# Sunset creating a differently-named file.
SUNSET_GCI = None

# ISO / RVZ paths -- FILL THESE IN:
ISO_DAY = r"FILL_ME_IN\SuperMarioSunshine.rvz"
ISO_NIGHT = r"FILL_ME_IN\SuperMarioSunset-GMSE11-v1.1.iso"

# Save is considered "done" once mtime+size hold steady this long (seconds):
DEBOUNCE_S = 1.5
# Boot straight into the game (True). If False, boots into the game AND makes
# closing the game window quit Dolphin (batch mode) -- kiosk-style swapping.
BATCH_MODE = False
# =====================================================================


def _mtime_size(path):
    try:
        st = os.stat(path)
        return (st.st_mtime, st.st_size)
    except FileNotFoundError:
        return (0, 0)


def watch_for_save(path):
    """Block until `path` changes, then stays stable for DEBOUNCE_S."""
    print(f"[armed] waiting for an in-game save...\n        watching {path}")
    baseline = _mtime_size(path)
    while _mtime_size(path) == baseline:
        time.sleep(0.5)
    print("[save]  write detected -- waiting for it to settle...")
    last = _mtime_size(path)
    while True:
        time.sleep(DEBOUNCE_S)
        cur = _mtime_size(path)
        if cur == last:
            break
        last = cur
    print("[save]  committed and stable.")


def close_dolphin(timeout=15):
    """Ask Dolphin to close gracefully; escalate only if it refuses."""
    print("[close] closing Dolphin (graceful)...")
    if sys.platform.startswith("win"):
        # taskkill WITHOUT /F sends WM_CLOSE to the GUI -> clean shutdown.
        subprocess.run(["taskkill", "/IM", "Dolphin.exe"],
                       capture_output=True)
        still = lambda: b"Dolphin.exe" in subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Dolphin.exe"],
            capture_output=True).stdout
    else:
        subprocess.run(["pkill", "-x", "Dolphin"], capture_output=True)
        still = lambda: subprocess.run(
            ["pgrep", "-x", "Dolphin"], capture_output=True).returncode == 0

    t0 = time.time()
    while still() and time.time() - t0 < timeout:
        time.sleep(0.5)
    if still():
        print("[close] still running after timeout -- forcing.")
        if sys.platform.startswith("win"):
            subprocess.run(["taskkill", "/F", "/IM", "Dolphin.exe"],
                           capture_output=True)
        else:
            subprocess.run(["pkill", "-9", "-x", "Dolphin"],
                           capture_output=True)
        time.sleep(1.0)
    print("[close] Dolphin exited.")


def carry_save(direction):
    """Copy the .gci across only if the two games use different filenames."""
    if not SUNSET_GCI or SUNSET_GCI == BASE_GCI:
        print("[save]  same .gci name for both games -> carry-over is automatic.")
        return
    import shutil
    src, dst = (BASE_GCI, SUNSET_GCI) if direction == "night" else (SUNSET_GCI, BASE_GCI)
    src_p, dst_p = os.path.join(CARD_DIR, src), os.path.join(CARD_DIR, dst)
    if os.path.exists(src_p):
        shutil.copy2(src_p, dst_p)
        print(f"[save]  copied {src} -> {dst}")
    else:
        print(f"[save]  WARN: expected source save {src} not found; skipping copy.")


def boot(iso):
    if not os.path.exists(iso):
        sys.exit(f"[boot]  ISO not found: {iso}\n        Fix ISO_DAY / ISO_NIGHT in the CONFIG block.")
    args = [DOLPHIN, "-e", iso]
    if BATCH_MODE:
        args.insert(1, "-b")
    print(f"[boot]  launching {os.path.basename(iso)} ...")
    subprocess.Popen(args, close_fds=True)


def countdown(seconds):
    """Sleep `seconds`, printing a once-a-second countdown on one line."""
    for s in range(seconds, 0, -1):
        print(f"\r[play]  swap prompt in {s:2d}s ... (Ctrl-C to cancel)", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 60 + "\r", end="")


def main():
    ap = argparse.ArgumentParser(description="SMS day/night hard-swap.")
    ap.add_argument("--to", choices=["day", "night"], default="night",
                    help="which ISO to boot after the swap (default: night = Sunset)")
    ap.add_argument("--mode", choices=["timer", "save"], default="timer",
                    help="timer = wait --wait seconds then prompt (default); "
                         "save = wait for an in-game memory-card save")
    ap.add_argument("--wait", type=int, default=30,
                    help="seconds to play before prompting, in timer mode (default: 30)")
    ap.add_argument("--dry-run", action="store_true",
                    help="run the wait, but don't close/copy/launch")
    args = ap.parse_args()

    if not os.path.isdir(CARD_DIR):
        sys.exit(f"Card dir not found: {CARD_DIR}")

    target_iso = ISO_NIGHT if args.to == "night" else ISO_DAY
    print(f"Target: {args.to.upper()}  ->  {os.path.basename(target_iso)}\n")

    if args.mode == "save":
        watch_for_save(os.path.join(CARD_DIR, BASE_GCI))
    else:
        print(f"[play]  go play -- I'll prompt you in {args.wait}s.")
        print("        (this is a swap TEST: nothing is auto-saved, so save in-game "
              "first if you want to keep progress.)")
        countdown(args.wait)

    if args.dry_run:
        print("[dry-run] would now: close Dolphin, carry save, boot target. Stopping.")
        return

    if input(f"Swap to {args.to.upper()} now? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Aborted -- keeping current session.")
        return

    close_dolphin()
    carry_save(args.to)
    boot(target_iso)
    print("\nDone. Enjoy dusk on Isle Delfino." if args.to == "night"
          else "\nDone. Back to daylight.")


if __name__ == "__main__":
    main()
