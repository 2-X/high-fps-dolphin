# TASK: fix the Poink short-launch at 180fps (Bianco 5, Super Mario Sunshine USA/GMSE01)

**You are picking this up cold. Read this whole file before touching anything.**

**Goal:** in Bianco Hills episode 5 ("Petey Piranha Strikes Back"), the Poinks — the
floating pig-balloons that latch onto FLUDD's nozzle, inflate while you hold R, and fire
at sleeping Petey when you release — travel only **~1/8 of the distance needed to reach
Petey** under the 180fps mod (`$180fps v12`). At stock speed they work. The user wants to
finish this episode at 180fps.

**Status:** the actor is fully reverse-engineered (all USA addresses below, disasm-verified).
Static analysis is EXHAUSTED and says the flight should be tick-rate-invariant — so the
root cause is one of exactly three live-observable suspects (§5). A purpose-built live
logger (`research/scripts/popolog.py`) is written, smoke-tested, and ready; **the next
concrete action is one instrumented gameplay capture (§6)**. The user paused before the
capture happened. Do NOT re-derive §2–§4; verify claims only if a live capture contradicts them.

Secondary deliverable: a `$180fps v13` bundle folding in the Poink fix plus the four
unrelated-but-confirmed rate bugs found during the sweep (§8).

---

## 1. Thirty-second orientation

- Project root docs: `sunshine/README.md` (address map, Gecko anatomy),
  `sunshine/HANDOFF-INPUT-BUG.md` (the 180fps scheduler mechanism, input fix v9, music fix,
  §5 has build/ROM paths and the exact launch command — all still current).
- Installed config: **`$Widescreen` + `$180fps v12`** enabled in the patched build's
  `User/GameSettings/GMSE01.ini`, `EmulationSpeed = 3.0` in both INIs. Canonical code text:
  `research/codes/180v12.txt`.
- How 180fps works (condensed; full derivation in HANDOFF-INPUT-BUG §2/§11):
  - Render = 179.82 fps (retrace-locked, EmulationSpeed 3.0).
  - Simulation = **~119.88 Hz** via the `TMarDirector::direct` substep scheduler
    (0x80299838, budget 1800/frame ÷ drain 15) — same effective rate as stock's 600/5
    (stock renders 30fps × 4 substeps).
  - Perform-list cues (decomp `include/JSystem/JDrama/JDRViewObj.hpp`):
    **CUE_MOVE=0x1 fires EVERY substep** (~120Hz stock AND v12 — invariant);
    **CUE_CALC_ANIM=0x2 fires on the LAST substep of each rendered frame only**
    (29.97Hz stock → 119.88Hz v12 — 4× more often), which is exactly why v12 forces
    `SMSGetAnmFrameRate` (0x802A7BD8) to return 0.5 instead of stock 2.0 (anim units/s
    preserved: 30×2 = 120×0.5 = 60). Consumers that use AnmFrameRate as anything OTHER
    than an anim playback rate are the standing bug class (§8).
- Decomp: `C:\Users\krisb\code\sms-decomp` (doldecomp/sms, JP). `src/Enemy/popo.cpp` is an
  EMPTY stub — only `config/GMSJ01/symbols.txt` has TPopo symbols. JP↔USA link orders
  differ completely; **popo.cpp mapping: USA = JP − 0x211F84** (fingerprint-verified).
- Tools (`research/scripts/`, need `SMS_DOL` env → `research/main.dol`, use `python` not
  `python3`): `dump.py LO HI` (capstone disasm, annotates r2/r13 pools), `callers.py ADDR`,
  `xref.py ADDR`, `gcmem.py PID ADDR..` (live GC memory), **`popolog.py` (new, §6)**.

---

## 2. The actor: TPopo — identification is SETTLED, don't redo it

The Poink is class **`TPopo`**. Proof: the episode-5 scene archive `data/scene/bianco4.szs`
(episodes are 0-indexed; it contains `bosspakkun/` = Petey) has a `popo/` enemy dir and
**no** other balloon-fish assets; `TNervePopoPossessedNozzle` ("possessed nozzle") exists;
`/enemy/popo.prm` param names match the mechanic. Scene extraction recipe: DolphinTool
`extract -s data/scene/bianco4.szs`, then `research/scripts/thp/arc.py <szs> list`.

