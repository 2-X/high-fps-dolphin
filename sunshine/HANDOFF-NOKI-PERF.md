# HANDOFF: Noki Bay Ep.1 performance drop - FIXED (2026-08-07)

**Status: SHIPPED. 105fps → 119 stable, no EFB config hacks needed.**
Code `$Noki pollution counting 30Hz gate (120fps Ep.1 perf)` enabled in `GameSettings/GMSE01.ini`.
Source + full doc: `research/codes/noki-pollution-30hz-gate-v1.txt`.

## Symptom
On M2 Max at 120fps, **Noki Bay Episode 1 ("Uncork the Waterfall")** was stuck at ~105fps
while everything else (including **Noki Bay Episode 2**) held 119. Area-specific, sustained,
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
thread" blocked in `-[MTLCommandBuffer waitUntilCompleted]`**: synchronous GPU→CPU readbacks:

| Dolphin function | samples / ~3658 | source |
|---|---|---|
| `AbstractStagingTexture::ReadTexels` | 1079 | EFB→RAM coverage readback (`countTexDegree`) |
| `PerfQuery::FlushResults` | 189 | `GXReadPixMetric` in `drawSyncCallback` (`countObjDegree`) |
| `FramebufferManager::PeekEFBColor` | 162 | EFB color peek |

These come from the **pollution degree-counting**: the game renders the goop coverage and
reads it back to CPU **every frame** to know how much pollution remains. SMS is a **30fps**
game; at 120fps (4×) that readback fires **4× as often as designed**. Ep.1 starts **fully
polluted** → maximal counting → the cap drops to 105. Ep.2 has no goop → no readback → 120.
`EFB peeks: 0` throughout (the stat counter excludes EFB-copy readbacks, which is why the
overlay alone looked innocent).

Confirmation before patching: toggling **Store EFB Copies to Texture Only** + **Skip EFB
Access from CPU** (live, Graphics → Hacks) removed the `ReadTexels` + `PeekEFB` paths → 105→115.
The residual 4fps was the `GXReadPixMetric` path those toggles don't cover, exactly the
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
scratch counters: objCtr `0x800016E0` (ticked per obj-cue), texCtr `0x800016E4` (ticked when
layer==0). On gated frames it `blr`s immediately; counters hold their last value; the visible
goop draw still runs every frame. All three readback stalls now fire at a quarter of the rate.

**Result:** 119 stable. OverlayStats on a gated frame: `BP loads 8196→999`, `XF loads
1490→221`, `Tokens 18/18→0/0`. Both EFB Graphics hacks turned back **OFF** (goop clears
normally again).

## To verify / if it regresses
- Spray goop and confirm it still **clears** at a normal pace (30Hz clear-detection should feel
  identical to stock). If it feels sluggish → back the divisor to 1-in-2: change the two
  `andi. r0,r11,3` words (`71600003`) to `71600001`.
- Crash on load would mean the C2 early-return LR assumption failed (it hasn't; timer-fix v15
  proves `blr`-in-C2 returns to caller); the fallback is gating the two `bl` call-sites directly.

## PC (180/360)
Same bottleneck at higher multipliers. Change both `andi.` masks: **180fps** `3`→`5`
(`71600005`), **360fps** `3`→`11` (`7160000B`). Worth profiling other polluted levels the same
way (`fpsprofile.sh`).

See also: `research/PERF-PLAYBOOK.md` (the general method), memory `sunshine-noki-pollution-perf`.

## v2 (2026-08-09): REQUIRED companion fix: the Bianco Ep.1 load freeze

The v1 gate froze **every polluted level whose actors stamp their models into
goop** (Bianco Ep.1 "Road to the Big Windmill", et al.) on load, ending in a
Metal `Preallocate` OOM after the vertex buffer doubled to ~64GB.

**Root cause (measured, not theorized):** gating `TPollutionManager::perform`
lets `pushModelStampTask` accumulate G frames of tasks. The same J3DModel
queued up to G times. On the pass frame `calcViewMtx()` calls `model->entry()`
per queue slot; J3D's `entry()` is a push-front intrusive list insert, so the
second insert of the same packet sets `packet->next = packet`. The J3D draw
walks the self-loop forever, streaming one mat packet into the FIFO. The game
thread never finishes the frame, nothing presents, Dolphin's vertex batcher
grows without bound. Confirmed by dumping the live FIFO ring from the frozen
process (`scripts/fifodump.py` + `scripts/gxdisasm.py`): one ~95-byte packet
(CALL DL 80abc880/815fb2e0 + matrix loads) repeated wall-to-wall. Noki Bay has
no model-stamping actors, which is why v1 tested clean there.

