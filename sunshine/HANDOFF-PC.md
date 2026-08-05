# PC session handoff — updated 2026-08-03 (session 2)

**Bottom line: 180fps is DONE — locked, correct speed, verified.** 360fps is **not reachable
as a logic rate** on this hardware today: the measured Plaza throughput ceiling is **5.17x**
and 360 needs **6.0x**.

Session 2 overturned three of session 1's conclusions. Where this doc and `README.md` §6
disagree, this doc wins. Corrections are marked **[CORRECTED]**.

---

## 0. The pacing model — settled, with proof

Session 1 claimed the render loop free-runs. **It does not.** [CORRECTED]

`0x802FC9A4` is the **per-frame VI governor**. All four of its `VIWaitForRetrace` calls
belong to it (the epilogue at `802fcb40`–`802fcb58` matches its `stwu r1,-0x20` prologue —
they are not separate functions):

```
802fc9c4: b      802fc9cc          ; jump into the gate
802fc9c8: bl     VIWaitForRetrace  ; (0x8034f684)
802fc9cc: bl     VIGetRetraceCount
802fc9d0: lwz    r0, 0x84(r30)     ; target
802fc9d4: subf   r0, r3, r0        ; target - count
802fc9d8: cmpwi  r0, 1
802fc9dc: bgt    802fc9c8          ; while (target - count > 1) wait
...
802fcb24: bl     VIWaitForRetrace  ; <-- the Gecko NOP (042FCB24 60000000)
802fcb30: bl     VIGetRetraceCount
802fcb3c: stw    r0, 0x84(r30)     ; target = count + r31   (r31 = fields/frame = 2)
```

`0x8034f684` is `VIWaitForRetrace` beyond doubt: `OSDisableInterrupts` → sleep on the
retrace queue until `retraceCount` (`-0x58f0(r13)`) changes → `OSRestoreInterrupts`.

With `target = count + 2`, the gate at `802fc9c8` blocks until `count >= target - 1` — i.e.
**one field**. NOPping `802fcb24` removes the *second* field, converting 30 → 60 frames per
emulated second. **One retrace wait per frame always remains.** The loop is retrace-locked.

Therefore:

```
real fps   = 59.94 x EmulationSpeed        <- HARD CEILING, cannot be exceeded
game speed = real_fps / (60 x framerate_global)
```

Speed is correct **iff the host actually sustains that multiplier**. This is purely a
throughput problem. The achievable ladder is exactly 120=2x, 180=3x, 240=4x, 360=6x.

**Independent confirmation:** frames:vblanks is 1:1 in every run ever logged —
166260:167639 (session 1), 20290:20292 (session 2 locked-180). A free-running loop would
diverge wildly.

Why session 1 got this wrong: its own §8 warning. The "free-run" read came from aggregating
loading screens (2400+ fps) with gameplay, plus stretches where the Z-on-TAB fast-forward
bug had disengaged the throttle entirely.

---

## 1. THE GOTCHA THAT COST THIS SESSION SEVERAL RUNS

**`User/GameSettings/GMSE01.ini` `[Core] EmulationSpeed` overrides BOTH
`User/Config/Dolphin.ini` AND the `-C Dolphin.Core.EmulationSpeed=` command-line flag.**

The per-game INI had `EmulationSpeed = 6.0` left over from session 1. Every run — including
ones explicitly launched with `-C ...EmulationSpeed=3.0` — silently ran at 6.0. Because 6.0
is *above* the machine's 5.17x ceiling, they all ran effectively unthrottled, which looks
exactly like "the throttle doesn't work."

Symptom to recognise: the game runs **fast**, and measured VPS ignores whatever speed you set.

**Always change speed in `User/GameSettings/GMSE01.ini`, not `Dolphin.ini`.**

---

## 2. Measured results (Vulkan, P-core pinned, Plaza `F2` savestate, batch mode)

### Throughput ceiling — run unthrottled and see what the host delivers

Warmed steady state: **310 VPS = 5.17x**, and it is *rock stable* (307.4 / 310.2 / 307.5 /
306.5 / 311.0 / 309.1 / 310.2 / 311.1 over 10s windows from 90s to 180s).

**Shader-cache warm-up is ~80 seconds.** Windows before that read 262–290 VPS. Any benchmark
shorter than ~90s measures the cold cache, not the machine. Session 1's 240–260 and 290–330
figures were partly cold.

