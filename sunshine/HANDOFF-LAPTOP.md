# Laptop session handoff — 120fps kit (created 2026-08-11)

**Goal:** play Sunshine at **120fps** on the laptop with the exact same fixes as the
desktop 240fps setup. Everything you need is in this repo.

## 1. Setup (Windows laptop)

1. Install mainline Dolphin (x64 release). Launch it once so
   `%APPDATA%\Dolphin Emulator\` exists, then quit it.
2. Copy from this repo into `%APPDATA%\Dolphin Emulator\`:

   | From | To |
   |---|---|
   | `dolphin-config/GameSettings/GMSE01.ini.laptop120` | `GameSettings\GMSE01.ini` ← **rename, drop the suffix** |
   | `saves/01-GMSE-super_mario_sunshine.gci` | `GC\USA\Card A\` |
   | `saves/SRAM.raw` | `GC\` |
   | `dolphin-config/Profiles/GCPad/*.ini` | `Config\Profiles\GCPad\` |
   | `dolphin-config/GCPadNew.ini`, `GCKeyNew.ini`, `Hotkeys.ini` | `Config\` (Windows dialect, from the desktop) |

   Save + SRAM refreshed **2026-08-11 00:54** (tonight's desktop session).
3. Graphics: Vulkan backend if available. Don't copy the desktop `GFX.ini` blindly —
   set `HiresTextures`/`CacheHiresTextures` only if you also copy the texture pack
   (the 4K pack is probably too heavy for a laptop; the 1080p zip in `textures/` is safer,
   or skip HD textures entirely).
4. Controller: load the GCPad profile, then re-pick the Device (name differs per machine)
   — bindings carry over.

The INI already has `EmulationSpeed = 2.0` in `[Core]` — the per-game INI overrides
both `Dolphin.ini` and any `-C` command-line flag (HANDOFF-PC §1 gotcha), so no other
speed setting is needed.

## 2. What's enabled (identical to the desktop set, 120 bundle instead of 240)

- `$SMS 120fps bundle (fpspatch, no-ForceOpen)` — regenerated 2026-08-11 with current
  fpspatch: includes the NPC talk-initiation fix and the skid U-turn fix from tonight,
  plus everything prior (BGM, StarFix, game-clock, Poink, Petey/anmrate, Noki gate,
  cogwheel SE, wipe pacing, audio-pump, THP repace, Ricco hook gate). The blue-coin
  lifetime fix **is** included at 120 (it was calibrated at 120 — this is the one rate
  where it's exactly right).
- `$SaveBox: Continue on top (blue coins)`
- `$Camera look-up extension v10`
- `$FOV 60`
- `$Widescreen`
- `$FLUDD Aim Invert v2 (up aims up, squat + first-person)`

`$Widescreen wipe fix v2` and `$GameHeap 7MB (HD portals)` are defined but deliberately
unticked (see README §1 update notes 2026-08-11).

## 3. If the laptop can't hold 120 with widescreen

Widescreen renders ~33% more pixels, which costs GPU/video-thread time. If you see
sustained slowdown (game runs slow-motion, speed < 100%):

1. Open Properties → Gecko Codes for GMSE01 and **untick `$Widescreen`** — that's the
   whole toggle; the game falls back to 4:3. (Untick in the Dolphin UI, or quit Dolphin
   first and remove the `$Widescreen` line from `[Gecko_Enabled]` — never edit the INI
   while Dolphin runs, it rewrites the file on close.)
2. Still short? Drop internal resolution (Graphics → Enhancements) before touching
   anything else — the fps ladder needs the *host* to sustain 2.0x throughput.
3. Nuclear option: `EmulationSpeed = 1.0` + only the `$60FPS`-style base gives free
   60fps at native speed on any hardware.

## 4. Audio at 120fps — needs the patched Dolphin build

At `EmulationSpeed = 2.0` a stock Dolphin plays music/cutscene audio **2x fast** (audio
runs off the emulated DSP clock — no INI fix exists, see `PLAN.md` at repo root).
The fix is the custom build: apply `dolphin-patches/high-fps-dolphin.patch` to Dolphin
source and build (see HANDOFF-INPUT-BUG.md for build paths + launch command). The INI
already carries `AudioPreservePitch = True` + `AudioBufferSize = 136` for that build.

If you play on stock Dolphin in the meantime, the game is fully playable — just
chipmunk music. Everything else (physics, timers, inputs, portals) is correct via
the Gecko bundle.

## 5. The game image

`Super Mario Sunshine (USA).rvz` is not in git — copy it from the desktop or the Mac
(`/Applications/gamecube/` there). Use the **vanilla** image; the HD-portal ISO needs
`$GameHeap 7MB` ticked.