Two instrumentation notes that made this findable:
- `[hifps]` NOTICE logs added to our Dolphin: PE token-coalescing events,
  CP breakpoint arm/disarm/hit with FIFO addresses, Metal Preallocate growth
  >64MB (kept in tree; near-zero cost).
- Dolphin token coalescing (`PixelEngine::SetToken` overwrites `m_token_pending`)
  was investigated and CLEARED: zero coalesced tokens in the failing run. The
  DrawSyncManager ring/breakpoint protocol is NOT the problem.

**Fix:** dedupe at the push. C2 @ `pushModelStampTask` USA **0x8019B120**
(disasm-verified) scans the queue slots (this+0x38, stride 8) for the incoming
model ptr (r5) and `blr`s on a hit, same shape as the stock queue-full
early-return. ctr untouched (callers can loop on it), only r10-r12 clobbered.
Emitted automatically by `fpspatch.py` alongside the gate (`noki_dedupe()`).

Verify: Bianco Ep.1 loads and plays; goop stamping/cleaning behaves; Noki Bay
Ep.1 still holds ~119.

## v3 (2026-08-11): REDESIGN: call-site gates; v1 gate + v2 dedupe RETIRED

**Symptom that exposed v1/v2's flaw (user, 240fps):** entering an M portal, the
rainbow-surface ripples of Mario's atom-dots hitting the gate "appear way later
than when the dots hit." Live capture (`research/scripts/warplog.py`) proved the
whole warp logic chain substep-clean. The desync was OUR code: the gate-surface
impact ripples are model stamps through `pushModelStampTask`. v1's whole-perform
`blr` also skipped the layer-0 stamp-queue drain (`calcViewMtx` 0x8019B16C), so
stamps batched 2G frames; the v2 dedupe then collapsed every same-model stamp in
the batch to ONE; at 240fps up to 7 of every 8 ripple stamps were silently
discarded, and survivors landed on pass frames. Ripples = late + sparse.

**v3 (in `fpspatch.py noki_gate()`, emitted per-fps):** gate ONLY the two
expensive counting calls at their call sites; everything else (crucially the
drain) runs every frame, so batches never form and the v2 dedupe is
unnecessary (removed; it also deleted legitimate same-frame stamps that stock
allows):
| hook | call | policy |
|---|---|---|
| 0x8019D8F0 | countObjDegree (GXReadPixMetric) | tick objCtr 0x800016E0, 1-in-FPS/30 |
| 0x8019D90C | calcViewMtx = stamp drain (layer 0) | tick texCtr 0x800016E4, ALWAYS |
| 0x8019D91C | per-layer countTexDegree (ReadTexels) | read texCtr, 1-in-FPS/30 |
| 0x8019D934 | last-layer finish | read texCtr, 1-in-FPS/30 |
`noki_copy_gate` (TEfbCtrlTex) is unchanged; texCtr still ticks exactly once
per rendered frame, so its phase contract holds. Perf is identical to v1 (the
readbacks were always the whole cost; the drain is cheap pointer walking).
`--check` now errors if the old 0x8019D8C8 / 0x8019B120 blocks reappear.

Verify at 240/360: M-portal entry: ripple rings appear ON dot impacts; goop
stamps/clears normally; Bianco Ep.1 still loads (the freeze can't recur: no
batching means no duplicate entry()). The old standalone `$Noki pollution
counting 30Hz gate` INI title and the pre-v3 120fps bundles still carry v1/v2
blocks (harmless while unticked, but never enable them alongside a v3 bundle).

## v4 (2026-08-19): the Bianco Ep.1 FREEZE was v3's own fin gate — FIXED

v3's "no batching" claim above was WRONG in one corner, and it froze Bianco
Ep.1's intro every time (the crash that got the gate CRASHES-quarantined under
BSE on both machines — BSE was innocent). Live-debugged on the PC at BSE-240:
emu thread spinning, ctrs frozen obj=521/tex=520, thread-context backtrace
J3D packet walk <- 0x8019B4D0 (pollution layer draw) <- viewobj walker.

