# HUD star-sparkle bug (120fps): investigation handoff

**Symptom:** the star sparkles around the HUD counters (shine ×N, blue-coin ×N,
coin ×N) stay active indefinitely; counters linger on screen during gameplay.
Intermittent ("only happens sometimes"). Screenshot taken on the beach level.

## What the stars are (fully reversed, USA addresses)

`TGCConsole2` (the HUD) owns three JPA star emitters, one per counter group:

| field | emitter | started by (clear STOP_EMIT) | stopped by (set STOP_EMIT) |
|---|---|---|---|
| con+0x124 | coin 'c_' | `startAppearCoin` 0x8014c7e8 (@0x8014c904) | `startDisappearCoin` 0x8014c518 (dir-exit only), `startCameraDemo` 0x8014d77c |
| con+0x144 | shine 's_' | `startAppearStar` 0x80149b00 (@0x80149e94) | perform retract 0x80141a54 / 0x80141d38, `pauseOut` 0x8014a854, `startDisappearStar` 0x80149ecc, `startCameraDemo` 0x8014d548 |
| con+0x164 | blue-coin 'd_' | same as 144 | same sites (+8 bytes) |

`JPABaseEmitter->mStatus` @ +0x11C, bit0 = STOP_EMIT. **The particles are
stepped/drawn by a separate `TEmitterViewObj` (gpEmitterManager4D2) in "Group
2D"**, NOT by the console. So if the console's logic stalls, sparkles keep
animating forever regardless.

The **coin** emitter is never stopped during normal play even in stock (SMS
leaves the coin counter + sparkle up once you collect a coin; it's stopped only
by camera demos / stage exit).

## The normal shine/blue-coin retract (what fails)

`TGCConsole2::perform` (USA 0x8014083c, MOVE-cue section) block @0x801418a4:
slides all counters out and stops emitters 144/164 **only when ALL guards
pass**, notably:

- shine pane (`TExPane*` con+0x140) interpolator offsets (+0x14/+0x18) **round
  to exactly (0,0)** (i.e. the slide-in animation fully arrived);
- `gpMarDirector->mState` (dir+0x64) not 5 (pause) / 0xB;
- `dir+0x124 != 2` (not talking); con+0x60, con+0x50, con+0x16C, con+0x8A all 0.

The complementary block @0x80141854: while shine pane is *not* at rest and
`[gp+0x7c]==0x0C400201` (a volatile camera/mode word at `[r13-0x60d8]+0x7c`),
counter con+0x30 counts up; >200 → `startAppearStar` (periodic reveal).

## Bug state captured live (gcmem probe, 2026-08-06 ~12:10–12:19)

- mState=4 (gameplay), d124=0, all retract guards pass EXCEPT:
- **shine pane frozen mid-slide at offset (0,-85) for ≥4.2 s** → retract can
  never fire → emitters 144/164 (and 124) all EMITTING → perpetual stars;
- con+0x30 read **-400 = constructor-virgin** → the maintenance block had
  NEVER run for that console object → the console's MOVE cue was not being
  delivered (or the console was a freshly recreated object that never got
  enabled), while particles kept drawing via the separate EmitterViewObj.

Later (after the user paused/unpaused and/or changed area) the same fields ran
normally: pane arrived (0,0) and retracted to -163, unk30 cycled, pauseOut set
STOP on 144/164. So the stuck state is a **stranded console state machine**,
not a permanently broken one, matches "only happens sometimes".

## Cue plumbing facts (needed to interpret)

- `TViewObj::unkC` is a **DISABLE mask** (`cue &= ~unkC` in testPerform).
  Console created with unkC=0xB (disabled) in `TMarDirector::setupObjects`
  (USA 0x8029c894), then **enabled** (`unkC.off(0xB)`) in
  `nextStateInitialize` states 2/4, but ONLY when `mMap (dir+0x7C) != 0xf`
  and (case 4) `mState <= 3` (USA 0x80298444/0x80298484).
