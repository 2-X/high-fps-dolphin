# Auto-flight recapture of M-portal preview footage — plan & state

Goal: reconstruct the original preview movie's camera paths (roughly), then have a
script fly the in-game camera along them automatically while Dolphin frame-dumps, and
feed the recordings into the existing THP pipeline (`../scripts/thp/`) at 384×432.

## Assets in this dir

- `colmap_{bianco,ricco,mamma}.png` — top-down height-colored collision maps with
  world-coordinate grids (regenerate: `python ../scripts/thp/col_map.py <map.col> out.png`;
  extract map.col from `data/scene/<level>0.szs` via `gcfs.py` + `arc.py`).
  mamma = Gelato Beach. Bounds: bianco x[-16182,20442] z[-26547,20946];
  ricco x[-25000,26030] z[-6340,25000]; mamma x[-17063,34352] z[-22121,30943].
- `shots_*.png` — contact sheets of the original footage (start/mid/end per shot).
  Shot structure: **Bianco 1 continuous pan; Ricco 3 shots (cuts ~f60,~f140);
  Gelato ~6 shots (~f60,~f112,~f140,~f267,~f292)**. 300 frames @29.97 total.

## Pipeline design

1. **Keyframes** (`keyframes_<level>.json`): per shot, a list of
   `{frame, pos:[x,y,z], target:[x,y,z], fov}` hand-authored by matching contact-sheet
   frames against the collision maps. Landmarks: Bianco windmill hill ≈ (8500,-13500),
   village lower-left quadrant, river runs N→S between them.
2. **Flight driver** (to build): external Python, extends `../scripts/gcmem.py`
   (which already locates MEM1 in the live Dolphin process) with WriteProcessMemory.
   Each emulated frame: Catmull-Rom interpolate pos/target, write into the active
   camera. Camera code: `CPolarSubCamera` (decomp `src/Camera/`, PAL symbols known,
   USA addresses NOT yet mapped — next work item). Options to stop the game fighting
   the writes: small Gecko to skip the camera-update call while a memory flag is set,
   or write after update each frame (racy but maybe fine at 120fps).
   Fields needed: camera world pos + look-at (JDrama::TLookAtCamera up/pos/at vectors)
   — get offsets from decomp headers, then find the live instance via xref/globals.
3. **Capture**: Dolphin PNG frame dump (GFX.ini `DumpFramesAsImages`) at IR 3x,
   levels loaded via episode select (pick episodes matching the footage's scenery),
   Mario parked out of frame.
4. **Assemble** (already built): crop mid-frame 8:3 band → 384×144 strips → stack
   Bianco/Ricco/Gelato per frame → `thp_from_frames.py <tmpl> <dir> out.thp 384 432`
   → `isopatch.py` into the HD ISO. 3× fits the 7MB heap with ~1MB slack (4× does not).

## Alternative playback mechanism (unexplored)

Scene archives contain authored camera path animations (`map/camera/*.bck`, e.g.
`bianco0_event0.bck`, `startcamera.bck`) played by the game's demo-camera system.
Authoring our own BCK and triggering it natively would avoid memory-race issues —
more reverse-engineering up front, cleaner playback. Consider if the memory-driving
approach fights the camera controller too much.

## Status

- [x] Level maps rendered (col format reversed — see col_map.py docstring)
- [x] Shot structure analyzed, contact sheets built
- [ ] CPolarSubCamera USA field/instance addresses
- [ ] Keyframe authoring (match contact sheets to maps)
- [ ] Flight driver script + camera-freeze Gecko
- [ ] Capture session + assembly
