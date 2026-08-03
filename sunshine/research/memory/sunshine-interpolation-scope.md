---
name: sunshine-interpolation-scope
description: Where the frame-interpolation hook goes in the custom Dolphin build (the correct fix for high-fps Sunshine)
metadata: 
  node_type: memory
  type: project
  originSessionId: 764823c6-5696-4125-89c5-057d6eca32c4
---

Full implementation scope written to `~/Dropbox/sunshine-highfps-interpolation-scope.md` (matches the audio-patch/windows-port doc convention). Interpolation is the proven-correct fix (see [[sunshine-portal-glow-bug]]): run EmulationSpeed=1.0 with ALL Gecko high-fps codes OFF (sqrt stays 0.5 → M portals work), and synthesize display frames in Dolphin.

**Present pipeline (verified in this build):** `VideoBackendBase::Video_OutputXFB` (VideoBackendBase.cpp:95, CPU thread) computes `presentation_time` + `next_swap_estimated_time`, pushes async `ViSwap` to the video thread → `Presenter::ViSwap` (Present.cpp:168) → `FetchXFB` (sets `m_xfb_entry`, an `RcTcacheEntry`=shared_ptr<TCacheEntry> with content-lock semaphore) → `Present` (Present.cpp:906) → `RenderXFBToScreen` (uses `m_post_processor->BlitFromTexture`, single-source) then `CoreTiming::SleepUntil(present_time)` + `g_gfx->PresentBackbuffer()`. Video thread pumps `AsyncRequests::PullEvents()` from Fifo.cpp:291/371 — present work is already on the GPU thread.

**v1 IMPLEMENTED + BUILDS CLEAN (2026-07-30).** Gated behind env `DOLPHIN_FRAME_INTERP=N` (unset/1 = off → stock path byte-identical). Design chosen = "fill the idle SleepUntil gap": in `ViSwap`, before `FetchXFB`, grab an extra content-lock on the current XFB → after FetchXFB retain it as `m_prev_xfb_entry` (skip on duplicate/geometry-mismatch); then before the real `Present()`, `PresentInterpolatedSubframes()` renders K-1 blended sub-frames pacing `SleepUntil(now + (present_time-now)*i/K)`. No latency added, `Present()` untouched (stock final frame). Blend = `mix(prev,cur,t)` fullscreen-triangle into an XFB-sized scratch RT, then reuse `RenderXFBToScreen`. Changes: FramebufferShaderGen.{h,cpp} (`GenerateFrameBlend{Vertex,Pixel}Shader`), Present.{h,cpp} (retention + `GetInterpolationFactor`/`EnsureBlendResources`/`RenderBlendToScratch`/`PresentInterpolatedSubframes` + members). NO GraphicsSettings/UI touched (env var instead). Built: `dolphin/build/Binaries/Dolphin.app`.

**Test config:** GMSE01.ini set to EmulationSpeed=1.0, `[Gecko_Enabled]` empty (sqrt=0.5 → portals work). Launch: `DOLPHIN_FRAME_INTERP=4 dolphin/build/Binaries/Dolphin.app/Contents/MacOS/Dolphin` (Sunshine=30fps → factor 4 = 120). User has true 120Hz panel. **Runtime-UNVERIFIED (I can't drive gameplay):** watch for Metal blend-shader compile, ImGui/OSD state across multi-present-per-ViSwap, XFB pool growth (content-lock leak), and whether idle gap exists to pace subframes. v2 later = optical-flow warp (same hooks, swap the blend shader). Blend v1 ghosts on fast motion; smooths pans.
