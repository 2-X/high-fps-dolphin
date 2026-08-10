#!/usr/bin/env bash
# Enable Dolphin file logging for the BGM coin-toss hunt (HANDOFF-MUSIC-BUG.md).
# Turns on the DSPHLE + AI log categories at INFO verbosity and log-to-file.
#
# MUST be run while Dolphin is CLOSED (Dolphin rewrites Logger.ini on quit and
# would clobber these edits). Log output lands in:
#   ~/Library/Application Support/Dolphin/Logs/dolphin.log
#
#   ./audiolog.sh          # enable
#   ./audiolog.sh grep     # show [hifps] + halt/desync lines from the log
set -euo pipefail

INI="$HOME/Library/Application Support/Dolphin/Config/Logger.ini"
LOG="$HOME/Library/Application Support/Dolphin/Logs/dolphin.log"

if [ "${1:-}" = "grep" ]; then
  grep -E "\[hifps\]|Halting|halted|desync|UCode being|Sync mail" "$LOG" | tail -80
  exit 0
fi

if pgrep -x Dolphin >/dev/null || pgrep -if Dolphin.app >/dev/null; then
  echo "Dolphin is running — quit it first (it rewrites Logger.ini on close)." >&2
  exit 1
fi

python3 - "$INI" <<'EOF'
import re, sys
path = sys.argv[1]
text = open(path).read()

def set_key(text, section, key, value):
    sec_re = re.compile(rf"(\[{section}\].*?)(?=\n\[|\Z)", re.S)
    m = sec_re.search(text)
    body = m.group(1)
    key_re = re.compile(rf"^{key} = .*$", re.M)
    if key_re.search(body):
        body = key_re.sub(f"{key} = {value}", body)
    else:
        body = body.rstrip("\n") + f"\n{key} = {value}\n"
    return text[:m.start(1)] + body + text[m.end(1):]

for section, key, value in [
    ("Logs", "DSPHLE", "True"),
    ("Logs", "AI", "True"),
    ("Options", "Verbosity", "4"),      # INFO (captures NOTICE/ERROR/WARNING too)
    ("Options", "WriteToFile", "True"),
]:
    text = set_key(text, section, key, value)

open(path, "w").write(text)
print("Logger.ini updated: DSPHLE+AI categories, verbosity INFO, write-to-file on.")
EOF

echo "Now launch Dolphin, play until you hit a SILENT level entry, then run:"
echo "  $0 grep"