**Two documented dead ends — do not walk into them again:**
- `TTabePuku` ("プクプク(レール巡回)", rail-patrol nozzle-biting fish that DRAGS Mario;
  mDragLength param). Fully RE'd at USA 0x80136570–0x8013909c. Rate-clean. Not the Poink.
- `TTobiPuku`/`TMoePuku` + `*LaunchPad` classes (pad-launched flying fish, USA
  ~0x80099000–0x800a2400; the pads even have inflate-on-pad code at 0x8009be58 that looks
  tantalizingly Poink-like). Not in Bianco. Not the Poink.

### USA TPopo map (TU 0x800e5bb8–0x800ea640; all fingerprint- and disasm-verified)

| Function | USA addr | size |
|---|---|---|
| TNervePopoThrown::execute | 0x800e5c34 | 0x98 |
| TNervePopoWait::execute | 0x800e5ccc | 0xF0 |
| TNervePopoExplosion::execute | 0x800e5e18 | 0x204 |
| **TNervePopoFly::execute (launch impulse at entry)** | **0x800e6078** | 0x29C |
| TNervePopoAttack::execute | 0x800e63b8 | 0x198 |
| **TNervePopoPossessedNozzle::execute** | **0x800e65ac** | 0x1D0 |
| possessedIn | 0x800e6870 | 0x114 |
| explosion | 0x800e6984 | 0x14C |
| **flyBehavior (flight timer/deflate/explode)** | **0x800e6ad0** | 0x1C4 |
| bind | 0x800e6f94 | 0x3EC |
| calcRootMatrix | 0x800e7604 | 0x4C4 |
| attackToMario | 0x800e7ac8 | 0x2A8 |
| walkBehavior | 0x800e7d70 | 0x4E0 |
| getGravityY | 0x800e843c | 0x1B4 |
| **checkTrigger (fill + release detection)** | **0x800e8898** | 0x310 |
| perform | 0x800e8d6c | 0x54 |
| init | 0x800e8dc0 | 0x24C |
| PopoPossessedCallback (visual swell joint cb) | 0x800e9284 | 0x3B0 |
| TPopoManager::perform | 0x800e9940 | 0xC0 |
| TPopoSaveLoadParams ctor (param defaults) | 0x800e9bb4 | 0x300 |

- **TPopo vtable (vptr value in live objects) = 0x803BA558**
- Nerve singleton vtables (match `*(*(popo+0x8C)+0x14)→vt`): Thrown 0x803BA4F8,
  Wait 0x803BA508, Explosion 0x803BA518, **Fly 0x803BA528**, Attack 0x803BA538,
  PossessedNozzle 0x803BA548
