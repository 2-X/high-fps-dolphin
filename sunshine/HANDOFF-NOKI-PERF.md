# HANDOFF — Noki Bay Ep.1 performance drop — FIXED (2026-08-07)

**Status: SHIPPED. 105fps → 119 stable, no EFB config hacks needed.**
Code `$Noki pollution counting 30Hz gate (120fps Ep.1 perf)` enabled in `GameSettings/GMSE01.ini`.
Source + full doc: `research/codes/noki-pollution-30hz-gate-v1.txt`.

## Symptom
On M2 Max at 120fps, **Noki Bay Episode 1 ("Uncork the Waterfall")** was stuck at ~105fps
while everything else — including **Noki Bay Episode 2** — held 119. Area-specific, sustained,
not a momentary hitch.

## Two wrong theories first (kept, because the misfires are instructive)
1. **Sun lens-flare `GXPeekZ` occlusion** (`TSunModel::getZBufValue`, 17 EFB depth peeks/frame,
   USA `0x8002EA70`). NOP'ing the call changed fps **not at all** and made the flare vanish
   (the peek feeds the draw decision, not just occlusion). Reverted.
2. **Goop *draw*** (`TPollutionLayerWave::perform`, USA `0x801A1E3C`). Killed the wave-surface
   draw → OverlayStats **byte-identical**, goop still visible. The draw is not the cost.

Both were plausible from the decomp. Both were disproven only by measuring. Lesson lives in
`research/PERF-PLAYBOOK.md`.

## Actual root cause (measured, `sample` of the emulation thread)
`research/fpsprofile.sh` on the running process, in-level, showed **~39% of the "CPU-GPU
thread" blocked in `-[MTLCommandBuffer waitUntilCompleted]`** — synchronous GPU→CPU readbacks:

| Dolphin function | samples / ~3658 | source |
|---|---|---|
| `AbstractStagingTexture::ReadTexels` | 1079 | EFB→RAM coverage readback (`countTexDegree`) |
| `PerfQuery::FlushResults` | 189 | `GXReadPixMetric` in `drawSyncCallback` (`countObjDegree`) |
| `FramebufferManager::PeekEFBColor` | 162 | EFB color peek |

These come from the **pollution degree-counting** — the game renders the goop coverage and
reads it back to CPU **every frame** to know how much pollution remains. SMS is a **30fps**
game; at 120fps (4×) that readback fires **4× as often as designed**. Ep.1 starts **fully
polluted** → maximal counting → the cap drops to 105. Ep.2 has no goop → no readback → 120.
`EFB peeks: 0` throughout — the stat counter excludes EFB-copy readbacks, which is why the
overlay alone looked innocent.

Confirmation before patching: toggling **Store EFB Copies to Texture Only** + **Skip EFB
Access from CPU** (live, Graphics → Hacks) removed the `ReadTexels` + `PeekEFB` paths → 105→115.
The residual 4fps was the `GXReadPixMetric` path those toggles don't cover — exactly the
prediction.

## The fix
C2 at **`TPollutionManager::perform` = USA `0x8019D8C8`** (PAL `0x80196150`), disasm-verified:
```
8019d8d0 rlwinm. r0,r4,0,7,7   ; cue & 0x01000000  -> countObjDegree()   (GXReadPixMetric)
8019d8f8 rlwinm. r0,r4,0,6,6   ; cue & 0x02000000  -> countTexDegree()   (EFB→RAM readback)
8019d900 rlwinm. r30,r4,16,24,31; layer = (cue>>16)&0xFF
8019d940 bl 0x801887ac         ; else: TJointModelManager::perform (visible DRAW — NOT gated)
```
Gates **both** counting passes to **1 frame in 4** (native 30Hz) via two self-contained
scratch counters — objCtr `0x800016E0` (ticked per obj-cue), texCtr `0x800016E4` (ticked when
layer==0). On gated frames it `blr`s immediately; counters hold their last value; the visible
goop draw still runs every frame. All three readback stalls now fire at a quarter of the rate.

**Result:** 119 stable. OverlayStats on a gated frame: `BP loads 8196→999`, `XF loads
1490→221`, `Tokens 18/18→0/0`. Both EFB Graphics hacks turned back **OFF** (goop clears
normally again).

## To verify / if it regresses
- Spray goop and confirm it still **clears** at a normal pace (30Hz clear-detection should feel
  identical to stock). If it feels sluggish → back the divisor to 1-in-2: change the two
  `andi. r0,r11,3` words (`71600003`) to `71600001`.
- Crash on load would mean the C2 early-return LR assumption failed (it hasn't — timer-fix v15
  proves `blr`-in-C2 returns to caller); the fallback is gating the two `bl` call-sites directly.

## PC (180/360)
Same bottleneck at higher multipliers. Change both `andi.` masks: **180fps** `3`→`5`
(`71600005`), **360fps** `3`→`11` (`7160000B`). Worth profiling other polluted levels the same
way (`fpsprofile.sh`).

See also: `research/PERF-PLAYBOOK.md` (the general method), memory `sunshine-noki-pollution-perf`.

## v2 (2026-08-09) — REQUIRED companion fix: the Bianco Ep.1 load freeze

The v1 gate froze **every polluted level whose actors stamp their models into
goop** (Bianco Ep.1 "Road to the Big Windmill", et al.) on load, ending in a
Metal `Preallocate` OOM after the vertex buffer doubled to ~64GB.

**Root cause (measured, not theorized):** gating `TPollutionManager::perform`
lets `pushModelStampTask` accumulate G frames of tasks — the same J3DModel
queued up to G times. On the pass frame `calcViewMtx()` calls `model->entry()`
per queue slot; J3D's `entry()` is a push-front intrusive list insert, so the
second insert of the same packet sets `packet->next = packet`. The J3D draw
walks the self-loop forever, streaming one mat packet into the FIFO — the game
thread never finishes the frame, nothing presents, Dolphin's vertex batcher
grows without bound. Confirmed by dumping the live FIFO ring from the frozen
process (`scripts/fifodump.py` + `scripts/gxdisasm.py`): one ~95-byte packet
(CALL DL 80abc880/815fb2e0 + matrix loads) repeated wall-to-wall. Noki Bay has
no model-stamping actors — why v1 tested clean there.

Two instrumentation notes that made this findable:
- `[hifps]` NOTICE logs added to our Dolphin: PE token-coalescing events,
  CP breakpoint arm/disarm/hit with FIFO addresses, Metal Preallocate growth
  >64MB (kept in tree; near-zero cost).
- Dolphin token coalescing (`PixelEngine::SetToken` overwrites `m_token_pending`)
  was investigated and CLEARED — zero coalesced tokens in the failing run. The
  DrawSyncManager ring/breakpoint protocol is NOT the problem.

**Fix:** dedupe at the push. C2 @ `pushModelStampTask` USA **0x8019B120**
(disasm-verified) scans the queue slots (this+0x38, stride 8) for the incoming
model ptr (r5) and `blr`s on a hit — same shape as the stock queue-full
early-return. ctr untouched (callers can loop on it), only r10-r12 clobbered.
Emitted automatically by `fpspatch.py` alongside the gate (`noki_dedupe()`).

Verify: Bianco Ep.1 loads and plays; goop stamping/cleaning behaves; Noki Bay
Ep.1 still holds ~119.
