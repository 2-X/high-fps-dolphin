#!/bin/zsh
# One-command BSMSO 120fps launcher.
#
#   ./play120.sh                 boot the proven BSMSO-GMSE01.iso, 120fps + 16:10
#                                (exact fit for the MBP 16" panel — no letterbox)
#   ./play120.sh --tv            use 16:9 WIDE instead (external TV/monitor)
#   ./play120.sh highfps         boot the 240-capable fork ISO instead
#   ./play120.sh --online        also ensure server + restart bridge (puppets)
#   ./play120.sh --ghost         also start the ghost bot (implies --online)
#
# Why this exists: BSE cold-boots at 30fps/4:3 EVERY launch (neither setting is
# persisted), and the aspect must be written before scene setup or the scene
# stays a stretched 4:3. set_bse_fps.py retries until the BSE module registers
# its settings (~seconds into boot), so run this and just play.
#
# Aspect plumbing (two halves, both set here):
#   game side    — BSE gAspectRatioSetting: 2 = 16:10 (Mac panel), 3 = 16:9 (TV)
#   display side — Dolphin per-game [Video_Settings] AspectMode: 4 = Custom
#                  (16:10) for Mac, 1 = ForceWide for TV. Written while Dolphin
#                  is quit (it rewrites the INI from memory on quit otherwise).

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$DIR/../../../dolphin/build/Binaries/Dolphin.app"
ISO=/Applications/gamecube/bsmso-work/BSMSO-GMSE01.iso
ONLINE=0
GHOST=0
BSE_ASPECT=2   # 16:10 — MBP 16" fullscreen area (3456x2160) exactly
for a in "$@"; do
  case "$a" in
    highfps)  ISO=/Applications/gamecube/bsmso-work/BSMSO-GMSE01-highfps.iso ;;
    --online) ONLINE=1 ;;
    --ghost)  ONLINE=1; GHOST=1 ;;
    --tv)     BSE_ASPECT=3 ;;
    *) echo "unknown arg: $a" >&2; exit 1 ;;
  esac
done

pkill -x Dolphin 2>/dev/null || true
# Dolphin rewrites the per-game INI as it quits — wait until it is fully gone
# before touching the INI, or the on-quit rewrite clobbers our edit.
for i in {1..20}; do
  pgrep -x Dolphin >/dev/null || break
  sleep 1
done
pgrep -x Dolphin >/dev/null && { kill -9 $(pgrep -x Dolphin); sleep 2; }

# Dolphin display aspect (per-game override), while Dolphin is quit.
BSE_ASPECT=$BSE_ASPECT python3 - <<'PYEOF'
import os, pathlib
ini = pathlib.Path.home() / "Library/Application Support/Dolphin/GameSettings/GMSE01.ini"
mac = os.environ["BSE_ASPECT"] == "2"
want = ({"AspectRatio": "4", "CustomAspectRatioWidth": "16", "CustomAspectRatioHeight": "10"}
        if mac else {"AspectRatio": "1"})
lines = ini.read_text().splitlines()
out, in_vs, seen, has_section = [], False, set(), False
for ln in lines:
    s = ln.strip()
    if s == "[Video_Settings]":
        in_vs, has_section = True, True
        out.append(ln)
        continue
    if in_vs and s.startswith("["):
        for k, v in want.items():
            if k not in seen:
                out.append(f"{k} = {v}")
        in_vs = False
    if in_vs and "=" in s:
        k = s.split("=")[0].strip()
        if k in want:
            out.append(f"{k} = {want[k]}"); seen.add(k)
            continue
        if k in ("AspectRatio", "AspectMode", "CustomAspectRatioWidth", "CustomAspectRatioHeight"):
            continue  # drop stale aspect keys not in the wanted set
    out.append(ln)
if in_vs:  # [Video_Settings] was the last section — flush missing keys at EOF
    for k, v in want.items():
        if k not in seen:
            out.append(f"{k} = {v}")
if not has_section:
    out.append("[Video_Settings]")
    out.extend(f"{k} = {v}" for k, v in want.items())
ini.write_text("\n".join(out) + "\n")
print(f"[play120] Dolphin display aspect set: {want}")
PYEOF

open -a "$APP" --args -e "$ISO"
echo "[play120] booting $(basename "$ISO") in the custom build…"

python3 "$DIR/set_bse_fps.py" --fps 120 --aspect "$BSE_ASPECT"

if (( ONLINE )); then
  if ! pgrep -f SMSO.ServerHost >/dev/null; then
    nohup "$DIR/run_server.sh" > /tmp/smso-server.log 2>&1 &
    sleep 3
    pgrep -f SMSO.ServerHost >/dev/null || { echo "[play120] SERVER FAILED — see /tmp/smso-server.log"; exit 1; }
    echo "[play120] server started"
  fi
  pkill -f bridge.py 2>/dev/null || true
  sleep 1
  nohup python3 -u "$DIR/bridge.py" --server 127.0.0.1 --name Kris --aspect "$BSE_ASPECT" > /tmp/bridge.log 2>&1 &
  echo "[play120] bridge running (log: /tmp/bridge.log)"
  if (( GHOST )); then
    pkill -f ghost_bot.py 2>/dev/null || true
    sleep 1
    nohup python3 -u "$DIR/ghost_bot.py" --server 127.0.0.1 --name Ghost > /tmp/ghost.log 2>&1 &
    echo "[play120] ghost bot running (log: /tmp/ghost.log)"
  fi
fi

echo "[play120] ready — pick your save and play. Bridge/ghost attach once you're in a stage."
