# BSMSO on Mac: native online stack

Reimplements the Windows-only BSMSO launcher's network bridge for macOS, so a Mac
can play (and solo-test) BSMSO online. The mod itself, the game, and the *server*
are unchanged; this only replaces the launcher's Dolphin-RAM ↔ network bridge.

Full protocol reverse-engineering: [`../PROTOCOL.md`](../PROTOCOL.md).

## Pieces

| File | Role |
|---|---|
| `protocol.py` | Constants, CRC32, TCP/UDP framing, packet builders/parsers, `PlayerSnapshot` (BE comm + LE wire). |
| `netclient.py` | `NetClient`: TCP join handshake, UDP register, heartbeat, snapshot send/recv threads. |
| `macmem.py` | `DolphinMem`: Mach read/**write** into Dolphin RAM; locates the comm buffer via the `SMSO` anchor at guest `0x817FC000`. Routes Mach calls through the signed `memhelper` (**no sudo**). |
| `memhelper/` | Tiny signed native helper (`memhelper.c` + `debugger.entitlements` + `build.sh`) holding the Mach task port. Ad-hoc-signed with `com.apple.security.cs.debugger` so `task_for_pid` succeeds without sudo. `macmem.py` auto-builds it on first use. |
| `bridge.py` | The bridge: reads your live Mario from the comm buffer → server; writes remote puppets back into RAM. **No sudo.** |
| `ghost_bot.py` | A synthetic peer that walks a circle. In `--follow` (default) it adopts the live player's stage/position so the puppet appears right next to you. No game/sudo needed. |
| `selftest_loopback.py` | Two bots through the real server; asserts they see each other. No game/sudo. |
| `run_server.sh` | Launches the real `SMSO.ServerHost.dll` via `dotnet`. |

## Solo online self-test (no friend, no second machine)

Four terminals. The game must already be BSMSO-patched (see `../`, `BSMSO-GMSE01.iso`)
and running in our custom Dolphin, and you must be **in a stage** (e.g. Delfino Plaza),
not the title screen.

```
# 1) Server
./run_server.sh
# wait for: Server listening on TCP+UDP port 27015

# 2) Bridge — publishes YOUR Mario and injects remote puppets. No sudo.
#    Auto-builds memhelper on first run. Retries until you're in a stage.
python3 bridge.py --server 127.0.0.1 --name Kris

# 3) Ghost — a second Mario that walks a circle next to you (auto-follows your stage)
python3 ghost_bot.py --server 127.0.0.1 --name Ghost
```

Expected: a second Mario appears beside you and circles. That proves the whole
pipeline end-to-end (game → bridge → server → bridge → puppet render) with nobody
else present.

### Before trusting the bridge near your live game: verify memory access

`bridge.py` writes into Dolphin's RAM. Confirm read+write work first (game must be
in a stage so the comm buffer exists):

```
python3 macmem.py --verify-write  # prints comm-buffer addr + does a no-op write round-trip
```

If `task_for_pid` fails (helper prints `ERR attach kr=…`): the Dolphin bundle must be
signed with `get-task-allow`. Re-sign our build (reverts on every rebuild):

```
codesign --force --sign - \
  --entitlements ../../../dolphin/Source/Core/DolphinQt/DolphinEmuDebug.entitlements \
  --options runtime ../../../dolphin/build/Binaries/Dolphin.app
```

The **caller** side is handled by `memhelper` (ad-hoc-signed with the debugger
entitlement): no sudo, no signed Python needed. If `macmem.py` reports "Comm buffer
NOT FOUND" while everything else works, you're not in a stage (title screen / paused).

## Real online with a friend

Same, but point `--server` at the host's IP (one player runs `./run_server.sh`, or a
Windows player hosts). Everyone's `--name` must be unique. Port 27015 TCP+UDP must be
reachable (LAN, VPN like Radmin/Tailscale, or port-forward). Per-player FPS and day/night
ISOs are fine: this is position sync, not lockstep.

## Known limitations (solo test unaffected)
- **Despawn:** `bridge.py` doesn't yet clear a puppet's slot on `PlayerLeft`, so a
  departed player's Mario freezes in place until you restart the bridge. TODO.
- **Outbound only for movement:** world events (shines/coins/story flags), model sync,
  voice, and game-mode are not yet bridged; only player position/animation. Add per
  `PROTOCOL.md` §A.5/§B.2 when needed.
