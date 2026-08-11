# Delfino canal boats (TFruitsBoat) — NOT fast under the fpspatch (assessed 2026-08-10)

User suspected the plaza gondolas/boats run fast at high fps. Verdict: **no — they cannot
run fast**; one of their two modes is exactly stock speed, the other is 4x SLOW (bird-bug
class). Code-level assessment only, no bench, no fix shipped.

**User closed it same session (2026-08-10): "boats are moving normal ish speed" and
"fish looked normal" in-game.** So: boat concern = false alarm; the TBoidLeader 4x-fast
finding below stands at code level but has NO user-visible complaint — don't ship a gate
for it unless someone actually sees fast shoals (plaza may simply not spawn boids where
the user looks).

## Identification

The canal boats are the fruit-transport boats **`TFruitsBoat` / `TFruitsBoatManager`**
(object names `FruitsBoat`/`B`/`C`/`D`, models `/scene/fruitsboat[b|c|d]`).
`sms-decomp/src/Enemy/fruitsboat.cpp` is an EMPTY STUB — everything below came from
disassembling the USA DOL (`sunshine/research/main.dol`) via the enemy factory string
table. Red herrings: `FerrisGondola` = Pinna ferris wheel (static TMapObjBase);
Ricco `riccoBoatL/S`/`riccoYacht*`/`riccoShip` = bob-in-place `MapObjFloat`, don't cruise.

## USA (GMSE01) addresses (pattern-verified, sizes match GMSJ01 symbols)

- Enemy factory 0x802AA718 (FruitsBoat block 0x802AA850)
- TFruitsBoat: ctor 0x800EC874, vtable 0x803BAB74, moveObject 0x800EB6BC,
  init 0x800EC150, load 0x800EC5F4, setBckTrack 0x800EC75C, calcRootMatrix 0x800EBEF4
- Nerves: BckTrace::execute ~0x800EAD38, GraphWander::execute ~0x800EAE98
- TFruitsBoatManager: ctor 0x800EB50C, vtable 0x803BAB20, load 0x800EB368
  (defaults: speed 4.0 → actor+0x140, turn 0.1 → +0x144, anim-rate 0.2 → param+0xE0)
- Framework: TLiveActor::moveObject 0x8021818C, J3DFrameCtrl::update 0x802E1730,
  TEnemyManager::perform 0x8021C5BC

## Pacing classification

Boats override `moveObject` but NOT `perform`; manager does NOT use shared MActors →
path is TEnemyManager::perform → TSpineEnemy::perform → TLiveActor::perform, which calls
moveObject on **every CUE_MOVE with no final-frame gate** = substep-paced, 120 Hz at
every G. Two placement-chosen movement modes:

1. **GraphWander (rail graph):** TGraphTracer advanced by raw `actor+0x140` (4.0) per
   substep, NO SMSGetAnmFrameRate; nerve sets mLinearVelocity = tracerPos − boatPos each
   tick (velocity re-applied inside moveObject 0x802181B0–0x8021820C). Raw units per
   pinned-120Hz substep → **stock speed at every G**.
2. **BckTrace (position baked in a BCK):** setBckTrack builds a private J3DFrameCtrl
   (actor+0x160), rate set at **0x800EC82C: bl SMSGetAnmFrameRate; fmuls; stfs →ctrl+0xC**
   (0.2 × AnmFrameRate), and the NERVE advances that ctrl on the substep clock →
   substep-paced ANMRATE_STUB consumer = **4x SLOW at every patched G** — same family as
   the kamome fix (`ANIMAL_SPEED_SITES`), opposite of "fast". Unfixed; bench if anyone
   reports sluggish boats. (Which mode dolpic placements use was not determined — no
   files/ extract on hand — but neither mode can be fast.)

Cosmetic body BCKs go through the normal MActor CALC_ANIM/stub path (correct); rocking/
tilt smoothing uses per-substep constants (correct).

## If "fast water traffic" is ever seen anyway

**TBoidLeader (fish schools) confirmed at source: `sms-decomp/src/Animal/boid.cpp:151-157`
runs updateGoal()/calcBoids() only under CUE_CALC_ANIM with no rate scaling → 4x fast at
EVERY patched G** (120 included). Shoals near the canals/harbor are the plausible "too
fast" sighting, not the boats. USA address not derived; JP perform = 0x80363D80 for
future pattern-matching.
