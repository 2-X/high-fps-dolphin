# Widescreen wipe-bars bug — investigation state (2026-08-04, paused)

> **2026-08-11 UPDATE — `$Widescreen wipe fix v2` DISABLED (unticked in live + kit
> INIs; definition kept).** Its `C2182DD8` ortho stretch (half-width ×0.0625×12 =
> ×0.75 → all wipe DRAWING magnified ×4/3 about screen center) is copy/draw-
> inconsistent for the EFB-copy wipes: `Hx_Test5` copies AND clears its tiles at
> unstretched EFB coordinates, then draws the fans up to ±107px away → scene
> chunks in the wrong place + never-recovered black slabs. Harmless on pure-
> geometry wipes (Circle/Test4), which is why only the tile-dissolve loading
> screens (boot→plaza, plaza returns) looked broken — the user's 2026-08-11
> "first loading screen every boot / every other one fine" report. Invisible on
> the PC before 2026-08-09 because the old PC INI enabled a phantom title (v2
> never ran there); glaring after fpspatch `wipe5_opt` (G≥3) made tiles 128px.
> Since v2 also never fixed the bars bug below, disabling loses nothing. If the
> bars bug is ever resumed, a v3 must either leave EFB-copy wipes unstretched
> (discriminate on wipe id at the CameraInit hook) or remap `Hx_GetFrBuffer`'s
> copy/clear rects through the same ×4/3 transform.

**Bug:** in the beloved config (gecko `$Widescreen` + Dolphin Widescreen Hack ON + Aspect Auto,
patched build `dolphin-src` 2606-184), the level-transition "bands collapse/reveal" animation
doesn't reach the left/right screen edges. Everything else about widescreen is great.

**Two gecko fixes were written, enabled, and did NOT fix it** (both still in the user INI as
`$Widescreen wipe fix v2 (stretch wipes 4:3 to 16:9)`; consider disabling — it stretches all
Hx wipes ×4/3 horizontally, may make circle wipes slightly oval):

- `C2181F84` — Hx_UpdateWipe dispatch hook: call Hx_CameraInit before every wipe draw
  (fixes Test2/Test2R which uniquely lack their own camera setup).
- `C2182DD8` — Hx_CameraInit ortho half-width ×0.75 (stretch wiper output ×4/3).

CAVEAT: the final test was in the right config but hook-liveness in RAM was not re-verified.
Every earlier "didn't work" test turned out to be invalid (savestate restored old code list,
or Dolphin never restarted). Verify with gcmem before trusting any test:
`0x80181F84` should be a branch (4BE807E4), not `819F0020`.

## ★ TOP LEAD FOR NEXT SESSION — never tested

`0x804167B8` — the "framerate global" that ALL the 120/180fps codes overwrite (0.5 → 2.0/3.0)
— is actually the **compiler's pooled literal `0.5f`**, shared by unrelated code. Confirmed
consumer: the stage-banner / band drawer at `0x802A5B44` ("em_1".."em_6" demos) uses
`lfs f2, -0x3E8(r2)` = [0x804167B8] as 0.5 (e.g. stage-name centering `(600-w)*0.5`). With the
180fps code active that's **3.0**, corrupting any geometry computed from it.

**5-minute experiment: reproduce the bars with the fps code DISABLED (stock 30fps, widescreen
still on).** If the bars are fixed at stock speed → the bug is the fps code's pooled-constant
collision, not widescreen, and the fix is a surgical per-site patch of the fps code's readers
(like FIX R1/R2/R3 did for other readers) instead of writing 0x804167B8 globally.

## Verified facts (do not re-derive)

### Hx wipe module (US GMSE01 addresses)
- `Hx_UpdateWipe` 0x80181E80; per-wipe fn ptr table 0x803C129C; type table 0x803C12D8
  (ids: 1/2 Circle, 3/4 Test1 corner-circles, 5/6 Test5 tile-dissolve, 7/8 Test4,
  9/10 Test2R/Test2 sprite-band, 11 Door, 12 Logo, 13 GameOver; odd = reveal).
- Wipe globals 0x803F43C0: +0 w(=640), +4 h(=480), +0x10 state(1=start,2=anim,3=done),
  +0x11 id, +0x12 type, +0x14 elapsed.
- `Hx_CameraInit` 0x80182D60: ortho ±w/2 centered (w/2,h/2), GXSetViewport(0,0,640,480).
  GXSetViewport=0x803630C8, C_MTXOrtho=0x8034A4D4, GXSetProjection=0x80362C34.
- `Hx_ResetWipe` 0x801821C0; TSMSFader ctor 0x80140008 calls ResetWipe(640,480);
  `TSMSFader::startWipe` 0x8013F860 (23 bl callers).
- **Test2/Test2R are the only wipes that don't call Hx_CameraInit** (draw with leftover
  projection). All others (incl. state-3 black cover) are self-consistent → cannot miss edges.
- Live-captured transitions (wipelog): level entry/exit uses Circle (1/2) and **Test4 (7/8)**;
  Logo (12) at boot. The em-demo banner (0x802A5B44) draws bands with its own ortho
  [0,600]×[16,464] — also self-consistent.

### Dolphin-side (2606 source in C:\Users\krisb\code\dolphin-src)
- Widescreen hack scales **perspective only** (VertexShaderManager.cpp:52) — never ortho —
  so it cannot squeeze 2D wipes. Heuristic (VideoCommon/Widescreen.cpp) has the
  Animal-Crossing guard: pure-ortho frames do NOT flip 16:9→4:3.
- Dolphin hack active-scaling misaligns SMS's DOF/haze overlay → "double vision" on distant
  terrain/items. The gecko code doesn't have this (it widens 2D consistently).
- User's combo matrix: gecko+hack+Auto = beloved true widescreen (hack dormant via heuristic);
  hack-driven = double vision; Force16:9 alone = stretch; gecko alone at Auto = displayed 4:3.
- Frame-interpolation in our patch is env-gated (`FRAME_INTERP`), default off.

### The live $Widescreen code
Body lives in **Sys/GameSettings/GMSE01.ini** (`$Widescreen [gamemasterplc]`, ~60 lines) —
user INI only enables it. Includes: 3D aspect 0x80412408 1.333→1.777; four TScreen orthos
[0,600]→[-100,700] (via 0x804123E8=700 + instr patches to load -100); pooled 600s
0x80416758→800, 0x80416620→700; fader-host screen → live rect (-53,-5,693,485);
~10 J2D pane repositioning C2s; `C2363138` = GXSetScissor hook (squeeze non-x=0 scissors
×3/4 centered).

### Test-hygiene traps (cost this session dearly)
1. Dolphin rewrites the user game INI from memory on close — edit only while closed.
2. **Savestates restore the OLD gecko code list + patched instructions** — any test through a
   savestate tests stale codes. Fresh boot only.
3. Gecko C2s in Dolphin: codehandler at 0x80001800, list after marker 0x00D0C0DE 0x00D0C0DE
   (~0x80002338). Verify a C2 applied by reading the hook site, not the INI.
4. `scripts/gcmem.py <pid> <addr...>` reads live memory (SMS_DOL=main.dol). MEM1 not found ⇒
   emulation stopped.

### Config file cheat-sheet
GFX.ini: `wideScreenHack`, `AspectRatio` (0=Auto,1=16:9,2=4:3,3=stretch).
Beloved config = wideScreenHack=True, AspectRatio=0, gecko $Widescreen+$180fps v12+$GameHeap.
