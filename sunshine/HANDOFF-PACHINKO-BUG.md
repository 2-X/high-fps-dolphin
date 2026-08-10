# HANDOFF — Pachinko / Chip-Shine red-coin FLUDD "suction" bug at 120fps

**Status: DIAGNOSIS ONLY. Not yet reproduced under instrumentation. No fix landed.**

## Symptom (user report, 2026-08-07)

Delfino Plaza secret shine — the pachinko/plinko-board level accessed by jumping off
the boat and entering under the bridge. Coin blocks (green/red/blue) sit between
`PachinkoKugi` peg columns on a slanted floor.

At 120fps the **top-left red coin is nearly unreachable**:

- Approaching from above with **FLUDD hover**, Mario gets **pulled toward the middle**.
- If you hold hover past the green coin, you get "sucked into the blue coin at the top
  middle" — user has to release hover with perfect timing to bank left.
- User believes this doesn't happen at stock 30fps ("the collisions being more
  frequent makes it seem like it's pulling me into the middle").

## Why this is puzzling under the current framework

Per [[sunshine-highfps-bug-surface]] and [[sunshine-fpspatch-generator]], **CUE_MOVE is
substep-pinned at 120Hz at every display rate** (stock 30fps: 4 substeps/frame · 30 =
120Hz; 60fps: 2·60; 120fps: 1·120). Mario's `playerControl()` — and therefore
`rocketing()` @ [MarioJump.cpp:923](../code/sms/src/Player/MarioJump.cpp:923) with its
hover spring, forward-vel accel, and brake — runs under CUE_MOVE and should tick at
the **same 120Hz** at stock and at hack. So the naive "rate-dependent brake/accel"
theory does **not** explain any 30fps↔120fps delta in hover behavior.

If the delta is real, the bug is either
(a) something violating the "sim at 120Hz always" invariant in this specific state, or
(b) something that runs per **render** frame by design (particles, spray push, coin/peg
    anim updates, FLUDD splash reaction), or
(c) something driven by input-poll rate (120Hz sample vs 30Hz sample of the analog
    stick), or
(d) a spawn/count effect (e.g., splash effects at pegs push Mario when there are 4× as
    many per second).

## Level / actor pointers (USA-relative unless noted)

- Pegs: **`MapObjPachinkoNail`** (BMD `PachinkoKugi.bmd`, collision id `PachinkoKugi`,
  type 2), registered in [MapObjInit.cpp:10322-10352](../code/sms/src/MoveBG/MapObjInit.cpp:10322).
  Static collision mesh — no per-tick actor logic on the peg itself.
- Coin blocks: standard `TCoinRed` / `TCoinBlue` items ([Item.cpp:348](../code/sms/src/MoveBG/Item.cpp:348),
  [Item.cpp:366](../code/sms/src/MoveBG/Item.cpp:366)).
- Shine name is `ChipShine` ([MapObjInit.cpp:10513](../code/sms/src/MoveBG/MapObjInit.cpp:10513)).
- Stage name is unknown from grep so far — likely `chip` / `casino_ex` variant.
  Confirm from a live save before instrumenting.

## Suspect code paths (in priority order)

### 1. FLUDD hover control loop — `TMario::rocketing()`  [MarioJump.cpp:923-993](../code/sms/src/Player/MarioJump.cpp:923)

