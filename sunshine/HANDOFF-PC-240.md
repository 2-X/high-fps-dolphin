# HANDOFF — PC 240fps test (BSE fork kxe)

**Date:** 2026-08-13. **Repo branch:** `fpspatch-generalize` — pull latest first.
**Read before doing anything:** `sunshine/HIGH-FPS-CATALOG.md` (§1.3 BSE architecture,
item 36, the 2026-08-12/13 snapshot entries), then `sunshine/bsmso/HANDOFF.md`.

## Mission

Boot-test the BSE fork at **240fps** on the PC (then 280/320). The fork kxe was built
and byte-verified on the Mac 2026-08-12 but has NEVER been run at 240. The Mac is
capped at 120 by hardware (catalog §1.2) and is running the 120 online kit in a
parallel session — coordinate via `sunshine/SYNC-240.md` (protocol below).

## The kit (all in this repo)

- **Fork kxe:** `sunshine/bsmso/BetterSunshineEngine-highfps-v400.kxe` (md5 693b9aca…)
  — BSE v4.0.0 + FPS_240/280/320 (enum 3/4/5, menu range widened, getFrameRate lookup
  {30,60,120,240,280,320}, updateFPS writes 0x804167B8 = FPS/60).
- **Source diff:** `sunshine/bsmso/bse-highfps-240-280-320.diff` (applies to BSE v4.0.0
  tag; tag == release source, validated).
- **ISO recipe** (swap the kxe into the PC's BSMSO ISO): extract the BSMSO ISO root
  (`pyisotools <iso> E`), replace `files/Kuribo!/Mods/BetterSunshineEngine.kxe` with the
  fork kxe, rebuild (`pyisotools <root> B --dest BSMSO-GMSE01-highfps.iso`). Game ID
  stays GMSE01 so the shared GMSE01.ini applies.
- **Custom Dolphin build:** required for correct audio + the Gecko code-cap relocation
  (`sunshine/dolphin-patches/high-fps-dolphin.patch` + README). Stock Dolphin = pitched
  audio + silently dropped late codes.

## PC Dolphin setup for 240 (per catalog §1.4 + item 36)

1. `RAMOverrideEnable=True`, `MEM1Size=0x04000000` (64 MB — BSMSO puppet heap needs it;
   40 MB crashes, 32 MB silently no-puppet). Dolphin.ini, applies at BOOT.
2. `EnableCheats=True` global AND per-game.
3. Per-game `EmulationSpeed = 4.0` (240/60). 280→4.6667, 320→5.3333.
4. **Select 240 in BSE's in-game settings menu** — the fork exposes all six rates and
   persists to memcard. Do NOT poke `0x8051E528`: the fork kxe shifts module data, that
   address is NOT mFPSValue there (the Mac bridge now discovers addresses at runtime;
   see `sunshine/bsmso/mac-online/bridge.py locate_bse_settings()` if you need a poke —
   name-string scan for "Frame Rate", value at Setting object +0x24).
5. Widescreen: BSE aspect setting via its menu (16:9 for a TV; 16:10 exists too), and
   Dolphin `wideScreenHack=False`. Disable any stock `$Widescreen` Gecko.

## What to expect at 240 — CRITICAL

**Every BSE-guarded Gecko code in the Mac companion self-disables at 240** (they gate on
`*0x804167B8 == 2.0f`; the fork writes 4.0 at FPS_240). So at 240 you are running BARE
BSE and ALL the 30Hz-class vanilla bugs return at 8x: repeating SEs, wipes
(decompose/recompose ~8x fast), Noki pollution perf, menu key-repeat, anmrate anims
(Petey/Gooper ~8x), blue coins, clocks (4x via timebase), Poink. **That is fine — the
milestone is only:**
1. Does the fork kxe BOOT and run stable? (Kuribo module load lines in the OSReport log.)
2. Is game speed CORRECT at 240 (not 2x/4x fast)? VPS ≈ 240, Speed 100%-of-400%.
3. Same check at 280/320 if 240 passes, and note real-world PC fps headroom.

A 240 companion bundle (`fpspatch --bse` currently ERRORS at fps≠120 by design) is the
NEXT step after boot confirmation — divisors become FPS/30=8, anmrate ×R/(2G) with the
global at 4.0 already generalizes, blue-coin needs keep-1-of-8, parity stays CONSTANT 2.
Read `sunshine/research/scripts/fpspatch.py` `bse_build()` before writing any of it.

## Known traps (all burned us before)

- Exact Gecko title match or codes silently drop; Dolphin rewrites the user GameSettings
  INI on quit — NEVER edit it while Dolphin runs (use `.claude/skills/dolphin-gecko`).
- Windows INI path: `%APPDATA%\Dolphin Emulator\GameSettings\GMSE01.ini`; use `python`
  not `python3` with gecko.py.
- Input INIs need the PC dialect (see `sunshine-input-mac-pc-dialect` note / repo kits).
- BSE cold-boots FPS_30 each launch UNLESS the memcard-persisted menu setting says
  otherwise — on the fork, set it in the menu once and verify it survives a reboot.

## Cross-session sync protocol

`sunshine/SYNC-240.md` is the shared mailbox between the PC session and the Mac session.
`git pull` before reading/writing; append a dated entry (`## 2026-08-13 PC — <topic>`);
commit just that file and push. Small commits, push often. The Mac session does the same.