- Actor fields: pos +0x10/14/18, liveflags +0x64 (bit0) and +0xF0 (bit 0x80 = "in flight,
  no hit yet"), spine +0x8C (→ +0x14 current nerve, +0x20 nerve timer), velocity
  +0xAC/B0/B4, **fill +0x198**, **flyTimer +0x19C**, full-latch +0x1CC, params obj +0x194,
  collision child +0x23C
- Params obj (+0x194) offsets / code defaults (bianco4 ships NO popo.prm → defaults apply):
  mSLReleaseSpeed **+0x3B4 = 10.0**, mSLFlyGravity +0x3C8 = **0.0**, mSLFlyLimitTime
  **+0x3DC = 300** (int), mSLWaterScaleMax **+0x404 = 2.0**, mSLPumpRate **+0x42C = 0.0001**,
  mSLLevelLimit **+0x440 = 1.2**, mSLScaleRate +0x454 = 0.99 (dead branch), thrown/move/
  attack gravities 0.5/0.1/0.1
- TPopo hit-actor type = **0x1000000D** (Mario side: `MarioReceiveMsg.cpp:520` — on
  HIT_MESSAGE_UNK5 sets `TWaterGun` flag that suppresses `emit()` → no water while latched)

---

## 3. The mechanic (disasm-verified — cite-able line addresses in the doc below)

Companion doc with the same content in memory-note form:
`research/memory/sunshine-poink-launch-bug.md`.

1. **Fill** (`checkTrigger`, called each spine tick from PossessedNozzle::execute at
   0x800e66d0): `r = analog R (0..255)` read via `gpMarioOriginal→+0x4FC→+0xB4`
   (processed R analog; decomp ref `MarioMove.cpp:1353`). If `r > 20`:
   `fill += r × mSLPumpRate` (full squeeze ≈ 0.0255/tick → ~78 ticks ≈ 0.65 s to cap 2.0);
   clamp to 2.0. Note: **water tank level is never read** (fills even when empty — matches
   the wiki). If `r < 20` (released) and (`+0x1CC` set or `fill > 1.2`): return TRUE →
   PossessedNozzle pushes the **Fly** nerve.
2. **Launch** (Fly::execute first tick, 0x800e60b8–0x800e6114):
   `dir = column 0 of the water-emit matrix` (`bl 0x802738c0` = get WaterGun,
   `bl 0x8026a2c0(…, 0)` = getEmitMtx(0) — same matrix the spray uses);
   `speed = mSLReleaseSpeed × fill / mSLWaterScaleMax` (= 6.0…10.0 units/tick);
   `vel(+0xAC..B4) = dir × speed`; `+0xF0 |= 0x80`. Yaw set from atan2(vel.x, vel.z).
3. **Flight** (`flyBehavior` per spine tick): `++flyTimer > 300` → Explosion nerve;
   `fill ×= 0.999` if > 1 (visual deflate only — speed is NOT re-read from fill);
   Fly::execute separately checks `+0xF0 bit 0x80` — if something CLEARED it (collision,
   via bind/TPopoCollision) → Explosion. `getGravityY` returns **0.0** during Fly →
   perfectly straight flight. Velocity integrated by `TLiveActor::moveObject`
   (decomp `src/Strategic/liveactor.cpp:277`) on CUE_MOVE.
4. The only two `SMSGetAnmFrameRate` calls in the whole TU (0x800e6680, 0x800e89ec) are
   `MActor::setFrameRate(...)` — anim playback only. **No** `SMSGetVSyncTimesPerSec` calls,
   **no** inline reads of the G global anywhere in the TU (a full-text scan found inline G
   reads NOWHERE in the binary — the three known readers are the only ones).

---

## 4. The puzzle — why static analysis says this can't happen (yet it does)

Fill, launch, flight timer, and movement ALL run on the spine/moveObject path = CUE_MOVE =
every substep = **~120Hz under both stock and v12**. Distance = speed × lifetime in ticks
— tick-count invariant. Every rate-scaled quantity checked (see §3.4). So the defect must
enter through one of the *inputs* to that invariant math. That's a closed list:

| # | Suspect | How it would produce ~1/8 distance | Discriminating live signature |
|---|---|---|---|
| 1 | **Fill fraction at release** | launch speed ∝ fill; fill ≈ 0.25 instead of 2.0 → flight covers ¼ the ground per tick (and dies at the same 300 ticks) | logger shows `fill` well below 2.0 at the `-> Fly` transition even though the user filled "fully" |
| 2 | **Launch direction pitched down** | gravity is 0, flight is a straight line along emit-mtx col0; if the nozzle pose at release points slightly into the ground, it impacts terrain at ~1/8 of the horizontal distance → collision-explosion | logger shows healthy `|v|` (~10) but `vel.y` clearly negative, flight ends by collision (`Fly -> Explosion` with `timer` ≪ 300) |
| 3 | **Early explosion** (collision flag 0x80 cleared by something else, or timer consumed faster than assumed) | flight terminates early regardless of speed/direction | `Fly -> Explosion` with small `end-timer` and short real duration; distance ≪ speed×300 |

Corresponding fix shapes (pick after the capture):
- Suspect 1 → instrument `checkTrigger`'s `r` next (is the processed R analog degraded by
  the v9 input gate or by pump-anim pulsing at 180?); fix likely a C2 at the fill-accum
  instruction (0x800e89ac–0x800e89c8) scaling pumpRate, or in the R-processing chain.
- Suspect 2 → the emit matrix is animation-posed; check nozzle pitch at release vs stock
  (log col0 of the mtx at launch); fix could be clamping vel.y ≥ 0 at Fly entry
  (C2 at 0x800e60e8..0x800e60f0 region) — cheap and behavior-safe for this actor.
