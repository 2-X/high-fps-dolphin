---
name: sunshine-fov-mod
description: "SMS USA FOV override Gecko — USA CPolarSubCamera layout (mFovy@+0x48, not JP's +0x30), unified C_MTXPerspective hook + entity-culling companion hook at SetViewFrustumClipCheckPerspective 0x802260CC, substitute-f1 pattern"
metadata:
  type: project
---

**Purpose:** override Super Mario Sunshine's ~50° default FOV to an arbitrary
value via Gecko. USA build (GMSE01) only.

## USA CPolarSubCamera layout (differs from JP decomp)

The JP decomp header (`sms/include/JSystem/JDrama/JDRCamera.hpp`) puts
`TPolarCamera::mFovy` at offset **0x30**. **USA is different — mFovy is at
offset 0x48**, so USA's CPolarSubCamera looks TLookAtCamera-shaped
(mUp@0x30, mTarget@0x3C, mFovy@0x48). Empirically confirmed at 19 direct
`gpCamera→lfs +0x48` reader sites across the DOL.

Confirmed USA offsets on the camera object:
- `+0x28` mNear
- `+0x2C` mFar
- `+0x48` **mFovy**
- `+0x4C` mAspect
- `+0x50` mMode
- `+0x64` unk64 (mode flag bits — JET_COASTER=0x1000, GATE_DEMO=0x200)
- `+0x68` mCurrentParams pointer

`gpCamera` (global CPolarSubCamera*) lives at **0x8040D0A8**.

## Why the naïve "write to mFovy" Gecko fails

Every frame `CPolarSubCamera::ctrlGameCamera_` (USA `0x800234E8`) does
`*mCurrentParams = param;` where `param` is a fresh copy of
`mSaveKindParam[mMode]` — this wholesale overwrite wipes any Gecko-installed
mFovy override on either the camera OR the params struct. So a raw
pointer-follow write is a no-op.

The failed store site inside `ctrlGameCamera_` (`stfs f0, 0x48(r31)` at
**0x8002380C**) is also a bad hook target — it's gated by
`isNormalDeadDemo()` and `(unk64 & 0x1200)`; in some scenes the guard skips
the store entirely, so a C2 there silently never fires.

## Working fix — substitute f1 in-flight at the three read sites

Instead of touching the mFovy memory field, C2-hook the `lfs f1, 0x48(rN)`
loads that feed each C_MTXPerspective call and substitute `f1 = <fov>` before
the projection matrix is computed. The mFovy field itself stays stale, but
every consumer that matters gets the right value.

USA C_MTXPerspective = **0x8034A404** (found as the target of the `bl` at
0x8002322C; body matches the tanf-based cotangent shape).

Three call sites need patching for a complete fix:

| Address | Site | Original insn | What it drives |
|---|---|---|---|
| `0x80023218` | `CPolarSubCamera::perform` mFovy load | `lfs f1, 0x48(r29)` | main world render |
| `0x8022BA98` | `SMS_GetLightPerspectiveForEffectMtx` (MtxUtil.cpp:420) | `lfs f1, 0x48(r4)` | shimmer (`TShimmer`) + all screen-texture reprojections: Boo transparency, slug goo, glass, hotel bathwater, NPC parts |
| `0x80193FFC` | `TMirrorCamera::perform` | `lfs f1, 0x48(r4)` | mirror maps (Hotel Delfino) |

Skip these to preserve stock behavior in their scopes: CameraDemo cutscenes
(0x80032D8C/0x80033088), TCameraJetCoaster (own fovy), JDrama JSG demo
cameras (0x802F725C/0x802F769C — the 0x30 offset there is genuine, not a
stale-JP-offset bug), TLookAtCamera setter.

## Gecko template (substitute f1 = float via r12 + stack slot)

Each hook is a 3-line C2. Pattern for one hook at address `ADDR`:

```
C2AAAAAA 00000002        ; AAAAAA = ADDR & 0x01FFFFFF
3D80XXYY 9181FFF8        ; lis r12, 0xXXYY ; stw r12, -8(r1)
C021FFF8 00000000        ; lfs f1, -8(r1) ; terminator (branch-back)
```

Where `0xXXYY0000` is the upper half of the target FOV as IEEE-754 float bits
(mantissa low bits are always 0 for the common integer FOVs). The substitute
does NOT re-execute the original `lfs f1, 0x48(rN)` — the whole point is to
replace the loaded value.

