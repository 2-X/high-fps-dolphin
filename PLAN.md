# Sunshine 360fps — Findings & Plan

## Where we are
- Target: Super Mario Sunshine (GMSE01), 360fps at **correct real-time speed** (physics, music, cutscenes all normal), **no AI/pixel frame-gen**.
- Hardware: i9-14900KF, RTX 4090, 360Hz 1440p.
- Dolphin: mainline x64 release on Desktop; config at `%APPDATA%\Dolphin Emulator`.

## What we proved empirically
- The Sunshine high-fps hack is a **sim-rate multiplier**: float at `0x804167B8`, value = fps/60
  (1.0=60, 2.0=120, 6.0=360). Shipped as `$60FPS [gamemasterplc]` (value 1.0).
- **60fps is free** (render every VI field at 100% emulator speed) — this is the clean base we're on now.
- **>60fps requires running the whole console faster** (EmulationSpeed = fps/60) because the VI only
  emits 60 fields/sec. At 120 (2x): physics rescaled correct, but **music + cutscenes ran 2x** —
  they live on clocks the physics code doesn't touch. At 360 (6x): everything 6x.
- Conclusion: sim-rate approach makes **game-time run fast**; only hand-rescaled subsystems stay correct.

## Why there's no INI fix for audio
Music runs off the emulated **audio hardware clock** (AI/DSP, ~32kHz), not a game variable, so a Gecko
code can't touch it. No Dolphin setting fixes tempo at EmulationSpeed>1 (Audio Stretching = pitch/stutter,
not tempo). => both real routes require a **custom Dolphin build**.

## Route A — brute-force native 360 (trying first)
Run at 6x, then slow each subsystem 1/6 so 6x restores it to normal wall-clock:
- **Physics**: already handled by the value-6.0 code (1/6 delta).
- **Audio**: modify Dolphin `SystemTimers.cpp` audio scheduling to run 1/6 rate at 6x. Key fn:
  `GetAudioDMACallbackPeriod` (Core/Core/HW/SystemTimers.cpp:78) + AudioDMA/DSP callbacks.
- **Cutscenes / timers / animation**: run on game-time. Ideal: find Sunshine's **global frame-delta**
  var and scale 1/6 there (one lever fixes physics+cutscenes+timers together) instead of the partial
  physics-only code. Otherwise per-subsystem whack-a-mole.
- Risk: fragile, open-ended list; audio/logic desync possible. This is the path the community abandoned.

## Route B — interpolation (the "right" answer, no AI)
Keep sim at **native 60** (audio/cutscenes/timers perfect by construction). Render 360 by interpolating
**real game object transforms** (camera, Mario's matrix) read from RAM between ticks — deterministic
geometry, the same fixed-timestep+interpolated-render trick modern engines use. NOT neural frame-gen.
- Needs: custom Dolphin build that decouples present-rate from VI + reads/interpolates transforms.
- Bigger build; correct audio for free. Per project doc, this is the actual heart of the project.

## Toolchain status
- git ✅ · disk 1.6TB ✅ · winget ✅
- **VS2022 + C++ workload installing now** (was missing) · cmake/ninja come with VS
- Dolphin source cloned to `dolphin-src/` ✅

## Next steps
1. Finish VS2022 install.
2. Build Dolphin from source (first compile 20–45 min); confirm our own build runs Sunshine at 60.
3. Route A: patch audio clock to scale 1/6 with a factor; wire factor to the fps target; test 360.
4. Assess cutscene/timer breakage; hunt global frame-delta var if needed.
5. If A stays fragile → Route B interpolation on the same build.

## Config state (current: clean 60fps base)
- `GameSettings/GMSE01.ini`: ladder codes present ($60/$120/$180/$240/$360), **$60FPS enabled**.
- `Dolphin.ini`: `EnableCheats=True`, `EmulationSpeed=1.000000`.
