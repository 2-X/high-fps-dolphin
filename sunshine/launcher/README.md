# SMS high-FPS launcher (Textual TUI)

One screen to configure and launch Super Mario Sunshine at high FPS — online or
offline — with a chosen FPS, FOV, and set of QOL fixes, saved as named profiles.

```
sunshine/launcher/sms          # run it (bootstraps its own venv on first run)
```

## What it does

- **Profiles** — save / load / edit / duplicate / delete named setups. The last
  one you launched is remembered and reselected next time. Stored in
  `profiles.json` (+ `last`), right next to the app.
- **Online / Offline** — one selector; it picks the disc *and* the code set:
  - **Offline** → the plain **Super Mario Sunshine (USA).rvz** disc + our stock
    high-fps Gecko kit. **Any FPS** (multiple of 60 ≥ 120) — the launcher runs
    fpspatch to build the bundle. Solo, no server.
  - **Online** → the **BSMSO / Better Sunshine Engine** disc. FPS is a *native*
    BSE setting (30 / 60 / 120, or 240 / 280 / 320 on the `-highfps` fork disc),
    snapped to the nearest. Adds the server + bridge (+ optional ghost bot).
- **Aspect / widescreen** — the Aspect dropdown (16:9 / 16:10 / **4:3 no
  widescreen**) is the whole widescreen control. Offline it enables the matching
  projection Gecko (`$Widescreen` for 16:9, a generated `$Widescreen 16:10` for
  16:10) **plus the level-entry curtain/wipe fix**; **4:3 applies no widescreen
  code at all** (native pillarboxed). Online it sets BSE's native aspect. It also
  sets Dolphin's display aspect. No separate widescreen toggle.
- **FOV** — type the **horizontal** FOV (the normal game number, ~70–120) and the
  launcher converts it to the vertical fovy the `$FOV` Gecko sets (per aspect) and
  reuses/builds that code. **Leave it blank to apply no FOV code at all** — the
  game keeps its stock FOV.
- **QOL toggles** — only genuine preference codes: Camera look-up, FLUDD aim
  invert, Save-box Continue-on-top, Tank controls. The framerate *correctness*
  fixes are **auto-applied**, not toggles: offline they're baked into the fpspatch
  bundle; online they're the BSE baseline set (particle parity, SE/wipe/anim-rate
  pacing, blue-coin timer, …) enabled for you.
- **HD portals** — a checkbox (works in both modes). On, the launcher installs
  our pruned UHD texture pack (Delfino M-portal textures + FLUDD/lives/coins
  HUD, digits, shine icons, episode-select wordmarks) into Dolphin's
  `Load/Textures/GMSE01/` and turns on `HiresTextures`/`CacheHiresTextures` for
  SMS. Both discs are GMSE01, so it applies offline and online alike; the
  `GMSE01` folder shadows any older full `GMS` pack. Off just disables hires
  textures for SMS (files stay on disk).
- **Generate-if-missing, reuse-if-present** — for the offline FPS bundle and the
  FOV code. The preview shows which already exist and which will be built.

## The launch flow (what "Apply & Launch" runs)

1. Quit Dolphin (so it can't rewrite `GMSE01.ini` on exit).
2. Generate the FOV code if this angle was never built, and add it to `[Gecko]`.
3. Set the **exact** `[Gecko_Enabled]` list: FOV + the always-on baseline fixes +
   whichever QOL toggles are on (nothing stale left enabled).
4. Set `[Core]` `EnableCheats=True`, `EmulationSpeed=FPS/60`, `AudioPreservePitch`.
5. Set the display aspect (`[Video_Settings]`), and MEM1=64MB (BSE puppet heap).
6. Set the display aspect + (if **HD portals** on) install the pruned pack to
   `Load/Textures/GMSE01/` and set `HiresTextures`/`CacheHiresTextures` in
   `[Video_Settings]` (`hdtextures.apply`).
7. Boot the right ISO; then poke the native FPS/aspect — offline: `set_bse_fps.py`;
   online: server + `bridge.py` (+ ghost), which re-assert it every loop.

## Keys

`Ctrl+S` save · `Ctrl+L` apply & launch · `Ctrl+R` refresh preview · `Ctrl+Q` quit.

## Layout

- `smslaunch/config.py`   — paths, ISO/FPS/aspect maps, the QOL catalog.
- `smslaunch/codegen.py`  — fpspatch FPS bundle + templated `$FOV N` generator.
- `smslaunch/inieditor.py`— safe GMSE01.ini editing (Dolphin-quit guard + backup).
- `smslaunch/launcher.py` — `apply()` + `launch()` orchestration, read-only `plan()`.
- `smslaunch/profiles.py` — profile schema + JSON store + last-used.
- `smslaunch/app.py`      — the Textual UI.

## Notes / limits

- Offline FPS: any multiple of 60, floor 60 (60 = native, no bundle; ≥120 builds
  the fpspatch bundle; no upper limit). Online FPS: the BSE native set
  (30/60/120/240/280/320); 240+ needs `BSMSO-GMSE01-highfps.iso`. Type freely —
  the field doesn't snap while you type; the preview shows the effective value.
- FOV input is **horizontal** degrees; the code sets the matching vertical fovy
  for your aspect (so the same number gives the same feel on 16:9 vs 16:10).
- Both discs are GMSE01, so they share one `GMSE01.ini` — the launcher rewrites
  the exact `[Gecko_Enabled]` set on each launch so the two never cross-contaminate
  (no fpspatch bundle under BSE, no BSE codes on the stock disc).
- Every INI mutation backs up to `GMSE01.ini.bak` first and refuses to run while
  Dolphin is alive.
