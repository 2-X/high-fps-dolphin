---
name: sunshine-highfps-hardware-ceiling
description: Sunshine sim-rate high-fps hack is CPU-bound at ~2x (120fps) on this Mac; higher needs Route B interpolation
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dbb6007-c95d-4861-9e85-c7c5a2202daf
---

The Super Mario Sunshine (GMSE01/USA) high-fps project uses a "sim-rate hack": Gecko codes make the game render every field + subdivide its sim delta, and Dolphin runs the console faster than real-time to restore correct speed. **Render-fps is tied 1:1 to emulation speed**: 60fps=1x, 120fps=2x, 180fps=3x, 360fps=6x.

**Key practical finding (tested 2026-07-17):** this Mac (Apple Silicon) sustains only ~2x emulation for Sunshine = the working **120fps** deliverable. At a requested 3x it delivered ~90–180fps (~1.5x) and at 6x only ~180fps — CPU/emulation-bound, **not** GPU (confirmed: same result at native 1x internal resolution). Because the console runs at half the requested multiplier, Mario always looked ~2x too fast in 180/360 tests — the tests are **confounded by the hardware ceiling**, not readable as game-logic results.

**Implication:** correct-speed 180/240/360 via the sim-rate hack is unreachable on this Mac regardless of any game-code fix — the hardware can't emulate fast enough. The 120fps we have is at the sustainable ceiling. The only path to higher present-rates is **Route B (interpolation)**: keep the sim at a sustainable 60/120 and interpolate real Mario/camera transforms from RAM between ticks, decoupling present-rate from emulation speed. See [[sunshine-simrate-mechanism]].
