---
name: sunshine-audio-fix
description: "Complete recipe that makes SMS 120fps audio correct (tempo + pitch) — two halves, binary + config"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dbb6007-c95d-4861-9e85-c7c5a2202daf
---

The working 120fps Sunshine audio (correct tempo AND pitch) needs **two halves together**:

1. **Binary patch (tempo):** `Source/Core/Core/HW/SystemTimers.cpp`, `GetAudioDMACallbackPeriod` — multiply the period by `Config::Get(Config::MAIN_EMULATION_SPEED)` when speed>1. Compiled into our custom Dolphin only. Saved as `~/Dropbox/sunshine-highfps-audio.patch`.
2. **Config (pitch):** `AudioPreservePitch = True` in `Dolphin.ini [Core]`. Dolphin's mixer does `in_sample_rate *= emulation_speed` (pitches up 2x) unless this is set — this was the missing piece that caused the original "high-pitched audio." Also `EmulationSpeed=2.0`, `EnableCheats=True`, Gecko `$120FPS`, and `AudioBufferSize=136` (default 80 underran at level-load → mixer's fill-audio-gaps looped a "frozen chord").

**Key gotcha:** launching *stock/official* Dolphin (not our build at `dolphin/build/Binaries/Dolphin.app`) plays audio sped-up again — the tempo fix is in the binary, not a setting. Config dir is shared between builds, so only the binary distinguishes them.

Residual: streamed cutscene/intro audio (separate mixer path) still uncompensated. Windows port guide: `~/Dropbox/sunshine-highfps-windows-port.md`. See [[sunshine-highfps-hardware-ceiling]], [[sunshine-simrate-mechanism]].
