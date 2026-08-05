# Super Mario Sunshine — High-FPS Project (Mac → PC migration)

> **🍎 ON THE MACBOOK? Read [HANDOFF-MAC.md](HANDOFF-MAC.md) FIRST (2026-08-04).**
> It is the return-migration router: Mac setup, which Gecko bundle at 120fps
> (⚠️ NOT `$180fps v12` — its input gate breaks at 120), the one-shot 180 attempt
> protocol, and how to continue the Poink work at 120 (needs the gcmem.py macOS port).

> **▶ ACTIVE TASK: [HANDOFF-POINK.md](HANDOFF-POINK.md)** — 180fps plays well (input fixed
> v9, music fixed v12, both user-confirmed). Current bug: Bianco 5 Poinks fly ~1/8 the
> distance to Petey. Actor fully RE'd (TPopo); next step is one instrumented gameplay
> capture with `research/scripts/popolog.py`. That doc also carries the v13 backlog of
> confirmed frame-rate bugs (splash gravity rate², truncation stall, …).
>
> Previous task (done): [HANDOFF-INPUT-BUG.md](HANDOFF-INPUT-BUG.md) — dropped inputs at
> 180fps + music freeze; keep for the scheduler mechanism, build paths, and launch command.
> Remaining smaller issue tracked there: Bianco windmills extra loud (§13.3).

> **⚠️ Read [HANDOFF-PC.md](HANDOFF-PC.md) first (2026-08-02).** Dolphin is now installed
> and running on the PC. That session invalidated several assumptions in §6's roadmap below:
> the bottleneck is Dolphin's **Video thread** (command-bound), not the PPC JIT and not the
> GPU; graphics settings and emulated CPU overclock are both no-ops; and the framerate is
> **not paced at all**, which is a correctness bug the Mac only masked by being CPU-limited.
> Current state: 290–330 fps in Plaza on Vulkan.

**Goal:** Super Mario Sunshine (USA, GMSE01) at high framerates with correct speed,
working M portals, correct audio, and all effects. Achieved **120fps fully working**
on the Mac (CPU-bound ceiling ~2x/120fps there). **Next frontier: 360fps on the PC.**

**State at migration (2026-07-31):** `TRUE-FIX v2` confirmed working by hands-on play
(M portals light on approach + enterable at full 120fps, normal speed, particles fixed).
`TRUE-FIX v3` (story-lock-correct variant, drops ForceOpen) added and **pending one test**
— see "Current test status" below.

---

## 1. Quick start on the PC

