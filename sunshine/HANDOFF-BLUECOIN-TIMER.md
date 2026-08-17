# HANDOFF: Blue coin timer fix (Super Mario Sunshine, GMSE01, 120fps)

**Status:** ✅ **DONE: v6 CONFIRMED in-game.** Delfino Plaza statue coin measured
**19s** (target 20s stock; ~1s is stopwatch + rise-in phase). No crash, no instant
death, spot behaves normally. Shipped code: `codes/bluecoin-timer-v6.txt`,
installed + enabled as `$Blue coin timer fix v6 (120fps)`. v5 (½-rate, 30s) and
the v1..v4 crash lineage are superseded, kept only as the debugging record.

**Date:** 2026-08-07
**Agents:** GLM-5.2 (built v1/v2/v3a, all crashed; isolated the padding bug).
Opus (2026-08-07): found the prior "v4" **still crashed**: it fixed the
fall-through but branched to the second-to-last `00000000` (one word before the
handler's branch-back), i.e. still a live dead-zero. Corrected the true rule,
rebuilt as v4 (ungated) + v5 (gated), added a static assert to the assembler and
the precise lesson to `dolphin-gecko/SKILL.md`. Installed v5.

## RESOLUTION (what changed this session)

- **True root cause of the crashes:** only the LAST word of a C2 block is the
  branch-back; every *other* `00000000` is a live cave word. Every path must
  converge on the LAST word (fall-through or a branch to *that exact word*). The
  old v4 branched both stores to a separate `pad` word that sat one slot before
  the branch-back → still executed `00000000` → same crash.
- **Fix:** place the odd-substep (HOLD) store LAST so it FALLS THROUGH into the
  single branch-back word (like the working no-op probe); only the decrement path
  needs an explicit `b`. Interior even-count padding uses `nop` (`60000000`),
  never a 2nd `00000000`. `coinhook_assemble.py` now asserts "no interior 0".
- **Shipped v5 (gated):** `sunshine/research/codes/bluecoin-timer-v5.txt`,
  installed + enabled as `$Blue coin timer fix v5 (120fps)`. Self-disables unless
  the framerate global `0x804167B8 == 2.0f` (120fps). Uses r6/r7 (gate) + r5
  (parity); does NOT touch r4.
- **v4 (ungated)** is `coinhook_assemble.py build_v4()`, the isolation fallback.
- **Register-clobber bug (found on first in-game test, fixed):** the first v5 did
  the parity test as `andi. r0,r5,1`, which overwrote r0 (= oldTimer-1, the value
  STORE_DEC stores). On even substeps r0 became 0 → `stw r0` wrote 0 into
  mStateTimer → coin died INSTANTLY (and the sprayed spot re-polluted at once).
  Fixed to `andi. r5,r5,1` (test in r5; r0/r3 survive). NOTE: the old v1 file had
  the same latent `andi. r0` but crashed on padding before it showed.
- **Rate calibration → v6 (SHIPPED):** with the corrected ½-rate v5, the Delfino
  Plaza statue coin measured **30s** (full 600-tick spawn→vanish) vs the **20s**
  stock target (600 ticks / 30fps native; unk150=120 appear + unk14C=480 disappear).
  So the substep runs ~40/sec at 120fps (≈1.33× stock, CPU-bound, not a clean 4×).
  `time = 600/(40·keep)`: keep ½→30s, ¾→20s. Shipped **v6 = ¾-rate**: hold on 1 of
  every 4 substeps (`andi. r5,r5,3 ; beq HOLD`). Two words differ from v5:
  `70A50001`→`70A50003`, `bne`→`beq`. File: `codes/bluecoin-timer-v6.txt`;
  installed + enabled as `$Blue coin timer fix v6 (120fps)`. Assembler:
  `build_v5_gated(hold_1_of=4)`. **Awaiting final ~20s confirm.**

### To test (save swap needed, user's call)
The live Card A save (`.../Dolphin/GC/USA/Card A/01-GMSE-super_mario_sunshine.gci`,
backup `.backup-20260806-234928`) has Ricco coins collected. The repo save
`sunshine/saves/01-GMSE-super_mario_sunshine.gci` has Ricco uncollected. Back up
the live save, copy the repo save over it, test, then restore.

---

## TL;DR for the next agent

1. The fix is a **parity gate** on the blue coin's `--mStateTimer` decrement so
   it ticks once per stock frame instead of once per substep (4x at 120fps).
2. The hook site `0x801BE880` is **proven safe** (no-op probe works).
3. v1/v2/v3a all crashed because of a **C2 block-layout bug**: a code path fell
   through into the trailing `00000000` pad, which the CPU executed as an
   instruction (`Unknown instruction 00000000`).
4. **v4 fixes this**: every path ends with an explicit branch. It's in
   `research/scripts/coinhook_assemble.py` (`build_v4()`).
5. **Install v4, test.** If the coin lasts ~2x longer (no crash), add the
   fps-global gate (snippet below) and that's the final code.

---

## What was being fixed

The blue coins that spawn when you spray a spot (in front of the M/X marks;
Ricco Harbor is the worst case) vanish ~4x too fast at 120fps. The ~16s stock
window collapses to ~4s, so you can't reach them.

This is the **same bug class** as the Poink `flyTimer` and the game-clock fix:
a frame/substep counter draining at the high-FPS rate instead of real-time.

---

## The mechanism (fully RE'd, verified against the running disc)

Source: `/Users/kbrethower/code/sms-decomp` (`src/MoveBG/Item.cpp`,
`include/MoveBG/Item.hpp`).

The disappearing blue coin (`TCoin`/`TCoinBlue`, actor type `0x20000010`) uses a
**frame counter**, not a stopwatch. `TCoin::perform` runs every `CUE_MOVE`
substep; when `isStateTimerEngaged()` (`mStateTimer > 0`), it does `--mStateTimer`:

```cpp
// Item.cpp:259 (TCoin::perform)
if (isStateTimerEngaged()) {
    --mStateTimer;          // <- the countdown
} else {
    // ... mStateTimer hits 0 -> makeObjDead() (coin vanishes)
}
```

**USA main.dol addresses** (verified against BOTH `research/main.dol` AND the
extracted dol from `Super Mario Sunshine (USA) [HD portals].iso`, byte-identical
at the hook site; the dols differ in only 2 bytes total, elsewhere):

- `TCoin::perform` function start: **`0x801BE7CC`** (mflr r0; stwu r1,-0x50(r1); ...)
- The decrement (the hook anchor):
  ```
  0x801BE878  lwz  r3, 0x104(r29)     # load mStateTimer (TItem+0x104)
  0x801BE87C  addi r0, r3, -1         # r0 = oldTimer - 1
  0x801BE880  stw  r0, 0x104(r29)     # <-- HOOK ANCHOR (replace with C2)
  0x801BE884  b    0x801BE908         # handler branches back to here (+4)
  ```
- Seed: `mStateTimer` is seeded from `unk14C = 480` (disappear lifetime) and
  `unk150 = 120` (appear timer) in `TItem::initMapObj` (`li r0,0x1E0; stw r0,0x14C(r31); li r0,0x78; stw r0,0x150(r31)`).
  Found at three `initMapObj` sites via the 480/120 fingerprint:
  `0x801BBAB8` (TItemNozzle), `0x801BCD88` (TShine), `0x801BE68C` (TCoin, loads
  `ms_watcoin_kira.jpa`).
- `isStateTimerEngaged()` = `mStateTimer > 0` (`include/MoveBG/MapObjBase.hpp:338`).
  Inlined at the call site as `lwz r0,0x104(r29); cmpwi r0,0; ble else; li r0,1; ...`.

**Confirmation the anchor is `TCoin::perform`:** the branch target `0x801BE908`
is `getColNum()` (`lhz r0,0x48(r29)`) followed by the `touchActor` collision loop
(matches `Item.cpp:287-289` exactly).

---

## The ROOT CAUSE of the crashes (the hard-won lesson)

v1, v2, v3a all crashed with **`IntCPU: Unknown instruction 00000000 at PC = 800026xx`**
(PC in `0x80002xxx` = inside the Gecko code handler's cave).

**The bug:** the SKILL.md rule says "the block MUST end with a `00000000` padding
word; the handler overwrites the LAST word with its branch-back." I interpreted
this as "pad with as many `00000000` as needed." But **every `00000000` in the
block except the very last one is a real cave word**, and if execution *falls
through* into it, the CPU tries to execute `0x00000000`, which is not a valid PPC
instruction → crash.

My v1/v2/v3a blocks had this structure:
```
storeR0:  stw r0,0x104(r29) ; b end
storeR3:  stw r3,0x104(r29)
end:      nop ; nop ; 00000000(pad)
```
The `storeR3` path: `stw r3` → falls into `nop` → `nop` → **`00000000`** → crash.
(The `b end` after storeR0 jumped over storeR3 correctly, but storeR3 itself had
no exit branch and fell through.)

**The fix (v4):** EVERY code path must end with an explicit `b <pad>` branch. No
fall-through anywhere. See `build_v4()` in `coinhook_assemble.py`.

### Proof the site itself is safe

A **no-op C2** at `0x801BE880` (just re-executes `stw r0,0x104(r29)`, count=1,
2 words: the store + pad) **worked perfectly**: coin spawned fine, just fast.
This proved the hook address, the C2 mechanics at this site, and register state
are all fine. The ONLY difference between "works" (no-op) and "crashes" (v1-v3a)
was the added gate logic with the fall-through bug.

### Other things ruled out (don't re-investigate)

- **NOT a disc-revision mismatch:** extracted the dol from
  `Super Mario Sunshine (USA) [HD portals].iso` (the 1.47GB / "1.10 GiB" build
  the user runs), byte-identical at the hook site.
- **NOT a register-clobber:** r4, r5 both crash (tried both); r0/r3 are dead at
  the site (rewritten at 0x801BE908/0x801BE924 before any read). r5-r12 are
  caller-saved and unused in this function. (I initially blamed r4; that was
  that was wrong; it was the padding bug all along.)
- **NOT gpMarDirector being null:** the guard (`cmplwi/beq`) is correct, and the
  game's own code at `0x801BE810` uses the same `lwz r3,-0x6048(r13)` deref.
- **NOT cave overflow:** reduced from 18→14 C2 hooks; still crashed.
- **NOT internal-branch mechanics:** Poink v14 (`120v14-poink-premature-explosion-gate.txt`)
  uses `andi.` + internal `beq`/`bge` and works fine.

---

## v4: the fix (designed, NOT yet tested)

Assembled by `research/scripts/coinhook_assemble.py` (`build_v4()`). Every path
ends in an explicit `b` to the pad:

```
C21BE880 00000006
80AD9FB8 28050000    lwz r5,gpMarDirector(r13) ; cmplwi r5,0
41820010 80A5005C    beq storeR0 ; lwz r5,0x5C(r5) [unk5C]
70A00001 4082000C    andi. r0,r5,1 ; bne storeR3
901D0104 4800000C    storeR0: stw r0,0x104(r29) ; b pad
907D0104 48000004    storeR3: stw r3,0x104(r29) ; b pad
00000000 00000000    pad (handler overwrites last word with branch-back)
```

**v4 is UNGATED**: it halves the decrement rate at ALL framerates (because
`unk5C & 1` alternates every substep at any rate). At 120fps this is correct
(coin lasts the right amount of time); at stock 30fps it'd make coins last 2x
too long. For the final code, **add the fps-global gate** at the top (use r6/r7,
NOT r4):

```asm
lis   r6, 0x8041
lwz   r6, 0x67B8(r6)     # framerate global = float(FPS/60)
lis   r7, 0x4000         # 2.0f
cmpw  r6, r7
bne   storeR0            # not 120fps -> stock decrement
# ... then the parity gate (lwz r5, ... etc)
```

This is the same gate idiom as `120v15-timer-fix.txt` (self-disables at stock
where the global is 0.5f, and at 180/240 where it's 3.0f/4.0f). **Run the gate
through the assembler** (`coinhook_assemble.py`); don't hand-encode. The field
orders are subtle (`andi.` is `rA,rS,imm`; `beq`=0x4182, `bne`=0x4082).

### Limitations of v4 (call these out to the user)

- **Only halves the rate** (parity-by-1-bit). At 120fps this is exactly right.
  For 180/240 you'd need modulo-3/4 instead of `&1` (the file's v1 TODO notes this).
- **Only hooks `TCoin::perform`.** The sibling state-timer site at `0x801AFCCC`
  (a different actor) is untouched. Red coins, shines, etc. are not affected.
- **Parity relies on `unk5C`** (`gpMarDirector->unk5C`) being the substep counter.
  This is the same field the shipping emitter fix (`fpspatch.py _parity_block`)
  uses to advance emitters at exactly 60Hz, so it's well-established. If v4 makes
  the coin last the wrong amount (e.g. still 2x fast, or 2x too slow), `unk5C`'s
  semantics at this exact call site may differ; re-verify by reading it at
  runtime.

---

## Environment / how to test

- **Game disc:** `/Applications/gamecube/Super Mario Sunshine (USA) [HD portals].iso`
  (the user runs this, not the stock `.rvz`). Extract its dol to compare with:
  ```python
  # dol offset at ISO+0x420 (4 bytes BE); main.dol is 4128928 bytes, Rev.00.
  ```
- **Decomp:** `/Users/kbrethower/code/sms-decomp` (JP source; root-cause tool).
- **RE tooling:** `research/scripts/timerfind.py`, `coinhook_assemble.py`. Needs
  capstone: `/tmp/smsre_venv/bin/python` (temp venv; recreate with
  `python3 -m venv /tmp/smsre_venv && /tmp/smsre_venv/bin/pip install capstone`
  if it's gone).
- **Gecko helper:** `python3 .claude/skills/dolphin-gecko/scripts/gecko.py`
  (from repo root). Takes body-only hex via `--code "$(...)"` or `--code-file`.
  It REJECTS files with `$Title`/comment lines; extract body with
  `grep -E '^[0-9A-Fa-f]{8} [0-9A-Fa-f]{8}$'`. Refuses to write while Dolphin
  runs; quit Dolphin with `osascript -e 'quit app "Dolphin"'` (the confirmation
  prompt often reports error -128 but still quits; verify with `pgrep -x Dolphin`).
- **Current INI state:** all blue-coin codes REMOVED. User's real save RESTORED
  (Ricco coins collected). To test blue coins in Ricco, the user has a repo save
  at `sunshine/saves/01-GMSE-super_mario_sunshine.gci` (Ricco uncollected);
  backup the live save before swapping (see git log / prior conversation for the
  exact backup path used, `.backup-20260806-234928`).
- **C2 budget:** user runs ~14 C2 hooks / 100 lines currently (Camera look-up v7
  was temporarily removed during debugging; user may want it back). SKILL.md
  warns the cave is small; keep codes compact.

## Files saved during this investigation

- `sunshine/research/codes/bluecoin-timer-v1.txt`: v1 code (CRASHES; header
  documents why). RE/mechanism comments are still accurate.
- `sunshine/research/scripts/coinhook_assemble.py`: field-correct assembler
  with `build_v4()` (the fix), `build_noop()` (the probe), and PPC encoders.
- `sunshine/HANDOFF-BLUECOIN-TIMER.md`: this file.

## Suggested next steps

1. Install v4 (ungated) and test in Ricco Harbor. Confirm coin lasts ~2x and
   NO crash. (Swap saves first per above.)
2. If good: add the fps-global gate (r6/r7), reassemble, test again.
3. Update `bluecoin-timer-v1.txt` → `-v4.txt` with the working code + the
   fall-through lesson added to SKILL.md (so the next C2 author doesn't repeat it).
4. Consider whether the user wants the Camera look-up v7 code re-enabled (it was
   removed to test the cave-overflow theory, which turned out NOT to be the cause).
