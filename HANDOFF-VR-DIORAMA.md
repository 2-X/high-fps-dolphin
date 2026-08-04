# Handoff — Sunshine VR diorama on Quest 3 (via DolphinXR)

**Written 2026-08-03 on the Mac; intended to be picked up on the PC.**
This is a separate track from the high-FPS project in `sunshine/README.md` — almost
none of that work carries over here (see "Relationship to the high-FPS project" below).

## Goal

Super Mario Sunshine rendered as a **static, smaller-than-life, third-person diorama**
in VR on the Quest 3 — the level floats miniature in front of you (ideally over the real
desk via passthrough) while you play normally with a controller. Later phase: hand-tracking
pinch gestures — spread two pinched hands to zoom in, squeeze together to zoom out, move
pinched hands to pan the camera. Mostly, though, the camera stays parked.

## Chosen stack (and what was ruled out)

- **DolphinXR** — https://github.com/iChris4/dolphinXR — actively maintained OpenXR
  rebuild of the old Carl Kenner "Dolphin VR" fork. Latest release **v0.3 (2026-07-02)**
  ships `DolphinRedux-app-quest-debug.apk` (experimental Quest-native build) plus
  Windows/Linux builds. Runs standalone on the Quest 3 — no PC streaming needed, but the
  PC is the sideload/build machine.
- Ruled out: original Dolphin VR fork (abandoned ~2016, dead SDKs), macOS anything
  (no OpenXR runtime exists on macOS), Vision Pro (no Dolphin VR layer exists).
- Mainline Dolphin has no merged VR support (see dolphin-emu PR #8380 history).

## Phase 1 — Install on the Quest 3 (no code, ~30 min)

1. Free developer account at developer.oculus.com, then Meta Horizon phone app →
   Devices → Quest 3 → Headset Settings → **Developer Mode** on → reboot headset.
2. On the PC: install adb (`winget install Google.PlatformTools` or use SideQuest).
   Connect Quest via USB-C, accept the "Allow USB debugging" prompt in-headset,
   confirm with `adb devices`.
3. Download `DolphinRedux-app-quest-debug.apk` from the DolphinXR v0.3 release page,
   then `adb install DolphinRedux-app-quest-debug.apk`.
4. `adb push "Super Mario Sunshine (USA).rvz" /sdcard/Download/`
   — use the **US RVZ** (same image as the high-FPS project; on the Mac it lived at
   `/Applications/gamecube/`, not in git). Nothing decomp/JP-related applies here.
5. Launch from App Library → Unknown Sources → Dolphin Redux. Point it at the game
   folder. Headset settings (launch-in-VR, resolution scale, reference space,
   controller bindings) live under the **OpenXR section** of in-app settings.
6. Start with **Vulkan** backend and **1x internal resolution**; Sunshine is one of the
   heavier GC titles for the XR2 Gen 2. GLES is the fallback backend.

Expectations: the Quest build is labeled *experimental* and the APK is a debug build —
expect rough edges and per-game fiddling.

## Phase 2 — Diorama view (config only, no code)

DolphinXR keeps the DolphinVR-heritage **per-game VR profiles**:

- **World scale** (Units-Per-Metre-style setting): raise it until the level shrinks
  from life-size to tabletop miniature. This single setting is the core of the effect.
- **Free-look camera**: pull back/up to a third-person vantage and leave it parked.
  Bind free-look move/zoom to the controller sticks — zero-code stand-in for hand
  gestures.
- **AR/passthrough mode** (added in their v0.2): miniature level floating over the real
  desk on Quest 3. Try this early — it is the strongest version of the concept.
- **"Lock Head Pose Per Frame"** compat option if the image swims/judders.
- Old Dolphin VR community configs for Sunshine (the first-person YouTube videos) have
  known-good per-game values worth mining, even though we invert the intent
  (miniature, not life-size).

Key insight: **game framerate barely matters in diorama mode.** The world is static in
room space, so head-tracking smoothness comes from the headset's reprojection, not the
emulator. 30fps emulation looks fine; the 120fps work is unnecessary here.

## Phase 3 — Pinch-gesture camera (the coding project)

Well-scoped because it never touches emulation — the gestures are just another writer
to the same free-look/world-scale state the settings UI already writes.

1. Fork/clone DolphinXR; build the Quest APK per the repo's `AndroidSetup.md`
   (Android Studio toolchain; works on Windows or Mac).
2. AndroidManifest: add `com.oculus.permission.HAND_TRACKING` + the hand-tracking
   `<uses-feature>` flag so Quest exposes hands to the app.
3. OpenXR layer: enable `XR_EXT_hand_tracking` at session creation, create the two
   hand trackers, poll `xrLocateHandJointsEXT` each frame next to the existing
   head/controller pose polling.
4. Gesture logic: pinch = thumb-tip↔index-tip distance < ~2 cm.
   - Both hands pinched → inter-hand distance ratio multiplies world scale
     (spread = zoom in, squeeze = zoom out); midpoint movement translates the camera.
   - One hand pinched → drag to pan/orbit.
   Estimated a few hundred lines in one subsystem. Exact file/function touchpoints in
   the DolphinXR tree have NOT been mapped yet — that is the first task of this phase.

## Relationship to the high-FPS project

- The custom Dolphin **audio DMA patch and sim-rate Gecko codes do not carry over** to
  DolphinXR and are not needed (diorama mode makes high fps irrelevant — see Phase 2).
- Shared assets: the US RVZ and the `.gci` memcard save (`sunshine/saves/`) — the save
  can be pushed to the Quest's Dolphin user folder if you want progress carried over.
- The M-portal / TRUE-FIX work is irrelevant here since stock game timing is used.
