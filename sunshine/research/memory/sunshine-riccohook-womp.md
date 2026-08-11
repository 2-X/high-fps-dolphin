# Ricco hook/gondola slide-clank SE — cadence gate (v1, 2026-08-10)

**Symptom:** near Ricco Harbor's cable hooks (the ride-basket "gondola" hangs
from one), the harbor clank plays "womp womp womp, a little staticy, faster
the more fps" — reported at 240fps WITH the full bundle including the 30 Hz
audio-pump gate, so the pump alone does not tame this emitter.

**Actor (decomp `Enemy/RiccoHook.hpp`, impl stub — RE'd from the USA dol +
live vtable scan):** `TRiccoHook` (TSpineEnemy, "フック", 4 instances in
Ricco), vtable USA 0x803B8344, ctor 0x800c7dac, `perform` 0x800c7a54.
Sounds: `MSD_SE_OBJ_CRANE_SIDEMOVE1` 0x3034 / `_SIDEMOVE2` 0x3035, chosen by
`mInstanceIndex`(+0x7C) parity — per-hook variety, NOT a time alternation.

**Root cause:** `TRiccoHook::perform` (move cue) requests the slide clank on
EVERY tick once `mTimer`(+0x154) reaches 0, and nothing re-arms the timer
(it is loaded once from a hit-table param at 0x800c7710). JAudio collapses
the flood into ~one audible retrigger per rendered frame: 30/sec stock = the
designed harbor clank, render-rate under the hack. Same class as the
[[sunshine-cogwheel-creak]] but the 1-in-4-substep form was NOT used: whether
this perform tick is substep- or render-paced was not conclusively pinned, so
the gate keys a rendered-frame clock instead, which is correct either way.

**Fix (in `fpspatch.py riccohook_se_gate(fps)`, `--no-riccohook` to omit;
reference `research/codes/riccohook-womp-gate-v1.txt`):** C2 at 0x800C7AB8
(the `lha r0,0x7C(r29)` parity load — sole entry to both SE call sites),
gating to 1 rendered frame in FPS/30 on the **audio pump's own low-arena
frame counter** (0x8000_16F8, incremented once per rendered frame at
MSound::mainLoop entry by `audio_pump_gate`). Keying that counter caps
requests at the native 30/sec wall-clock AND phase-locks them near
pump-processed frames. Gated ticks bctr to the function's own epilogue
0x800C7B28 (both SE paths converge there); the mTimer bookkeeping sits above
the hook, untouched. Clobbers r0/r11/r12/ctr/cr0 — all dead at the hook.
Overwritten original A81D007C, dol-verified. Fail-open: no pump cave → the
counter stays 0 → modulo passes every tick = stock.

**How found:** live MEM1 actor scan while the user sat in Ricco (712 objects
dumped by vtable match — the scratchpad `liveactors.py` pattern: scan for
TMapObjBase-family vtables found by similarity against 0x803C2AB8, then read
name ptrs) → only Ricco actor class with per-tick SE emission = フック; SE
callee pair (gate 0x800132b4 / start 0x800189d4) enumerated across the whole
dol by `bl`-target scan with `li r3/r4` backtrack. The KANRANSYA_RAPID enum
red herring: 0x3086 appears NOWHERE in the USA dol.

**Ear-test to confirm (pending):** stand near / ride the Ricco gondola basket
at 240fps — the clank cadence should match the stock 30fps harbor rattle. If
it instead sounds sparse or gappy, the SE may need per-processed-frame
keep-alive; then move the divisor from FPS/30 to a smaller value or gate
inside JAudio's restart path instead. See [[sunshine-fpspatch-generator]],
[[sunshine-highfps-bug-surface]].
