# TASK: fix dropped inputs at 180fps (Super Mario Sunshine, USA/GMSE01)

> **STATUS UPDATE (session 4, 2026-08-04): the input fix is BUILT AND INSTALLED.
> See §11 at the bottom. `$180fps v9` is enabled in the patched build's INI,
> smoke-tested (no hang), and hook-verified in live memory. Awaiting user
> playtest. §§2–4 below are the original analysis; the pad chain they said was
> "not located yet" is now fully located (§11.1).**

**You are picking this up cold. Read this whole file before touching anything.**

**Goal:** the user wants to *play* Super Mario Sunshine at 180fps. 180fps already works:
correct speed, smooth, cutscenes fine. **One bug blocks playing: edge-triggered inputs are
dropped roughly half the time.** Jump is the worst (you die constantly). Other one-shot
actions are affected too. Analog stick movement is fine.

**Secondary (do the input bug first):** the audio is *partly* wrong at 180fps (see §10). It has
a real diagnosis and is probably the same root cause as the input bug, so fixing input may fix
it for free. Check §10 before assuming it's separate work.

Success = the user can play at 180fps without losing jumps.

**Confirmed working as of the last session:** 180fps at correct speed (v8 fixed the residual
10% slowness, user-confirmed), smooth gameplay, cutscenes normal with music and animation.

---

## 1. Thirty-second orientation

Dolphin emulates the GameCube. Gecko codes patch the game's PPC code in memory. This project
makes SMS run at high framerates by:

1. `044167B8 <float>` - the game's "framerate global" G (`fps/60`; stock 0.5 = 30fps, 3.0 = 180)
2. `042FCB24 60000000` - NOP one of two `VIWaitForRetrace` calls per frame (30 → 60 frames
   per *emulated* second)
3. Dolphin's `EmulationSpeed = N` runs the whole console N times faster than real time


The render loop is **retrace-locked**, so:

```
real fps = 59.94 x N        <- hard ceiling, cannot be exceeded
```

At N=3 you get a rock-solid 179.82 fps. That part is done and verified; don't re-derive it.

---

## 2. The bug: mechanism (this is understood, don't re-investigate)

**SMS simulates at a fixed 120 Hz internally.** The scheduler is in `TMarDirector::direct`
(**0x80299838**):

```
8029985c: li   r3, 0x258            ; 600
8029986c: divw r25, r3, r0          ; budget = 600 / (int)(60G)     per frame
80299938: acc = director->0x54 ; acc += budget
  8029994c LOOP HEAD: if (flags@0x4c & 0x4000) -> PRE-work @80299c28
  80299958   substep body   <-- ONE SIMULATION STEP = 1/120 s
  80299974   acc -= 5
  80299980   if (acc < 5) flags |= 0x4000       ; "last substep this frame"
  80299bf4   if !(flags & 0x4000) -> 80299d08 (clears 0x6000) -> b 8029994c
  80299c00 POST-work -> 80299c24: b 80299d24 -> return
```

Stock 30fps → 4 substeps/frame. 120fps → exactly 1. **180fps needs 2/3 of a substep per
frame**, but the loop originally always ran **at least one**, so the sim ran at 180 Hz
instead of 120 → the game ran 1.5x too fast.

**The installed fix (`v8`) gates that loop** so a frame can run *zero* substeps. Result:
correct speed at 180fps. But now **the simulation only runs on 2 of every 3 rendered frames**,
while the per-frame PRE-work and POST-work still run on all 3.

**That is the cause of the input bug.** Jump is edge-detected (`pressed = now & ~prev`). The
pad latch appears to advance every frame, but the code that *consumes* the trigger only runs
on simulation frames. A press that lands on a skipped frame gets latched away unread.

This explains every observed detail: only edge-triggered actions break, analog is immune, and
the loss rate (~1 in 3 frames skipped) matches "about half the time" in practice.

**The fix is to sample input in lockstep with the simulation**: don't advance the pad
latch on skipped frames.

### ★ The decisive evidence (use this as your A/B control)

The user found a case where input is **never** dropped:

| context | input | result |
|---|---|---|
| Talking to the NPC at the top of the Bianco Hills windmill | **B** | **always works** |
| Controlling Mario (dive) | **B** | drops ~half the time |

Same button, same controller, same frame. **This proves the pad latch and the trigger
computation are working correctly.** The hardware read happens every frame and the edge is
computed correctly. What differs is *who consumes it*:

- **Dialogue / NPC code runs in the per-frame path** → runs on all 3 frames → sees every press.
- **Mario's control code runs in the substep path** → runs on 2 of 3 frames → misses presses
  that land on a skipped frame.

So do **not** go looking for a broken pad driver. The read is fine. The problem is purely that
the latch advances 3 times per 2 simulation steps, so an edge can be created and destroyed
between two consecutive reads without any simulation frame ever observing it.

**Preferred fix: only advance the pad latch on simulation frames** (gate the pad read/update on
`acc >= 15`, the same condition the substep loop uses). Then `prev` and `now` step at 120 Hz in
lockstep with the sim, every edge survives to be consumed, and per-frame consumers like
dialogue still see input at 120 Hz, plenty responsive, and no risk of double-triggering.

*(Alternative if that's awkward: sticky trigger bits. OR each frame's `now & ~prev` into a
pending mask that is cleared only when a simulation frame consumes it. This preserves per-frame
consumers exactly, but risks double-firing dialogue, so prefer the gate.)*

