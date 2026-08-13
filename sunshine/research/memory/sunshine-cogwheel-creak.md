# Noki urn-lift rope-creak SE — cadence gate (v1, 2026-08-09)

**Symptom:** Noki Bay Ep.1 ("Uncork the Waterfall") urn-pulley lifts — spray
water into the pot, ride the plate up — play the rope-pull creak far too
frequently at high fps ("unnatural, bizarre"). Only the sound is wrong; lift
speed is fine.

**Actors (decomp `MapObjMare.hpp`, impl is an empty stub — all RE from the USA
dol):** `TCogwheel` (the wheel, "天秤"), `TCogwheelScale` (plate "天秤皿" / pot
"天秤ポット"). Sounds: `MSD_SE_OBJ_MR_TSUBO_PULL` 0x3060 (JAL registration name
"マーレー壷を支えるロープ" — *the rope supporting the Mare urn*) and
`MSD_SE_OBJ_MR_TSUBO_WATER` 0x3061 (pot drain).

**Root cause:** `TCogwheel::control` (USA 0x801da084) requests SE 0x3060 every
control() tick while |wheel speed @+0x138| > 0.01 (emit block 0x801da1d4–228);
`TCogwheelScale::control` (0x801da818) requests 0x3061 every tick while the pot
drains (block 0x801da84c–898). control() runs once per SUBSTEP via `movement()`
in `TMarDirector::direct()` — 120 Hz at every G, so the *request* rate is
invariant. JAudio (`JAISeEntry::storeBuffer` same-actor/same-id dedupe + the
per-frame processor) collapses the flood into ~one audible retrigger per
RENDERED frame → creak fires at 30/sec stock but FPS/sec hacked (4x at 120).

**Fix (in `fpspatch.py cogwheel_se_gate()`, `--no-cogwheel` to omit; reference
copy `research/codes/cogwheel-creak-gate-v1.txt`):** C2 at 0x801DA1E8 and
0x801DA860 gating both call sites to 1 substep in 4 on the director's substep
counter (gpMarDirector+0x5C, same counter as the particle parity gate). Divisor
is the CONSTANT 4 (= 120 Hz substeps / 30 Hz native), NOT a function of G —
same class as the Poink 40. Gated ticks bctr to the game's own SE-skip targets
(0x801DA22C pure epilogue / 0x801DA89C merge). Clobbers r12/ctr/cr0 only, all
dead at both hooks. Overwritten originals: C002DA10 (lfs f0,-0x25f0(r2)) and
806D9FBC (lwz r3,-0x6044(r13)), both dol-verified.

**Ear-test to confirm (pending):** ride the urn lift in Noki Ep.1 at 120fps —
creak cadence should match stock 30fps feel. If instead the creak sounds
*choppy or re-attacks* every ~130ms, the SE is a keep-alive loop that our gate
lets lapse between requests — then the fix direction flips: keep requesting
every substep but throttle only the JAudio *restart* (would need a hook inside
storeBuffer's stop+restart path instead).

**How found:** SE-id immediate scan of main.dol (`li rX,0x3060`) → only one
gameplay emitter pair; JAL registration table in decomp `MSoundSE.cpp:240`
names the rope. See [[sunshine-fpspatch-generator]], [[sunshine-highfps-bug-surface]].

## v2 (2026-08-10) — SUPERSEDED by the global SE frame-process gate

The user then reported the SAME too-fast behavior on FLUDD hover and Gooper
Blooper sounds. Tracing those (TWaterGun::emit → PO_HOVER/PO_WATER_HI/
PO_NORMAL_NOZZLE_IMI; bgtentacle.cpp:1404 → BS_GESO_TAKEN_HAND, requested
every CUE_MOVE tick while Mario holds the tentacle) forced reading the actual
JAudio state machine (decomp JAIGFrameSe.cpp / JAIEntrySe.cpp):

- `JAISeEntry::storeBuffer`: request while sound in state 5 → refresh (5→4,
  keep-alive, NO restart); a SECOND request before the next frame process
  (state already 4) → `it->stop(0)` + restart.
- `JAIBasic::sendPlayingSeCommand` (per rendered frame): resets 4→5, advances
  per-sound `unk14` counters (pitch evolution, e.g. HINO_SEED_LQ_LEV).
- `JAIBasic::checkNextFrameSe` (per rendered frame): releases continuous SEs
  still in state 5 (unrefreshed), starts pending sounds, `--unk2` one-shot
  lifetime countdown.

So the audible retrigger cadence for EVERY repeating SE = the frame-process
rate (30/sec stock, FPS/sec hacked) — not the request rate. Two consequences:

1. The v1 per-site request gate was WRONG: 1 request per 4 substeps starves
   the keep-alive window (released between requests) → fresh restart every
   other frame = 60/sec chop at 120fps. Removed before any ear test.
2. The correct fix is ONE pair of hooks gating the processor itself to
   1 rendered frame in FPS/30: `checkNextFrameSe` USA **0x80305204** and
   `sendPlayingSeCommand` USA **0x80305958** (both entries vtable-verified at
   0x803ac4dc/f0 + 0x803e2500/14; first insn mflr r0; early-blr skip; send
   hook owns scratch counter 0x800016E8, check hook tests counter+1 without
   storing since it runs first and is init-conditional). This normalizes the
   whole class — hover, spray, creak, tentacle — plus one-shot lifetimes and
   pitch counters, in 2 C2 blocks.

fpspatch: `se_frame_gate()` replaces `cogwheel_se_gate()`; --check enforces
divisor FPS/30, counter-store ownership, and REJECTS any resurrected per-site
gate at 0x801DA1E8/0x801DA860. Code: codes/se-frameprocess-30hz-gate-v1.txt.