- Suspect 3 → dump who clears +0xF0 bit 0x80 (bind 0x800e6f94 / TPopoCollision
  receiveMessage 0x800e9864) and gate it; or if it's the timer, C2 the compare at
  0x800e6b00 (`cmpw flyTimer, prm+0x3DC`).

A useful control: `$120fps + TRUE-FIX v3` with `EmulationSpeed = 2.0` in both INIs is the
known-good config (see HANDOFF-INPUT-BUG §5) — capturing one launch there gives the stock
baseline numbers (expect fill = 2.0, |v| = 10, straight flight ending by timer at 300 or
by hitting Petey).

---

## 5. What is already ruled out (do not redo)

- The TPopo TU has no frame-rate-scaled physics (full scan; §3.4).
- No inlined copies of `SMSGetAnmFrameRate`/`SMSGetVSyncTimesPerSec` exist anywhere in
  .text — the v12 getter patch covers 100% of AnmFrameRate consumers.
- None of the 14 `SMSGetVSyncTimesPerSec` callers feeds velocity/position (fresh
  classification of all 14: timers/fades/scheduler/anim-rate bakes only).
- All 66 AnmFrameRate call sites in the Player/Mario region (0x800E0000–0x80160000) are
  anim-rate setters — including TPopo's two.
- The sim substep rate is equivalent stock↔v12 (119.88Hz; HANDOFF-INPUT-BUG §5).
- `TTabePuku` / `TTobiPuku` / launch pads: wrong actors (§2).
- bianco4.szs contains no popo.prm — code defaults are live, so a "bad prm" theory is out.

---

## 6. Next action: the live capture (everything is ready)

1. Start the logger (self-arming — safe to start before Dolphin):
   ```
   cd C:\Users\krisb\code\high-fps-dolphin\sunshine\research
   python scripts\popolog.py
   ```
   It waits for Dolphin, finds MEM1 by code signature, scans for vptr 0x803BA558, then
   logs: params on first sight, every nerve transition with fill/timer/pos, launch velocity
   vector + |v| + distance-to-Mario, fill changes ≥0.02 during pumping, and on Fly-exit the
   real-seconds flown, distance in units, and end-of-flight timer value. Output: console +
   `research/scripts/popolog.txt` (appends; timestamped).
2. Have the user boot the patched build (command in HANDOFF-INPUT-BUG §5), enter Bianco 5,
   latch a Poink, fill fully, aim at Petey, release. 2–3 launches.
3. Read `popolog.txt`, match against the table in §4, implement the indicated fix as a C2
   added to a new `$180fps v13` bundle (= v12 + fix; see §8 for what else goes in v13).
4. Optional baseline: repeat once under `$120fps + TRUE-FIX v3` / EmulationSpeed 2.0.

Logger internals if it needs adjusting: TPopo field offsets in §2; it treats a freed vptr
as scene-unload and rescans; Mario position global = 0x8040E10C (`gpMarioPos`).

---

## 7. Traps (inherited from the project — they are all real)

1. **Dolphin rewrites `User/GameSettings/GMSE01.ini` from memory on quit** — edit only
   while Dolphin is fully closed, ideally via the `dolphin-gecko` skill
   (`python .claude/skills/dolphin-gecko/scripts/gecko.py`).
