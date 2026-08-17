# Turn-around run (skid U-turn) nearly impossible under the high-fps bundles (FIXED in fpspatch 2026-08-10, awaiting playtest)

**Symptom (user, 2026-08-10):** the running U-turn skid (flip the stick while
dashing) gets progressively harder under the high-fps bundles, with Mario arcing
around instead of planting the skid. User hypothesized a frame-counted
threshold needing G-scaling; that is NOT the mechanism.

## The mechanic (decomp `src/Player/MarioRun.cpp` + USA disasm)

- `TMario::running()` enters `MARIO_STATUS_TURN` (0x443) when the inlined
  `isRunningTurnning()` sees `|mIntendedYaw(+0x90) − mFaceAngle.y(+0x96)| >
  0x471C` (~100°) AND `mForwardVel(+0xB0) >= mTurnNeedSp` (param +0x1034,
  default 10.0). USA sites (found via the unique ±0x471C cmpwi pair):
  - **0x8025AF64** - running()'s entry check (`lha r3,0x96(r31)` …)
  - **0x8025A874** - turnning()'s cancel check (`!isRunningTurnning() → RUN`)
- `mIntendedYaw = matan(stick) + cameraYaw(gpCamera+0x258)`, computed in
  `TMario::checkController` (USA ~0x80251dbc region, the tank-controls site).
- `doRunning()` converges face → intendedYaw by `IConverge(diff,0,rotSp,rotSp)`
  per tick; `rotSp = 0x200..0x400` scaled by mForwardVel (≈4.9°/tick at dash
  speed ≈ **675°/s** at 120 Hz ticks).
- ALL of it is CUE_MOVE work: 120 Hz at every G including stock (30fps × 4
  substeps). The check itself is rate-invariant.

## Root cause: stick freshness, not frame counting

Stock reads the pad once per rendered frame (30 Hz); all 4 substeps reuse the
sample, so a physical stick flip lands as one big stale jump, and the 100° gap is
guaranteed. Under the bundle the pad is read on every substep frame (~120 Hz):
the intendedYaw target sweeps smoothly through the player's real thumb roll and
the 675°/s yaw pursuit tracks THROUGH the flip. Numerically the trigger window
shrinks from ~130 ms (stock quantization) to ~110 ms of stick-roll time; only
near-instant, perfectly center-crossed flicks still trip it. Center-crossing
flicks keep working because the deadzone makes the target flip discontinuously;
rim-rolls (how most thumbs flip) are the broken case.

## Ruled out

- Frame-counter/threshold scaling (user's hypothesis): no counter exists in the
  turn path; `mStatusTimer > 0xF0` in running() gates BRAKE, not TURN.
- Per-rendered-frame state clearing (the NPC-talk pattern): `changePlayerStatus`
  has no debounce; nothing per-frame touches the turn predicate.
- `makeHistory` counters (unk538/unk53B @+0x538): armed flag never consumed.
- WALK_END blips from neutral samples: walkEnd returns to RUN next active tick
  and the flip then triggers immediately (discontinuous case works).

## The fix: `fpspatch.py turnaround_fix()` (default-on with the substep retune)

Run running()'s threshold compare against **mFaceAngle.y from 4 sim ticks ago**
(= the exact 33 ms staleness stock sampling gave the check), leaving steering
fully fresh. C2 @0x8025AF64; ring of 4 face halfwords in low arena
0x80001724 (0x1720 lastCtr, 0x172C owner) indexed by gpMarDirector+0x5C & 3.
- 4 is a CONSTANT at every G (sim ticks pinned 120 Hz, Poink-40 reasoning).
- Reseeds to vanilla on tick gaps (run-start after WAIT: no stale-face false
  skids) and on owner change (TEMario in Shadow-Mario chases: both actors
  degrade to vanilla rather than cross-contaminate).
- Self-gates on framerate global 0x804167B8 != 0.5f → inert without the bundle,
  one code valid at every rate. Clobbers r0/r4/r12/cr0 (all dead at hook).
- turnning()'s cancel check @0x8025A874 deliberately NOT hooked: face is frozen
  during TURN, delayed == current, stock cancel semantics preserved.
- No false positives for ≤100° deflections: delayed face trails ≤ 4·rotSp
  (~20°) only during convergence, 0 at rest.

Standalone A/B code: `research/codes/turnaround-fix-v1.txt`. Emitted into all
`bare*.txt` bundles; `--check` errors if the substep retune ships without it.

## If playtest says it's still not enough

Escalation knobs, in order: (1) delay 6 ticks instead of 4 (50 ms window,
beyond stock but forgiving); (2) also OR-in a windowed intendedYaw delta
(|yaw(t) − yaw(t−4)| > 0x471C) to catch flicks during camera swings; (3) hook
the turnning() cancel too if turns visibly start then abort. A live logger in
the popolog.py pattern (sample mStatus/mIntendedYaw/mFaceAngle/mForwardVel per
tick, find why diff never crossed 0x471C) settles any dispute. TMario is found
via gpMarioPos 0x8040E10C (hoverlog.py has the locator).
