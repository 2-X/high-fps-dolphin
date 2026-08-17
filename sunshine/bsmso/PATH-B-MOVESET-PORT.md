# Path B: port BetterSunshineMoveset to native Gecko (stock fpspatch disc)

**Goal:** run the moveset (Hover Burst, SMO Dive, …) on the *stock* GMSE01 disc
with our fpspatch high-fps engine, as toggle-able C2 Gecko codes (no BSE/Kuribo
runtime). Path A (solo BSE disc) already lets you play it today; Path B is the
"keep our own engine" version. This doc is the RE kickoff (2026-08-14).

## Tooling
`tools/kxdump.py` (run with `venv/bin/python`): parses the KXER module, lists
imports, applies relocations symbolically, and disassembles with capstone.
`kxdump.py <module.kxe> --asm out.asm` → full annotated disasm. Format spec:
`tools/kuribo-src/source/LibKuribo/modules/kxer/Binary.hxx`.

## Module facts (BetterSunshineMoveset.kxe)
- KXER v0. **code** 0xa0..0x7460 (29 632 B), **relocations** 1015
  (ADDR16_HA×295, ADDR16_LO×298, ADDR32×167, REL24×255), **imports** 15,
  no data/bss/exports/embedded. **entry** = code+0x3c4.
- Read-only constants live at the tail of the code section (~code+0x53c8+),
  since there's no data section.
- Reloc operands target the instruction's immediate halfword (**addr+2**), not
  the instruction start; account for this when correlating disasm to relocs.

## ★ Architecture finding: it's NOT branch-patch hooks
The moves are **not** installed as `PatchB/Patch32` at fixed game addresses.
The module registers with **BSE's runtime extension framework** (the 15 imports
are all `BetterSMS::…`). None of this framework exists on the stock disc, so a
Gecko port must re-implement the *moves*, not the framework. Registration
(module ctor, code+0x900..0xa34):

| BSE API | count | role |
|---|---|---|
| `Player::addUpdateCallback(void(*)(TMario*,bool))` | 9 | per-frame move logic / input detection |
| `Stage::addUpdateCallback(void(*)(TMarDirector*))` | 1 | stage-level per-frame |
| `Player::addInitCallback` | 2 | per-player setup on spawn |
| `Player::addLoadAfterCallback` | 1 | post-load setup |
| `Player::registerStateMachine(u32 id, bool(*)(TMario*))` | 4 | **new move states** |
| `Player::registerData/getData/getRegisteredData` | - | per-player move state blob |
| `Player::setAnimationData/isAnimationValid` | - | animation control |
| `PowerPC::writeU32` | 19 | direct game-memory pokes (enable transitions) |

### Handler table (code offsets, from the ctor relocs)
- init: code+0x02078, code+0x033a4 · loadAfter: code+0x0213c
- Player.update ×9: 0x02550, 0x03c48, 0x03460, 0x01290, 0x039ec, 0x03dbc, 0x028cc, 0x002dc, (+one more)
- Stage.update: 0x01734
- **state machines (id → handler):**
  - `0xF00001C0` → code+0x013d4   (custom BSE state)
  - `0xF00001C1` → code+0x03698   (custom BSE state)
  - `0x0000088F` → code+0x03afc   (overrides/extends an existing SMS state)
  - `0x000024DF` → code+0x03e84   (overrides/extends an existing SMS state)

### Moves (from module strings) + tuning
`Fast Dive/Rollout, Ground Pound Jump, Hover Burst, Burst Cancel, Hover Slide,
Long Jump (+Crouch Button), NO FLUDD, Rocket Dive, SMO Dive, Side Dive,
Water Ground Pound`. Params via **`/mario/better_movement.prm`** (a PRM/JMP-style
blob read off-disc at runtime): `mMaxJumps, mMultiJumpMultiplier,
mMultiJumpFSpeedMulti, mBaseJumpMultiplier, mSlideMultiplier`,
`movement__turbo_nozzle_data`. So multi-jump/long-jump are param-driven; dives
and Hover Burst are the state-machine moves.

## Port strategy (don't port BSE; port each move)
Re-implement per move as a self-contained C2, using the disassembled handler as
the spec:
1. **One per-frame hook** on TMario's player update (a single C2 at Mario's
   update site) that runs the move checks (the Gecko stand-in for the 9
   `addUpdateCallback`s).
