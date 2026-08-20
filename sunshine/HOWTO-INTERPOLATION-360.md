# HOWTO: Frame interpolation to 360Hz (locked 180 logic + 2:1 blend)

*Written 2026-08-20 from code inspection of `dolphin-src` + the patch + all prior docs.
This is the fallback plan for a correct-speed 360Hz image (native 360 sim is host-limited
to ~303fps, HANDOFF-PC.md §3).*

## What the feature actually is

An env-gated present-path blender in our fork (`Present.cpp/.h`,
`FramebufferShaderGen.*`). With factor K, each time a **distinct** XFB arrives,
Dolphin presents K-1 extra frames of `mix(prev_frame, new_frame, i/K)` — a linear
crossfade, **not** motion interpolation — paced evenly across the distinct-frame
interval, then presents the real frame through the stock path. Multiplies the
*present* rate by K without touching game logic. Expected character: smooths pans,
**ghosts fast motion** (double-image on Mario during quick moves).

## Enablement recipe (do this tomorrow)

There is **no INI key and no GUI toggle**. The only switch is the environment
variable `DOLPHIN_FRAME_INTERP` (integer, clamped 1–8; unset or `1` = off = stock
path). It is read **once** at the first frame and cached — set it before launch;
changing it requires relaunching Dolphin.

1. **Dolphin closed** (it rewrites the per-game INI on quit), switch the kit to 180:
   - Gecko: the fpspatch 180 bundle — `python sunshine/research/scripts/fpspatch.py 180
     --no-forceopen` — enabled in the live `%APPDATA%\Dolphin Emulator\GameSettings\GMSE01.ini`
     via the usual gecko.py / dolphin-gecko flow (keep the QoL codes + `$J3D
     duplicate-entry guard v2`; disable the 240 bundle).
   - `[Core] EmulationSpeed = 3.0` in the same per-game INI (the global Dolphin.ini copy
     is inert, HANDOFF-PC.md §1).
2. **Launch with the env var set, capturing stderr** (the feature logs only via
   `fprintf(stderr, ...)` — invisible in a normal GUI launch and NOT in dolphin.log):

   ```powershell
   $env:DOLPHIN_FRAME_INTERP = "2"
   Start-Process -FilePath "C:\code\high-fps-dolphin\dolphin-src\Binary\x64\Dolphin.exe" `
       -ArgumentList @("-e", "<path-to-iso>") `
       -RedirectStandardError "$env:TEMP\interp-stderr.log"
   ```
3. **Verify it is live** in `%TEMP%\interp-stderr.log`:
   - at boot-ish: `[FRAME_INTERP] factor = 2 (env set)`
   - once per 60 distinct frames: `[FRAME_INTERP] active: +1 blends across 5.6ms
     distinct-frame interval`
   - failure mode: `[FRAME_INTERP] blend produced no texture (shader/pipeline creation
     failed) -- interpolation inactive` (printed once).
   - **The OSD FPS counter will still read ~180.** It counts emulated frames
     (`Core.cpp` → `CountFrame()`), not presents; blended presents bypass it. Confirm
     360 with a driver-level overlay (RTSS / NVIDIA stats) or by eye.

### Rate pairings

| Target image | Sim rate | Gecko bundle | EmulationSpeed | DOLPHIN_FRAME_INTERP |
|---|---|---|---|---|
| **360 @ 360Hz (plan A)** | 180 | fpspatch 180 | 3.0 | **2** |
| 360 @ 360Hz (plan B, most-validated sim) | 120 | fpspatch 120 | 2.0 | **3** |
| 360 online (BSE has no 180) | 120 | `play240.ps1 -Fps 120` kit | 2.0 | **3** |
| not this | 240 | — | 4.0 | K is integer-only; 240→360 is 1.5:1 (judder anyway, HANDOFF-PC §3) |

The interp code never reads `EmulationSpeed` — it is driven purely by the wall-clock
spacing of distinct XFBs, so it composes with any sim rate. `180 × 2` is exactly how
HANDOFF-PC.md §3 intended it to be driven.

## Design facts (verified in code, Present.cpp)

- `ViSwap` retains the previous XFB (extra content lock) and requires prev/cur to match
  in width/height/format; otherwise that frame is presented normally (self-heals next
  frame). Blank frames / geometry changes just skip interpolation.
- Blend interval = gap between the two most recent distinct frames' **intended present
  times**, clamped to **[4ms, 60ms]**; out of range → 16.67ms fallback. At 180 the gap
  is 5.56ms (safe); at 240 sim it would be 4.17ms, uncomfortably near the 4ms clamp.
- Blends render `mix(prev,cur,t)` into an XFB-sized scratch RT and go through
  `RenderXFBToScreen` (post-processing applies), paced with
  `CoreTiming::SleepUntil(base + interval*i/K)`; the real frame then sleeps to its own
  intended present time in stock `Present()` → nominally even ~2.78ms spacing at 360.
- Duplicate XFBs are **dropped** while interpolating (the blend stream covers them);
  irrelevant at 180 where every field is distinct (1:1 frames:vblanks confirmed).
- OSD/ImGui and frame dumping happen only on real frames — blends are clean.
- No added latency by design: the real frame still presents at its intended time;
  blends only fill the gap before it.
- Cost: +180 blends & presents/sec on the **video thread** — the same thread behind the
  5.17x serialization ceiling. At 3.0x sim there is headroom (180 ran at CPU 58% /
  Video 46%), but watch VPS; if 180 drops below 180 VPS the whole cadence degrades.

## Constraints

- **VSync:** keep the validated `VSync = False` first — pacing is manual
  (`SleepUntil`), designed around non-blocking presents. `VSync = True` at 360Hz would
  quantize presents to refresh slots but stacks two throttles; only try it if you see
  tearing/irregular cadence with it off.