| target | needs | vs 5.17x ceiling | verdict |
|---|---|---|---|
| 120 | 2.0x | 2.59x margin | trivial |
| **180** | **3.0x** | **1.72x margin** | **locked, verified correct** |
| 240 | 4.0x | 1.29x margin | should hold; untested |
| 360 | 6.0x | **0.86x — short by 16%** | not reachable today |

### Locked 180 — the validated configuration

| metric | value |
|---|---|
| mean VPS | **179.65** (target 179.82 = 3.0 x 59.94) |
| **game speed** | **0.9990x** |
| worst 2s window | 173.0 VPS (96%) |
| frames:vblanks | 20290:20292 (1:1) |
| CPU thread | 57.7% of one core |
| Video thread | 46.1% of one core |
| VK submission | 7.8% |

### Backend — Vulkan wins, D3D11 answered [CORRECTED §3.4 / §4.1]

| backend | VPS | mult | note |
|---|---|---|---|
| **Vulkan** (pinned) | **307.4** | 5.13x | best |
| Vulkan (no pinning) | 288.7 | 4.82x | |
| D3D12 (pinned) | 265.8 | 4.43x | |
| D3D11 (pinned) | 263.6 | 4.40x | **tested — no win** |

D3D11 was session 1's top "to do". It is dead. Caveat: the three 45s runs are partly inside
the warm-up window, so their absolute numbers are pessimistic — but Vulkan *unpinned* still
beat D3D12 *pinned*, so Vulkan's advantage is robust.

### Host CPU tuning — real but smaller than hoped [CORRECTED §4.3]

P-core pinning (`ProcessorAffinity = 0xFFFF`, logical 0–15) + `High` priority: **+6.5%**
(288.7 → 307.4 VPS). Session 1 estimated 10–20%. Ultimate Performance power plan was
**already active**, so that lever was already spent.

---

## 3. Why 360 is blocked — and the one idea left

At the 5.17x ceiling **neither hot thread is saturated**: CPU 77.2%, Video 77.1%. Scaled to
6.0x they would need ~89% each, which individually fits. The loss is **CPU↔Video
serialization** — almost certainly the game's per-frame draw-sync forcing a barrier so the
two threads cannot overlap. Both sitting at the same ~77% is the signature of a lock-step
barrier, not of a producer/consumer bottleneck (which would saturate one side).

Untried idea worth one experiment: affinity is currently `0xFFFF`, which lets Windows place
the CPU thread and Video thread on **hyperthread siblings of the same physical core**.
Pinning to `0x5555` (logicals 0,2,4,…,14 — one per physical P-core) guarantees they never
share silicon. Could be a meaningful slice of the missing 16%.

If that falls short, the honest path to a 360Hz *image* is **locked 180 logic + frame
interpolation to 360** (2:1, exact). That source is already in
`dolphin-patches/high-fps-dolphin.patch` (`Present.cpp/.h`, `FramebufferShaderGen.*`).

Note also that **240 into a 360Hz panel is 1.5:1 — uneven cadence, visible judder.** Even if
240 runs, 180 is the better target for this display.

---

## 4. Current validated config

`User/GameSettings/GMSE01.ini`: `[Core] EmulationSpeed = 3.0`; enabled Gecko =
**`$180fps + TRUE-FIX v4`** only (added this session; = v3 body with framerate word
`40400000` and the FX add-constant at `C002DD68`). Mirrored into
`sunshine/dolphin-config/GameSettings/GMSE01.ini`.

`User/Config/Dolphin.ini`: `GFXBackend = Vulkan`, `CPUThread = True`,
`OverclockEnable = False`, `AudioPreservePitch = True`, `AudioBufferSize = 136`,
`DSPHLE = True`. (`EmulationSpeed` here is **inert** — see §1.)

`User/Config/GFX.ini`: `InternalResolution = 3` and `EFBScaledCopy = True` **restored** —
both free, the 4090 sits at ~15%. `VSync = False`, `ShaderCompilationMode = 0`,
`LogRenderTimeToFile = True`, `ShowFPS/ShowVPS/ShowSpeed = True`.

**Lowering resolution does nothing** — confirmed twice. The video thread's cost is FIFO
parsing / vertex loading / draw submission, proportional to *frames drawn*, not pixels.

---

## 5. Still open

- **`$180fps + TRUE-FIX v4` correctness is unvalidated by eye.** No confirmation yet that
  particles render and M portals glow at 180. The FX math is right (`60/180 = 0.333`, `+1.0`
  → `(int)1`), but nobody has looked. **Do this first next session.**
