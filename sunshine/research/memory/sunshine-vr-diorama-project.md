---
name: sunshine-vr-diorama-project
description: "Plan to run Super Mario Sunshine as a miniature third-person VR diorama on Quest 3 via DolphinXR, later adding pinch-gesture camera control"
metadata: 
  node_type: memory
  type: project
  originSessionId: 83887dc7-b027-4e35-8dcf-b3a376898c45
---

As of July 2026, Kris wants Super Mario Sunshine as a static, smaller-than-life third-person diorama in VR (not first-person), eventually with hand-tracking pinch gestures: spread hands = zoom in, squeeze = zoom out, move pinched hands = pan camera.

Chosen path: **DolphinXR** (github.com/iChris4/dolphinXR), an actively maintained OpenXR rebuild of the old Carl Kenner Dolphin VR fork. Latest release v0.3 (July 2, 2026) ships `DolphinRedux-app-quest-debug.apk` (experimental Quest build). Not supported on macOS; Quest 3 standalone is the target.

Key facts:
- Diorama view needs no code: per-game VR profiles with a Units-Per-Metre-style world scale + free-look camera; v0.2 added AR/passthrough mode (miniature level over the real desk) and a "Lock Head Pose Per Frame" compat option.
- Game framerate barely matters in diorama mode (head tracking comes from headset reprojection), so the [[sunshine-highfps-hardware-ceiling]] 120fps work is not needed here; the custom Mac build's sim-rate/audio patches do not carry over to DolphinXR.
- Pinch gestures = Phase 3 coding project: manifest `com.oculus.permission.HAND_TRACKING`, enable `XR_EXT_hand_tracking` at session creation, poll `xrLocateHandJointsEXT` per frame, map gestures onto the existing free-look/world-scale state. Build via repo's AndroidSetup.md (Android Studio on the Mac works).
- Use the US ISO converted to RVZ, pushed via adb; decomp/JP notes from [[sunshine-simrate-mechanism]] are irrelevant to this branch of the project.

Picked over old Dolphin VR (abandoned, Windows-only, dead SDKs) and Vision Pro (no Dolphin VR layer exists).
**How to apply:** if VR/Sunshine comes up, assume Quest 3 + DolphinXR path; offer to map exact code touchpoints in the DolphinXR repo for the hand-tracking phase.
