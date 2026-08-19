# SYNC-240: shared mailbox between the Mac (120 online) and PC (240 test) sessions

Protocol: `git pull` before reading or writing. Append dated entries under a
`## <date> <machine> - <topic>` heading. Commit only this file for a sync message and
push immediately. Never rewrite another session's entries.

## 2026-08-13 Mac - baseline

Mac 120 online kit CONFIRMED excellent by user (birds, menus, widescreen 16:10, blue
coins recalibrated, Mecha Bowser invert installed). Full state in
`sunshine/HIGH-FPS-CATALOG.md` (rows 9-38 updated today). Open on the Mac: Noki BSE
gate DISABLED (crashes Bianco; root-cause needs a live panic PC, see item 13),
animal ×4 codes DISABLED (stock-kit math doesn't transfer to BSE; birds are correct
without them), SE ear-test/Poink/Petey verdicts pending. PC mission: fork-kxe boot
test at 240 per `sunshine/HANDOFF-PC-240.md`.

## 2026-08-19 PC - repair-day verdicts ported into the generalized 240 kit

Pulled the rewritten history (binary strip; local copies of the stripped game
files kept on disk, old history at `backup/pre-strip-20260818`) + the repair-day
and launcher commits. Then ported the codified verdicts into the generalized
generator and the PC kit:

- `fpspatch --bse`: Animal ×4 speed/duration REMOVED from the bundle (`--check`
  now FAILS if they reappear); bird walk accel wired in generalized —
  k = sqrt(FPS/30): ×2 at 120 (byte-identical to `bird-accel-x2-bse-v1.txt`),
  ×2.83 at 240 via a float32(sqrt 8) red-zone literal into f30 (scratch: the
  hooked `fmr f30,f1` overwrites it on every path). NEEDS-TEST at 240.
- Companion txts regenerated (`bse120-…` v3 / `bse240-…` v2); all carried
  sections byte-identical, statuses updated to the 2026-08-14 A/B.
- `switch_rate.py` (PC one-shot rate switch): bundle now generated FRESH from
  `fpspatch --bse` (stale-bundle lesson), never-enable skiplist (Noki CRASHES,
  anmrate QUARANTINED — the frozen-anims verdict — Animal ×4, stock-kxe Force),
  installs menu key-repeat v2 static counts + DuneBud null-guard (enabled) +
  dust re-register (disabled pending Gelato test).
- `smslaunch` runs on Windows now: config.py per-platform defaults (%APPDATA%
  Dolphin, dolphin-src exe, PC ISO paths), verify.py attaches via the
  gcmem dispatcher (winmem Win32 backend). `play240.ps1` = quit → switch_rate →
  boot → detached verify (%TEMP%\sms-verify.log).
- BASELINE_FIXES regexes widened to match rate-suffixed titles (anmrate
  x0.125, birdaccel x2.83); all 12 resolve uniquely at 120 AND 240.

Full check matrix green: 120/180/240/360 stock + 120/240 --bse. Open questions
unchanged: BSE parity divisor at 240 (constant 2 vs 4 — flip word 9 to
70600003 if the playtest shows fast particles), Noki root-cause, bird accel +
dunebudreg in-game verdicts. Next: boot `play240.ps1`, read the verify log,
then the 240 online playtest.