2. **Every C2 block must end with a `00000000` pad word** (handler overwrites the last word).
3. `EmulationSpeed` lives in BOTH `User/GameSettings/GMSE01.ini` and `User/Config/Dolphin.ini`.
4. Never write the INIs with PowerShell UTF-8 (BOM breaks Dolphin's parser) — use Python.
5. Verify every hand-assembled word with capstone (`scripts/verify.py` / dump.py round-trip).
6. `04` patches to constructor-time values are racy at boot — patch per-frame or hook.
7. Use `python` (Store `python3` is a stub). Set `SMS_DOL` for all scripts.

---

## 8. The v13 backlog — confirmed rate bugs from the full-binary sweep (user asked for these)

Independent of the Poink, fold these into `$180fps v13` (all statically confirmed, none
yet patched; details + instruction windows in `research/memory/sunshine-poink-launch-bug.md`
bottom section):

| Priority | Site | Bug | Fix shape |
|---|---|---|---|
| ★★★ | **0x802670C8** (fn 0x80267050, splash droplet system, `/mario/timg/splash.bti`) | droplet gravity = `−0.5 × AnmFrameRate²` → stock −2.0, v12 −0.125 (**16× weak**, droplets float). Consumer integrates `v+=g; p+=v` at 0x80266F20. | C2 at 0x802670D8 forcing the product to −2.0 (quadratic — getter patching can never fix both this and linear consumers). Value is baked at scene-construct time — verify per-scene construction before trusting a boot test. |
| ★★ | **0x80177DB4** | `(int)(counter × rate)` with rate 0.5 truncates to 0 → increment stalls; compared vs 360 (wait loop) | C2 rounding like the EmitterViewObj fix (+0.5 before fctiwz won't suffice at rate 0.5 with counter 1 → use max(x,1) shape) |
| ★★ | **0x80008064 / 0x80008098** (fn 0x80008024/0x80008F70) | two more `rate²` products feeding a per-tick approach step; sibling 0x800080C4/D8/0x800090B0 store `param × rate` to +0x144 consumed vs a hard 100.0 distance gate → follow behavior 4× slow | same shape as splash fix; identify the TU's owner first (single caller 0x8000A754) |
| ★ | 0x8000AB4C, 0x800F4B78, 0x80205F24, ~~0x801744D0~~, 0x802A8994/A8 | `1.0/rate` reciprocals → 4× too big under v12 | audit each consumer before patching — some may be anim-frame conversions that are already correct. 0x801744D0 (TSelectMenu stick-repeat cache) RESOLVED 2026-08-10 by the shine-select cadence gate (HANDOFF-INPUT-BUG session 8) — under the 120 Hz select tick the stubbed 0.5 rate is correct again |
| ★ | 0x801D690C/0x801D6998 | `rate × 0.25` threshold vs an unscaled 0.015/tick decay → gate trips at wrong time | site-local constant fix |
| ★ | 0x801727E4 (`getWipeCloseTime` = 30/vsync) | screen-wipe close time 6× short at 180 | only fix if wipes visibly misbehave; VSync-consumer class is otherwise cosmetic |
| ★★ | **TBossEelTooth** (Noki, Eely-Mouth) — USER-SIGHTED at 180 (2026-08-09, PC): pulled gold tooth floats + wiggles up/down ~30s (stock ~1/3 of that) while **vibrating** | duration = frame-counted release timer running G× long; vibration = per-render-frame bob against 2-of-3 sim stagger | JP `perform` @0x802E8B84 (`bosseel.cpp` is an unmatched stub — raw disasm needed; fingerprint USA, do NOT assume the popo −0x211F84 delta transfers). **First check whether this is the ★★ 0x80177DB4 truncation-stalled wait-vs-360 site above** — a barely-advancing wait counter is exactly a 30s wiggle |

Also known-broken (different subsystem, do not conflate): Bianco windmills EXTRA LOUD —
positional-SFX staleness class, see HANDOFF-INPUT-BUG §13.3. At 180 on the PC this class
is now general (2026-08-09): boat + Noki glow SFX persist with a sine-wave amplitude
wobble. Fix design: gate `MSound::mainLoop`'s `frameLoopDyna()` walk to sim cadence.

---

## 9. File inventory for this task

| File | What |
|---|---|
| `sunshine/HANDOFF-POINK.md` | this file |
| `research/memory/sunshine-poink-launch-bug.md` | same findings in memory-note form + full v13 bug windows |
| `research/scripts/popolog.py` | the live logger (ready; smoke-tested arming + attach loop) |
| `research/scripts/popolog.txt` | its output log (created on first run) |
| `research/codes/180v12.txt` | currently installed bundle — v13 = this + fixes |
| `sunshine/HANDOFF-INPUT-BUG.md` | scheduler/input/music context, build paths, launch cmd |
| `C:\Users\krisb\code\sms-decomp` | JP decomp; popo mapping USA = JP − 0x211F84 |

Good luck. The hard RE is done — one gameplay capture picks the fix.
