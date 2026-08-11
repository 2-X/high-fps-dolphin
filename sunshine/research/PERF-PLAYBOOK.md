# High-FPS Performance Playbook — how to find & remove framerate bottlenecks

**When to use this:** one area/level/boss drops frames while the rest holds the cap, or
you want to push the whole game to a higher rate (120 → 180 → 360) and need to know what's
actually in the way. This is the repeatable method that took Noki Bay Ep.1 from 105 → 119.

**The one rule: MEASURE FIRST, patch second.** This project burned two sessions on
*plausible* theories that were wrong — the sun lens-flare `GXPeekZ` occlusion (NOP'd it,
nothing changed, and it broke the flare) and the goop *draw* (`TPollutionLayerWave`, killed
it, stats byte-identical). Both were reasonable from the decomp. Both were wrong because
nobody had measured which thread and which function were hot. Don't hypothesize a cause you
haven't seen in a profile.

---

## The two instruments

### 1. OverlayStats — per-frame GPU work (the "what is the frame made of" view)
Enable `OverlayStats = True` in `GFX.ini` (or Graphics → Advanced → Show Statistics). It draws
a live table. Screenshot it in the **slow** spot and again in a **fast** spot and diff:

| Row | What a high value means |
|---|---|
| `BP loads` | render-state changes (blend/texenv/Z). High + low geometry = state-change churn. |
| `XF loads` | transform/lighting/texgen setup. Same story. |
| `Primitives (DL)` / `Vertex streamed` | actual geometry volume — real draw cost. |
| `EFB peeks` | `GXPeekARGB/Z` framebuffer peeks. **NOTE: this counter does NOT include EFB-copy readbacks** — a scene can stall hard on readbacks with `EFB peeks: 0` (Noki did). |
| `Tokens` | GP draw-sync tokens — the pollution/readback callbacks show here (18/18 polluted, 0/0 gated). |

OverlayStats tells you the GPU-side *shape* of the frame. It does **not** tell you where the
host CPU time goes — for that you need instrument 2.

### 2. `sample` — which host function is eating the frame (the flame-chart view)
`research/fpsprofile.sh` wraps this. Get into the slow spot, hold a steady view, then:
```
sunshine/research/fpsprofile.sh 5        # 5-second profile of the running Dolphin
```
It samples the process and summarizes the hot leaves on the **"CPU-GPU thread"** (the
emulation thread — its budget IS the frame). Run it in the fast spot too; the delta is the
bottleneck. This is the instrument that actually found Noki.

---

## The decision tree (read the profile, pick the class)

**A. Readback stall** — the profile is dominated by any of:
```
AbstractStagingTexture::ReadTexels     (EFB→RAM copy read back to CPU)
Metal::StagingTexture::Flush           → -[MTLCommandBuffer waitUntilCompleted]  (the block)
PerfQuery::FlushResults                (GXReadPixMetric / pixel-metric readback)
FramebufferManager::PeekEFBColor       (GXPeekARGB)
```
This is the **#1 high-fps killer on Metal.** The game renders something and reads it back to
CPU **every frame**; on Metal each read is a synchronous pipeline stall. Because SMS is a
**30fps** game and we run it at N× (120=4×, 180=6×, 360=12×), these reads fire **N× too
often**. → Go to **The 30Hz gate** below. This is almost always the answer for a
single-area drop.

**B. Genuine draw cost** — profile dominated by `VertexManagerBase::RenderDrawCall`,
`DrawIndexed`, `BPFunctions`, shader work, *with no readback rows*. The scene really is
drawing a lot (heavy geometry, overdraw, huge state churn). Levers: reduce the draw at the
game level (gate/cull the offending actor), lower internal resolution (only helps if
fill-bound), or accept it. Rarer than (A) in this game.

**C. CPU/emulation throughput ceiling** — no single Dolphin function dominates; time is in
JIT'd game code ("??? in unknown binary") and both hot threads sit at the same busy-but-not-
saturated % (the lock-step signature). This is the **180→360 wall on the PC** (see
`HANDOFF-PC.md` §S3) — a CPU↔GPU per-frame serialization, not fixable in config. Levers:
host CPU affinity, or locked-rate + frame interpolation. Different problem entirely.

---

## The 30Hz gate — the reusable fix for class A

Everything the game does *per rendered frame* runs at N× native. Anything that doesn't need
to (readback-driven bookkeeping, coverage counting, slow ambient updates) can be **gated back
to native 30Hz** — run it 1 frame in N and let it hold its value between. Invisible to the
player, removes (N−1)/N of the cost.

**Shape of the gate (see `codes/noki-pollution-30hz-gate-v1.txt` for a full worked example):**
1. Find the per-frame function that triggers the readback (profile → decomp → USA address by
   fingerprint, same method as every other code here).