Common float-bits upper halves:
- 60° → `4270`
- 73° → `4292`
- 75° → `4296`
- 80° → `42A0`
- 82° → `42A4`
- 85° → `42AA`
- 90° → `42B4`
- 95° → `42BE`
- 100° → `42C8`
- 110° → `42DC`
- 120° → `42F0`

## Full working code (unified 3-hook, FOV 82° shown)

```
$FOV 82 [kris]
C2023218 00000002
3D8042A4 9181FFF8
C021FFF8 00000000
C222BA98 00000002
3D8042A4 9181FFF8
C021FFF8 00000000
C2193FFC 00000002
3D8042A4 9181FFF8
C021FFF8 00000000
```

To retune, swap `A4` in all three lis words (bytes at positions 3 of
lines 2, 5, 8) in lockstep — folding the hooks into ONE entry keeps that
edit local.

## Entity-culling companion hook (fixed 2026-08-10)

Symptom: with the FOV widened, actors/enemies vanish near the screen edges
while still visible — the game's frustum culling still used the stale ~50°.

All entity culling funnels through one function:
`SetViewFrustumClipCheckPerspective(fovy, aspect, near, far)` = USA
**0x802260CC** (JP 0x800C1414; found by scanning for `bl` preceded by
`lfs f1,0x48/lfs f2,0x4C` camera arg setup — 10 dispersed callers; body
verified: 4× fcmpu early-out vs sKeepViewClip* statics at r13-0x612C…,
`bl tanf` = 0x8033C5CC, tail `bl SetViewFrustumClipCheck` = 0x80226174,
size 0xA8 same as JP). Callers: TLiveManager::clipActorsAux,
TConductor::clipAloneActors, gesso, enemyAttachment, fishoid,
TAnimalManagerBase, NpcManager.

Fix = 4th C2 hook at its ENTRY substituting f1, gated on value window
[40,56) — same philosophy as the unified render gate:

```
C22260CC 00000008
7C0802A6 3D804220    ; mflr r0 (re-exec original) ; lis r12,40.0 hi
9181FFF8 C001FFF8    ; stw/lfs f0 via -8(r1)
FC010000 41800024    ; f1 < 40 -> stock
3D804260 9181FFF8    ; 56.0 hi
C001FFF8 FC010000
40800010 3D80XXYY    ; f1 >= 56 -> stock ; XXYY = FOV float upper half
9181FFF8 C021FFF8    ; f1 = FOV
60000000 00000000
```

Why the window gate (not a flat force): **NpcManager passes fovy/aspect
SWAPPED** (stock game bug — `SetViewFrustumClipCheckPerspective(mAspect,
mFovy, ...)`), so its f1 ≈ 1.33 must pass through untouched to preserve
stock NPC clip behavior. Out-of-window demo fovs also stay stock; worst
case there is a clip frustum wider than render = slightly less culling,
which is invisible (the dangerous direction is narrower-than-render).

Retune = change BOTH substitute words in lockstep: `3D40XXYY` (render
hook, r10) and `3D80XXYY` (clip hook, r12). Installed in the live INI as
$FOV 58/60/62 (all unified+clip form now); reference file
`sunshine/research/codes/fov73-unified.txt`.

## Known limitation (as of 2026-08-09)

Portal-preview scenes (M-portals in Delfino Plaza) still render at native
~50° while our shimmer hook at `0x8022BA98` unconditionally forces 73°
during the preview's effect-mtx computation — so the shimmer inside the
portal preview is misaligned (mirror image of the world-shimmer bug we
fixed). Fix requires either widening the preview scene's own fovy or gating
the shimmer hook on "not a preview render pass"; see
[[sunshine-portal-preview-upscale]] for the preview render path.

## Falsely-plausible dead-ends (don't re-tread)

- **Camera+0x30 store**: writes a benign TLookAtCamera-shaped field, not
  mFovy. Won't crash; won't change anything.
- **`mCurrentParams->mFovy` write**: gets stomped every frame by
  `*mCurrentParams = param`.
- **C2 at `0x8002380C` (ctrlGameCamera_ store)**: guarded, sometimes never
  fires — appears to install cleanly but silently no-ops in some scenes.
- **`getFovy()` inlines reading 0x30**: no — every `.getFovy()` in USA
  compiles to `lfs f, 0x48(r_cam)`. Not a stale-JP-offset problem, USA is
  internally consistent at 0x48.
- **Overriding C_MTXPerspective entry** (0x8034A404 unconditional f1 fixup):
  works as a diagnostic sledgehammer but widens EVERYTHING including HUD /
  billboards / any non-camera use.
