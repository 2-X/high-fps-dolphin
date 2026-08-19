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

## 2026-08-19 PC - 240 RUNS AT CORRECT SPEED (substep pin); playtest verdicts

First BSE-240 boot ran the whole game exactly 2x fast (FPS 240 = VPS 240,
physics/anims 2x; A/B at 120 on the same pipeline was correct). Root cause,
live-measured then DOL-confirmed: vanilla TMarDirector's substep scheduler
(budget 600/int(60*G) per frame, 5/substep) runs the FIRST substep of every
frame UNCONDITIONALLY — no zero-substep path exists, so 120 is the highest
rate vanilla paces right (why bare BSE-120 works at all) and at 240 the sim
rides the render rate.

Fix (commit c18c827): "$Substep 120Hz sim pin" emitted by `fpspatch --bse`
at fps > 120 — the stock-kit trio verbatim: substep_granularity(2) constants
(1200/10 = 120 Hz sim at EVERY rate) + the zero-substep C2 + the v11
SMSGetAnmFrameRate 0.5f stub + the v9 input latch. Divisors are now split by
cadence class (`bse_sim_fps()`): substep-paced (blue-coin, shimmer, bird
accel x2) use 120-sim values at every rate; render/audio (wipe, SE, menu
repeat) and timebase (game clock) scale with the real rate. The v2 parity
caveat is RESOLVED: the gate counts the substep counter, 120 Hz under the
pin, so the constant 2 is exact.

IN-GAME CONFIRMED at 240 on the PC: correct speed, 240/240, verify PASS.
QOL now installed per-rate by switch_rate (FLUDD v3, $FOV 60 BSE, camera
look-up; user-enabled titles preserved). OPEN: Bianco Hills caps ~170 —
pollution readbacks 8x too often (item 13); the noki gate stays
CRASHES-quarantined under BSE. NOTE the crash predates the substep pin —
worth a guarded re-test with OSReport/panic logging armed. Birds feel slow
to the user vs the (broken) 2x session; they are at the Mac-120 calibration
— needs an eye-comparison against the Mac, not a code change, first.

## 2026-08-19 PC - online pairing handoff, need the server

240 is confirmed correct-speed on the PC and every client-side piece for online is in
place (winmem/gcmem Win32 backend, bridge/set_bse_fps on the dispatcher, smslaunch +
play240.ps1). The online playtest is blocked on ONE thing: `bundle-server/` is gitignored
and lives only on the Mac, so the PC has no dedicated server and `server_addr` defaults to
127.0.0.1 (hosting a server it does not have).

Full details + run order: `sunshine/HANDOFF-ONLINE-PAIRING.md`.

MAC SESSION — pick one and reply here:
- ROUTE A (preferred): copy `sunshine/bsmso/bundle-server/` to the PC (gitignored, hand it
  over like bsmso-work was). `dotnet` IS installed on the PC, so it can host; that lets us
  prove the pipeline solo before adding a second machine. Then the Mac joins 192.168.1.20:27015.
- ROUTE B: Mac hosts via run_server.sh -> POST THE MAC'S LAN IP IN THIS FILE. The PC has no
  way to discover it, and it is the only thing missing for the PC to join.

Also confirm which network the Mac reaches the PC on: the PC has LAN 192.168.1.20 AND a
second adapter 10.5.0.2 (VPN?). Port 27015 must be reachable on TCP *and* UDP.

Carry-over worth taking on the Mac: `bridge.py::_validate_setting_value_addr` is circular
(derives the object from the hit it is validating, so it accepts any pointer-to-name,
including pointer tables). It handed back a table entry here and a poke corrupted two live
mName pointers. Fixed on this side with a small-enum range check on the value field; the
Mac only avoids it today because the stock-kxe hardcoded fast path hits first.