2. C2-hook it at entry. Keep a scratch frame counter (`0x800016E0+`, OS low arena is free).
   Increment once per frame; when `(ctr & (N-1)) != 0`, `blr` immediately (skip the work).
   *(A `blr` inside a C2 block returns to the game caller — LR is preserved; proven by the
   timer-fix v15 code which hooks a `blr` directly.)*
3. Re-execute the overwritten entry instruction on the run-path; end the block with the single
   `00000000` branch-back (see the Gecko C2 gotchas in `README.md`).

**Rate divisor by target.** An `andi.` mask only implements "1 in N" when **N is a power of
two** — `x & (N-1)` equals `x mod N` only in that case. For any other N you need a real
modulo. `x & 5` is *not* `x mod 6`: it is zero for x = 0, 2, 8, 10, … — a garbage gate firing
at the wrong cadence, not a 1-in-6 gate. (An earlier version of this table said to use mask
`5` for 180 and `11` for 360; both were wrong.)

| Target fps | multiplier N | gate |
|---|---|---|
| 120 | 4 | `andi. r0,r11,3` |
| 240 | 8 | `andi. r0,r11,7` |
| 180 | 6 | modulo (below) |
| 360 | 12 | modulo (below) |

The modulo form — five instructions, no scratch state, exact for every N (`r11` = counter,
`r0`/`r4` scratch; a following `bne` skips the work):
```
li    r4,N          ; 38800000|N
divwu r0,r11,r4     ; q = ctr / N
mullw r0,r0,r4      ; q * N
subf. r0,r0,r11     ; ctr - q*N = ctr mod N, sets CR0
bne   skip
```
`fpspatch.py`'s `_rate_gate(g)` emits exactly this (mask when the multiplier is a power of
two, modulo otherwise) — reuse it rather than hand-assembling.

Tie it to the fps-active discriminator (`0x804167B8 == 2.0f`) if you want it to self-disable
when the hack is off — the same guard the timer/anim codes use.

**Caveat:** gate only work whose *result* tolerates 30Hz updates (counters, coverage,
ambient). Do NOT gate anything gameplay-timing-critical (nerve/spine timers, input) — those
are handled by the substep scheduler, not by frame gating. If a gated system starts to *feel*
laggy (e.g. goop clearing sluggishly), back the divisor off one step (1-in-4 → 1-in-2).

---

## What else to audit for more frames (candidate list)

The Noki fix removed *one* per-frame readback. Anywhere else the game reads the framebuffer
back or does per-frame heavy bookkeeping is a candidate for the same treatment. Profile the
suspect area first, then check the decomp for these call patterns:

- **`GXReadPixMetric` / `GXReadBoundingBox`** — pixel-metric / bbox readbacks. Pollution uses
  the former; other effects or minigames may use bbox. Every caller is a per-frame stall at N×.
- **`GXCopyTex` to main memory + a CPU read of that buffer** — any EFB→RAM-then-read effect
  (reflection/refraction buffers, procedural textures, the pollution coverage map).
- **Heat-haze / water-refraction screen grabs**, lens/flare occlusion, real-time shadow-map
  readbacks — screen-reading effects on specific bosses/areas.
- ~~**Screen-transition tile morphs**~~ — FOUND AND FIXED (2026-08-10): the
  decompose/recompose wipe `Hx_Test5` does **80 EFB copies per rendered frame**
  (64×64 tile grid, capture+clear+redraw each tile each frame) — 12× the designed
  rate at 360fps, tanking fps for exactly the wipe's 20 rendered frames. Fixed
  game-side: `fpspatch.py wipe5_opt()` (128px tiles + half-scale copies = 4× fewer
  copies, look preserved), emitted at G ≥ 3. Full RE + fix design:
  `memory/sunshine-wipe-morph-perf.md`. Diagnostic A/B:
  `codes/wipe5-test4-swap-diag.txt`. Note this one is copy-COUNT churn (render-pass
  switches), not a CPU readback — it shows as class B in a profile, not class A,
  and the 30Hz gate does NOT apply (skipping wipe frames flashes the raw scene).
- **Any actor whose per-frame `perform` does GX state floods** at N× where the *visual* only
  needs 30Hz (slow ambient surfaces, distant animated decals).

For each: `fpsprofile.sh` in that area → if a readback row appears → find the game function →
30Hz-gate it. If no readback and it's just draw volume → class B, weigh the lever.

---

## Cross-references
- Worked example + addresses: `../HANDOFF-NOKI-PERF.md`, `codes/noki-pollution-30hz-gate-v1.txt`
- Gecko C2 mechanics & the gotchas that cost days: `../README.md` §5 "Gecko gotchas"
- The 180/360 throughput wall (class C): `../HANDOFF-PC.md` §S3
- Sim-rate mechanism / `0x804167B8` fps discriminator: memory `sunshine-timer-fix`,
  `sunshine-simrate-mechanism`