Windows Dolphin user folder = `Documents\Dolphin Emulator\` (or the portable `User\` dir).
Copy:

| From this folder | To (Windows Dolphin) |
|---|---|
| `saves/01-GMSE-super_mario_sunshine.gci` | `GC\USA\Card A\` |
| `saves/SRAM.raw` | `GC\` |
| `dolphin-config/GameSettings/GMSE01.ini` | `GameSettings\` — **this contains ALL the Gecko codes** |
| `dolphin-config/GFX.ini`, `Dolphin.ini`, `Hotkeys.ini`, `GCPadNew.ini`, `GCKeyNew.ini` | `Config\` (review before overwriting — paths inside are Mac-specific; safest is to copy `GFX.ini` settings `HiresTextures = True`, `CacheHiresTextures = True` manually) |
| `dolphin-config/Profiles/GCPad/*.ini` | `Config\Profiles\GCPad\` |
| `textures/SMS 4K 2.0c (4K).zip` → extract inner `Load/Textures/GMS/` | `Load\Textures\GMS\` (PC can afford the 4K pack; 1080p zip also included) |
| `dolphin-patches/high-fps-dolphin.patch` | apply to Dolphin source & build — **required for correct audio**, see §4 |

- Controller: the profile **`Current Mac Setup (Elite+KBM dual).ini`** is the exact
  dual Xbox-Elite + keyboard/mouse binding used during development. Device names
  (`SDL/0/Xbox One Wireless Controller`, `Quartz/0/Keyboard & Mouse`) will differ on
  Windows — load the profile, then re-pick the Device and the bindings carry over.
  (`Quartz` = Mac keyboard backend; on Windows re-bind those to `DInput/XInput` devices.)
- The game itself: `Super Mario Sunshine (USA).rvz` lives at
  `/Applications/gamecube/Super Mario Sunshine (USA).rvz` on the Mac — transfer separately
  (not in git).
- Savestates (`saves/savestates/`) are **build-version-locked**; they probably won't load
  on a different Dolphin build. The `.gci` memcard save is the portable one and is all you need.

## 2. Which Gecko code to use (all are in `GameSettings/GMSE01.ini`)

Enable **exactly one** of the `120fps + …` bundles at a time (they all write the
framerate global and will fight).

- **`$120fps + TRUE-FIX v3 (respects story locks, no ForceOpen)`** ← intended final.
  120fps everywhere, normal speed, M portals glow on approach (~354u radius),
  locked portals stay goop-covered. **Pending one confirmation test** (see below).
- **`$120fps + TRUE-FIX v2 (proximity glow reimplemented, full speed)`** ← confirmed
  working, but its ForceOpen part **opens story-locked portals too** (sequence-break risk:
  the goop-covered Gelato M shows lit). Use only if v3 fails.
- **`$120fps + M AUTO v2 + FX (400u radius + whirl state-hold)`** ← the earlier benchmark:
  everything perfect except the game runs 4x within ~400u of a portal.
- `$120fps + HOLD Dpad-Left to enter M portals` ← the original manual workaround.
- Diagnostic/history codes (`PROBE *`, `Bisect-*`, `Diag-*`, `FIX R*`, `TEST *`) — keep for
  reference, don't enable.

### Current test status (the one open question)

v3 removes ForceOpen on the theory that the stage script actually *does* open the correct
gates at 120fps and only the glow input was broken. **Test:** boot Delfino with v3 only;
if Bianco/Ricco Ms light on approach → v3 is final. If nothing lights → re-add the
"script window" (design in `research/memory/sunshine-portal-glow-bug.md`, bottom sections):
C2 @0x801EB034, while gate closed and `gate->0xcc < 180`: increment 0xcc and write 0.5f to
0x804167B8 — gives the script a stock-timing window during scene fade-in, flags respected.

### Anatomy of the TRUE-FIX bundle (for building the 360 version)

```
044167B8 40000000   <- framerate global 0x804167B8 = 2.0 (120fps; 0.5=stock 30)
042FCB24 60000000   <- NOP one retrace-wait (frame pacing)
C20066EC 00000002   <- effect-loop fmuls hook (part of original mod)
C2C28028 EC2105B2
FEC00890 00000000
[FX]     3x C2 at 0x802887A8 / 0x80288D30 / 0x80288DEC:  f1 += 0.5 before fctiwz
         (fixes EmitterViewObj `for(i=(int)SMSGetAnmFrameRate();...)` truncating to 0 —
          restores ALL small particle effects; stock-safe: 2.0+0.5 still truncates to 2)
[GLOW]   C2 at 0x801EBA60 (inside TModelGate::perform, only reached when gate open):
         XZ dist^2(player, gate) < threshold -> glow(this+0xD0)=1.0, lit-timer 0xCA=0xC8
         else run original load (natural decay). Threshold built from pool floats:
         500^2*0.5 = 125000 (~354u). Pool: 500.0 @ -0x2234(r2), 0.5 @ -0x7fd8(r2),
         1.0 @ -0x2298(r2), 40000 @ -0x2270(r2). r2 = 0x80416BA0.
[v2 only] ForceOpen C2 at 0x801EB034: guarded call to startOpen (0x801EBFD4) — REMOVE for
         story-correctness (v3).
```

For **360fps**: framerate global value = fps/60 → `044167B8 40C00000` (6.0). EmulationSpeed
and the pacing NOP interplay needs re-derivation (see `research/memory/sunshine-simrate-mechanism.md`
and the untested `$180CO/$360CO co-scaled const` ladder codes in the ini — the 0x80414904
const may need co-scaling: 0.01 x value). The FX fix generalizes: at 360, AnmFrameRate =
60/360 = 0.1667 → +0.5 still yields (int)0.667 = 0 — **the FX hook must become
`f1 = max(f1, ~1.0)` or the +constant raised (e.g. +0.9) for 360**. The GLOW hook is
framerate-independent. All gate constants (rise/decay/timers) scale with fps — see the
"rise/decay clock mismatch" section of the portal memory doc before chasing new symptoms.

## 3. Key addresses (USA GMSE01) — hard-won, disasm-verified

- SDA bases: **r2 = 0x80416BA0, r13 = 0x804141C0** (from `__init_registers` @0x8000536C).
  An earlier wrong r2 caused a whole wrong root-cause theory; trust these.
- Framerate global: **0x804167B8** (stock 0.5 = 30fps/60; readers = the 3 fns below)
- `SMSGetVSyncTimesPerSec` = **0x802A7C48** ("reader3", 14 callers — enumerated & classified
  in the portal memory doc); `SMSGetAnmFrameRate` = **0x802A7BD8** ("reader2", 215 callers);
  reader1 = 0x802A5B44
- `TMarDirector::direct` vsyncRate line: caller ret **0x80299854** (`600/(int)vsync` substep
  budget — the 4x-speed lever, decomp `MarDirectorDirect.cpp:44`)
- **ModelGate.cpp TU: 0x801EAC64–0x801EC8C0** — perform **0x801EB014** (0xAA8),
  receiveMessage 0x801EBBDC, screenBlur 0x801EBD84, startOpen 0x801EBFD4, loadAfter 0x801EC048.
  Gate fields: 0x70 flags (bit0=open master switch, bit1=glow-rise enable), 0x71 destination,
  0x72 bone, 0x78 MActor, 0xC4 state, 0xC8/0xCA lit-timer seed/countdown (360), 0xD0 glow,
  0xD4 rise (0.1), 0xD8/0xDC decays (0.02/0.025)
- EmitterViewObj truncation sites: **0x802887A8, 0x80288D30, 0x80288DEC**
- Player/cam position vec for distance checks: `-0x60B4(r13)` = 0x8040E10C

## 4. Custom Dolphin build (REQUIRED for correct audio)

`dolphin-patches/high-fps-dolphin.patch` applies to upstream dolphin-emu at the commit in
`UPSTREAM_COMMIT.txt`. It contains:
- `SystemTimers.cpp` — the **audio DMA tempo patch** (120fps-correct audio; pair with
  `AudioPreservePitch = True`, already in the shipped configs). Stock Dolphin will have
  chipmunk/wrong-tempo audio with the fps hack. Details: `research/memory/sunshine-audio-fix.md`.
- `Present.cpp/.h`, `FramebufferShaderGen.*` — frame-interpolation experiments (Phase-2
  exploration; rejected on Mac for latency/quality but source kept — may be revisited at 360
  if the PC can't hold 360 logic Hz).

```
git clone https://github.com/dolphin-emu/dolphin
cd dolphin && git checkout <hash from UPSTREAM_COMMIT.txt>
git apply path/to/high-fps-dolphin.patch
# then normal Windows Dolphin build (Visual Studio)
```

~~At 360Hz the audio patch's tempo factor may need generalizing — it was written for 2x.~~
**Stale — the patch reads `Config::Get(Config::MAIN_EMULATION_SPEED)` at runtime and
generalizes to any speed (verified in source; HANDOFF-PC §6).**

## 5. Research toolkit (`research/`)

- `main.dol` — USA executable, extracted from the RVZ (`dolphin-tool extract`)
- `scripts/` — capstone-based disasm + Gecko-builder scripts. Setup:
  `python3 -m venv venv && venv/bin/pip install capstone`. Key helpers: robust
  function-start detection (naive `mflr;stw` prologue matching MERGES functions — cost us
  a wrong TU identification once), annotated r2/r13 pool dumps, C2 builders with
  per-word capstone verification (always verify: capstone can't decode fcmpo/fcmpu — treat
  a "(pad)"-looking word as suspect and hand-check).
- `memory/` — the full project knowledge base. **Read
  `sunshine-portal-glow-bug.md` first** — it is the chronological root-cause history
  (including the dead ends and why they were dead ends).

### Gecko gotchas that cost days (memorize these)

1. **Dolphin rewrites the user `GameSettings/GMSE01.ini` from memory on quit.** Edit only
   while Dolphin is fully closed. The helper `gecko/skill/gecko.py` enforces this
   (`add`/`remove`/`enable` + auto-backup).
2. **C2 codes: the code handler overwrites the LAST word of the block with its branch-back.**
   Every C2 block must end with a `00000000` pad word or your last instruction is silently
   destroyed (symptom: crash or mysterious no-op).
3. **Boot-time code runs before the first Gecko application** — `04` patches to constructors
   that run at boot are racy/void. Patch the stored value each frame (pointer-chase) instead.
4. Cave size is NOT a practical limit (~200+ lines fine); historical "overflow" failures
   were all gotcha #2.

## 6. The 360Hz roadmap

1. Port everything (this folder), verify 120fps parity on PC with `TRUE-FIX v3`.
2. Resolve the v3-vs-script question (§2) so the base is story-correct.
3. Bump to 240 (`044167B8 40800000` = 4.0) then 360 (`40C00000` = 6.0), EmulationSpeed to
   match, and re-test the known fragile systems in order:
   audio patch factor → FX truncation threshold (§2) → glow rise/decay balance →
   sub-step scheduler behavior (`600/(int)vsync` = 1.67 at 360 → **integer division hits 1**,
   watch for a new class of truncation bugs there — `600/360` truncates to 1, meaning
   `unk54` accumulates remainder differently; read `MarDirectorDirect.cpp` first).
4. The decomp (`doldecomp/sms`, JP) is the fastest root-cause tool — find the system in JP
   source, then locate the USA address by function-size fingerprinting (scripts show how).

`GO GET 360. 🌴`
