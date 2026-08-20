# high-fps Dolphin patch: build & setup

`high-fps-dolphin.patch` is the custom-Dolphin half of this project. The Gecko
bundles in `sunshine/gecko/` and the profiles emitted by `fpspatch.py` **do not
work on a stock Dolphin build**: they need both the code changes here *and* one
runtime setting (§3). This file documents what the patch contains, how to build
it, and the non-obvious prerequisites.

## 0. TL;DR

```bash
git clone https://github.com/dolphin-emu/dolphin
cd dolphin
git checkout $(cut -d' ' -f1 ../sunshine/dolphin-patches/UPSTREAM_COMMIT.txt)
git apply ../sunshine/dolphin-patches/high-fps-dolphin.patch
# ...then build normally (see §2), and in Dolphin enable the MEM1 override (§3).
```

Pinned upstream base: see [`UPSTREAM_COMMIT.txt`](UPSTREAM_COMMIT.txt)
(`b6d8bc299e…`, the `master` HEAD this patch was cut against).

## 1. What the patch changes (23 files, 5 independent features)

| Feature | Files | Why it's needed |
|---|---|---|
| **Gecko code-limit relocation** ⭐ | `Core/GeckoCode.cpp`, `PowerPC/MMU.cpp` | Stock Dolphin holds the whole code list in the cramped `0x80001800`–`0x80003000` window → **~406 code lines max**, silently *skipping* codes past that with only a `NOTICE` log. This patch relocates the list into over-provisioned MEM1 (`0x81800000`, capped 256 KB → **thousands** of lines) and BAT-maps it via spare pair 4. **Requires the MEM1 override (§3).** |
| **>4.4× throttle fix** ⭐ | `Core/CoreTiming.cpp`, `Core/CoreTiming.h` | `std::lround` returns a 32-bit `long` on Windows (LLP64); the GC clock × 6 (for 360 fps) overflows it, silently disabling the speed limit. Switched to `llround` + lazy throttle-clock init. Without this, **360 fps has no working throttle at all.** |
| **Route-A audio tempo** | `Core/HW/SystemTimers.cpp`, `Core/HW/DSPHLE/UCodes/Zelda.*` | When the console runs at `EmulationSpeed = G` to render high fps, scale the audio DMA period by G so DSP/AI audio plays at correct wall-clock tempo instead of G× fast. Plus DSP-desync instrumentation. |
| **Frame interpolation + overlay QoL** | `VideoCommon/Present.*`, `VideoCommon/FramebufferShaderGen.*`, `VideoCommon/Statistics.cpp`, `Core/Config/GraphicsSettings.*` | Optional XFB blend interpolation (`DOLPHIN_FRAME_INTERP=N`) and a collapsible stats overlay. 2026-08-20: pacing feedback loop fixed (floor-tracking estimator); NOT play-viable yet — see `sunshine/HOWTO-INTERPOLATION-360.md` §FIRST PLAYTEST. |
| **Non-blocking readbacks (experimental, default OFF)** | `VideoBackends/Vulkan/VKPerfQuery.cpp`, `VKTexture.*`, `VideoCommon/AbstractStagingTexture.h`, `FramebufferManager.*`, `VideoBackendBase.cpp`, `VideoConfig.*`, `Core/Config/GraphicsSettings.*` | `GFX.ini [Settings] HiFpsNonBlockingReadbacks` / per-game `[Video_Settings]`: stale-tolerant PerfQuery + EFB-peek paths without GPU fence waits. 2026-08-20 in-game A/B: slightly SLOWER at 360-target (submit overhead outweighs the fences) — keep OFF pending a submit-batching rework. |

⭐ = the two features that make the high-fps Gecko bundles function. They were
**missing from earlier revisions of this patch.** If you cloned this repo before
2026-08-11 and only got audio/interpolation changes, re-pull and re-apply.

## 2. Build

Standard Dolphin build for your platform; the patch adds no new dependencies.
- **Windows:** open `Source/dolphin-emu.sln` in Visual Studio, build `Release|x64`.
- **Linux/macOS:** `mkdir build && cd build && cmake .. && make -j$(nproc)`.

See the upstream [Dolphin build guides](https://github.com/dolphin-emu/dolphin#building-for-various-platforms).

## 3. ⚠ Required runtime setting: the MEM1 override

The code-limit relocation only triggers when Dolphin has **over-provisioned
MEM1** (retail games can't see RAM past 24 MB, so that region is guaranteed free).
You must turn this on or you're back to the ~406-line limit and codes silently
drop:

- **GUI:** Config → **Advanced** → **Enable Emulated Memory Size Override**, then
  set **MEM1** above 24 MiB (32 MiB is plenty; the list is capped at 256 KB).
- **Or in `Dolphin.ini`** under `[Core]`:
  ```ini
  RAMOverrideEnable = True
  MEM1Size = 0x02000000
  ```

When it works you'll see this in the log (ACTIONREPLAY category):
`[hifps] Gecko code list relocated to 81800000..81840000 (N code lines max), BAT4 mapped`.

## 4. Rebasing onto a newer Dolphin

The Gecko relocation depends on internal APIs (`GetRamSizeReal`, `MMU::DBATUpdated`,
BAT SPRs) that occasionally move. To rebase: check out the new upstream, `git apply
--3way` this patch, resolve, then regenerate the pin + patch:

```bash
git rev-parse HEAD > ../sunshine/dolphin-patches/UPSTREAM_COMMIT.txt   # + append the subject line
git diff > ../sunshine/dolphin-patches/high-fps-dolphin.patch
```