- Fullscreen is not required; no fps-divides-refresh check exists in code. For clean
  results the monitor should be at 360Hz and `K × sim fps == refresh` (exact 2:1).
- Backend-agnostic (VideoCommon level); use the validated Vulkan config.

## Current code status: INTACT (2026-08-20)

- `Present.cpp/.h` and `FramebufferShaderGen.cpp/.h` in
  `C:\code\high-fps-dolphin\dolphin-src` are **byte-identical** to the hunks in
  `sunshine/dolphin-patches/high-fps-dolphin.patch` (`git apply --check --reverse`
  passes for these files). The `CoreTiming` support (`SleepUntil`, the `llround`
  throttle-overflow fix) also matches.
- The built binary **`dolphin-src\Binary\x64\Dolphin.exe` (2026-08-10 13:14) contains
  the feature** — it postdates the last edit to the interp files (2026-08-09 22:41)
  and the corresponding `.obj`s are fresh. This is the exe `play240.ps1` launches.
- A second, **stale** checkout exists at `C:\Users\krisb\code\dolphin-src` (binary
  2026-08-03): same interp sources, but it predates the CoreTiming `llround` fix
  (throttle silently breaks above ~4.4x there). Don't use it.
- Patch↔tree drift exists but is confined to non-interp files: the patch still carries
  diagnostic-logging hunks (TextureCacheBase / PixelEngine / CommandProcessor /
  MTLStateTracker) that have since been removed from the tree, and the tree's
  `GeckoCode.cpp` list-relocation is a newer revision than the patch's. None of this
  touches the interpolation path.
- As of tonight (Aug 20 ~00:16) the tree also has fresh **uncommitted** non-blocking-
  readback perf work (`VideoConfig`, `FramebufferManager`, `VKTexture`,
  `VideoBackendBase`) that is NOT in the Aug 10 binary. Any rebuild for that work
  carries interpolation along unchanged.

## Prior test history: NEVER PLAY-TESTED, anywhere

- **2026-07-30 (Mac):** v1 implemented ("fill the idle SleepUntil gap" design), built
  clean into `Dolphin.app`. Memory `sunshine-interpolation-scope.md` is explicit:
  **"Runtime-UNVERIFIED"**. Planned test (EmulationSpeed=1.0, Geckos off, K=4 → 120Hz)
  was never run.
- Shelved on Mac by preference: HIGH-FPS-CATALOG §1.2 — "user prefers the sim-rate feel
  (no added latency) and rejected blend v1's ghosting." The ghosting verdict is the
  *anticipated* property of a linear crossfade, not a recorded in-game observation.
- The pacing has since been revised (current code spreads blends across the whole
  distinct-frame interval — the "burst-then-stall" fix comment in
  `PresentInterpolatedSubframes`). This revision is also untested.
- **Windows:** the binary contains it, but no documented session ever set
  `DOLPHIN_FRAME_INTERP`. HANDOFF-MAC.md and HANDOFF-WIPE-BARS.md both note it as
  "env-gated, default off; ignore it."

## Open risks for the first live run (the old watch list, still open)

1. Blend shader/pipeline compile on **Vulkan/Windows** (only ever compiled on Metal/Mac
   toolchain checks) — the one-shot stderr failure line above is the tell.
2. Real cadence: blends are timed from `Clock::now()` at ViSwap, so late ViSwaps can
   bunch the blend against the real frame. Judder here would show as 360Hz that doesn't
   look smoother than 180.
3. Ghosting severity at K=2 on 180 base — much milder inputs than the Mac plan
   (5.6ms apart vs 33ms), so the old objection may not apply; judge by eye.
4. XFB texture-pool growth / content-lock leak over long sessions (extra lock per
   distinct frame is released next frame — verify VRAM is flat).
5. OSD/ImGui state across multiple presents per ViSwap (OSD is only drawn on real
   frames; watch for flicker of the FPS overlay).
6. `SleepUntil` granularity on Windows at 1.4ms sleep targets (K=2 @180 needs ~2.8ms
   accuracy; the throttle already hits this at 240, so likely fine).

## FIRST PLAYTEST (2026-08-20, PC, 180x2) — VERDICT: NOT VIABLE YET

The mode ran (factor=2, blends across 5.6ms confirmed in stderr) but Delfino
sagged to ~120fps with the HOST MOSTLY IDLE. Two distinct causes found:

1. **Pacing feedback loop (FIXED, in tree)**: sub-frames were paced off the
   raw measured distinct-frame interval, which includes delay injected by our
   own pacing sleep -> positive feedback (observed 5.6 -> 10.9ms drift). Fix:
   floor-tracking estimator in Present.cpp/.h (snap down instantly, drift up
   2%/frame). Built + verified live; insufficient alone.

2. **Critical-thread occupancy (OPEN — the real flaw)**: the interval/2
   pacing sleep + blend + extra present all execute ON THE VIDEO THREAD per
   distinct frame. At a 180 base that is ~2.8ms dead time out of a 5.6ms
   budget — the Video thread keeps <50% capacity for frame translation, so
   any scene whose translation cost exceeds the remainder collapses via
   backpressure (Delfino). It is NOT a GPU present-rate ceiling: native mode
   sustained 303 presents/sec with the Video thread genuinely busy.

**Designed fix (next session): an async sub-frame presenter** — a dedicated
thread that receives the prepared blend texture and owns the mid-interval
sleep + PresentBackbuffer (m_swap_mutex already guards presents), so the
Video thread never sleeps. Until then the mode stays parked; 240 native is
the recommended play config.