**Test procedure:** the windmill NPC is your control. After any change, B on the NPC must still
work 100% of the time, and Mario's dive must go from ~50% to 100%. If the NPC regresses, you
gated something too broadly.

---

## 3. What is already ruled out (do not redo)

- `0x80298e80` - director **state-machine dispatcher** (13-entry jump table @`0x803DF05C`). Not input.
- `0x80360400` - **GX flush** (writes GX commands to the write-gather pipe at `0xCC008000`). Not input.
- The accumulator `director->0x54` is read/written by **only** the 5 instructions in the
  scheduler above (verified with `xref.py`). Nothing else depends on the 600/5 scale.
- The framerate global G is **not** the lever for gameplay speed, proven by a probe that set
  G=6.0 and changed nothing about movement (cutscenes did go slow-mo). Don't chase G.

---

## 4. Recommended approach

The pad read has **not** been located yet. Find it mechanically, not by opening functions at random.

**Route A: via the SI hardware registers (preferred).** The GameCube reads controllers
through the Serial Interface at `0xCC006400`. Find the code that touches SI / the PAD library,
then walk up to the per-frame `PADRead`-equivalent and whatever computes the trigger bits.
`callers.py` gives you `bl` xrefs; `xref.py` gives r2/r13-relative data xrefs.

**Route B: via live memory diffing.** `gcmem.py` reads GameCube RAM out of a running Dolphin.
Snapshot memory with a button held vs released, diff, and the pad state words fall out
immediately. Then `xref.py` whoever reads that address.

**Route C: the decomp.** `git clone https://github.com/doldecomp/sms` (JP, *matching* decomp).
Find `TMarioGamePad::read` / the trigger computation in source, then locate the USA address by
function-size fingerprinting. Addresses do NOT transfer directly (JP vs USA). Fingerprint.

Once found, gate it the same way the scheduler is gated: **only advance the pad latch when
`acc >= 15`** (the v8 threshold), so input is sampled at 120 Hz in lockstep with the sim.

**Plausible alternative if gating the read is awkward:** make the trigger bits *sticky* across
skipped frames: accumulate `now & ~prev` into a pending mask that is only cleared when a
simulation frame actually consumes it. This may be easier than moving the read.

---

## 5. Current state: exactly what is installed

Two Dolphin builds. **Use the patched one** (`dolphin-src`), which has the audio tempo fix:

| | path |
|---|---|
| **Patched build (use this)** | `C:\code\high-fps-dolphin\dolphin-src\Binary\x64\Dolphin.exe` |
| ~~Stock portable build~~ (GONE, do not use) | ~~`C:\code\high-fps-dolphin\dolphin-bin\Dolphin-x64\Dolphin.exe`~~ |
| ROM | `C:\Users\krisb\kris-documents\games\dolphin\Super Mario Sunshine (USA).rvz` |
| DOL for disasm | `sunshine\research\main.dol` |

