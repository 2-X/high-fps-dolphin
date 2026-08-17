# Route A: audio compensation patch (draft, apply AFTER vanilla build passes)

## Goal
When the console runs at N× (EmulationSpeed=N) to render high fps, make DSP/AI audio play at
correct **wall-clock tempo** instead of N× fast, by slowing the audio subsystem 1/N in game-cycles.

## Mechanism
Audio DMA is scheduled every `callback_period` CPU cycles in `AudioDMACallback`. The game's audio
engine is driven off that same AI interrupt, so scaling the period scales the whole audio subsystem
coherently (generation + playback), avoiding dropout. Multiply the period by N so it fires 1/N as
often in game-cycles → at N× emulation = 1× wall-clock tempo.

## Patch site
`Source/Core/Core/HW/SystemTimers.cpp`, `GetAudioDMACallbackPeriod()` (~line 78).
Add include: `#include "Core/Config/MainSettings.h"` (for MAIN_EMULATION_SPEED).

## First-cut change
```cpp
static int GetAudioDMACallbackPeriod(u32 cpu_core_clock, u32 aid_sample_rate_divisor)
{
  u64 period = static_cast<u64>(cpu_core_clock) * aid_sample_rate_divisor /
               (Mixer::FIXED_SAMPLE_RATE_DIVIDEND * 4 / 32);
  // Route A high-fps audio compensation: keep tempo at real-time when console runs fast.
  const float speed = Config::Get(Config::MAIN_EMULATION_SPEED);
  if (speed > 1.0f)
    period = static_cast<u64>(period * speed);
  return static_cast<int>(period);
}
```

## Recipe once patched
- `EmulationSpeed = 6.0` (drives 6× console speed AND audio compensation)
- Gecko `$360FPS` (value 6.0 @ 0x804167B8) for physics
- Test: does music play at correct tempo at 360fps?

## Open risks / iterate empirically
- Multiple audio paths: `m_dma_mixer` (32kHz DSP, likely music/SFX) vs `m_streaming_mixer`
  (48kHz streamed, maybe voice/some BGM/cutscene audio). This patch only scales the DMA (DSP) path.
  Streaming audio may need a parallel fix (AudioInterface AIS / streaming period).
- Mixer rate-control/resampling may partially fight the change → watch for pitch vs stutter.
- Cutscenes/timers are separate (game-side); not addressed here.
- Should be gated behind its own config flag before it's a real feature (it changes fast-forward
  audio behavior globally). For first validation, EmulationSpeed-tied is fine.
