# Decompose/recompose transition lag at 240/360fps — Hx_Test5's 80 EFB copies/frame

> **2026-08-11 PLAYTEST VERDICT: wipe5_opt's tile morph REJECTED — ids 5/6 now
> swap to Hx_Test4 by default at G≥3 (`wipe5_swap` in fpspatch.py).** The
> user's boot→plaza reveal showed wrong-scale scene chunks + big black slabs
> (two screenshots, two sessions). Verified via gcmem against the LIVE game:
> every wipe5 hook word, the full grab-cave body, f22 double, 128px strides,
> smooth count/divisor, and the id-5/6 timer bypass were all in RAM exactly as
> designed, and `$Widescreen wipe fix v2` (a real but independent copy-vs-draw
> misalignment — see below) was confirmed disabled at both its hook sites. So
> the artifact is inherent to how the 128px half-scale morph renders (per-tile
> anomalies remain unexplained: the swirl math is per-frame-uniform across
> tiles, yet the damage was non-uniform — suspect Dolphin's handling of the
> repeated same-address half-scale copies, or the EFB rows 448–512 stale-band
> claim below being wrong). Rather than iterate blind, the pre-vetted fallback
> shipped: **wipe ids 5/6 → Hx_Test4** (fn-table 04s at 0x803C12B0/B4 →
> 0x8017E46C; zero copies; paced at stock cadence by the plain wipe_pace gate —
> the swap must ship WITHOUT wipe5_smooth and WITHOUT the id-5/6 bypass, which
> check() enforces). `--no-wipe-swap` restores the tile morph for future work.
>
> **If the authentic tile dissolve is ever wanted back**, do the single-capture
> redesign instead of re-tuning the morph: capture the whole 640×448 EFB ONCE
> per frame (GetFrBuffer(bigbuf,0,0,640,448), clear=TRUE gives the black
> background in one pass) into spare MEM1 above the game's 24MB (32MB override
> is on; e.g. 0x81A00000, clear of Dolphin's gecko list at ~0x817FE000), init
> the tex obj as 640×448, keep stock 64px fans/strides, and remap each fan's
> immediate-mode texcoords (u' = tx/640 + u·0.1, v' = ty/448 + u·(64/448)) via
> small C2s at the three WGPipe texcoord stores — 1 copy/frame instead of 80,
> bit-stock geometry. Sketch only; nothing built.

**Symptom (user, 2026-08-10):** the scene-transition "decomposition / recomposition"
animation tanks the framerate at 240/360fps and then plays out slowly/laggily —
recompose still crawling after Mario has spawned and is running around normally.
Mario being normal while the effect crawls is the tell: the effect is per-RENDERED-
frame work whose own progress is frame-counted, while Mario rides the substep
scheduler.

## Root cause (disasm, USA main.dol)

