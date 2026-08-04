#!/bin/bash
# One-shot: sideload DolphinXR onto the Quest 3 and stage Sunshine + 120fps Gecko codes.
# Prereqs: Quest in Developer Mode, plugged in over USB-C, debugging prompt accepted
#          in-headset. adb installed (macOS: brew install android-platform-tools;
#          Windows: winget install Google.PlatformTools, run via git-bash).
set -euo pipefail

PKG=org.dolphinemu.dolphinemu.quest.debug
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"
APK="$DIR/DolphinRedux-app-quest-debug.apk"
APK_URL=https://github.com/iChris4/dolphinXR/releases/download/v0.3/DolphinRedux-app-quest-debug.apk
FILES="/sdcard/Android/data/$PKG/files"

# Game image is not in git — set GAME_RVZ to its local path if not at the Mac default.
GAME="${GAME_RVZ:-/Applications/gamecube/Super Mario Sunshine (USA).rvz}"

[ -f "$APK" ] || { echo "==> Downloading DolphinXR v0.3 Quest APK"; curl -sL -o "$APK" "$APK_URL"; }

echo "==> Waiting for Quest over USB..."
adb wait-for-device
adb devices

echo "==> Installing DolphinXR"
adb install -r "$APK"

if [ -f "$GAME" ]; then
  echo "==> Pushing Super Mario Sunshine RVZ (this takes a minute)"
  adb push "$GAME" /sdcard/Download/
else
  echo "!! Game not found at: $GAME — set GAME_RVZ=/path/to/rvz and re-run, or push manually."
fi

echo "==> Launching once so Dolphin creates its user folders"
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
sleep 5

echo "==> Pushing 120fps Gecko codes + memcard save"
adb shell mkdir -p "$FILES/GameSettings" "$FILES/GC/USA/Card A" 2>/dev/null || true
adb push "$REPO/sunshine/dolphin-config/GameSettings/GMSE01.ini" "$FILES/GameSettings/GMSE01.ini" \
  || echo "  (Android/data push blocked on this OS build — in-headset use Dolphin's" \
          " Settings > User Data > Import to bring GMSE01.ini in instead)"
adb push "$REPO/sunshine/saves/01-GMSE-super_mario_sunshine.gci" "$FILES/GC/USA/Card A/" 2>/dev/null || true

echo ""
echo "Done. In-headset: App Library > Unknown Sources > Dolphin Redux."
echo "Point it at /sdcard/Download for the game; Gecko codes are under the game's Cheats menu."
echo "NOTE: at 2x sim rate audio tempo will be wrong on this stock build (needs our DMA"
echo "patch ported into a custom DolphinXR build) — test framerate first, fix audio later."
