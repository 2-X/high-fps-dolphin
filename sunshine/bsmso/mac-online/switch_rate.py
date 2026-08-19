"""Switch the whole PC kit between BSE framerates in one shot.

Does everything a rate change needs, in the order that actually works:
  1. Disable every BSE-<other rate> companion code (they guard on the wrong
     framerate literal and would silently self-disable anyway, but leaving them
     enabled wastes Dolphin's C2 cave, which is finite -- overflow makes codes
     silently stop running).
  2. Generate + install + enable the companion bundle for the target rate,
     STRAIGHT FROM fpspatch --bse.  The generator is the source of truth; a
     stored bundle bites silently when it goes stale (2026-08-14 on the Mac: a
     reused bundle still carried superseded gates).  The committed
     research/codes/bse<fps>-companion-v1.txt is only the no-python fallback.
  3. Install the static per-rate codes the Mac launcher generates per-launch:
     menu key-repeat v2 (BSE ticks the d-pad repeat at the render rate ->
     FPS/30x-fast menu scroll) and the DuneBud null-guard (vanilla no-null-check
     on the sand-dust emitter create; BSMSO crashes "Invalid write 0x154").
  4. Install the force-FPS/aspect 04 writes (bse_force.py) so the rate is live
     from the first frame instead of after a stage loads.
  5. Set EmulationSpeed = FPS/60 in BOTH Dolphin.ini and the per-game
     GMSE01.ini [Core] -- the per-game value overrides the global one, so a
     stale per-game entry silently wins.

Dolphin MUST be closed: it rewrites the per-game INI from memory on quit and
would clobber every edit made here.

Usage:
    python switch_rate.py --fps 120
    python switch_rate.py --fps 240 --aspect 3
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GECKO = os.path.join(REPO, ".claude", "skills", "dolphin-gecko", "scripts", "gecko.py")
FPSPATCH = os.path.join(REPO, "sunshine", "research", "scripts", "fpspatch.py")
BUNDLE = os.path.join(REPO, "sunshine", "research", "codes", "bse{fps}-companion-v1.txt")
CODES_DIR = os.path.join(REPO, "sunshine", "research", "codes")

# Titles that must NEVER land in [Gecko_Enabled], per the codified verdicts:
#   CRASHES ........ Noki gate (crashes Bianco Ep.1; still installed for the
#                    investigation, enabled never)
#   Raw anim-rate .. QUARANTINED 2026-08-14: froze water-slide/bonk-star/warp
#                    anims in-game (BSE natively compensates those consumers)
#   Animal x4 ...... never correct under BSE ("mach 10" birds) -- current
#                    bundles no longer emit them; this guards stale fallbacks
#   Force .......... the 120 bundle's stock-kxe mFPSValue poke; bse_force.py
#                    emits the discovered-address version instead
NEVER_ENABLE = ("CRASHES", "Raw anim-rate", "Animal x4", "Force")

APPDATA = os.environ.get("APPDATA", "")
GAME_INI = os.path.join(APPDATA, "Dolphin Emulator", "GameSettings", "GMSE01.ini")
DOLPHIN_INI = os.path.join(APPDATA, "Dolphin Emulator", "Config", "Dolphin.ini")

CODE_RE = re.compile(r"[0-9A-Fa-f]{8} [0-9A-Fa-f]{8}")


def _run(cmd):
    """subprocess.run with BOTH sides pinned to UTF-8.  Without this, a child
    python on Windows emits cp1252 (the em-dashes in the code titles become
    0x97), the utf-8 reader thread dies, and .stdout comes back None."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def dolphin_running() -> bool:
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout.lower()
    return "dolphin.exe" in out


def parse_bundle_text(text):
    """[(title, [code lines])] from companion-bundle text ($ titles + hex pairs)."""
    blocks, cur = [], None
    for line in text.splitlines():
        s = line.rstrip()
        if s.startswith("$"):
            cur = (s[1:], [])
            blocks.append(cur)
        elif cur is not None and CODE_RE.fullmatch(s.strip()):
            cur[1].append(s.strip())
    return [(t, l) for t, l in blocks if l]


def generate_bundle(fps):
    """The companion bundle for `fps`, fresh from fpspatch --bse (the source of
    truth -- a stored bundle bites silently when stale).  Returns (text, origin)
    or (None, reason) when the rate has no companion (fpspatch explains why:
    280/320 have no exact divisors; 30/60 are native rates)."""
    r = _run([sys.executable, FPSPATCH, str(fps), "--bse"])
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout, "fpspatch --bse (fresh)"
    fallback = BUNDLE.format(fps=fps)
    if os.path.isfile(fallback):
        print(f"[switch] WARNING: fpspatch --bse failed "
              f"({(r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else 'no output'}) "
              f"-- falling back to the COMMITTED bundle, which may be stale")
        with open(fallback, encoding="utf-8") as fh:
            return fh.read(), os.path.basename(fallback)
    return None, (r.stderr or r.stdout).strip() or "fpspatch produced no output"