- The v3-vs-script question from `README.md` §2 is still open.
- 240 (`EmulationSpeed = 4.0` + framerate word `40800000`) is untested.
- The `0x5555` HT-aware affinity experiment (§3).
- `04414904` co-scaled const: the plain `$120FPS`/`$180FPS` ladder codes carry it, the
  TRUE-FIX bundles do not. v2/v3 were confirmed correct at 120 without it, so it is probably
  unnecessary — but it has never been explained.

## 6. Environment — session 1's §7 is STALE [CORRECTED]

All of these are **installed**, contrary to session 1:

- **Python 3.12.10** at `C:\Users\krisb\AppData\Local\Programs\Python\Python312\python.exe`
  (`python3` is the Store stub — use `python`). **capstone 5.0.7** present.
- **VS Build Tools 2022** (MSVC 14.44.35207, Windows SDK 10.0.26100), with CMake and Ninja
  bundled under `BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\`.

`sms_dump.py` has a hardcoded Mac `DOL=` path — override it, e.g.
`sed 's|^DOL=.*|import os; DOL=os.environ["SMS_DOL"]|'`.

**Patched Dolphin:** built this session at `C:\Users\krisb\code\dolphin-src` (upstream
`b6d8bc2`, patch applied cleanly). README §4's warning that the audio tempo factor "was
written for 2x" is **wrong** — the patch reads `Config::Get(Config::MAIN_EMULATION_SPEED)`
at runtime and generalises to any speed:

```cpp
const float speed = Config::Get(Config::MAIN_EMULATION_SPEED);
if (speed > 1.0f) period = static_cast<u64>(period * speed);
```

**Build-version mismatch:** the patched build stamps **2606-184**; the portable binary in
`dolphin-bin/` is **2606-278**. Savestates are build-locked, so **`GMSE01.s02` will not load
on the patched build** — make a fresh benchmark savestate there. The `.gci` memcard save is
portable and unaffected.

---

## 7. Measurement methodology (reusable — this part of session 1 was right)

- `render_times.txt` / `vblank_times.txt` are **per-frame intervals in ms**, one per line.
  `fps = 1000 * N / sum`. They only flush on close — stop Dolphin to collect.
- Benchmark harness: `Dolphin.exe -e "<rom>" -s "<state>" -b` boots straight into the
  savestate with no UI. Reproducible, and the character stands still.
- **Run at least 90 seconds** and read the tail — the shader cache needs ~80s to warm.
- To measure the ceiling, set `EmulationSpeed` *above* what the host can do and see what it
  delivers. One run answers "is target X reachable" for every X.
- Thread names via `GetThreadDescription` P/Invoke; `ProcessThread.TotalProcessorTime`
  deltas over a wall-clock window give % of one core.
- **Do not aggregate across a session.** Always chronological windows, one area, steady state.
- Beware background load — a session was wasted measuring while Palworld ran. Check first.

---

# ★ SESSION 3 (2026-08-04): 180fps WORKS. Root cause was the substep scheduler.

**Status: 180fps runs at correct speed, smooth, cutscenes intact.** Two bugs remain
(edge-triggered input, level BGM). Everything below supersedes §3's "movement scales with N"
framing — that was a symptom, not the cause.

## S3.1 The actual mechanism (this is the important part)

`TMarDirector::direct` = **0x80299838**. It runs a fixed-timestep scheduler:

```
80299850: bl   SMSGetVSyncTimesPerSec   -> f1 = 60*G
80299854: fctiwz                        -> (int)
8029985c: li   r3, 0x258                ; 600
8029986c: divw r25, r3, r0              ; budget = 600 / (int)(60G)      <- per frame
80299938: acc = director->0x54 ; acc += budget ; store
  8029994c LOOP HEAD: if (flags0x4c & 0x4000) -> PRE-work @80299c28
  80299958   substep body (r28++ ; if r28==1 flags|=0x2000)
  80299974   acc -= 5                                                     <- quantum
  80299980   if (acc < 5) flags |= 0x4000        ; mark last substep
  80299bf4   if !(flags & 0x4000) -> 80299d08 (clear 0x6000) -> b 8029994c
  80299c00 POST-work -> 80299c24: b 80299d24 -> return