- Pause (state 5) strips MOVE+CALC from the main perform lists (uVar8|=3 in
  `direct()`) → HUD logic frozen during pause by design; Group-2D list unk30
  still gets MOVE (pause menu animates; some console fields tick → don't trust
  con+0x86 as a liveness signal, it's likely draw-side).
- At 120fps the hack runs 1 substep/frame vs stock 4; perform-MOVE runs per
  substep, so all counter timings stay real-time-correct. The known-risky part
  is the **substep flag collapse** (first 0x2000 + last 0x4000 on the same
  substep) and anything keyed to state-transition edges.

## Leading hypotheses (discriminated by the running watcher)

1. **Interrupted slide + cue starvation**: something (pause during the ~40-frame
   slide-in, talk (d124==2), or a state transition) freezes the console while
   the shine pane is mid-slide; at 120fps an exit edge is missed so the freeze
   outlives its trigger. Watcher signature: mask≠0 or mState/d124 edge right
   before spY freezes at non-zero with s144=s164=0.
2. **Console recreated but never enabled**: scene load ordering at 120fps makes
   the state-2/4 enable miss the fresh console (or mMap==0xf path) → virgin
   console (unk30=-400) frozen all scene. Watcher signature: `con` pointer
   changes, mask stays 0xB, unk30 stays -400 while mState=4.

## Tools added

- `research/scripts/starprobe.py`: one-shot/looping dump of console HUD state
  (flags, counters, emitters). `SMS_DOL=../main.dol python3 starprobe.py 1 10`
- `research/scripts/starwatch.py`: transition logger (mask, mMap, mState,
  d124, con ptr, unk30, ConsoleStr phase, spY, emitter STOP bits). Currently
  running in background → `/tmp/starwatch.log`.
  `cd research/scripts && SMS_DOL=../main.dol python3 starwatch.py 3600 > /tmp/starwatch.log`
- gpMarDirector (USA) = **0x8040E178** ([r13-0x6048], r13=0x804141C0);
  console = [dir+0x74]. (An earlier arithmetic slip said 0x8040DB78, wrong.)

## Repro guidance

Play normally; the moment stars stick, note the wall-clock time and what just
happened (pause? talk/sign? shine banner? area entry?). Then read
`/tmp/starwatch.log` around that timestamp; the transition that strands the
console will be the last mask/mState/d124/spY edge before the freeze.

## Fix directions (once mechanism confirmed)

- If interrupted-slide: C2 hook in the retract guard to accept "pane at rest
  anywhere" (compare against interpolator-done instead of ==0), or force-stop
  emitters 144/164 whenever their pane is off/frozen >N frames.
- If missed enable: C2 in nextStateInitialize (or per-frame guard) to re-apply
  `console->unkC &= ~0xB` in state 4.
- Big hammer (works for both): tiny C2 watchdog in perform's DRAW path (always
  runs): if mState==4 and no MOVE tick seen for >120 frames, set STOP_EMIT on
  all three emitters and clear unkC disable bits.

---

# RESOLUTION (2026-08-06, same day)

