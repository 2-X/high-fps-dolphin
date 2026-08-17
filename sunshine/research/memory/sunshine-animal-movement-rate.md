# Birds fly at 1/4 speed under the fps patch: animal movement-rate misuse (FIXED 2026-08-10)

## Root cause

The Delfino kamome (`TAnimalBird`, managed by `TMewManager`) are **shared-anim
enemies**: `TEnemyManager::performShared` calls `moveObject()` on **every
substep with no final-frame gate** (`TAnimalBase::perform`'s
`graphics->unk0 & 2` gate is NOT the path kamome take). The substep clock is
120 Hz in stock and in every retuned G, so stock consumes
`speed * SMSGetAnmFrameRate()(=2.0)` at 120 Hz. The `ANMRATE_STUB` (returns
0.5) is correct for anim rates (calc_anim runs 4x more often) but wrong for
these substep-paced speeds → **birds fly/walk/turn at exactly 1/4 speed at
EVERY patched framerate** (120 included; nobody noticed until the higher-fps
sessions).

Measured (240fps, savestate bench, GMSE01):
- stock flying kamome: |v| 10.29/tick × 120 ticks/s ≈ **1235 units/s**
- patched (pre-fix): **295–300 units/s**; ground hop ~17 (accel is rate², 16x low)
- patched + fix: **1030–1210 units/s**, wing-flap playback still 59–60 anim-frames/s

A second, masking bug: the bird-nerve **duration helper @0x8000AB38**
(`N * 1/AnmFrameRate` → spine ticks) made every perch/flight phase **4x
longer** with the stub, so birds covered a stock-looking distance per leg at
quarter pace, and perched 4x longer.

## Fix (in fpspatch.py, ships in every bundle with `substep`)

- `ANIMAL_SPEED_SITES` - 13 movement-classified `bl SMSGetAnmFrameRate` sites in
  the Animal TU range (0x80005000–0x80013000): each C2-hooks bl+4 with
  `fadds f1,f1,f1 ×2` (f1 ×4 → stock 2.0). Rate² users (march accel/decel)
  reuse the scaled f1 → ×16 automatically. Sites: execWalk ×7, init turn
  speed, BirdWalkOnGround, doLanding ×2, doFlyToCurPathNode ×2.
- `animal_duration()` - C2 at the helper's `fdivs` (0x8000AB60), scales the
  quotient ×0.25 **gated on LR < 0x80013000** (the helper has two non-Animal
  callers, 0x80211984 / 0x8023F3D0, which are calc_anim-paced and keep stub
  semantics).

## Side finding fixed at the same time

The family-B raw anim-rate blocks divided by **2G**, correct only at G=2.
calc_anim frequency is **pinned at 120 Hz by the substep retune**, so the right
scale is the **constant R/4** at every G (was 1.5x slow at 180, 2x slow at
240). `_anmrate_block` now multiplies by 0.5² gated on framerate-global ≠ 0.5f
(self-disabling at stock). The `0x8013B/C` hooked cluster was identified as
**Bowser Jr. (limitkoopajr.prm)** via string refs; Petey (0x800955CC) is also
in the list; their anims were visibly slow at 180/240 before this.

## Suspected follow-up (unverified)

`TBoidLeader` (fish schools / flocks, `boid.cpp`) moves on `CUE_CALC_ANIM`
with **no rate scaling** → likely 4x FAST under the patch (calc_anim 120/s vs
stock 30/s). Not user-reported yet; verify with the same bench.

## Bench method (reusable)

- `dolphin-bin` portable build + `User/StateSaves/GMSE01.s02` boots into a
  Delfino scene: `Dolphin.exe -e <rvz> -s <state> -b`. Set EmulationSpeed in
  the game INI `[Core]`; the `-C Dolphin.Core.EmulationSpeed=` form
  intermittently kills the process at state-load.
- The state bakes the OLD codelist; this stock build does NOT re-apply INI
  gecko codes after a state load. Instead: find `00D0C0DE 00D0C0DE` in
  0x80001000–0x80003800 and **WriteProcessMemory the new list after it**
  (room ≈3.2 KB). Inject ONCE per boot; re-injecting while running moves C2
  caves under the executing game and hangs it.
- The state's substep accumulator (`gpMarDirector+0x54`, gpMarDirector ptr @
  0x8040E178) is deeply negative → the retune's skip-gate stalls the sim for
  ~15 s; poke it to 0.
- Bird instances: scan MEM1 for vtable `0x803ABE78`; mPosition +0x10,
  mLinearVelocity +0x94, MActor +0x74 → +0x28 → [0] → +4 = J3DFrameCtrl
  (rate +0xC, frame +0x10). Substep counter: gpMarDirector+0x5C.
- Measure `dist-while-flying / fly-time` (|v|>0.5), not raw dist/sec; birds
  perch, and the duty cycle poisoned an early measurement (looked like a 6x
  slowdown that wasn't real).