```

**One substep = 5/600 = 1/120 s. SMS simulates at a fixed 120 Hz** — stock 30fps runs 4
substeps/frame, 120fps runs exactly 1. That is why 120 is flawless: one render per sim step.

**The bug:** the loop always runs **at least one substep per frame** (the exit flag is cleared
by the PRE-work block before the head re-tests it). At G=3 budget = `600/180` = **3**, below
the drain of 5, so the accumulator can never gate and you get exactly 1 substep/frame:

```
sim rate = fps  (not 120)   ->   speed = fps/120 = 179.82/120 = 1.5x
```

That is the whole 1.5x mystery. It is also why the G=6 probe changed nothing (budget 1 is
still floored to 1 substep) while **cutscenes went slow-mo** — cutscenes are driven off the
budget, gameplay off the floored substep count. The framerate global was never the lever.

`director->0x54` (the accumulator) is read/written by **only** those 5 instructions — nothing
else in the game depends on the 600/5 scale. Verified by xref.

## S3.2 The fix ladder (all in `GameSettings/GMSE01.ini`)

- **v6** `C2299948` — skipped the loop by jumping to the function's return. **Speed became
  correct at 180fps** (proof of diagnosis) but flashed black and hung the audio: it skipped
  the per-frame PRE- and POST-work too.
- **v7** `C2299958` — gate at the loop body instead; on a zero-substep frame set `0x4000`
  (so next frame still runs PRE-work), `li r29,0` (return value), and jump to **POST-work
  0x80299c00** rather than past it. **This is the one that works.**
- **v8** = v7 + ×3 granularity, because `600/180` truncates 3.333→3 and loses 10%
  (sim 107.9 Hz vs 119.88 → "slightly slow even at a steady 179"):

```
0429985C 38600708   ; numerator 600 -> 1800
04299974 3803FFF1   ; drain 5 -> 15
04299980 2C00000F   ; loop-continue compare 5 -> 15
```
  (and the C2's own threshold 5 -> 15). Gives **exactly 119.88 Hz at stock / 120 / 180 / 360**.
  240 is the odd one out (`1800/240` = 7, →111.9 Hz); it needs a ×12 scale (7200/60).

## S3.3 Still broken at 180

1. **Edge-triggered input is unreliable** (~half of jumps lost; other one-shot actions too;
   analog movement is fine). Almost certainly the pad latch (`pressed = now & ~prev`) advances
   every frame while the check only runs on simulation frames, so presses landing on a skipped
   frame are latched away unread. **Fix: gate the pad read on the same accumulator.** The pad
   read has NOT been located yet — ruled out: `0x80298e80` (director state-machine dispatcher,
   13-entry jump table @0x803DF05C) and `0x80360400` (GX flush to the 0xCC008000 write-gather
   pipe). Look at the virtual `perform(-1,&msg)` chain on director fields
   0x40/0x38/0x3c/0x1c/0x20/0x24.
2. **Level BGM** — silent under v7, "first tone only" under v8. Cutscene music is fine. The
   scale-corruption theory is dead (see S3.1 xref), so it tracks the substep *rate*. No theory yet.

## S3.4 Tooling built this session

- `gcmem.py` — reads GameCube memory out of a live Dolphin process. Finds MEM1 by matching the
  `VIWaitForRetrace` prologue from `main.dol`, then translates 0x80xxxxxx to host pointers.
  **Use this first** instead of inferring machine state from feel; it settled G=3.0 vs 6.0
  immediately after several wasted rounds of guessing.
- `xref.py` (find all r2/r13-relative refs to an address), `callers.py` (find `bl` sites),
  `findconst.py` (scan the SDA pool for a float value).

## S3.5 TRAP: the benchmark savestate is poisoned

`User/StateSaves/GMSE01.s02` was captured during the 360 session and **restores G=6.0,
overriding whatever Gecko code is enabled** — confirmed by reading memory after loading it.
Any speed conclusion drawn from an `F2` run is invalid. Throughput/VPS numbers are unaffected
(those are Dolphin-side). **Boot clean, or make a fresh savestate.**

## S3.6 TRAP: EmulationSpeed lives in two places

Set it in **both** `User/GameSettings/GMSE01.ini` `[Core]` **and** `User/Config/Dolphin.ini`.
A mismatch (per-game 2.0, global 3.0) produced "movement *and* audio both 1.5x fast", because
the emulator ran at one value while the audio patch read the other. Also never write these
files with PowerShell `Set-Content -Encoding UTF8` — it adds a **UTF-8 BOM** and Dolphin then
fails to parse `[Core]` at all.

## S3.7 Correction to §3 / README

The Mac **did** have correct 120fps audio (it ran the patched build). Session 2's claim that
its 120 was "accidentally right because the hardware was the limiter" is wrong: with the
retrace lock, fps = 59.94 x N always, so N=2 gives a genuinely correct 120.