**Root cause confirmed: orphaned PAUSE-MENU sparkle emitter.** The perpetual
stars were `TPauseMenu2::mEmitter` (menu at gpMarDirector+0xAC, emitter ptr
+0x110, the star sparkle on the selected pause-menu item. Its deletion is an
`mFadeAnim == 0.0f` tick inside `disappearWindow()`; at 120fps the director
leaves pause state 5 before the menu close-anim reaches that tick (mFadeAnim
observed frozen at 11.0 of ~46), so the emitter is left alive+emitting forever,
one more per pause cycle. Secondary leak: `pauseOut` stops the shine/blue-coin
counter emitters but never the coin one (con+0x124).

Validated by live mach_vm_write of STOP_EMIT into both orphaned emitters
(status 0x28 -> 0x29 confirmed in memory; on-screen fade pending user confirm).

**Shipped: `$120fps + StarFix (stop coin sparkle on unpause)` v2** (installed
+ enabled in GMSE01.ini): C2 @0x8014A850 inside pauseOut:

```
C214A850 00000007
809D0124 8064011C   # stop coin counter emitter con+0x124
60630001 9064011C
806D9FB8 806300AC   # gpMarDirector -> pauseMenu(+0xAC)
80630110 28030000   # -> mEmitter(+0x110); null check
41820010 8083011C   # stop it (STOP_EMIT)
60840001 9083011C
809D0144 00000000   # re-exec original; pad (handler clobbers last word)
```

Constraints at the hook: r29=console, r3/r4 free, **r0 must be preserved**
(holds 0 for a later stb). Emitters carry ENABLE_DELETE (0x8) so stopping them
lets the manager free them once particles die, no slot leak.

Tooling note: any "wait for Dolphin to quit" logic must use `pgrep -x Dolphin`;
`pgrep -if dolphin` self-matches scripts whose path contains "dolphin"
(this repo!). `gecko.py`'s guard still has that bug, pending user OK to patch.

## v3 addendum (final shipped fix)

v2 alone was insufficient: TPauseMenu2 re-creates the item sparkle **every
bounce loop** (create gated on `mBounceAnim == mEffectKeyFrame`, USA create
site 0x80155d8c) and overwrites mEmitter WITHOUT deleting the old one; each
pause session orphans several immortal emitters (observed 4-5 alive at screen
top, y≈24-40). They persist until a scene change frees the manager.

**v3 = v2 + second C2 @0x80155D8C**: stop the previous mEmitter right before
each re-create (r6/r7 scratch there; r0/r4/r5 live, do not touch):

```
C2155D8C 00000004
80DF0110 28060000
41820010 80E6011C
60E70001 90E6011C
806DA024 00000000
```

Possible follow-up: same create pattern exists at 0x8015ef40, 0x801608f4,
0x8016605c, 0x8016a980, 0x8016b800 (guide/save/option menus): extend the same
stop-before-create hook if lingering stars appear after those screens.
gpEmitterManager4D2 (USA) = [r13-0x5fdc] = 0x8040E1E4.

## v4 addendum (watchdog: the actual persistent stars)

The stars surviving v3 were **three continuous (maxFrame=0) banner emitters**
(episode-title/wipe sparkles, TConsoleStr) stranded at fixed screen positions
their cleanup milestone is skipped at 120fps (menu/banner logic ticks per
frame but emitters age at parity-60Hz = 1/4 the stock per-tick rate). Pause
plumbing STOPs all 2D emitters on pause and re-enables on unpause, which is
why they vanished while paused and returned on unpause.

Beware pool ghosts when scanning: the manager free list (mgr+0x14) keeps
freed emitters with stale "alive-looking" status/age; only membership in
mgr+0x44 group lists means active. Emitter+0x10 is the AGE frame counter
(f32), NOT a position; real position = unk160 (+0x160) / mTrans (+0x19C).

**v4 = v3 + watchdog C2 @0x80324EB8** (inside JPAEmitterManager::calcBase's
per-emitter else-branch; r29=manager, r30=emitter, r0/r3/r4 scratch, ends by
re-executing `mr r3,r30`): if manager==gpEmitterManager4D2 ([r13-0x5fdc] =
0x8040E1E4) && maxFrame(+0x1E8)==0 && !(status&1) && age(+0x10) raw-bits >
600.0f (10s at parity-60Hz) → set STOP_EMIT. Stranded emitters get re-stopped
within one frame of any unpause re-enable; legit sparkles never reach 10s
(counter emitters re-cleared each reveal, menu item recreated every bounce).
Cosmetic: on fresh level entry, title sparkles may linger up to ~10s once.

```
C2324EB8 00000009
806DA024 7C03E840
40820034 807E01E8
2C030000 40820028
807E011C 70600001
4082001C 809E0010
3C004416 7C040040
4081000C 60630001
907E011C 7FC3F378
60000000 00000000
```

Naming note: "$120fps + StarFix" contains NO framerate-global writes; it is
an add-on safe alongside exactly one base 120fps variant (TRUE-FIX v3).