**Root cause (disasm-verified):** `finish` (0x8019B334) is the ONLY resetter
of the two model-stamp queue counts — its tail is `sth 0 -> this+0x28` (the
drain's stamp queue) and `-> this+0xD4` (the push-task queue). v3 gates the
fin CALL 1-in-N while the drain runs per frame, so on gated frames the counts
never reset: the drain re-enters every STALE entry each frame, and the first
same-model re-push (Bianco's goop stampers push their ONE persistent model
every frame) makes a single drain pass entry() the same J3DModel twice ->
J3D push-front self-loop -> the per-frame layer draw walks it forever.
Selectivity explained: Noki Bay has no stamping actors (clean twice over);
M-portal ripples are transient unique-model stamps (no same-model re-push);
Bianco freezes ~2s into the intro, the moment its stampers activate.

**Fix (`_fin_call`/`NOKI_QRESET` in fpspatch.py, stock AND BSE variants):**
fin STAYS gated (it also zeroes the degree accumulators, which must stay in
phase with the gated counting), but the gated skip path now does the queue
resets itself — r3 holds the queue object (mgr+0x70) at the call site:
`li r12,0; sth r12,0x28(r3); sth r12,0xD4(r3)`. Both `--check` suites enforce
the resets in the fin block.

## v5 (2026-08-19, same night): v4 alone was NOT ENOUGH — dedupe reinstated

The freeze REPRODUCED IDENTICALLY with v4 in place: deterministic, counters
frozen at exactly obj=521/tex=520 on both runs. So stale gated-frame queue
counts were not the operative mechanism (v4's resets stay — they are correct
by stock semantics and keep the queue one frame deep). The surviving
mechanism is a **same-frame double-push of one model**: stock tolerates it
only because the ungated counting pass draws-and-clears the buffer BETWEEN
the two pushes; with counting gated, the duplicate survives into a single
drain pass → double `entry()` → self-loop. Two pushes of one model land in
one frame the moment the intro's stampers activate (pollution-frame 521),
which is why the freeze is deterministic and intro-anchored.

**The fix was already in the repo: the v2 `noki_dedupe()` push guard —
verified in-game against this exact freeze on 2026-08-09 at 120fps.** v3's
retirement rationale ("deletes legitimate same-frame stamps") only ever
described v1's 2G-frame *batches*; with the per-frame drain the queue holds
at most one frame of stamps, and a same-frame same-model duplicate is never
legitimate (it would self-loop stock J3D too). The dedupe is also inherently
self-gating — with fin running every frame (hack off) the queue empties
between pushes and the scan never hits — so it ships unguarded under BSE.
v5 = v4 resets + dedupe, `--check` now REQUIRES the dedupe with the gate
(the exact inverse of the v3-era check). Ripple regression cannot recur
(that needed v1's batching): verify rings still land ON dot impacts.

**PC fps caveat:** with all readbacks gated 1-in-8 the PC's Bianco cap
(~170 at 240) did not visibly move before the freeze — the readback stall is
a Mac/Metal measurement and may not be the PC/Vulkan bottleneck. Profile the
PC before crediting this gate with fps there; it is kept primarily for the
Mac (measured 39% of the emu thread) and for correctness parity.

## v5 FAILED TOO — QUARANTINED AGAIN (2026-08-19 late). Forensic state dump.

**v5 (v4 resets + reinstated dedupe) froze byte-identically: THIRD freeze at
exactly obj=521/tex=520.** That determinism across three code variants kills
every queue-side theory, including v5's same-frame-double-push story. What
the third live autopsy established (all scripts in the session scratchpad —
regdump/bucketwalk/cyclehunt/streamdisasm, reusable):

- The wedge is the emu thread streaming GX forever from the pollution stamp
  draw path: stable backtrace `GX write-gather <- streamer 0x802E0390 <-
  wrapper 0x802EDE04 <- packet walk 0x802EDCA4 <- bucket walk 0x802EFB08 <-
  0x8019B4D0 (layer draw) <- viewobj walker`.
- The J3DDrawBuffer (live at 0x8145E9E0 that run) was HEALTHY: 16 buckets,
  ONE packet, no cycle, chain terminates. NOT the v1 self-loop.
- The streamer runs with `this` = 0x804045DC — the pollution GLOBALS block —
  and reads its loop bound (lhz +6 = 1910 that run) and "display list"
  pointers from float-looking words there. Either that globals block is a
  by-design material singleton whose fields were CLOBBERED, or a packet's
  material pointer dangles into it. Frame 521 ≈ 2.2s = the intro demo's
  actor handoff — the leading suspicion is an entry whose owner is torn down
  before a draw/clear, leaving the buffer referencing dead state; the gates
  perturb the entry()/draw/clear phasing enough to expose it. NOT RESOLVED.
- Empirical A/B stands: gate off -> no freeze (long play sessions); gate on
  -> deterministic freeze. And the gate did NOT raise PC Bianco fps.

**Verdict (superseded within the hour — see RESOLVED below):** call-site
gating of the counting pass looked unsafe pending a full phase-contract RE.
On the PC the fps justification was absent anyway — profile PC/Vulkan first
(thread-context SRR0 sampling of the CPU thread works and is how this freeze
was located).

## RESOLVED (2026-08-19, freezes #4 and #5): J3D push-front has no
## already-head check. Fixed at the corruption site. Offline CONFIRMED.

Freeze #4 (OFFLINE stock disc, stock 240 bundle — proving engine
independence: same ctrs 521/520, same backtrace) finally yielded the
structure: walking the drawbuffer at the SHAPE-packet level (which the
earlier bucket-level walks never descended to) found **shape packet
0x815A8708 with next(+4) == itself** — the v1 self-loop one level down.

Root cause, complete:
- `J3DMatPacket::addShapePacket` (USA **0x802EDC18**) is a bare push-front:
  `head = this->0x34; if (head) packet->next = head; this->0x34 = packet` —
  NO check whether packet is already entered. If packet == head, it writes
  `packet->next = packet`. Same shape at 0x802ED914 (head at +0x8) and the
  J3DDrawBuffer bucket entries 0x802EFA80 / 0x802EFAA0 (head at bucket[i]).
- The invariant that normally prevents re-entry is the per-frame buffer
  clear/rebuild; the noki gate's skipped passes break it in polluted
  stamping levels, so the same shape packet re-enters while still head.
  Frame 521 of Bianco Ep.1 = the intro demo's stamp cadence hits the
  double-entry. Freezes #1-#3 were all this; v4/v5 (queue resets, push
  dedupe) were upstream of the real site and couldn't reach it.

