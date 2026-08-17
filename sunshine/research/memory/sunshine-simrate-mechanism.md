---
name: sunshine-simrate-mechanism
description: "How the SMS high-fps Gecko codes work (USA addresses) + the \"0.5 floor\" is actually a native value, not a runtime clamp"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8dbb6007-c95d-4861-9e85-c7c5a2202daf
---

Ground-truth from disassembling the USA `main.dol` (extracted from the RVZ via `dolphin-tool extract`; capstone PPC in `work/disasm.py`). Corrects the PC handoff's assumption.

**⚠️ CORRECTION (2026-07-30, proven by disasm, supersedes the "frame-rate value" claim below):** `0x804167B8` is **NOT a frame-rate value**. It is the **`0.5` Newton-Raphson coefficient of the game's inlined square-root routine** (`frsqrte` + `fnmsubs` refinement). USA `main.dol` has **exactly 3 readers** (`0x80005A68`, `0x80005C58`, `0x800067FC`), all the same rsqrt-Newton pattern; **zero timing readers** (verified via full-dataflow xref, all base regs). The compiler deduped the timing-`0.5` and the sqrt-`0.5` into one sdata2 word (r2=`0x8041E790`, at `-0x7fd8(r2)`; sits in a const block with 600.0/60.0/50.0). Overwriting it to 2.0 **corrupts every sqrt/vector-magnitude in that TU**, which is what breaks the SMS rainbow-M portals (proximity glow needs a correct distance). The "speed change" from toggling it is a *side effect* of the sqrt corruption scaling velocities, NOT a real timestep scale. Confirmed by user A/B: sqrt=0.5 ⇒ always double-speed + M works; sqrt=2.0 ⇒ correct-speed + M broken. See [[sunshine-portal-glow-bug]]. **The real per-frame timing knob is the sub-step count (r4/r31) passed into the director pacing loop `0x802FC9AC`, not this constant.**

**The Gecko high-fps codes (USA GMSE01), as originally understood (value claim now known WRONG, see correction above):**
- `044167B8 <val>` - writes to global `0x804167B8`. Natively `0.5` (`0x3F000000`). The mod treats value = fps/60 (2.0=120fps) but this actually just corrupts sqrt; the speed effect is incidental.
- `04414904 <k>` - writes a per-frame constant to `0x80414904` (native `0.01`). The 120fps code sets `0.02` = `0.01 x value`.
- `042FCB24 60000000` - NOPs `bl 0x8034F684` (kills a call that would re-derive the delta).
- `C20066EC …` - replaces `fmr f22,f1` at `0x800066EC` with `lfs f22,[0x804167B8]; fmuls f1,f1,f22; fmr f22,f1` (scales a per-frame float by the value).

**The handoff's ladder codes ($120/$180/$240/$360) only vary `044167B8`** and leave `0x80414904` fixed at `0.02`. Hypothesized incomplete: co-scaling it to `0.01 x value` (0.03/0.04/0.06) might fix speed. **Untested/inconclusive** because the Mac can't sustain the required emulation speed to read it (see [[sunshine-highfps-hardware-ceiling]]).

**Decomp note:** the doldecomp/sms repo (cloned at `sms/`) is **JP-only** (`config/GMSJ01`, `GMSP01`; no USA config) and building needs the JP disc + MWCC toolchain. `SMSGetVSyncTimesPerSec()` returns hardcoded 30 (NTSC, unaffected by the hack); `SMSGetAnmFrameRate()=60/30=2.0`. `TMarDirector::direct()` uses integer sub-step scheduling (`600/(int)vsync`, `-5` quantum). Timing is pervasively integer-quantized; no single clamp to remove.
