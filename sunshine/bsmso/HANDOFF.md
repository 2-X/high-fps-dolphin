# BSMSO-on-Mac: Handoff (for Fable, /architect mode)

**Date:** 2026-08-11. **Repo:** `/Users/kbrethower/code/high-fps-dolphin`, branch `fpspatch-generalize`.
**Read first:** the memory file `sunshine-bsmso-mac-integration` (in the auto-memory dir) and
`sunshine/bsmso/PROTOCOL.md`. This doc is the live-state pointer on top of those.

## Goal
Play **Better Super Mario Sunshine Online (BSMSO v1.1)** on this Mac at high FPS while friends
play at any FPS. Position-sync, not lockstep: each player runs own Dolphin+ISO; only
positions/animations/flags sync. Immediate sub-goal the user wants: **solo self-test** (a
synthetic "ghost" player appears and walks in their game with nobody else present).

## What is DONE and verified
1. **BSMSO patched ISO built + boots** in our custom Dolphin, plays solo (user did Bianco @30fps).
   - ISO: `/Applications/gamecube/bsmso-work/BSMSO-GMSE01.iso`. Pristine root at
     `.../bsmso-work/pristine-root/`, patched root at `.../bsmso-work/bsmso-root/`.
   - Built from BSE v4.0.0 release payloads (main.dol/boot.bin/KuriboKernel.bin) + BSMSO `.kxe`
     + `.szs`. Recipe + hook-collision analysis in the memory file. **Game ID stays GMSE01** so
     our Gecko stack + texture packs still apply. **Zero collisions** vs our ~107 hook addresses
     (`sunshine/bsmso/doldiff.py` + `hook-addresses.txt` prove it).
2. **The real BSMSO dedicated server runs natively on this Mac** via `dotnet`.
   - Launch: `sunshine/bsmso/mac-online/run_server.sh` → "listening on TCP+UDP port 27015".
3. **Full protocol reverse-engineered** to byte level: `sunshine/bsmso/PROTOCOL.md`
   (comm-buffer RAM layout in BIG-endian, TCP/UDP wire in LITTLE-endian, CRC32, packet catalog,
   ghost-bot checklist §C.2). Decompiled C# under `sunshine/bsmso/decompiled/`.
