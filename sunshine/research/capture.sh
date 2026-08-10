#!/usr/bin/env bash
# Live-capture SMS state from a running Dolphin for bug diagnosis (macOS).
# macOS task_for_pid needs privilege, so this wraps the logger in sudo.
#
#   ./capture.sh poink     # log Bianco-5 Poink launches  -> scripts/popolog.txt
#   ./capture.sh bgm LOG   # log BGM/track state on transitions
#   ./capture.sh state     # one-shot dump of live BGM slots
#
# Boot SMS in the patched build FIRST, get to the relevant spot, then run this
# and perform the action (2-3 Poink launches, or the level transition).
set -euo pipefail
cd "$(dirname "$0")"
export SMS_DOL="$PWD/main.dol"
# arm64-native python to match the arm64 Dolphin target; no sudo needed once the
# build is re-signed with get-task-allow (see HANDOFF: Dolphin must be debuggable).
PY="/usr/bin/python3"; [ -x "$PY" ] || PY="$(command -v python3)"
[ -f "$SMS_DOL" ] || { echo "missing $SMS_DOL"; exit 1; }
pgrep -x Dolphin >/dev/null || pgrep -if Dolphin.app >/dev/null || { echo "Dolphin isn't running — boot the game first."; exit 1; }

mode="${1:-poink}"; shift || true
echo "SMS_DOL=$SMS_DOL   python=$PY"
case "$mode" in
  poink) exec "$PY" scripts/popolog.py "$@" ;;
  bgm)   exec "$PY" scripts/bgmlog2.py "${1:-scripts/bgmlog.txt}" ;;
  state) exec "$PY" scripts/bgmstate.py "$@" ;;
  *) echo "usage: $0 {poink|bgm [logfile]|state [--watch SECS]}"; exit 2 ;;
esac