2. **Inline the state logic:** instead of BSE's `registerStateMachine`, read
   controller + `TMario` fields and drive `mario->mState` / velocity /
   animation directly (SMS already has the nozzle/dive/jump primitives; BSE's
   `setAnimationData` etc. are thin wrappers over SMS functions).
3. **Per-player data** → offline is a single Mario; use a fixed scratch RAM
   region (same pattern as the existing high-fps C2 scratch, e.g. 0x800016F0).
4. **Params** → bake the `better_movement.prm` values as code constants (or a
   small editable Gecko data block) instead of reading the file.

## Difficulty / next milestone
Tractable **one move at a time**; each handler is a few hundred bytes of PPC.
Main unknowns: exact `TMario` field offsets and which raw SMS functions replace
the BSE wrappers.

**Milestone 1 (next):** fully disassemble **Hover Burst** (the favorite): find
which handler/update-callback implements it (correlate to the "Hover Burst" /
`_movement_params` strings + `getRegisteredData` name args), extract its trigger
condition (nozzle == Hover + input), the `TMario` fields it writes, and the
velocity/animation it applies. Produce a first C2 draft + test on the stock disc.
Then Burst Cancel, then the dives.

## ★ Milestone 1: Hover Burst IDENTIFIED (2026-08-14)
Corrected registration order (each `bl`'s handler = the lis/addi HA/LO pair
before it; reloc operands sit at instruction+2):
- init#1 `0x0429c`, init#2 `0x02078`, loadAfter `0x033a4`
- Player.update ×9: `0x0213c, 0x02550, 0x03c48, 0x03460, `**`0x01290`**`, 0x039ec, 0x03dbc, 0x01734, 0x002dc`
- Stage.update `0x028cc`
- states: `0xF00001C0`→`0x013d4`, `0xF00001C1`→`0x03698`, `0x088F`→`0x03afc`, `0x24DF`→`0x03e84`

**Hover Burst = trigger `PU5 @ code+0x01290` + state `0xF00001C0 @ code+0x013d4`.**
PU5 is the per-frame detector; on trigger it transitions Mario into the custom
state 0xF00001C0 (id loaded from the constant at `code+0x53c8`) and kicks a
velocity. Trigger logic (in order):
1. `lwz r5,[0x8040E178]; lbz r5,0x64(r5); cmpwi r5,4` → **current nozzle == HOVER(4)**
2. enabled-setting byte via `code+0x05428` (the "Hover Burst" toggle): 0 ⇒ bail
3. Mario state whitelist on `mario->0x7c` (nerve/state id) + status bit `mario->0x77 & 8`
4. float threshold: `mario->0xb0` vs const `@code+0x070b0` (bail if above)
5. button gate: `ctrl = mario->0x4fc`, `btns = ctrl->0xd0`, mask from `sub_0x04704`
   (configured button); `(mask & btns)==0` ⇒ bail
6. anim guard on `mario->0xe0` (`!=7`)
7. **fire:** `setState(mario, 0xF00001C0, …)` then apply velocity at `&mario->0xa4`
   using float param `@code+0x07090`

### TMario field offsets discovered (GMSE01, to reuse in the C2)
`+0x77` status flags (byte) · `+0x7c` current state/nerve id (u32) ·
`+0xa4` velocity vector (TVec3f mSpeed, burst writes here) · `+0xb0` a float
gate (speed/timer) · `+0x4fc` controller ptr; `ctrl+0xd0` button state ·
`+0xe0` animation object ptr. Verify against decomp / our camera+FLUDD codes.

**Next:** disassemble the state handler `0x013d4` (what runs *during* the burst:
rise curve, cancel window = "Burst Cancel") + `sub_0x04704` (button mask) +
resolve `[0x8040E178]` and the nozzle enum, then draft a self-contained C2 that
hooks Mario's per-frame update and reproduces steps 1–7. Test on the stock disc.

## Open questions
- Handler→move-name mapping (need per-handler disasm; the `getRegisteredData`
  string arg per handler will name it).
- Whether `0x088F` / `0x24DF` are SMS state IDs we can reuse or BSE-internal.
- TMario field offsets on GMSE01 (cross-ref decomp / our existing camera & FLUDD
  codes which already poke TMario).