**The ONLY build is the patched `dolphin-src` one (window title `Dolphin b6d8bc2`).** It is
NOT portable (no `portable.txt`, no `<build>\User\` dir), so the live user folder is
`%APPDATA%\Dolphin Emulator\` and the live game INI is
`C:\Users\krisb\AppData\Roaming\Dolphin Emulator\GameSettings\GMSE01.ini`.
Do NOT write to `dolphin-bin\...\User\`, `dolphin-src\Binary\x64\User\`, or a repo-root
`GameSettings\` - none of those are read by the running emulator.

Launch:

```bash
& "C:\code\high-fps-dolphin\dolphin-src\Binary\x64\Dolphin.exe" -e "C:\Users\krisb\kris-documents\games\dolphin\Super Mario Sunshine (USA).rvz"
```

**Enabled Gecko code: `$180fps v8 (v7 + substep granularity x3: 1800/15 = exact 119.88Hz)`**
with `EmulationSpeed = 3.0`. Code text is in `sunshine/research/codes/180v8.txt`. Its two
non-obvious parts:

```
; --- granularity x3 (600/5 truncates 3.333->3 and loses 10% at 180) ---
0429985C 38600708   ; numerator 600 -> 1800
04299974 3803FFF1   ; drain 5 -> 15
04299980 2C00000F   ; loop-continue compare 5 -> 15

; --- the zero-substep gate, hooks 0x80299958 (loop body entry) ---
C2299958 00000007
801A0054 2C00000F   ; lwz r0,0x54(r26) ; cmpwi r0,15      (acc vs drain)
40800024 A01A004C   ; bge ->normal     ; lhz r0,0x4c(r26)
60004000 B01A004C   ; ori 0x4000       ; sth  (so NEXT frame still runs PRE-work)
3BA00000 3D808029   ; li r29,0 (return value) ; lis r12,0x8029
618C9C00 7D8903A6   ; ori r12,0x9c00 (=0x80299c00 POST-work) ; mtctr
4E800420 3B9C0001   ; bctr ; addi r28,r28,1  <- ORIGINAL instruction, re-executed
60000000 00000000   ; nop ; PAD (required, see §7)
```

`1800/15` yields **exactly 119.88 Hz** at stock / 120 / 180 / 360. (240 is the odd one:
`1800/240` = 7 → 111.9 Hz; it would need a ×12 scale, 7200/60.)

**Known-good fallback:** `$120fps + TRUE-FIX v3` with `EmulationSpeed = 2.0` in **both** INIs
is fully correct (speed, audio, everything). Use it to A/B, and offer it to the user if you
end up stuck.

---

## 6. Tooling (already built, use it, don't rebuild it)

In `sunshine/research/scripts/`. All need `SMS_DOL` set:

```bash
export SMS_DOL="C:/Users/krisb/code/high-fps-dolphin/sunshine/research/main.dol"
```

| script | what it does |
|---|---|
| `dump.py LO HI` | disassemble a GC address range (capstone, annotates r2/r13 float pool) |
| `callers.py ADDR` | find every `bl` call site targeting ADDR |
| `xref.py ADDR` | find every r2/r13-relative load/store referencing ADDR |
| `findconst.py` | scan the SDA pool for a float value |
| `gcmem.py PID ADDR...` | **read GC memory from a live Dolphin process** |
| `bench2.ps1` | batch-mode benchmark harness (per-thread CPU + frame logs) |

`gcmem.py` locates MEM1 by matching the `VIWaitForRetrace` prologue from `main.dol`, then
translates `0x80xxxxxx` to host pointers. **Use it early.** The previous session wasted several
rounds inferring machine state from how the game felt; one memory read settled it.

Python 3.12 + capstone are installed. Use `python`, not `python3` (that's the Store stub).

---

## 7. Traps that have already cost real time

1. **Dolphin rewrites `User/GameSettings/GMSE01.ini` from memory when it quits.** Any edit made
   while Dolphin is running is silently reverted. **Always confirm Dolphin is closed before
   editing.** Use the helper: `python .claude/skills/dolphin-gecko/scripts/gecko.py` (there's a
   `dolphin-gecko` skill, invoke it).
2. **C2 code blocks MUST end with a `00000000` pad word.** The code handler overwrites the last
   word of the block with its branch-back. If your final word is a real instruction it is
   silently destroyed. Add a `60000000 00000000` line to make the count land right.
3. **`EmulationSpeed` lives in TWO files**: `User/GameSettings/GMSE01.ini` `[Core]` *and*
   `User/Config/Dolphin.ini`. **Set both.** A mismatch produced "movement *and* audio both
   1.5x fast" (emulator ran one value, audio patch read the other).
4. **Never write these INIs with PowerShell `Set-Content -Encoding UTF8`** - it adds a UTF-8
   BOM and Dolphin then fails to parse `[Core]` entirely. Use Python with `newline=""`.
5. **`User/StateSaves/GMSE01.s02` is poisoned.** It was captured during a 360fps session and
   **restores G=6.0, overriding whatever Gecko code is enabled** (confirmed by reading memory).
   Any speed conclusion from an `F2` run is invalid. Boot clean or make a fresh savestate.
6. **Don't benchmark while other games run.** Two sessions were wasted measuring while Palworld
   was open. Check first: `Get-Process | Where-Object {$_.CPU -gt 30}`.
7. **Verify every hand-assembled instruction with capstone before shipping it.** Every word in
   v7/v8 was verified this way. It caught nothing only because it was used consistently.

---

## 8. How to test

The user is the fastest oracle. They can tell in ten seconds of play whether jumps drop. But
**verify it doesn't hang first** (you're patching a per-frame scheduler; the failure mode is a
hang, not a wrong number):

```powershell
$p = Start-Process -FilePath "C:\code\high-fps-dolphin\dolphin-src\Binary\x64\Dolphin.exe" `
     -ArgumentList @("-e","`"<ROM>`"","-b") -PassThru
Start-Sleep -Seconds 40
(Get-Process -Id $p.Id -ErrorAction SilentlyContinue) -ne $null   # must be True
```

Frame logs land in `<build>\User\Logs\{render,vblank}_times.txt`, one interval in ms per line,
so `fps = 1000*N/sum`. They flush as they go. `render:vblank` should stay ~1:1 and VPS ~179.82.

A useful earlier lesson: when the fix jumped to the function's *return* instead of into the
POST-work, the symptom was constant black flashing plus stuck audio. **If you see black
frames, you've skipped per-frame work that must still run.**

---

## 9. Background

`sunshine/HANDOFF-PC.md` §"SESSION 3" has the full derivation of the scheduler mechanism and
the v6→v7→v8 ladder. `sunshine/README.md` has the address map, the Gecko code anatomy, and the
M-portal/particle history. `research/memory/` is the older knowledge base.

Key addresses (USA GMSE01, disasm-verified, trust these):

- SDA bases: **r2 = 0x80416BA0, r13 = 0x804141C0**
- Framerate global **0x804167B8**; readers `SMSGetAnmFrameRate` **0x802A7BD8** (= `1/G`) and
  `SMSGetVSyncTimesPerSec` **0x802A7C48** (= `60G`)
- `TMarDirector::direct` **0x80299838**; substep accumulator `director->0x54`; flags
  `director->0x4c` (bit `0x2000` = first substep, `0x4000` = last substep)
- `VIWaitForRetrace` **0x8034F684**; per-frame VI governor **0x802FC9A4**
- Player/cam position vec `-0x60B4(r13)` = **0x8040E10C**

Good luck. The hard part is done. The simulation now runs at the right rate. This is one
well-scoped bug between the user and playing at 180fps.

---

## 10. The audio symptoms (secondary, likely the SAME root cause)

Observed at 180fps under v8, reported by the user:

| symptom | detail |
|---|---|
| **Bianco Hills BGM** | **perfect** |
| **Mario + FLUDD sounds** | **perfect** |
| **Coin sounds** | **perfect** |
| **In-world object sounds** (enemies, level objects) | **pulsate / echo**, rhythmic amplitude wobble |
| **Delfino Plaza BGM** | **silent** |
| Cutscene music + audio | **normal** |

**Note the split carefully: it is not "audio is broken".** BGM, Mario, FLUDD and coins are all
clean. Only sounds belonging to **objects positioned in the world** are affected. Mario/FLUDD
sounds are effectively listener-local and coins are UI-ish; neither needs continuous 3D
parameter tracking. World-object sounds do (distance attenuation, panning, doppler), all
recomputed from the emitter's position.

Earlier, under v7 (sim at 107.9 Hz), *all* level BGM was silent; under v8 (sim at exactly
119.88 Hz) Bianco came back. **So the audio tracks the simulation rate.** That is the single
most important clue. Do not treat this as an unrelated audio bug.

### Why this is probably the input bug wearing a different hat

Under v8 the simulation runs on **2 of every 3** rendered frames, while per-frame PRE/POST work
runs on **all 3**. Anything that reads simulation state but updates per-frame now samples a
value that only changes 2 times out of 3: a 3-frame beat pattern (a 60 Hz cycle at 180fps).

- **Pulsating world-object SFX** is exactly what that produces, and the symptom split confirms
  it precisely. Positional sound parameters (volume, panning, distance attenuation, doppler)
  recomputed **every frame** from emitter positions that only move on **2 of 3** frames give a
  repeating 2-then-1 stagger → audible amplitude wobble at a 60 Hz beat. Sounds that don't
  track a world position (BGM, Mario, FLUDD, coins) are untouched, **which is exactly what
  the user observes.** This is the same bug as the input drop, one layer over: a per-frame
  consumer reading simulation state that updates at 2/3 the rate.
  The fix is the same shape: **update positional audio parameters in lockstep with the
  simulation** (gate on `acc >= 15`) instead of every frame.
- **Plaza silent while Bianco plays** fits too. Delfino Plaza uses **dynamic layered music**
  whose layer volumes crossfade based on where Mario is; Bianco's is comparatively static. If
  the crossfade interpolation is driven per-frame with a delta that assumes the simulation
  ran, the layers can converge to volume 0 → silence, while a static track is unaffected.
  **Test this cheaply:** if any other level with static music works and only the dynamically-
  layered areas are silent, that confirms it.

### Suggested order

1. Fix the input latch (§2–§4). **Both symptoms share one root cause:** a per-frame consumer
   reading state that now updates on only 2 of 3 frames. Input drops and object-sound pulsing
   are the same defect in two subsystems.
2. **Re-test audio immediately afterward.** If the pad fix works by gating on the accumulator,
   applying the same gate to the audio parameter update is likely a one-line variation, and
   both symptoms may resolve together.
3. Only if they persist, investigate the audio path separately. Note the emulator-side audio
   tempo patch (`SystemTimers.cpp`, scales the audio DMA period by `EmulationSpeed`) is
   **known-good**: it is what makes 120fps audio correct, and cutscene audio proves it works
   at N=3 too. Don't start by suspecting it.

### History worth knowing

The user originally said the missing music was fine and asked for it to be left alone. That was
when *all* level music was silent. Now that Bianco's music works and the SFX pulse, the audio is
worth fixing, but **input remains the priority**, because dropped jumps are what make the game
unplayable.

---

# ★ SESSION 4 (2026-08-04): input fix built + installed. Music bug scoped.

## 11.1 The pad chain: fully located (USA, disasm-verified)

Decomp (`C:\Users\krisb\code\sms-decomp`, doldecomp/sms, JP-matching) gave the
structure; fingerprinting gave the USA addresses:

```
TApplication::gameLoop  (~0x802a5f00..)          per RENDER frame:
  0x802a600c: bl 0x802a8054   TMarioGamePad::read()   <- THE LATCH ADVANCE
  0x802a6010-44: for 4 pads: updateMeaning() + onFlag(0x40)
  ...
  0x802a60ec: lwz r3,4(r31); ... vtable+0x64          mDirector->direct()
```

- `TMarioGamePad::read` = **0x802a8054** (calls JUTGamePad::read = 0x802c8b9c
  → PADRead; then reset-combo check). Static, no args.
- `TMarioGamePad::updateMeaning` = **0x802a80e0** (one big function to
  0x802a8978; computes `mEnabledFrameMeaning(+0xd4) = mMeaning(+0xd0) & ~prev`).
- Pad object: `mButton.mButton +0x18`, **`mTrigger +0x1c`, `mRelease +0x20`**,
  halfword meaning copies +0xdc/+0xde/+0xe0, flags +0xe2.
- `TApplication`: `mDirector +0x4`, `mAppState +0x8`, `mGamePads[4] +0x20`.
- **TMarDirector vtable = 0x803df0c8** (unique data ref to direct 0x80299838 at
  vtable+0x64 = 0x803df12c; CodeWarrior layout, two zero header words).
- KEY DESIGN PRECEDENT: `direct`'s extra-substep path (stock 30fps, substeps
  2..4) **zeroes each pad's mTrigger/mRelease then calls updateMeaning**
  (0x80299a6c-80299aa8) so an edge is consumed exactly once per frame. v9
  mirrors this exact pattern for zero-substep frames.

## 11.2 The fix: `$180fps v9` (installed & enabled)

`sunshine/research/codes/180v9.txt` = v8 + one C2 at **0x802a600c** (replaces
`bl TMarioGamePad::read`):

```
if (app->mDirector != 0
    && app->mDirector->vtable == 0x803df0c8      ; gameplay director only
    && director->0x54 < 5) {                     ; acc+budget(10) < drain(15)
    ; zero-substep frame: DON'T advance the pad latch;
    ; zero mTrigger/mRelease on all 4 pads (the game's own extra-substep
    ; pattern) so per-frame consumers (dialogue) can't double-fire
} else {
    call TMarioGamePad::read                      ; normal
}
; falls through to the updateMeaning loop either way
```

Predicate math: at G=3 budget = 1800/180 = 10; end-of-frame acc cycles
10,5,0; acc<5 exactly predicts the v8 gate's zero-substep frames.
**The `<5` threshold is 180-specific** (the bundle hard-sets G=3.0, so this is
consistent with v8's contract). Menus/title/movies use other director classes →
vtable check falls through to a normal read (verified live: title screen
director vtable = 0x803ad240, gate inactive).

All 29 words capstone-verified. Block ends `4E800421 00000000` (pad rule §7.2).

**Verified this session:** applied via `dolphin-gecko` skill helper (Dolphin
closed first), v8 unticked / v9 the only enabled code, `EmulationSpeed = 3.0`
in both INIs, game boots and runs 45s+ (no hang), and live memory shows both
hook sites (0x802a600c, 0x80299958) patched to cave branches.

## 11.3 What the user must test (10 seconds each)

1. **Mario dive/jump (B/A repeatedly)** - should go from ~50% to ~100%.
2. **Windmill NPC dialogue (B)** - must still advance exactly ONE box per
   press: no drops (would mean over-gating) and no double-advance (would mean
   the trigger-zeroing isn't sufficient).
3. If double-advance appears anywhere (dialogue, pause menu), the refinement is
   to also zero the meaning-edge fields +0xd4/+0xde on skip frames.

## 11.4 Music bug: new evidence (user, this session) + tooling

Symptoms now: **fresh boot into a level = BGM fine. ANY transition breaks it**:
load-save→Plaza = silent; return-from-level→Plaza = single sustained tone;
re-enter Bianco (ep3) = single sustained tone. So it is the BGM
**teardown/restart path on scene change**, not dynamic layering (Bianco's
static BGM breaks too, so the layered-crossfade theory in §10 is dead).
"Single tone" = sequencer got note-on then stopped advancing → suspect the
JASystem seq tick / stream-load state machine after a stop/start cycle, still
plausibly beating against the 2-of-3-frames sim pattern.

Located for live diagnosis (all USA, disasm-verified):
- `MSBgm::startBGM` = **0x80016978**; `MSBgm::stopBGM` = 0x800167ec (by-track
  variant; the id variant is nearby); `MSBgm::smBgmInTrack[3]` = **0x803E9C80**
  (MSBgm* per track; `MSBgm+0x14` = JAISound*); `smMainVolume` = 0x8040C1C0.
- `gpMSound` = [0x8040D05C]; `MSGBasic` (JAIBasic) = [0x8040D060];
  `JAIBasic::startSoundActor` = 0x80301e80; `JAISound::setVolume` = 0x8030a57c.
- **`scripts/bgmstate.py <pid>`** dumps the live BGM slots + JAISound words.
  Sanity-tested on the title screen (track[0] = id 0x80010012 playing).

**Next session procedure:** run `bgmstate.py` in the working state, then have
the user do one transition into the broken state and run it again. Empty slot →
startBGM never fired / failed (walk the scene-init caller). Live JAISound with
tone stuck → stall is inside JASystem track processing (follow the handle to
the TTrack and read its tempo words, updateTempo formula is in decomp
`JASTrack.cpp:588`). That one diff should cut the search space in half.

---

# ★ SESSION 5 (2026-08-04): INPUT FIX USER-CONFIRMED. Music is the only bug left.

**The user played with `$180fps v9` enabled (only code) and confirmed the input
bug is FIXED.** Task complete; do not touch the input path again unless a
regression is reported.

## 12.1 Opus 5 parallel-session findings (merged; trust these)

A parallel Opus 5 session independently analyzed the same bug. Corrections and
additions to keep:

- **Mario reads `mEnabledFrameMeaning` (+0xD4), not `mButton.mTrigger`**
  (`TMario::checkController`, decomp `MarioMove.cpp:1315`; A=0x80 jump,
  B=0x100 dive). v9 still works because skipping `TMarioGamePad::read()`
  freezes the JUT latch *and* the meaning latch derives from it; user-confirmed.
- **The instance `pad->mButton` is a per-frame copy of the static
  `JUTGamePad::mPadButton[4]` at 0x80404484** (CButton stride 0x30; statics:
  mPadStatus 0x80404454, mPadMStick 0x80404544, mPadSStick 0x80404584,
  derived statically, not live-verified). Patches to instance fields would be
  overwritten on the next read. v9 dodges this only because it skips the copy.
- `JUTGamePad::CButton::update` = 0x802C9240. `TMarDirector+0x18` is a
  **pointer** to the pad array, not inline. `mDisabledFrames` +0xE8.
- All three latches are invertible (rollback math in Opus's notes). Its
  rate-independent rollback variant (C2 at 0x80299958, 18 lines) is saved at
  `research/codes/180v9-rollback-opus.txt` - NOT installed; use only if v9
  needs replacing (e.g. for a future 240fps bundle where v9's `acc<5`
  prediction is wrong).
- `direct()` structure correction: the "PRE-work" branch is the **DRAW branch**
  (draws last frame's state, runs changeState), then substeps simulate. Flag
  0x4000 persists across calls.
- decomp file for direct: `src/System/MarDirectorDirect.cpp` (matching source).

## 12.2 Music bug: current state (the only remaining bug)

Symptoms after v9 (user, this session):
- Boot → save → **Plaza BGM works** (the earlier "blank on load" did not repro).
- Plaza → Bianco: **Bianco BGM silent**.
- Bianco → Plaza: **first note of the Plaza theme repeating on a loop**.

So: first scene OK, every subsequent scene transition broken. "First note
repeating" narrows it to either **retrigger** (something calls startBGM /
resets the seq every frame, Plaza has sound-change cubes and
MSStageDistFade logic pumped from `stageLoop`, which runs only on the last
substep now) or **stall** (seq starts, first event plays, sequencer never
advances past it and hits a loop point).

Transition path (decomp, read this session):
`TMarDirector::nextStateInitialize` case 9/12 (area exit): wipe 0.4s +
`gpMSound->fadeOutAllSound(SMSGetVSyncTimesPerSec()*0.4f)` (= **72 frames at
G=3**, fades every SE category + `MSBgm::setAllTracksVolume(0,72)`), then on
the new scene cases 2/3/4: `MSMainProc::startStageBGM` → `MSound::initSound`
(re-sets unkA8|=2, stops unk7C/unk80) → `MSBgm::startBGM(stageBgm)` →
`setVolume(0.75, 0, 8)`. Opus flagged the same `SMSGetVSyncTimesPerSec`
seconds→frames conversions as the suspect class: anything counted in "frames"
that actually ticks at the 120Hz sim rate (not the 180Hz render rate) runs
1.5x long at 180, e.g. a still-running 72-frame fade-to-zero on a track
handle that the new scene's BGM then reuses would silence it.

**Next step is LIVE, not static.** Run `scripts/bgmstate.py <pid> --watch 10`
(upgraded this session) samples the BGM slots + MSound flag block at 2Hz and
reports churn vs. freeze:
- slot empty → startBGM never fired/failed → walk changeState/nextStateInitialize
- handle static → sequencer stalled → follow JAISound → TTrack, read tempo
  words (decomp `JASTrack.cpp:588 updateTempo`, uses `Kernel::getDacRate`)
- handle/id churn → retrigger → find the caller (stageLoop / sound cubes /
  MSStageDistFade; `callers.py 0x80016978`)

Protocol: capture `--watch 10` in (a) working Plaza, (b) silent Bianco,
(c) first-note-loop Plaza, and diff. Addresses in §11.4.

---

# ★ SESSION 6 (2026-08-04): MUSIC FREEZE ROOT-CAUSED. v12 installed (merged lineages).

## 13.1 The music bug: captured and diagnosed

Deep logger (`scripts/bgmlog2.py`, follows JAISound → JAISeqParameter->unk0 →
`TrackMgr::sRootTrack` [ptr @ **0x8040E6C0**, count @ 0x8040E6C8] → TTrack)
captured broken BGM live. Signature of every broken track:

```
cursor frozen, wait-timer frozen, active=1, not paused, tempo VALID (80/120),
tick rate unk3B0 = 0.0000
```

The sequencer is configured but computes **zero ticks per audio frame** →
cursor never advances → notes already sent to the synth ring forever ("single
tone / first note looping"); if it froze before the first note-on you get
silence. It is a deadlock: with rate 0 the seq never reaches its next tempo
command, so nothing ever recomputes the rate.

`TTrack::updateTempo` = **0x8031b814** (USA): rate = timebase(+0x3BA) ×
tempo(+0x3B8) / gDacRate(32028.5 @ 0x8040CDF0, r13-0x73D0) × 80/60, then
**× outerParam->unk18 (tempo proportion) if outer switch 0x40 is set**
(outer ptr = track+0x304). Tempo was valid in every capture → the zero factor
is the outer proportion. The game never legitimately sets it to 0 (MSModBgm's
death-slowdown bottoms at 0.3, changeTempo min 1.0), so 0 = uninitialized /
raced parameter (JAI port-cmd path, JAISystemInterface: mFlags&0x80 →
setParam(0x40, mTrackTempo)).

**Fix (in v10/v12): C2 at 0x8031b8c8**, the `lfs f0, 0x18(r3)` that loads the
outer proportion; if it reads 0.0, substitute 1.0 (r2 pool: 0.0 @ -0x5E8, 1.0
@ -0x7FE8). Self-contained, race-agnostic, cannot affect legit tempo mods.

## 13.2 Version untangling (parallel Opus 5 session, coordinate via this file!)

Two sessions edited the same INI concurrently. Lineages:
- Fable: v9 (input gate, **user-confirmed fix**) → **v10** = v9 + BGM tempo guard
- Opus: its own "v10" → **v11** = base + Fable's v9 gate (adopted verbatim) +
  conditional FX hooks (C22887A8/C2288D30/C2288DEC, 6-line versions gated on
  -0x9FB8(r13)) + anim-rate patch (`042A7BD8 C0228028` + blr =
  SMSGetAnmFrameRate forced to 0.5, "anim rate 60Hz")

**Resolution: `180fps v12` = v11 + BGM tempo guard = union of everything.**
Enabled set now: `$Widescreen` + `$180fps v12` ONLY. v8/v9/v10/v11 remain in
[Gecko] unticked. Files: `research/codes/180v12.txt` (canonical), v11
deduplicated in the INI. If you are the parallel session: build on v12, don't
re-enable earlier versions, and note changes here.

## 13.3 User-reported status + remaining

- Input: fixed (v9 gate, in v12). Music: v9 already improved it ("works every
  other level and re-load into delfino"); remaining failures were the rate-0
  freeze (Plaza sometimes silent on first load). v12's guard targets exactly
  that. Awaiting user test.
- **NEW/remaining: Bianco windmills are EXTRA LOUD**, first confirmed instance
  of the §10 positional-SFX class (world-object volume params staled/raced by
  the 2-of-3 sim pattern; likely distance attenuation never applied → default
  full volume). Not yet investigated. Start at MSSetSound::frameLoopDyna /
  MSMarioPosVolume; same gating family as everything else.
- Logger `bgmlog2.py` is self-arming (waits for game boot, re-arms between
  sessions). Leave one running during any test.

---

# ★ SESSION 7 (2026-08-10): NPC talk-INITIATION fix (impossible at 360fps)

Symptom: B near an NPC would not open dialogue at 360fps AT ALL; flaky-feeling
at lower rates. This is NOT the v9 latch class; dialogue-ADVANCE was fine.

Root cause (decomp `MarDirectorEvent.cpp` + USA disasm, all verified):
- `TMarDirector::movement_game` (USA **0x8029A788**, runs once per SUBSTEP via
  the director's virtual `movement` 0x8029A4AC) starts a talk only if
  `(director+0x128 & 2) && (pad->mEnabledFrameMeaning & 0x800)`. It sets
  bit0 of +0x128 each tick a talkable NPC is near (0x8029A8F8), and sets pad
  flag 0x4 (+0xE2) which is what makes updateMeaning translate B → talk
  meaning 0x800 next frame (`MarioGamePad.cpp:131`).
- The tail of `changeState` (USA **0x802981EC**, runs once per RENDERED frame)
  promotes bit0→bit1 and clears; on frames where bit0 wasn't set it CLEARS bit1.
- Under the substep retune, skip frames run changeState but not movement_game:
  at G=6 (2 skips between substeps) bit1 is promoted then cleared before the
  next movement_game ever tests it → **talk initiation structurally impossible
  at 360**. At G=3 the first substep frame after each skip sees bit1 cleared →
  ~50% of initiation presses eaten.

Fix (in fpspatch, emitted with the substep retune; also in `--check`):
**`0429A908 540007FF`**: retarget the test `rlwinm. r0,r0,0,30,30` (bit1) to
bit0, which movement_game itself just set. Vanilla-equivalent at stock/G=2:
the 0x800 meaning can only exist if pad flag 0x4 was set at frame start, which
only an earlier movement_game tick does. The "NPC already near" debounce
survives via that path. Rate-independent, zero cave words.

Verified: only two real consumers of +0x128 exist (movement_game, changeState
tail; the 0x128(r1) hit at 0x802BCB80 is a stack slot). 120/180/360 bundles
regenerated `--check`-clean and reinstalled into the live INI
(`%APPDATA%\Dolphin Emulator\GameSettings\GMSE01.ini`).

---

# ★ SESSION 8 (2026-08-10): shine-select screen cadence fix (unusable at 360fps)

Symptom: the in-stage episode/shine select screen is completely unbounded by
the framerate: at 360fps one tap of left/right skips from episode 8 to 1
(repeat delay ~0.11s at ~30 steps/sec vs stock 0.33s at 10/sec).

Root cause (all USA addresses disasm-verified this session):
- The select screen runs under **TSelectDir** (vtable **0x803C0EF0**, ctor
  0x80177538) - a separate director. Its `direct()` (**0x80175EC4**) calls
  plain `JDrama::TDirector::direct()` (**0x802F7D28**, the `bl` at
  **0x80175FE8**), which fires CUE_MOVE|CUE_CALC_ANIM on the menu once per
  RENDERED frame. None of the TMarDirector gating (substep scheduler, v9 pad
  latch) applies: menu logic runs 30 Hz stock → 60G Hz under the bundle.
- Twice broken on top of that: `TSelectMenu::initData` (**0x8017449C**) caches
  `+0x14C = 1.0/SMSGetAnmFrameRate()` (**0x801744D0**, one of the §8-backlog
  "reciprocal" sites) and times its stick-repeat as `N * (+0x14C)` ticks; the
  v11 stub pins the rate at 0.5, so the cache reads 2.0 at every G instead of
  the 1/G the formula needs. Same for the pad's own repeat
  (`TMarioGamePad::reset`: delay 20/rate=40, interval 6/rate=12 ticks) with
  `read()` free-running at render rate on this director.
- Key addresses: TSelectMenu::perform = **0x80172C90** (MOVE body is a
  10-state jump table @0x803C0E7C), TSelectMenu ctor 0x801753D0, vtable
  0x803C0E58, rsetup 0x801761B0. String-pool trick for this TU: perform/ctor
  addrs were found via "<TSelectMenu>" @0x803884B8 referenced as pool base
  0x80388458 + 0x60 from rsetup (lis/addi pairs, NOT r13/r2-relative).

Fix (fpspatch `select_gate` + extended `input_latch`, emitted with the substep
retune, both enforced by `--check`): hold the whole select-screen tick to
**1 frame in ceil(G/2) = a 120 Hz cadence**, exactly what every 0.5-stub
constant is calibrated for, so the 40-tick repeat delay is 0.33s at 10
steps/sec, bit-exact stock timing, at every even G (G=3 rounds to 90 Hz, mild).
- **C2 @0x802F7DBC** (v2): inside the SHARED `JDrama::TDirector::direct`, at
  the MOVE-pass `bl TViewObj::testPerform` (0x802FCC94; `this` in r30, args
  r3=unk10/r4=3/r5=&graphics already set). Vptr-compares against TSelectDir
  (inert for logo/menu/movie directors), increments a low-arena frame counter
  (**0x800016E8**; 0x16E0/16E4 are Noki's, 0x16F0 camera) and skips ONLY the
  MOVE|CALC_ANIM testPerform on gated frames; the CUE_DRAW pass at 0x802F7DD0
  still runs every frame.
  On gated frames the call is NOT skipped; it goes out with **r4 = 2
  (CUE_CALC_ANIM only)**, and only CUE_MOVE is withheld.
  **Two traps, both shipped and user-sighted 2026-08-10, do not repeat:**
  1. v1 hooked TSelectDir::direct's own `bl TDirector::direct` (0x80175FE8)
     and skipped the WHOLE call, draw included. "Skipped frames re-present
     the old XFB" was WRONG: 2-in-3 presented frames carried no fresh render,
     which PWM-dimmed the 360 Hz panel to ~1/3 brightness ("reduced gamma?")
     and beat against XFB presentation as a black blink every 1–2 s.
  2. v2 skipped the whole MOVE|CALC_ANIM testPerform: the 3D shines flickered
     light/translucent at 2-in-3 duty. TSelectShineManager::perform
     (USA 0x80178158, vtable 0x803C0F98) enters its J3D shine models into the
     draw buffers on **CUE_CALC_ANIM** (sets model frame from shine+0x3C then
     calls two virtuals = calc + entry) while its CUE_DRAW branch draws the
     two J3DDrawBuffers (+0x50/+0x54) and then CLEARS them (frameInit x2 at
     the tail, `bl 0x802ef66c`). A draw with no same-frame entry draws no
     shines. CALC_ANIM passthrough is safe: the shine path re-applies the
     same +0x3C frame (idempotent), and TSelectMenu's non-MOVE path handles
     only CUE_DRAW, it ignores CALC_ANIM entirely.
  3. v3's CALC_ANIM passthrough surfaced a THIRD regression (user-sighted as
     "micro-flickering"): **TSelectGrad::perform** (USA 0x80175560, vtable
     0x803C0EC8) advances its background color-cycle ON CUE_CALC_ANIM: a RAW
     +/-2 per call on channel bytes +0x20/21/22 (state machine +0x10/14/18),
     family-B raw-rate class. At 240fps the gradient strobed 8x stock behind
     the shine panels. Fix: **select_grad_gate** (C2 @0x80175584, the beq
     after perform's cue&2 test) holds the ramp body to 1-in-2G frames
     (native 30 Hz) on the same select counter, read-only; both exits jump to
     the function's own join 0x80175728 so its draw branch is untouched.
     Emitted only alongside select_gate (at G=2 the counter never ticks and a
     frozen gate would freeze the ramp).
  Rule distilled: gate ONLY CUE_MOVE globally; draw AND draw-buffer entry
  (CALC_ANIM) must run every rendered frame; any RAW-rate advancer that
  rides CALC_ANIM (grad ramp) then needs its own native-cadence gate. Audit
  every CALC_ANIM consumer of a director before passthrough: the select
  screen's full set is TSelectMenu (ignores it), TSelectShineManager
  (idempotent frame-pin + entry), TSelectGrad (RAW advancer, the trap),
  TEmitterViewObj (MOVE-only).
- **input_latch TSelectDir case**: second vtable compare in the v9 block; pad
  reads gated to the SAME frames via the predicate `(ctr+1) % N`, predicted,
  not stored, because read() runs BEFORE direct() in gameLoop, and only the
  direct-gate increments. Trigger edges are therefore consumed by exactly one
  menu tick (same pending-edge mechanism as gameplay v9).
- At G=2 neither block is emitted (cadence already 120 Hz; indeed the
  select screen was always fine at 120fps); bare120.txt is byte-identical.

Follow-ups NOT done: title-screen/file-select (TMenuDir) and any other
TDirector-direct directors have the same class of bug; the counter +
per-vtable-case architecture extends to them if they ever annoy. The other
§8 reciprocal sites (0x8000AB4C, 0x800F4B78, 0x80205F24, 0x802A8994/A8)
remain unaudited; 0x801744D0 is RESOLVED for the select screen by cadence
(not patched; under a 120 Hz tick, 1/0.5 = 2.0 is the correct value again).
