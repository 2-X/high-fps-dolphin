---
name: sunshine-poink-launch-bug
description: "Bianco 5 Poink (TPopo) flies ~1/8 distance at 180fps — full actor RE, USA addresses, static analysis says tick-invariant, live logger ready (popolog.py)"
metadata:
  type: project
---

# Poink short-launch bug at 180fps (v12) — investigation state (2026-08-04)

**Symptom (user):** In Bianco Hills ep5 (Petey fight), filled Poinks launch and travel
~1/8 the distance needed to hit Petey. Works at stock.

## Actor identification (settled — two wrong turns first)

- The Poink = **`TPopo`** (`src/Enemy/popo.cpp` in decomp — empty stub, symbols only).
  Proven by: bianco4.szs (ep5) contains `popo/` + `bosspakkun/` and NO puku dirs;
  `TNervePopoPossessedNozzle`; `/enemy/popo.prm` param names `mSL*`.
- **Wrong turn 1:** TTabePuku = "プクプク(レール巡回)" rail-patrol fish that bites the nozzle
  and drags Mario (mDragLength). Fully RE'd (USA TU 0x80136570–0x8013909c) — rate-clean.
- **Wrong turn 2:** TTobiPuku/TMoePuku + LaunchPads = pad-launched flying fish
  (USA ~0x80099000–0x800a2400, inflate fn 0x8009be58, pad release 0x8009bfd0) — not Bianco.

## USA TPopo map (JP − 0x211F84; fingerprint-verified)

TU 0x800e5bb8–0x800ea640. Key functions:
- `TNervePopoFly::execute` **0x800e6078** (launch impulse at entry, 0x800e60b8–0x800e6114)
- `TNervePopoPossessedNozzle::execute` **0x800e65ac** (calls checkTrigger @0x800e66d0)
- `TPopo::checkTrigger` **0x800e8898** (fill + release detection)
- `TPopo::flyBehavior` **0x800e6ad0** (flight timer + deflate + explode)
- `TPopo::getGravityY` 0x800e843c, `bind` 0x800e6f94, `perform` 0x800e8d6c,
  MgrPerform 0x800e9940, PossessedCallback 0x800e9284 (visual swell from fill)
- **TPopo vtable = 0x803BA558**. Nerve vtables (match via `*(spine+0x14)->vt`):
  Thrown 0x803BA4F8, Wait 0x803BA508, Explosion 0x803BA518, **Fly 0x803BA528**,
  Attack 0x803BA538, PossessedNozzle 0x803BA548.

## Mechanic (disasm-verified)

- Possessed: `checkTrigger` each spine tick: r = analog R (0..255) via mario→+0x4FC→+0xB4;
  if r>20: `fill(+0x198) += r × mSLPumpRate(prm+0x42C, 0.0001)`, clamp to
  `mSLWaterScaleMax(+0x404, 2.0)`. If r<20 (release) and (full-latch +0x1CC ||
  fill > mSLLevelLimit(+0x440, 1.2)) → fire (return 1 → Fly nerve).
- Launch (Fly entry): `vel(+0xAC..B4) = emitMtx-col0 × mSLReleaseSpeed(+0x3B4, 10.0) × fill/2.0`;
  emit mtx = water-spray direction (`0x802738c0` → `0x8026a2c0(…,0)`).
- Flight: `flyBehavior`: `++flyTimer(+0x19C) > mSLFlyLimitTime(prm+0x3DC, 300)` → Explosion;
  `fill ×= 0.999` (visual); explosion also when liveflag 0xF0 bit0x80 cleared (collision).
  `getGravityY` returns mSLFlyGravity = **0.0** in Fly → straight line.
- bianco4.szs has NO popo.prm → code defaults apply (from TPopoSaveLoadParams ctor 0x800e9bb4).

## Why static analysis says it SHOULDN'T break (the puzzle)

Everything (fill, launch, timer, movement) runs on the spine/moveObject path =
**CUE_MOVE (0x1)** which fires EVERY substep: ~120Hz at stock AND under v12
(1800/15 scheduler). Distance = speed×lifetime is tick-count-invariant.
CUE_CALC_ANIM (0x2) fires last-substep-only (30Hz stock → 119.88Hz v12), which is
why v12's AnmFrameRate=0.5 patch is correct for anims. The only two
SMSGetAnmFrameRate calls in the TPopo TU (0x800e6680, 0x800e89ec) are anim-rate-only.
No VSync calls, no inline G reads in the TU (and none exist anywhere in .text).

Remaining suspects, discriminable ONLY live:
1. fill fraction at release much lower than stock (analog-R path / pump pulsing)
2. launch direction (emit mtx col0) pitched down at release → ground impact ≈1/8 way
3. early explosion (collision flag 0x80 cleared) or flight timer consumed too fast
   by something not yet seen

## Next step

**`scripts/popolog.py`** (self-arming, modeled on bgmlog2): attaches to Dolphin,
scans MEM1 for vptr 0x803BA558, logs nerve transitions, fill, |v| at launch,
flight duration/distance at explosion, params. One Bianco-5 attempt under v12
pins which of the three suspects it is. Compare optionally against a 120fps
TRUE-FIX v3 run (known-good) or stock-speed run.

## Related genuine rate bugs found during the sweep (fix in v13 alongside)

- **0x802670C8**: splash droplet gravity = −0.5·AnmFrameRate² (consumed at 0x80266F20,
  `v+=g; p+=v`): stock −2.0, v12 −0.125 (16× weak — droplets float). Quadratic →
  needs site patch, not getter change. Constructor-baked: mind Gecko boot-race.
- **0x80177DB4**: `(int)(counter × rate)` truncates to 0 at rate 0.5 → wait-counter
  vs 360 may stall (same class as EmitterViewObj bug; NOT covered by v12 FX hooks).
- **0x80008064 / 0x80008098**: two more rate² products; 0x800080C4/D8/0x800090B0
  approach-speed ×rate (4× small at v12) vs hard 100.0 gate — camera/effect follow TU.
- Reciprocal sites (×4 too big at v12): 0x8000AB4C, 0x800F4B78, 0x80205F24,
  0x801744D0, 0x802A8994/A8. Threshold mismatch: 0x801D690C/0x801D6998.
- VSync callers (14) reclassified: all timers/fades/scheduler, no physics.
  getWipeCloseTime (0x801727E4) = 30/vsync → 6× short wipes at 180.
