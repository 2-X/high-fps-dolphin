# Heat-haze shimmer pulsates 4x fast under fpspatch — diagnosed, fix candidate v1 (2026-08-11)

User report: heat mirage "more active / pulsates faster than it should" at high fps,
plus a worry the FOV mod offsets it. Verdict: **real, 4x fast at EVERY patched G**
(constant, not G-scaled); **the FOV mod is NOT the cause** of the world-shimmer look.

## Mechanism

`TShimmer` (decomp `sms-decomp/src/Map/Shimmer.cpp`) is the fullscreen indirect-warp
actor (screen-texture reprojection). Its warp scroll is a BTK advanced on every
CUE_MOVE by a private `J3DFrameCtrl` at `this+0x58` — rate pinned 1.0 by
`J3DFrameCtrl::init` in `load()`, never touched again, **never scaled through
SMSGetAnmFrameRate()**. Family-B raw-rate class: the substep retune pins the MOVE
pass at 120 Hz at every G (stock 30 Hz) → 4x fast. Not coverable by fpspatch's
`ANMRATE_SITES` (those hook rate *stores*; here no store exists — init's 1.0 is the
only writer), so it needs its own hook.

## USA (GMSE01) addresses (pattern-verified against main.dol)

- `TShimmer::perform` = **0x8019F83C** (size 0x288, same as PAL 0x801980C4;
  identified among the 9 callers of the effect-mtx fn by the 9600.0f
  `mPosition.set(0,0,9600)` constant at `-0x4148(r2)` — with r2 = 0x80416BA0,
  NOT fovcallers.py's stale 0x80416B80)
- MOVE block: lwz r4,0x58(r29) @0x8019F88C · setFrame stfs @0x8019F898 ·
  **hook site lwz r3,0x58(r29) @0x8019F89C** · bl J3DFrameCtrl::update
  (0x802E1730, corroborated by [[sunshine-fruitsboat-pacing]]) @0x8019F8A0
- `SMS_GetLightPerspectiveForEffectMtx` (USA) entry = **0x8022BA74** (size 0x6C,
  contains the FOV hook's lfs @0x8022BA98); 9 callers incl. shimmer, telesa (Boo),
  namekuri (slug), BathWaterManager, NpcParts

## Fix candidate — `codes/shimmer-pace-v1.txt` (untested in-game as of writing)

C2 at 0x8019F89C: re-exec the lwz (r3 = frame ctrl), then if framerate global
(0x804167B8, `-0x3E8(r2)`) != 0.5f store **0.25f into ctrl->mRate (+0xC)** each
MOVE tick (idempotent, survives scene-reload re-init; self-disables at stock).
120 Hz x 0.25 = stock 30 units/s, fractional frames interpolated by the BTK.
Clobbers f0/f13/r12/cr0, all verified dead at the site.

If confirmed in-game, fold into fpspatch.py as a constant (G-independent) block
next to the ANMRATE family — same "pinned 120 Hz" reasoning, docstring bullet
belongs under the rate-INDEPENDENT list.

## FOV-mod interaction (the "offset" half of the report)

Not guilty for world shimmer: the unified $FOV hook substitutes the same fovy for
the `SMS_GetLightPerspectiveForEffectMtx` caller (whitelist at C_MTXPerspective
entry), and aspect comes from the same `gpCamera->getAspect()` on both the render
and effect paths (widescreen included) → reprojection stays aligned. The one real
offset is the **portal-preview pass** (renders ~50° while the hook forces the
override) — pre-existing, documented in [[sunshine-fov-mod]]. A wider FOV also
simply shows more shimmering ground per frame, which can read as "more active",
but the pacing bug above is the dominant effect.
