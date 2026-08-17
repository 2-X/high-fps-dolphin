# HANDOFF-MAC: return migration PC → MacBook (2026-08-04)

**Read this first on the Mac.** It routes into every other doc. Goal on the Mac:
run the current state of the project at **120fps** (the Mac's confirmed CPU ceiling),
attempt 180 once for the record (expected to fail, see §4), then **continue the
Poink/balloon-pig bug (HANDOFF-POINK.md)** at 120.

Everything needed is in this repo **except two large files** (§1 step 0). The
Windows PC state is frozen as of this commit: save, input configs, Gecko INI,
Dolphin patch, and all research docs are current as of 2026-08-04 ~03:35 (all five
active sessions wrote their conclusions into the repo before stopping; nothing
lives only in chat history).

---

## 1. Mac setup, in order

**Step 0: files that don't travel in git:**

- The game: `/Applications/gamecube/Super Mario Sunshine (USA).rvz` - already on the Mac.
- The **HD-portals ISO** (AI-3x M-portal previews + heap DOL patch baked in). Either
  copy `C:\Users\krisb\kris-documents\games\dolphin\Super Mario Sunshine (USA) [HD portals].iso`
  (1.5 GB) off the PC, **or rebuild it locally**: the shipped THP is committed at
  `research/thp-assets/EX128x144_ai3x.thp`; inject it into a fresh ISO with
  `research/scripts/thp/isopatch.py` (see `research/memory/sunshine-portal-preview-upscale.md`
  for the exact recipe; remember the heap fix must be a **DOL patch in the ISO**, not
  just the Gecko, because 04-writes race boot constructors).
- Savestates do NOT travel (build-version-locked; also they restore stale Gecko lists,
  trap #5 in §6). The `.gci` memcard save is the portable truth.

**Step 1: patched Dolphin build (REQUIRED for correct audio):**

```
git clone https://github.com/dolphin-emu/dolphin
cd dolphin && git checkout b6d8bc299ee7d03496d624b2e6b9a18d70522435
git apply <repo>/sunshine/dolphin-patches/high-fps-dolphin.patch
# normal macOS build (cmake) → build/Binaries/Dolphin.app
```

The audio tempo patch reads `EmulationSpeed` at runtime; **it is NOT hardcoded to
2x** (README §4 says otherwise; that line is stale, HANDOFF-PC §6 + the patch source
win). The same build is correct at 120 (speed 2.0) and 180 (3.0). The frame-interp
code in the patch is env-gated (`FRAME_INTERP`), default off; ignore it.

**Step 2: Dolphin user folder** (`~/Library/Application Support/Dolphin/`):

| From repo | To |
|---|---|
| `saves/01-GMSE-super_mario_sunshine.gci` (latest, PC 2026-08-04 02:10) | `GC/USA/Card A/` |
| `saves/SRAM.raw` | `GC/` |
| `dolphin-config/GameSettings/GMSE01.ini` - **all Gecko codes** | `GameSettings/` |
| `dolphin-config/mac-originals/GCPadNew.ini`, `GCKeyNew.ini` | `Config/` |
| `dolphin-config/mac-originals/Profiles/GCPad/*.ini` | `Config/Profiles/GCPad/` |
| `dolphin-config/Dolphin.ini`, `GFX.ini`, `Hotkeys.ini` (Mac-era originals) | `Config/` - then apply §1 step 3 deltas |
| `dolphin-config/FreeLookController.ini` | `Config/` (needed for the camera-recapture thread) |
| `dolphin-config/GraphicMods/GMSE01.json` | `Config/GraphicMods/` |
| `textures/` zip → `Load/Textures/GMS/` | optional; PC currently runs HiresTextures **off** |

**Input configs: which version is which:**
- `dolphin-config/mac-originals/` = the Mac bindings with `Quartz/…` device names;
  **use these on the Mac**, they'll bind immediately.
- `dolphin-config/` root + `Profiles/` = the current **PC** versions (WGInput/DInput
  device names). Same bindings except **two deliberate PC-era changes** to carry over
  by hand if you like them: keyboard **Z is now `C` (was `Tab` on the Mac)**, and the
  Mac-only mouse-buttons 6/7 as stick modifiers were dropped.
- Master profile: `Current Mac Setup (Elite+KBM dual).ini`. Load it, re-pick devices
  if the controller enumerates differently, bindings carry.

**Step 3: settings that must be set deliberately (don't trust stale copies):**

- `Config/Dolphin.ini [Core]`: `EmulationSpeed = 2.0` ← the committed Mac-era file
  says 0.5 and the PC file (`Dolphin.ini.pc`) says 3.0 - **both wrong for Mac@120**.
- `GameSettings/GMSE01.ini [Core]`: `EmulationSpeed = 2.0` too. ⚠️ The per-game value
  **overrides** Dolphin.ini and even the `-C` command-line flag (trap #3).
- `AudioPreservePitch = True`, `AudioBufferSize = 136` (default 80 underruns at level
  load → frozen-chord loop).
- GFX: `wideScreenHack = True`, `AspectRatio = 0` (Auto), pairs with the `$Widescreen`
  Gecko. PC also runs IR 4x; Mac was 3x; Mac GPU is not the bottleneck, either is fine.

**Step 4: Gecko codes for Mac@120.** In `GameSettings/GMSE01.ini` `[Gecko_Enabled]`:

```
$Widescreen
$120fps + TRUE-FIX v3 (respects story locks, no ForceOpen)
$GameHeap 7MB (HD portals)
```

- ⚠️ **Do NOT enable `$180fps v12` (or v9–v11) at 120.** The v9 input-latch gate's
  `acc<5` predicate is 180-specific; at G=2.0 it holds on **every** frame and would
  suppress the controller read entirely. The input/music fixes exist because of
  180's 2-of-3-frames substep pattern; **that pattern does not exist at 120**
  (120fps = exactly 1 substep/frame), so v12's extra machinery is unnecessary there.
- `$Widescreen wipe fix v2` - currently enabled on PC, confirmed **not** to fix the
  wipe bars, stretches all Hx wipes 4:3→16:9 (may ovalize circle wipes). Leave OFF.
- TRUE-FIX v3 carries **"pending one confirmation test"** status since July: boot
  Delfino, approach Bianco/Ricco portals. If they glow, **v3 is final**; if nothing
  lights, fall back to `$120fps + TRUE-FIX v2` and see README §2 for the
  "script window" alternative design.
- Editing codes: use the `dolphin-gecko` skill / `gecko/skill/gecko.py`; it already
  **defaults to the Mac INI path** and guards with `pgrep`. Dolphin rewrites the INI
  on quit; edit only while fully closed (trap #1).

---

## 2. The state of the world (what got fixed while on the PC)

Confirmed working at 180 on the PC, in `$180fps v12` (union bundle):

- **Input drops** - fixed (v9 latch gate), user-confirmed. 180-only bug.
- **BGM freeze/silence after transitions** - fixed (v12 tempo-proportion guard at
  `C231B8C8`), root-caused via live capture; final user confirmation still pending.
  180-only symptom; the guard itself is rate-agnostic and harmless anywhere.
- **HD M-portal previews** - SHIPPED & validated (AI-3x THP + 7MB heap). Rate-independent.
- **Widescreen** - `$Widescreen` gecko + widescreen hack, "beloved config".

Still open (full detail in the per-thread docs):

| Thread | Doc | Status | At 120 on Mac? |
|---|---|---|---|
| **Poink launch (THE active task)** | `HANDOFF-POINK.md` | blocked on one live capture | **yes - see §5** |
| Wipe bars don't reach screen edges | `HANDOFF-WIPE-BARS.md` | 2 fixes failed; top lead untested | yes - likely reproduces (predicted 4x off at 120 vs 6x at 180) |
| v13 rate-bug backlog (splash gravity rate², truncation stall, reciprocals…) | `HANDOFF-POINK.md` §v13 + poink memory doc | statically confirmed, unpatched | **yes - AnmFrameRate = 0.5 at 120, same as v12 forces** |
| TRUE-FIX v3 confirmation | `README.md` §2 | pending since July | yes - do it first (§1 step 4) |
| Windmills extra loud / positional SFX | `HANDOFF-INPUT-BUG.md` §13.3 | untouched | **no - 180-only, skip on Mac** |
| Camera recapture / Free Look previews | `research/camera-recapture/PLAN.md` | maps+shots done; RE + driver not started | yes, but needs the §5 memory-layer port first |
| 240/360 ladder | `HANDOFF-PC.md` | PC-only, 360 blocked at 5.17x even there | dead on Mac |
| VR diorama (Quest 3) | `research/memory/sunshine-vr-diorama-project.md` | plan only | orthogonal; Mac is a fine build host |

**Wipe-bars, the 5-minute experiment nobody ran:** reproduce the bars with the fps
code **disabled** (stock 30fps, widescreen on). `0x804167B8`, the "framerate global"
every fps code overwrites, is actually the game's pooled `0.5f` literal, and the
stage-banner drawer at `0x802A5B44` reads it as geometry. If the bars are clean at
stock, it was never a widescreen bug; the fix is per-site reader patches instead of
writing the global. This experiment is even easier on the Mac.

---

## 3. The 180 attempt on the Mac (do it once, for the record)

Expectation per `research/memory/sunshine-highfps-hardware-ceiling.md`: the Mac is
CPU/emulation-bound at **~2x**. Requesting 3x previously delivered ~1.5x effective
(90–180 fluctuating), which makes any game-logic observation at "180" **confounded
garbage**: Mario runs visibly fast/slow as the ratio wanders. The PC needed 3.0x
with 1.72x headroom to lock 179.65 VPS.

Protocol:
1. Enable `$180fps v12` **only** (disable the 120 bundle), `EmulationSpeed = 3.0`
   in BOTH INIs.
2. Boot Plaza, watch the VPS/speed overlay (ShowVPS/ShowSpeed are in the shipped GFX).
3. Lock at ~179–180 VPS / ~0.999x speed → congratulations, report back, everything in
   §2's "confirmed at 180" column now applies on the Mac.
4. Anything less (the expected outcome): revert to the §1 step 4 code set +
   `EmulationSpeed = 2.0` and stay at 120. Do not chase game bugs observed during an
   unstable-rate run. That trap already cost sessions (see hardware-ceiling doc).

---

## 4. Poink / balloon pigs at 120: how to continue (`HANDOFF-POINK.md` is the bible)

Short version: Bianco 5 Poinks (actor `TPopo`, fully RE'd, vtable `0x803BA558`) fly
~1/8 the needed distance at 180. Static analysis is exhausted; the flight math
*should* be tick-rate-invariant. Three live suspects remain (fill fraction low /
launch pitched down / early explosion), each with a ready fix shape. What's missing
is **one instrumented capture** with `research/scripts/popolog.py` (never ran against
gameplay; `popolog.txt` has only two "armed" lines).

**On the Mac there is a prerequisite: the memory layer is Windows-only.**
`gcmem.py` = kernel32 `OpenProcess`/`VirtualQueryEx`/`ReadProcessMemory`;
`popolog.py`/`bgmlog2.py`/`bgmstate.py` find the PID via PowerShell `Get-Process`.

**First Mac task: port `gcmem.py` to macOS** (this one port unblocks the entire
live-diagnosis half of the project, including the future camera flight driver):
- Reimplement `class Dolphin` over `task_for_pid` + `mach_vm_region` + `mach_vm_read`
  (ctypes against libsystem_kernel), keeping the same `read/f32/u32/base` interface so
  `popolog.py` et al. need only the PID-discovery line swapped (`pgrep -if dolphin`).
- `task_for_pid` needs privileges: run the scripts under `sudo` (simplest), or grant
  the debugger entitlement. SIP does not need to be disabled for a user-built,
  non-hardened Dolphin.app you compiled yourself in step 1.
- MEM1 discovery logic carries over: scan readable regions ≥ 24 MB, byte-match the
  `VIWaitForRetrace` prologue (`SIG_VA 0x8034F684`, bytes from `research/main.dol`,
  path via `SMS_DOL` env var).
- Alternative if `task_for_pid` fights back: Dolphin's built-in MemoryWatcher pipe or
  the `dolphin-memory-engine` project, but the home-grown port keeps the tooling
  self-contained.

**Then the capture, exactly as HANDOFF-POINK §6 says**, but at 120 it is the
*baseline control*, and it is diagnostic either way:
1. `python3 scripts/popolog.py` (self-arming; start before Dolphin).
2. Boot **120 bundle** (TRUE-FIX v3, speed 2.0), Bianco 5, latch a Poink, fill fully
   (hold R ~0.65s to the 2.0 clamp), aim at Petey, release. 2–3 launches.
3. Read `popolog.txt` against the §4 suspect table:
   - **Poinks fly true at 120** → the bug lives in the 180 substep architecture
     (v7/v8 zero-substep frames); a healthy 120 log is the reference trace to diff
     against a PC 180 log later. Continue enjoying Bianco 5 meanwhile.
   - **Poinks fall short at 120 too** → the bug is in the AnmFrameRate family
     (0.5 at 120 as well); suspect 2 (nozzle emit-matrix) leads; **fully fixable on
     the Mac**, fix shape in HANDOFF-POINK §4, ship it as `$120fps v13` and
     mirror it into the 180 bundle for the PC later.
4. While in there: the ★★★ splash-droplet gravity bug (`0x802670C8`, rate² → 16x-weak
   droplets) is also live at 120 and its fix is spec'd. Good second target for v13.

---

## 5. Knowledge-preservation map (where everything lives)

- **This repo is the single source of truth.** The Claude auto-memory on the PC is
  machine-local and does NOT travel; everything it knew has been written into these
  docs. A Mac Claude session should start from this file + `README.md`.
- `HANDOFF-POINK.md` - active task: complete TPopo RE, suspects, decision tree,
  capture procedure, v13 backlog.
- `HANDOFF-WIPE-BARS.md` - wipe engine map, failed fixes, pooled-constant lead.
- `HANDOFF-INPUT-BUG.md` - scheduler/substep mechanism, v9 input fix, test protocols.
- `HANDOFF-PC.md` - PC benchmark truths (Video-thread bottleneck, 5.17x ceiling);
  mostly moot on Mac but wins where it contradicts README (audio factor, ceiling notes).
- `research/memory/*.md` - knowledge base; `sunshine-portal-glow-bug.md` is the
  chronological root-cause history. Known stale bits: README §4 "audio written for 2x"
  (wrong), `sunshine-simrate-mechanism.md`'s sqrt-constant theory (obsolete, corrected
  in the portal doc), hardware-ceiling doc's "120 accidentally right" (corrected in
  HANDOFF-PC §S3.7).
- `research/codes/*.txt` - Gecko source for the whole 180 v-ladder + particle fix.
- `research/scripts/` - portable except `gcmem.py`/`popolog.py`/`bgmlog2.py`/
  `bgmstate.py`/`bench2.ps1` (Windows; see §4). `sms_dump.py` has a stale hardcoded
  path; set `SMS_DOL` env instead. Setup: `python3 -m venv venv && venv/bin/pip
  install capstone pillow`.
- `dolphin-config/mac-originals/` - Mac input configs; root = PC versions.
- `saves/` - portable memcard save (latest) + SRAM. Savestates = PC-build-locked junk
  on Mac.
- `research/thp-assets/EX128x144_ai3x.thp` - the shipped HD preview movie, for
  rebuilding the ISO on Mac.

Traps (verbatim from the project, all platform-independent, memorize):
1. Dolphin rewrites `GameSettings/GMSE01.ini` on quit; edit only while closed.
2. Every C2 Gecko block ends with a `00000000` pad word or the last instruction dies.
3. `EmulationSpeed` in the per-game INI **overrides** Dolphin.ini and `-C` flags.
4. Never write Dolphin INIs with a UTF-8 BOM; `[Core]` becomes unparseable.
5. Savestates restore the old Gecko list + patched instructions; fresh boot only.
6. `04` patches to boot-constructor values are racy; patch per-frame or in the DOL.
7. Verify hand-assembled words with capstone; it can't decode `fcmpo`/`fcmpu` - a
   "(pad)"-looking word may be a real instruction.

`120 IS HOME. GO POP THE PIGS. 🎈🐷`