def gen_menu_repeat(fps):
    """(title, [code lines]) for the static menu key-repeat v2 code -- the same
    math as smslaunch.codegen.gen_menu_repeat_bse (kept in sync BY HAND; the
    launcher package assumes its own repo layout).  TMarioGamePad::reset sets
    d-pad repeat delay/interval as TICK COUNTS sized for a 30Hz pad ticker; BSE
    ticks it at the render rate, so menus scroll FPS/30x too fast.  STATIC on
    purpose: a runtime guard fails here because reset() runs at boot before any
    FPS poke lands (research/codes/menu-repeat-bse-v1.txt has the post-mortem)."""
    delay, interval = 10 * fps // 30, 3 * fps // 30
    if not (0 < delay < 0x8000 and 0 < interval < 0x8000):
        raise SystemExit(f"menu repeat counts out of li range for fps {fps}")
    return (f"Menu key-repeat BSE-{fps} v2 (static)",
            [f"C22A89C8 00000002",
             f"{0x38A00000 | delay:08X} {0x38C00000 | interval:08X}",
             f"3884000F 00000000"])


# Rate-independent BSE codes the Mac launcher installs from research/codes --
# (filename, enable).  The dust re-register stays install-only until the
# in-game Gelato pass (launcher BASELINE has it unverified too).
STATIC_BSE_CODES = [
    ("dunebud-null-guard-bse-v1.txt", True),
    ("dunebud-dust-v1.txt",           False),
]


def set_enabled(titles_to_keep):
    """Rewrite [Gecko_Enabled] to exactly titles_to_keep (order preserved)."""
    with open(GAME_INI, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out, in_en = [], False
    for ln in lines:
        if ln.startswith("["):
            in_en = ln.strip() == "[Gecko_Enabled]"
            out.append(ln)
            continue
        if in_en:
            continue          # drop existing entries; we re-emit below
        out.append(ln)
    if "[Gecko_Enabled]" not in out:
        out.append("[Gecko_Enabled]")
    idx = out.index("[Gecko_Enabled]")
    out[idx + 1:idx + 1] = [f"${t}" for t in titles_to_keep]
    with open(GAME_INI, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def set_emulation_speed(fps):
    """EmulationSpeed = FPS/60 in both INIs (per-game overrides global)."""
    speed = fps / 60.0
    for path, section in ((DOLPHIN_INI, "[Core]"), (GAME_INI, "[Core]")):
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        out, in_sec, done = [], False, False
        for ln in lines:
            if ln.startswith("["):
                if in_sec and not done:
                    out.append(f"EmulationSpeed = {speed:g}")
                    done = True
                in_sec = ln.strip() == section
            if in_sec and re.match(r"\s*EmulationSpeed\s*=", ln):
                out.append(f"EmulationSpeed = {speed:g}")
                done = True
                continue
            out.append(ln)
        if in_sec and not done:
            out.append(f"EmulationSpeed = {speed:g}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        print(f"[switch] EmulationSpeed = {speed:g} in {os.path.basename(path)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, required=True,
                    choices=[30, 60, 120, 240, 280, 320])
    ap.add_argument("--aspect", type=int, default=3)
    ap.add_argument("--no-bundle", action="store_true",
                    help="force codes + EmulationSpeed only (bare BSE)")
    args = ap.parse_args()

    if dolphin_running():
        print("REFUSING: Dolphin is running - it rewrites the INI on quit and "
              "would clobber these edits. Close it and retry.")
        return 1

    enable = []

    # --- companion bundle (generated fresh; see generate_bundle) ----------
    if not args.no_bundle:
        text, origin = generate_bundle(args.fps)
        if text is None:
            print(f"[switch] no companion bundle for {args.fps}fps "
                  f"({origin}) - continuing with force codes only")
        else:
            n_installed = 0
            for title, lines in parse_bundle_text(text):
                _run([sys.executable, GECKO, "add", "--title", title,
                      "--code", "\n".join(lines)])
                n_installed += 1
                if any(marker in title for marker in NEVER_ENABLE):
                    continue                       # installed, never enabled
                enable.append(title)
            print(f"[switch] installed {args.fps} companion bundle from "
                  f"{origin} ({n_installed} codes, {len(enable)} to enable)")

    # --- static per-rate + rate-independent codes (the launcher parity set) -
    if args.fps != 30:                             # 30 = native tick counts
        title, lines = gen_menu_repeat(args.fps)
        _run([sys.executable, GECKO, "add", "--title", title,
              "--code", "\n".join(lines)])
        enable.append(title)
        print(f"[switch] installed ${title}")
    for fname, want_enabled in STATIC_BSE_CODES:
        path = os.path.join(CODES_DIR, fname)
        if not os.path.isfile(path):
            print(f"[switch] WARNING: {fname} missing - skipping")
            continue
        with open(path, encoding="utf-8") as fh:
            blocks = parse_bundle_text(fh.read())
        for title, lines in blocks:
            _run([sys.executable, GECKO, "add", "--title", title,
                  "--code", "\n".join(lines)])
            if want_enabled:
                enable.append(title)
            print(f"[switch] installed ${title}"
                  + ("" if want_enabled else " (NOT enabled - needs in-game pass)"))

    # --- force codes (must come first in [Gecko_Enabled] order-wise) ------
    r = _run([sys.executable, os.path.join(HERE, "bse_force.py"),
              "--fps", str(args.fps), "--aspect", str(args.aspect),
              "--install"])
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        return r.returncode

    force_titles = [f"BSE Force {args.fps} FPS (fork kxe)"]
    label = {0: "4:3", 2: "16:10", 3: "16:9 WIDE", 4: "21:9", 5: "32:9"}.get(args.aspect)
    if args.aspect >= 0 and label:
        force_titles.append(f"BSE Force {label} (fork kxe)")

    set_enabled(list(dict.fromkeys(force_titles + enable)))
    set_emulation_speed(args.fps)

    print(f"[switch] now at {args.fps}fps: "
          f"{len(force_titles + enable)} codes enabled. Relaunch Dolphin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