**The fix: `$J3D duplicate-entry guard v1`** (canonical:
`research/codes/j3d-dup-entry-guard-v1.txt`): 4 tiny C2s, one per insert —
`if (head == packet) skip the insert` (already entered; beqlr on the leaf
list inserts, `li r3,1; blr` on the bucket entries). Structurally kills the
1-cycle on ANY engine, any gate state, zero behavior change otherwise.
**Offline Bianco Ep.1 intro CONFIRMED surviving in-game with the stock 240
bundle's gate active.** BSE re-test pending; the BSE bundle title is now
"... v6 (safe with the J3D duplicate-entry guard — REQUIRES it enabled)".

Deployment lesson (cost one false-negative test run): BOTH launchers
rewrite `[Gecko_Enabled]` to their profile's exact set, silently dropping
hand-enabled titles. The guard is now wired in permanently: smslaunch
`config.HARDENING_FIXES` (+ auto-install of the body in `launcher.apply`,
both engines) and switch_rate `STATIC_BSE_CODES`; shipped kit INIs carry it
enabled. **Always verify hooks in MEMORY (gcmem: branch opcodes at the four
sites), never just in the INI.**

### Guard v2 (same night, freeze #6): head-check was not enough — chain-walk

With v1 the offline session got much further (pollution-frame 2865 vs 521)
then froze again: live walk showed a **3-cycle** — three DIFFERENT packet
instances of the same stamp shape (0x815ACC48 -> 0x815AB668 -> 0x815AA088 ->
back). Push-front re-entry of a packet sitting MID-chain weaves a cycle the
head-check cannot see. **v2** (`research/codes/j3d-dup-entry-guard-v2.txt`,
same INI title family): the two SHAPE-list inserts now do a bounded
CHAIN-WALK (scan for the incoming packet, skip if present; 32-hop cap fails
open to the stock insert; clobbers r11/r12/ctr only, r0/head preserved for
the resumed code). The bucket-array inserts keep the cheap head-check
(bucket chains can be long; no bucket-level weave ever observed). Any
double-entry is now a no-op — the semantically correct outcome, since the
packet is already scheduled. NEEDS-TEST: the same offline Bianco session.

### Guard v3 (2026-08-20, freeze #7 — Bianco Ep.2): a FIFTH insert family

v2 survived the Ep.1 intro and long play, then Ep.2 froze at pollution-frame
13794 with **all four v2 guards verified live and innocent**: the corpse
held a bucket-level mat-packet 1-cycle (0x813AD984 next=itself) created by
the **J3DDrawBuffer sort-entry family** — four raw push-fronts v1/v2 never
hooked: 0x802EF740 (the killer: fast path taken when packet+0x3C top bit
is set), 0x802EF7D0 (by-index chain-end), 0x802EF89C (anm-sort),
0x802EF998 (Z-sort). An exhaustive sweep of 0x802ED000–0x802F0400 confirms
these four were the ONLY remaining unguarded push-fronts. **v3 = the v2
blocks verbatim + four new capped chain-walk caves** (same v2.1
pointer-validity discipline; these sites are mid-function so the dup path
exits via mtctr/bctr to each function's epilogue — LR is stale there).
Canonical: `research/codes/j3d-dup-entry-guard-v3.txt`. Deployed to live +
kit INIs, smslaunch, switch_rate; enable v3 INSTEAD of v2 (shared hook
addresses — double-hooking corrupts). This falsifies the v2 paragraph's
"no bucket-level weave ever observed". New forensics tools persisted:
`research/scripts/j3d_cycle_walker.py` (two-level cycle walk — the older
probe silently swallowed mat-level cycles), `livedisasm.py`,
`freeze7_pktdump.py`. NEEDS-TEST: full Bianco Ep.1 + Ep.2 sessions.