- The effect is the Hx wipe module's **`Hx_Test5`** (wipe ids 5 = reveal /
  6 = close in the fn table at `0x803C129C`). The whole wipe TU maps
  **JP − 0xC0388 → USA** (verified: fn-table entries match JP symbols;
  `Hx_CameraInit` lands on the handoff's known `0x80182D60`).
  Key USA addresses: `Hx_Test5 0x8017DF74`, `Hx_Test4 0x8017E46C`,
  `Hx_UpdateWipe 0x80181E80`, `Hx_GetFrBuffer 0x80182A20`,
  `Hx_TimerCountDown 0x80181E58`.
- Every rendered frame in wipe state 2, Test5 walks the screen in **64×64
  tiles (10×8 = 80)** and PER TILE calls `Hx_GetFrBuffer` =
  `GXSetTexCopySrc (0x8035E388)` + `GXSetTexCopyDst (0x8035E48C)` +
  `GXCopyTex(dest, clear=TRUE) (0x8035EE5C)` + pix-mode sync — an **EFB copy
  into the static 8KB tile buffer at 0x803F4440** (wipe globals `0x803F43C0`
  + 0x80) — then redraws the tile as a 16-segment sin/cos swirled triangle-fan
  (2 transcendental calls per segment, 17 verts immediate-mode).
- **80 EFB copies per frame is native-30fps work**: 2,400 copies/s by design →
  28,800/s at 360fps. In Dolphin each partial EFB copy is a render-pass switch;
  the framerate collapses for the wipe's duration.
- The wipe runs a **fixed 20 rendered frames** (`Hx_TimerCountDown` decrements
  `globals+0x3C`, set to 20 in Test5's state 0). When fps collapses, those 20
  frames stretch in wall-clock → the visible "slow, laggy" decompose/recompose.
- The other wipes are innocent: **Test4 = pure sin/cos geometry, ZERO copies**
  (this is why level entry/exit via doors — Circle + Test4, per wipelog — never
  lagged); Circle/Door do 1–5 small 48×48 morph copies per frame
  (`__Hx_FrBufferMorf 0x801824B4`, `Hxs_FrBufferMorf2/2B 0x80181170/0x80180F64`).
  Full-TU scan: Test5's loop is the only multi-copy site.

## The fix — `fpspatch.py wipe5_opt()`, emitted at G ≥ 3

Double the tile grid to **128×128 (5×4 = 20 copies/frame, a 4× cut)** using the
GX half-scale idiom so the 8KB buffer still fits:

1. **One atomic C2 @0x80182A5C** (Hx_GetFrBuffer's `bl GXSetTexCopySrc`),
   discriminated by `r29 == 0x803F4440` (only Test5 uses the static buffer; all
   other callers pass heap pointers): doubles the src rect to 128×128, then runs
   the dst setup itself with `GXSetTexCopyDst(64, 64, GX_TF_RGB565, mipmap=TRUE)`
   (mipmap = box-filtered half-scale copy) and resumes at `0x80182A74`. Src-widen
   and dst-halve live in ONE cave ON PURPOSE: a silently-dropped companion block
   could otherwise pair "src 128" with "dst full-res" = 16–32KB GXCopyTex over the
   8KB buffer = BSS stomp. All drop modes of this design degrade to stock or to a
   cosmetic glitch, never corruption. r29 is GetFrBuffer's own saved nonvolatile,
   so the flag is recomputed after the bctrl instead of parked in a volatile.
2. **C2 @0x8017E18C**: re-exec `lfs f22,-0x4604(r2)` (pooled 32.0 — shared, can't
   be edited) then `fadds f22,f22,f22` → half-tile offset/fan radius 64.
3. **04 @0x8017E39C/0x8017E3D8**: loop strides `0x40 → 0x80`.

Visual delta: transition chunks 2× coarser, tile content half-res during the
morph only. 640/128 = 5 exactly; bottom row reads EFB rows 480–512 (physical EFB
is 528 tall — clear color, not garbage — and that band maps offscreen anyway,
same as stock's 448-row tile).

Not emitted at 120fps (G=2): the M2 Max held 119 through these wipes; stock look
kept there. Flag: `--no-wipeopt`.

## Diagnostic / fallback

`research/codes/wipe5-test4-swap-diag.txt` — 2×04 data-table swap pointing wipe
ids 5/6 at Hx_Test4 (zero copies). If lag persists WITH the swap, the diagnosis
is wrong (measure again); if the optimized Test5 is still too heavy at 360, the
swap is the nuclear fallback (different-looking transition, zero cost).

## ⚠️ Interaction found 2026-08-11: `$Widescreen wipe fix v2` misaligns Test5
## (real, but NOT the reported bug — disabling it did not fix the artifact)

User screenshot (first loading screen after boot, 240fps): scene chunks drawn in
the wrong place + big black slabs during the tile-dissolve reveal. First
diagnosis blamed the separately-enabled `$Widescreen wipe fix v2`
gecko (C2 @0x80182DD8 inside Hx_CameraInit) scales the wipe ortho half-width
×0.75 (pooled 0.0625 × 12.0), magnifying all wipe DRAWING ×4/3 horizontally,
while Test5's EFB copies and clear-to-black rects stay at unstretched EFB coords
— every fan lands up to ±107px from the rect it just blacked out. Only copy-based
wipes are affected (Test5 + FrBufferMorf family); Circle/Test4 are pure geometry
→ "first loading screen every boot broken, every other loading screen fine"
(boot→plaza and plaza returns are Test5; level doors are Circle/Test4). The v2
code was enabled on the PC only since the 2026-08-09 evening kit commit
(cfe8691; before that its title was a phantom), and wipe5_opt's 128px tiles made
the misalignment 2x bigger — hence "new" on 2026-08-10/11. FIX: v2 unticked in
live + kit INIs (it never fixed its own bars bug — see HANDOFF-WIPE-BARS.md).
Lesson: any wipe-camera transform must either exempt EFB-copy wipes or remap
Hx_GetFrBuffer's copy/clear rects through the same transform.
OUTCOME: user retested with v2 confirmed dead at both hook sites (gcmem) — the
artifact persisted unchanged → v2 was compounding, not causal. Keep it off
regardless; the shipping fix is the Test4 swap (see verdict at top).

## Verify (playtest checklist)

1. Enter/exit a stage that uses the tile-morph transition at 240/360: fps dip
   should be gone or small; decompose/recompose completes in ~20 frames' worth
   of wall-clock (fraction of a second), no longer outliving Mario's spawn.
2. Look of the wipe: same swirl, 2× chunkier grid. If it looks broken in a
   gap/quarter-tile way, one of the four pieces didn't apply — run
   `fpspatch.py <fps> --check` and re-install; the pieces ship together.
3. Door/hotel and circle transitions unchanged (their morphs don't hit the
   Test5 buffer discriminator).

Cross-refs: `PERF-PLAYBOOK.md` (worked example #2), `HANDOFF-NOKI-PERF.md` (the
readback sibling), fn-table dump in this session's transcript.

---

# Wipe DURATION fix — "the map loads way too fast" (ADDED 2026-08-10, awaiting playtest)

**Symptom (user, 2026-08-10):** the level-load decompose/recompose animation
plays far too fast at high framerates (once wipe5_opt stopped the fps collapse
that used to mask it). Should be framerate agnostic.

## Root cause (disasm, USA)

Every Hx wipe times itself in RENDERED frames and none of them read the rate:

- `Hx_StartWipe` (USA 0x80181FD8) stores a *seconds x mRate* duration at
  `globals+0x1C` and `Hx_UpdateWipe` (0x80181E80) stores the rate at `+0x18` /
  accumulates it at `+0x14` — but a full-TU sweep found **zero readers** of all
  three fields. Dead API.
- Instead each wipe fn stores a hardcoded frame count into the shared timer
  `globals+0x3C` (Test5 = 20, Test4 = 38, Circle = 25/30, GameOver = 10/100,
  Logo = 5/11/255 + movie-struct counts) and ends when `Hx_TimerCountDown`
  (0x80181E58, decrements once per call) hits 0; the slide/sweep wipes also
  advance `Hx_MotionSet`-built motion structs once per `Hx_MotionUpdate` call
  (0x80181D74). All of it once per rendered frame → FPS/30 = 2G x too fast.
  Test5's 20 frames: 0.67s at stock 30fps → 55ms at 360fps.

## The fix — `fpspatch.py wipe_pace()`, emitted whenever FPS%30==0 and FPS>=60

Hold the wipe CLOCK (not the draw) at native 30 Hz, one counter + two gates:

1. **C2 @0x80181F7C** (Hx_UpdateWipe state-2 `stfs f31,0x18(r31)`, right before
   the fn-table blrl): tick low-arena counter **0x800016F4** once per rendered
   wipe frame (16E0/16E4 = Noki, 16E8 = select, 16F0 = camera).
2. **C2 @0x80181E70** (`addi r0,r3,-1`, TimerCountDown's decrement): pass 1
   frame in N = FPS/30 (ctr % N on the shared counter); gated frames store the
   timer back unchanged. Logo's 4x back-to-back calls keep their stock ratio
   (all-or-nothing per frame).
3. **C2 @0x80181D74** (MotionUpdate entry): same gate; gated frames bctr to the
   fn tail 0x80181DD8 (`lfs f1,0x20(r3); blr`) so callers still get the value.

Safety argument (all verified with callers.py): both helpers' 39 call sites are
inside wipe fns; wipe fns have ZERO direct callers (dispatch only via
Hx_UpdateWipe's blrl); Hx_UpdateWipe's single caller is TSMSFader::drawWipe,
once per rendered frame (fader built with mRate = SMSGetVSyncTimesPerSec() at
boot, Application.cpp:240). The one outside entry, Hx_MovieStartSyncEx (bl from
0x802B5CF4), calls neither helper — so the counter can never be stale when a
gate runs (no stall-hazard). Draw runs every frame from frozen state — the
select_gate lesson (gate cadence, never presentation). Visual result is
bit-exact stock cadence: 30 Hz steps over the stock wall-clock duration.

## SMOOTH pacing for Test5 (ADDED 2026-08-10 evening — user: "still choppy, doesn't sync with Mario")

wipe_pace restored stock DURATION but stock duration is 30 Hz-STEPPED — correct
vs stock, but reads as chop next to 240fps-smooth Mario. For Test5 only, fpspatch
`wipe5_smooth(fps)` goes beyond stock: per-frame progress at stock wall-clock.

- `04 @0x8017E078`: state-0 frame count `li r0,20` -> `li r0,20*N` (N = FPS/30).
- `C2 @0x8017E14C`: progress divisor — re-exec `lfs f1,-0x4614(r2)` (pooled 20.0,
  shared const) then f1 *= 2G read from the framerate global -> 20N. f0 is dead
  at the hook (next read at 0x8017E164 is preceded by its own lfd @0x8017E15C).
- wipe_pace(smooth56=True): the TimerCountDown gate C2 grows an id-5/6 bypass
  (`lbz r11,0x43D1(r12)` = wipe globals+0x11; ids 5/6 decrement EVERY frame).
  PAIRING IS MANDATORY: rescale without bypass = 2Gx slow; bypass without
  rescale = 2Gx fast. check() enforces both directions. Test5 never calls
  Hx_MotionUpdate, so the motion gate needs no exemption. Other wipes stay on
  the 30 Hz gate (that IS stock cadence for them).

`--check` enforces: all three blocks together, divisor = FPS/30 on both gates,
shared counter in all three, original instructions in the right slots. Flag:
`--no-wipepace`. Emitted at 120 too (wipes were 4x fast there, just less silly).

Verify (playtest): enter/exit a stage at 240/360 — decompose/recompose should
take its stock ~2/3s; door/circle/gameover/logo wipes likewise stock-paced; no
transition hang (a hang would mean a gate ran with a frozen counter — can't
happen per the callers argument, but that is the failure mode to watch).

---

# M-portal dots-vs-ripples desync — ROOT CAUSE = our own Noki gate (FIXED v3, 2026-08-11)

Symptom: entering an M portal at 240/360, the surface ripples of the atom-dots
hitting the gate appeared way later than the visual impacts; destination
recompose also felt behind Mario.

Investigation (all in this session, method = measure-then-patch):
- `scripts/warplog.py` (live TMario sampler: mStatus 0x1336/0x1337, state +0x84,
  timer +0x86, base via [0x8040E10C]−0x10, holder gate +0x68) proved the warp
  status machine substep-clean: ~95-110 ticks/s at 240fps, stock phase durations.
- Decomp reading proved the dot-push callback (TWarpInCallBack, JPAParticle
  unk50) executes in JPABaseEmitter::calc()/doParticle() — the 60Hz-gated path.
- The gate's +0xB8/+0xB9/+0xBC whirl machinery never ran during the take
  (sampled frozen) — it is gated on +0xB8==1 (ambient shimmer, not impact rings).
- The rings are MODEL STAMPS via pushModelStampTask. The v1 Noki gate blr'd all
  of TPollutionManager::perform on gated frames INCLUDING the layer-0 stamp
  drain (calcViewMtx 0x8019B16C) -> stamps batched 2G frames; the v2 dedupe then
  discarded all-but-one same-model stamp per batch -> at 240fps ~7/8 ripple
  stamps deleted, survivors late. Self-inflicted, exactly like the wipe chop.

Fix: Noki gate v3 (fpspatch `noki_gate()`): per-call-site gates on the two
counting readbacks only; drain runs every frame; dedupe retired. Full table in
HANDOFF-NOKI-PERF.md v3 section. Lesson (now thrice-learned): NEVER hold a
whole perform to a cadence — gate the expensive LEAF calls; everything else in
the function is someone's data flow.
