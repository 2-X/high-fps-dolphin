# HANDOFF — ONLINE PAIRING (PC 240 ↔ Mac 120)

**Written:** 2026-08-19 from the PC session. **Branch:** `fpspatch-generalize` — pull first.
**Read alongside:** `sunshine/SYNC-240.md` (cross-session mailbox — append, don't rewrite),
`sunshine/bsmso/mac-online/README.md`, `sunshine/bsmso/PROTOCOL.md`.

## Mission

Get one BSMSO online session running with the **PC at 240fps** and the **Mac at 120fps**
simultaneously. Everything except the server is in place. This is the last untested
milestone in the 240 kit.

**Cross-framerate is explicitly supported — this is not a hack.** BSMSO is position sync,
not lockstep: each player runs their own Dolphin + ISO and only positions/animations/flags
travel. `mac-online/README.md`: *"Per-player FPS and day/night ISOs are fine — this is
position sync, not lockstep."* The wire protocol carries no frame counter or tick index,
and FPS is a purely local per-peer BSE setting. 240 ↔ 120 is a supported pairing.

## THE ONE BLOCKER — the dedicated server

`sunshine/bsmso/bundle-server/` (the real `SMSO.ServerHost.dll`) is **gitignored** and exists
**only on the Mac**. It never came over with the `bsmso-work` handoff, so the PC currently
has no server. With no `config.local.json`, `SERVER_ADDR` defaults to `127.0.0.1`, i.e. the
PC tries to host a server it does not have.

Pick one route. **Route A is recommended** — it proves the whole pipeline solo, on one
machine, before a second machine and a network join the list of things that can be wrong.

### Route A — send `bundle-server/` to the PC, PC hosts (RECOMMENDED)

The server is a plain .NET dll and **`dotnet` is already installed on the PC**
(`C:\Program Files\dotnet\dotnet.exe`), so it should run on Windows unchanged.

1. On the Mac, copy the whole `sunshine/bsmso/bundle-server/` directory to the PC (same way
   `bsmso-work` was handed over — it is gitignored, so do NOT commit it).
2. PC runs it with `dotnet SMSO.ServerHost.dll` (the Mac's `run_server.sh` is just
   `DOTNET_ROOT=… ; cd ../bundle-server ; dotnet SMSO.ServerHost.dll "$@"` — a `.ps1`
   equivalent is trivial). Expect: `listening on TCP+UDP port 27015`.
3. Solo ghost test on the PC first (proves game → bridge → server → bridge → puppet with
   nobody else present), then the Mac joins at **`192.168.1.20:27015`**.

⚠ The Mac's `run_server.sh` hardcodes a Homebrew `DOTNET_ROOT`
(`/usr/local/Cellar/dotnet/10.0.101/libexec`) and the bundle's `runtimeconfig` was patched
to `rollForward` → net10. Check the PC's `dotnet --list-runtimes` covers it; if not, the
same `runtimeconfig` edit applies.

### Route B — Mac hosts, PC joins

1. Mac: `sunshine/bsmso/mac-online/run_server.sh` → wait for `listening on TCP+UDP port 27015`.
2. **Write the Mac's LAN IP into `sunshine/SYNC-240.md`** — the PC session needs it and has
   no way to discover it. Then on the PC create `sunshine/launcher/config.local.json`
   (gitignored, copy from `config.local.json.example`) with `"server_addr": "<MAC_LAN_IP>"`,
   or set `SMS_SERVER=<MAC_LAN_IP>`.

## Network facts (measured on the PC, 2026-08-19)

| | |
|---|---|
| PC LAN IP | `192.168.1.20` |
| PC second adapter | `10.5.0.2` — looks like a VPN (Radmin/Tailscale?) |
| Port | `27015`, **TCP *and* UDP**, both must be reachable |
| PC `dotnet` | present, `C:\Program Files\dotnet\dotnet.exe` |

⚠ **Confirm which network the Mac is actually on.** If the Mac reaches the PC over the VPN
rather than the LAN, point the bridge at the `10.5.x` address instead of `192.168.1.20`.
Windows Firewall will likely prompt on the first inbound connection — allow it, or
pre-authorise 27015 TCP+UDP.

## PC state — what is already done (nothing needed here)

- **Fork ISO**: `C:\Users\krisb\kris-documents\games\dolphin\bsmso-work\BSMSO-GMSE01-highfps.iso`
  (game id `GMSE01`). Contains the fork `BetterSunshineEngine.kxe`
  (md5 `693b9aca0a60e833c75f63814863c440`) + `BetterSunshineMoveset.kxe` + `_BSMSO.kxe`.
  All three confirmed loading in the OSReport log, no panics.
- **240 runs at correct speed** (substep 120Hz sim pin, commit `c18c827`), verify PASS.
- **Windows memory backend**: `mac-online/winmem.py` (Win32 `ReadProcessMemory` /
  `WriteProcessMemory` / `VirtualQueryEx`) + `mac-online/gcmem.py` dispatcher. `bridge.py`
  and `set_bse_fps.py` import `gcmem`, which picks `winmem` on Windows and `macmem` on
  macOS — **the Mac path is unchanged**. No entitlement/codesign dance is needed on Windows.
- **Launcher**: `sunshine/launcher/sms.ps1` (TUI) and `mac-online/play240.ps1`
  (quit → `switch_rate.py` → boot → detached verify → `%TEMP%\sms-verify.log`).
- MEM1 override **64 MB** (`RAMOverrideEnable=True`, `MEM1Size=0x04000000`), `EnableCheats`
  global + per-game, `EmulationSpeed = FPS/60`, `wideScreenHack=False` (BSE renders real
  widescreen; the hack stretches 4:3 instead), `ConfirmStop=False` so automation can close
  Dolphin without the stop dialog blocking it.

## Gotchas that already cost time — don't re-pay them

- **`mFPSValue` moved on the fork kxe**: `0x8051E528` (stock) → **`0x8051EBA8`** (fork);
  aspect → **`0x8051EB58`**. The 120 bundle still ships `$BSE Force 120 FPS`
  (`0451E528 00000002`), which on the fork writes an enum into unrelated live data —
  `switch_rate.py` now skips any bundle-carried `Force` title. `bse_force.py` discovers the
  addresses at runtime from BSE's own Setting *name* strings, so a kxe rebuild self-heals.
- **`bridge.py:_validate_setting_value_addr` was circular** — it derived the object from the
  same hit it was checking, so it accepted *any* pointer-to-name, including pointer TABLES.
  It handed back a table entry and a poke corrupted two live `mName` pointers (restored).
  Fixed by additionally requiring the value field to be a small enum
  (`BSE_SETTING_VALUE_MAX`). **The same bug is in the Mac's copy of this logic** — it is
  only latent there because the stock kxe's hardcoded fast path hits first. Worth taking.
- **Dolphin rewrites the per-game INI from memory on quit** — never edit `GMSE01.ini` while
  it runs. Use the `dolphin-gecko` skill.
- **Emulation stopping looks identical to a broken memory backend.** When no game is booted,
  MEM1 is unmapped and every scan returns nothing. Check the window title contains `GMSE01`
  before believing a "cannot find MEM1" result — this cost a long false diagnosis.
- **BSE cold-boots 30fps / 4:3 every launch** (nothing persists to memcard), and
  `updateFPS(TMarDirector*)` is a **gameplay-only** callback — it never runs on the title
  screen. That is why the rate is forced with Gecko `04` writes rather than a boot-time poke.
- **The comm buffer only exists in a stage.** `bridge.py` and `winmem.py --verify-write` both
  report "not found" on the title screen. Be in Delfino Plaza before judging.

## Run order once a server exists

```
# 1. server (whichever machine hosts)
run_server.sh                      # mac      -> "listening on TCP+UDP port 27015"
dotnet SMSO.ServerHost.dll         # windows

# 2. boot the game and get INTO A STAGE (Delfino Plaza), both machines
powershell -ExecutionPolicy Bypass -File sunshine\bsmso\mac-online\play240.ps1 -Fps 240   # PC
# Mac: its own 120 launcher / smslaunch

# 3. prove memory access on each client (in a stage)
python sunshine/bsmso/mac-online/winmem.py --verify-write     # PC
python3 sunshine/bsmso/mac-online/macmem.py --verify-write    # Mac

# 4. bridge, one per player, unique --name
python bridge.py --server <HOST_IP> --name Kris-PC
python3 bridge.py --server <HOST_IP> --name Kris-Mac

# 5. optional solo proof — a synthetic peer that walks next to you
python ghost_bot.py --server <HOST_IP> --name Ghost
```

`smslaunch` wraps steps 1/2/4 behind its Online selector once `server_addr` is set.

## Open items (not blocking the pairing)

- `bridge.py` still does not clear a remote slot on `PlayerLeft` — a departed player's Mario
  freezes in place until the bridge restarts. Fine solo; fix for real play.
- Only position/animation is bridged. World events (shines/coins/story), model sync, voice
  and game-mode are specced in `PROTOCOL.md` §A.5/§B.2 but not implemented.
- Bianco Hills caps ~170fps on the PC (pollution readbacks 8× too often — catalog item 13);
  the Noki gate stays CRASHES-quarantined under BSE.
- Bird accel at 240 (`k = sqrt(FPS/30)` ≈ ×2.83) is NEEDS-TEST; user wants an eye-comparison
  against the Mac's 120 before any code change.

## Sync protocol

`sunshine/SYNC-240.md` is the shared mailbox. `git pull` before reading or writing, append a
dated `## <date> <machine> — <topic>` entry, commit only that file, push immediately. Never
rewrite the other session's entries.