4. **Python online stack written + Milestone-1 verified** in `sunshine/bsmso/mac-online/`:
   `protocol.py`, `netclient.py`, `bridge.py`, `ghost_bot.py`, `macmem.py`,
   `selftest_loopback.py`. **M1 PASS:** two ghost bots exchanged ~300 snapshots/5s through the
   real server; ghost auto-follow (adopts the live player's stage/pos) confirmed. Code was
   human-reviewed. `mac-online/README.md` has the run procedure.

## THE BLOCKER (this is the whole job right now)
`macmem.py` / `bridge.py` must read+write the running Dolphin's emulated RAM via Mach
(`task_for_pid` → `mach_vm_read_overwrite` / `mach_vm_write`). **`task_for_pid` returns
`kr=5` (KERN_FAILURE)** in every configuration tried:
- `sudo python3 macmem.py` → kr=5
- `python3 macmem.py` (no sudo, same user) → kr=5

**Root cause (confirmed by inspection, 2026-08-11):**
- SIP is ON.
- The **target** Dolphin now HAS `com.apple.security.get-task-allow` (we re-signed it; see below). That side is done.
- The **caller** is Homebrew `python3` 3.14 (`/usr/local/bin/python3`, a pyenv/homebrew build)
  which has **no `com.apple.security.cs.debugger` entitlement** and is **not an Apple platform
  binary**. On Apple Silicon, AMFI refuses `task_for_pid` from such a caller *even as root* and
  *even when the target has get-task-allow*. **The calling binary must itself be entitled/trusted.**
  This is the remaining gate. `sudo` does NOT help (it was a red herring: the gate is the
  caller's code signature, not uid).

Facts gathered for you:
- `/usr/local/bin/python3` (caller) → no debugger/task entitlement.
- `/usr/bin/python3` → Apple platform binary, Python **3.9.6** (macmem.py is stdlib-only, runs on 3.9).
- `/usr/bin/lldb` present (Apple-signed, has the debugger entitlement): attaches to get-task-allow apps.
- Running Dolphin binary confirmed carrying `get-task-allow`.

### FIRST STEP for whoever picks this up: a 2-command diagnostic + likely quick win
1. **Confirm the target is truly attachable** (isolates caller-vs-target):
   `sudo lldb -p <dolphin_pid> -o "process status" -o detach -o quit -b`
   (get pid via `pgrep -x Dolphin`.) If lldb attaches, the target is 100% fine and it is
   *purely* the python-caller entitlement. (Near-certain given the facts above.)
2. **Try the Apple platform interpreter** (cheapest possible fix; it may just be trusted):
   `/usr/bin/python3 sunshine/bsmso/mac-online/macmem.py`   (try WITH and WITHOUT sudo)
   If this prints the comm-buffer address, the blocker is gone and you skip all the below.

### If /usr/bin/python3 doesn't work: fixes in priority order
**A. Sign a dedicated interpreter copy with the debugger entitlement (most likely correct).**
   Make a `debugger.entitlements` with `com.apple.security.cs.debugger`=true (also keep
   get-task-allow + disable-library-validation). Copy the *real* python Mach-O (not the venv
   symlink: resolve it) to a local path, `codesign --force --sign - --entitlements
   debugger.entitlements --options runtime <copy>`, and run the bridge with that interpreter.
   Gotcha: framework pythons are shims; you may need to copy the actual
   `.../Python.framework/Versions/3.x/Resources/Python.app/Contents/MacOS/Python` or use a
   pyinstaller/py2app single binary. Verify with `codesign -d --entitlements -`.

**B. Tiny signed native memory-helper (most robust; recommended if A is fiddly).**
   ~120 lines of C or Swift: `task_for_pid` + `mach_vm_read_overwrite` + `mach_vm_write`,
   exposing a trivial line protocol over stdin/stdout or a localhost UNIX socket
   (`READ <hexaddr> <len>` / `WRITE <hexaddr> <hexbytes>` / `LOCATE`). `codesign --force --sign -
   --entitlements debugger.entitlements --options runtime helper`. Then `macmem.py` shells out to
   this helper instead of calling ctypes Mach directly (swap the 3 methods: `_raw_read`,
   `_raw_write`, region-enum). Clean separation; the entitled surface is tiny and auditable.
   This is the standard pattern for Mach memory tools on Apple-Silicon+SIP.

**C. Frida** (`pip install frida`, `frida`/`frida-python`): handles the injection/entitlement
   dance itself; can read/write process memory. May still need its own signed helper/sudo. Faster
   to prototype than B but adds a heavy dependency.

**D. lldb-scripted backend:** drive `/usr/bin/lldb -p PID` in batch (or its Python module inside
   lldb's entitled process) to `memory read`/`memory write`. Works without custom signing but is
   slow/awkward for a 60 Hz loop; acceptable only for the one-shot `LOCATE`/proof.

**Recommendation:** try the 2-command diagnostic + `/usr/bin/python3`. If that fails, do **B**
(signed native helper): it's the durable fix and keeps `macmem.py`'s clean API. Deleg­ate B to a
`coder`; keep the entitlement/codesign reasoning and the diff review in your own context.

### STILL-UNPROVEN even after task_for_pid works
`mach_vm_write` into Dolphin's MEM1 may or may not need extra handling (it's a RW mmap; expected
to work once the task port is held, but untested). Prove read first (`macmem.py` prints comm
addr), then prove a *no-op* write (read 8 bytes at the comm buffer, write them back unchanged,
confirm KERN_SUCCESS) before running the full bridge.

## Codesign state you inherit (IMPORTANT)
We re-signed the Dolphin **bundle** with Dolphin's own committed debug entitlements:
`codesign --force --sign - --entitlements dolphin/Source/Core/DolphinQt/DolphinEmuDebug.entitlements --options runtime dolphin/build/Binaries/Dolphin.app`
That file = {allow-jit, disable-library-validation, audio-input, apple-events} **+ get-task-allow**.
- Do **NOT** sign with a get-task-allow-*only* plist: it strips allow-jit/library-validation and
  Dolphin won't launch (dyld rejects Homebrew Qt: "different Team IDs"). We hit this; the
  whole-bundle sign with DolphinEmuDebug.entitlements fixed it (`codesign --verify` passes).
- **This re-sign reverts on any Dolphin rebuild.** Redo it after rebuilding.
- Current Dolphin is running with the correct signature (pid changes; `pgrep -x Dolphin`).

## End-to-end solo test (once the caller-entitlement blocker is cleared)
4 terminals. Game must be running **in a stage** (Delfino Plaza), not the title screen.
1. `sunshine/bsmso/mac-online/run_server.sh`  (wait for "listening … 27015")
2. `<entitled-python-or-helper> sunshine/bsmso/mac-online/macmem.py`  → prints comm-buffer addr (go/no-go)
3. `<entitled-python> sunshine/bsmso/mac-online/bridge.py --server 127.0.0.1 --name Kris`
4. `python3 sunshine/bsmso/mac-online/ghost_bot.py --server 127.0.0.1 --name Ghost`
Expected: a second Mario circles next to the player. That proves the whole pipeline solo.
For real online: point `--server` at the host IP; unique `--name` per player; 27015 TCP+UDP reachable.

## Other open items (not blocking the solo test)
- **120/240 fps bundle re-enable** on the patched ISO: currently the per-game `GMSE01.ini` `[Core]`
  was set to stock (EmulationSpeed=1.0, EnableCheats=False) for clean boot testing. To play at
  120/240, flip those back and confirm the fpspatch bundle + BSE's built-in 60fps toggle stays OFF
  (FPS_30). Use the `dolphin-gecko` skill for INI edits (Dolphin clobbers external edits on close);
  re-verify `$FOV NN [kris]` stays enabled after.
- **Despawn TODO:** `bridge.py` doesn't clear a remote slot on `PlayerLeft`, so a departed puppet
  freezes. Fine for solo (ghost keeps sending); fix for real play (wire a PlayerLeft callback in
  netclient → zero `RemoteSnapshots[slot].connected`).
- **Only player position/animation is bridged.** World events (shines/coins/story), model sync,
  voice, game-mode are speced in PROTOCOL.md §A.5/§B.2 but not yet implemented in the bridge.
- **No night HD ISO** exists on this machine: only day HD (`/Applications/gamecube/Super Mario
  Sunshine (USA) [HD portals].iso`) + pristine `.rvz`. Night variant was requested but never built.

## Artifact map (all under `sunshine/bsmso/` unless noted)
- `PROTOCOL.md` - byte-level protocol spec (load-bearing).
- `mac-online/` - the Python stack + `run_server.sh` + `README.md`.
- `bundle-server/` - extracted, runnable .NET server (runtimeconfig patched to rollForward → net10;
  `DOTNET_ROOT=/usr/local/Cellar/dotnet/10.0.101/libexec`).
- `bundle-launcher/` - extracted managed DLLs (`SMSO.*.dll`), source of the protocol RE.
- `decompiled/` - ilspycmd C# (needs `DOTNET_ROOT` set to run ilspycmd).
- `bundle_extract.py` - my .NET single-file bundle parser (sig prefix `8b1202b96a612038`, int64
  header-offset at sig−8).
- `doldiff.py`, `hook-addresses.txt` - hook-collision checker (result: zero collisions).
- `bse-release/` - BSE v4.0.0 release (source of main.dol/boot.bin/KuriboKernel.bin).
- `upstream/BSMSO_1.1/` - the original mod zip contents (read-only).
- `venv/` - python venv with pyisotools + capstone.
- Dolphin build: `dolphin/build/Binaries/Dolphin.app` (+ `dolphin-tool`).
- `get-task-allow.entitlements` - the minimal plist I first tried (DON'T use alone; see codesign note).

## Driving this with /architect
- Keep in your own context: the codesign/entitlement reasoning, the hook-collision decisions, and
  reviewing any memory-access code (it writes into the user's live game: review the write path).
- Delegate: the signed native helper (coder), any protocol extension (coder, spec in PROTOCOL.md),
  research on Apple-Silicon task_for_pid entitlement specifics (researcher) if the helper approach
  hits a wall. The user is at the machine, willing to run `codesign`/`sudo` commands themselves,
  but sudo is NOT passwordless. Hand them exact commands and ask for pasted output.
- Save durable findings to the `sunshine-bsmso-mac-integration` memory file as you go.
