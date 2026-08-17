# Low-arena scratch collision: camera look-up block vs wipe/pump counters (sand-castle soft-lock, FIXED 2026-08-10)

**Symptom (user, 2026-08-10, 240fps bundle):** sliding through the Gelato Beach
sand castle to enter the secret course soft-locked the game: input dead, Mario
eventually plays his sleep idle, fish/music keep running, screen never fades.
Not a freeze: a scene transition that never completes.

## Live evidence (probed the stuck process via gcmem)

- A wipe WAS active: Hx wipe globals `0x803F43C0` showed state/id = 02/02
  (Circle wipe) with the per-frame rate accumulator (+0x14) advancing at 240/s
  (Hx_UpdateWipe running every rendered frame).
- The shared wipe timer (+0x3C) sat frozen at its initial 25 forever → the
  wipe never ends → TMarDirector never changes scene → input stays disabled.
- The wipe_pace counter `0x800016F4` read **0x434D4559 = the camera code's
  init-magic 0x434D4558 ("CMEX"?) + 1**, oscillating ...58/59/5A under a
  store-war; the pump counter `0x800016F8` likewise hovered at the camera
  constant 0x460E4800 (9106.0f ≈ the 50° angle limit) + tiny increments.

## Root cause

**Camera look-up extension v8/v10** (hand-written Gecko code, 5 C2 hooks) keeps
a **0x40-byte** state block at `0x800016F0` (+0x04 init-magic `0x434D4558`,
checked every camera tick; magic mismatch → full block re-init). The fpspatch
slot map believed "0x16F0 = camera" was **4 bytes**, and later fixes parked:

- `WIPE_CTR = 0x16F4` (wipe_pace) → the camera's **magic word**
- `AUDIO_PUMP_CTR = 0x16F8` (audio_pump) → a camera angle constant
- `TURNAROUND_SCRATCH = 0x1720-0x172F` (skid U-turn fix) → camera +0x30..+0x3C

Outside wipes the wipe tick is idle, the magic stays intact, nobody notices
(the pump counter increments the camera's 9106.0 constant, but the camera only
*validates* +0x04). **During a wipe with the camera hook still updating** (event
camera = exactly the sand-castle entry), every frame goes: wipe tick bumps
magic → camera sees "corrupt", re-inits, restores magic → the TimerCountDown
gate reads magic+1, and `0x434D4559 & 7 == 1 ≠ 0` → gate blocks → timer never
decrements → permanent hang. Cruel twist: the magic itself is `& 7 == 0`, so
without the tick war the gate would have failed OPEN (8× fast wipe), not shut.

## Fix

Rebase the camera block `0x800016F0 → 0x80001730` (0x1730-0x176F verified free
in the full INI: only other 16xx/17xx users are the fpspatch counters and the
turnaround scratch; `38C0176A` elsewhere is a `li` immediate, not an address).
Mechanically: the base appears only as 5 `ori` halfwords across the hooks:
`60A516F0`×2, `606316F0`×2, `60E716F0` → `...1730`. Applied to v10 AND the
dormant v8, in both the live INI (via gecko.py) and
`sunshine/dolphin-config/GameSettings/GMSE01.ini`. fpspatch.py slot-map
comments now carry the full map (see WIPE_CTR) with the camera block sized.

## Lessons

- **A low-arena "slot map" in comments is load-bearing.** Two codes were built
  against a stale copy of it. The map now lives in ONE place (WIPE_CTR) with
  sizes, and the camera entry records its true 0x40-byte reach.
- Magic-word self-healing blocks turn a benign 4-byte overlap into a
  every-frame store war; the colliding counter can never win.
- The wipe_pace note's predicted failure mode ("a hang would mean a gate ran
  with a frozen counter; can't happen per the callers argument") was right
  that the tick always runs; it didn't foresee an EXTERNAL writer resetting
  the counter between tick and gate. Fail-open gates (pass on `ctr==0`-style
  garbage) would have degraded instead of hanging.

Cross-refs: [[sunshine-wipe-morph-perf]] (the wipe_pace design),
HANDOFF-INPUT-BUG.md session 7 (the sibling "starved event" class; this one
looked identical from the couch but was a different mechanism).