The lateral-drift-inducing lines:
- `mForwardVel += mag * cos(angleDiff) * mDivingParams.mAccelControl.get()` (line 958,
  the "wide-angle" branch — the branch that fires when the stick and face are within
  ±0x1555 of each other, i.e., you're aiming roughly forward).
- `mSlideVelX = mForwardVel * sin(mFaceAngle.y)` / `mSlideVelZ = mForwardVel * cos(...)`
  (lines 982-985).
- `mVel.y = (unk314 - mPosition.y) * mHoverParams.mAccelRate.get()` (spring, line 989).
- `mForwardVel *= mHoverParams.mBrake.get()` (line 990).

If ANY of these run per-render-frame instead of per-substep, they'll accumulate 4×
per second at 120fps. **Verify:** breakpoint `TMario::rocketing` and confirm it's
called from `playerControl` → CUE_MOVE at 120Hz *only*. If it's ever entered from
CUE_CALC_ANIM or the draw path, that's the bug.

### 2. FLUDD spray push-force on Mario

The hover nozzle sprays water downward. If the spray applies a **recoil / reaction
push** to Mario per-emitter-tick, and the emitter fires per render frame, hover-lift
would be 4× stronger at 120fps — which would over-brake the fall and let the slanted
floor + peg deflection dominate.

Look at `TWaterGun::perform(CUE_MOVE)` and `perform(CUE_CALC_ANIM)` — the CUE_MOVE
path is fine; CUE_CALC_ANIM is not (it runs at display rate for animation).
Files: [WaterGun.cpp](../code/sms/src/Player/WaterGun.cpp),
[SplashManager.cpp](../code/sms/src/Player/SplashManager.cpp).

### 3. Splash particles at peg contact

`TSplashManager` (or the spray emitter) spawns particles when water hits geometry.
Peg contacts × frames-per-sec = 4× splash-per-second at 120fps. If any splash particle
imparts collision force on Mario (unlikely for splash, but worth ruling out), that's
the "suction". Check the emitter rate gate — the existing `_rate_gate` in `fpspatch.py`
handles the *one* known emitter site, but there may be a FLUDD-specific one.

### 4. Input polling latency

`mInput`, `mIntendedMag`, `mIntendedYaw` are read once per Mario tick. If the stick
sample is refreshed at 30Hz but the sim reads at 120Hz, three of every four ticks see
identical input — should be neutral, but the timing of "hold vs release" edges shifts.
Probably not the cause here, but rule out.

## Anti-hypotheses (do not chase without evidence)

- **"Peg reflect impulse is applied 4× per second."** PachinkoNail is static collision
  and reflection is via `mWallPlane` in `MarioPhysics.cpp`. That runs under CUE_MOVE at
  substep-pinned 120Hz. Rate-invariant.
- **"Mario's brake/accel constants."** Same reason — CUE_MOVE-driven, invariant.
- **"Anim-rate."** [[sunshine-highfps-bug-surface]] shows anmrate is a family-B animation
  bug set already covered by `fpspatch.py`'s `anmrate()`. Would affect animation speed,
  not physics drift. Not this bug.

## Diagnostic plan

1. **Confirm the 30fps↔120fps delta first.** In this build (`fpspatch 60`? or stock
   `main.dol`?) do the exact same approach with the exact same stick input and see if
   Mario ends up in a different place. If the delta is <1 block width, we may be
   chasing analog-stick noise, not a bug.
2. **Freeze the stick, freeze the world.** Put Mario mid-air over the pachinko board
   with `mFreezeTimer` set, activate hover, release stick to neutral, unfreeze. Does
   he still drift toward center? If yes, the bug is in hover physics alone (path 1 or
   2). If no, it's input-driven (path 4) or peg-interaction (path 3).
3. **Log `TMario::rocketing` call rate.** One line in the function that prints via
   `OSReport` or a scratch counter at a known address (like the timer-fix uses
   `0x800016E0`). Count calls/sec at 30fps and at 120fps. If they differ, path 1 is the
   bug. If both are 120/sec, path 1 is invariant and the drift comes from elsewhere.
4. **Kill FLUDD spray push.** Temporarily NOP the CUE_MOVE branch in
   `TWaterGun::perform` (or comment it in a source build) and see if hover still drifts.
5. **The `starkill.py`/`starprobe.py` pattern applies here.** Use `gcmem.py` (Mac now
   supports live memory read per [[sunshine-mac-memtool-ported]]) to sample Mario's
   `mVel.x`, `mVel.z`, `mForwardVel` per frame during a hover attempt and diff between
   stock and hack. Any per-tick delta > 0 is the bug source.

## Save/setup

- Save file needed: a save that has entered this shine's stage (name TBC — likely
  `chip` or `casino_ex`; check `saves/` and `dolphin-config` for existing setup).
- Run the hover approach from a fixed spawn (top of the slide, above the top-left
  red-coin block).
- Compare **stock `main.dol`** (30fps) against **current fpspatch-generalize branch**
  at 120fps.

## Instrumentation

**`research/scripts/hoverlog.py`** — live TMario state sampler. Auto-locates the
TMario instance by matching gpMarioPos (`0x8040E10C`) against every candidate
pointer in MEM1, then verifies via mForwardVel + mWaterGun sanity. Samples
mPosition, mVel, mForwardVel, mSlideVelX/Z, mFaceAngle.y, mIntendedYaw/Mag,
mStatus, and mCurrentNozzle at a configurable wall-clock rate.

```
cd sunshine/research/scripts
sudo -E SMS_DOL=../main.dol ../venv/bin/python hoverlog.py 60 20 --only-hover \
    > hoverlog-current.txt
```

Run the top-left-red-coin approach under hover twice — once with the enabled
`$180fps v12`, once with stock (no high-fps code active). If per-tick `dv` /
`dp` in the hover state differ meaningfully, the physics ARE tick-rate-varying
and the "sim pinned at 120Hz" invariant is broken in this state. If they
match, drift is coming from something outside `rocketing()` (splash push,
particle collision, input polling edges, or something in `TWaterGun::perform`
running under CUE_CALC_ANIM).

## Sim rate — the actual enabled code

Currently enabled in `dolphin-config/GameSettings/GMSE01.ini` is **`$180fps v12`**
(not $120fps). The "sim pinned at 120 Hz" argument still holds: at G=3,
direct() accumulates 10 tokens per call and each substep costs 15, so every 3
direct() calls yield 2 substeps → 180 · 2/3 = 120 Hz sim. So the anti-hypothesis
in this doc holds for 180fps too. When comparing against stock, compare against
stock **30fps native**, not against $120fps.

## Not yet done

- Reproduce with `hoverlog.py` running.
- Identify the exact stage name for this level (grep `saves/` and level enum).
- Compare stock 30fps trace to $180fps trace.
- Propose a Gecko patch based on which suspect path (1–4) shows divergence.

Related: [[sunshine-highfps-bug-surface]], [[sunshine-fpspatch-generator]],
[[sunshine-simrate-mechanism]], [[sunshine-mac-memtool-ported]].
