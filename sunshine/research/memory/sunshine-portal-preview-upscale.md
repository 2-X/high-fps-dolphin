# M-portal level previews: mechanism + HD upscale pipeline (2026-08-04)

**STATUS: SHIPPED & USER-VALIDATED.** AI 3× (384×432) previews + the 7MB game-heap
patch confirmed working in-game — user: "wow they are amazing… proves out your heap
fix." Next planned step: Free Look recapture (see plan section) for maximum quality,
feeding the same pipeline at 384×144 per strip. The x4plus temporal flicker is present
in the shipped movie; recapture eliminates it at the source.

## How the previews actually work (fully reversed, USA addresses)

The image inside each M graffiti portal is **not** a texture in any scene file. It is a
**THP video**: `/data/EX128x144_q0.thp` — 128×144, 300 frames, 29.97fps, no audio, ~10s
loop. Each frame is a **vertical filmstrip of three 128×48 slices**: Bianco Hills (top),
Ricco Harbor (middle), Gelato Beach (bottom). Each gate's material samples its third.
Effective per-portal resolution is **128×48**, which is why previews look like smears.

Pipeline:

- `TMarDirector::thpInit` (`MarDirectorLoadResource.cpp`) opens the THP **only when
  `mMap == 1` (Delfino Plaza)**. Open/prepare failure error-outs the whole scene load, so
  a broken file is obvious immediately.
- The gate model (`map/map/gate/05_gate01.bmd` / `05_gate02rico` / `05_gate03manma`,
  inside `data/scene/dolpicN.szs`) contains NO preview pixels — just three 8×8
  `dummy_8x8i4` placeholder textures, a 32×32 spec sheen, the 32×32 `P_ms_indwp1_ia`
  indirect-warp ripple, and the 64×64 `P_gate_msk_m2` M-shaped mask.
- `TModelGate::loadAfter` (USA `0x801EBF20` = PAL `0x801E3F20`; **USA = PAL + 0x8000
  throughout ModelGate**) calls `THPPlayerGetVideoInfo` (USA `0x8001e9ec`) at
  `0x801ec168`, then stamps the returned dims into the three dummy BTI headers:
  fmt=I8, Y = w×h, U/V = (w>>1)×(h>>1) (`0x801ec194`–`0x801ec1bc`).
- `TModelGate::perform` (USA `0x801EAEEC`, size 0xAA8) binds the current decoded
  Y/U/V planes each frame; TEV does YUV→RGB (same scheme as `THPDraw.c`).
- `THPPlayerCalcNeedMemory`/`SetBuffer` size everything from the file header:
  read ring = bufSize×10, texture sets = 3×(Y+U+V).

**Conclusion: nothing anywhere hardcodes 128×144. A higher-res THP flows through the
entire engine automatically.** GX texture cap 1024 ⇒ max clean scale 6× (768×864);
we built 4× (512×576).

## Tooling (all in `sunshine/research/scripts/thp/`, stdlib + Pillow only)

- `gcfs.py` — list/extract GameCube ISO filesystem (FST).
- `arc.py` — Yaz0 decompress + RARC (.szs/.arc) list/extract.
- `bmdtex.py` — decode J3D BMD TEX1 textures → PNG (I4/I8/IA4/IA8/RGB565/RGB5A3/RGBA32/CMPR).
- `thp_upscale.py <in.thp> <out.thp> <scale> [quality]` — full rebuild: walk frames →
  re-stuff THP-JPEG → decode → Lanczos + mild unsharp → baseline 4:2:0 JPEG →
  normalize markers to THPConv layout (SOI + merged DQT + SOF0 + merged DHT + SOS;
  THP JPEGs have **no 0xFF stuffing** and no APP0) → de-stuff → reassemble with
  correct next/prev/size chain and header.
- `isopatch.py <src.iso> <dst.iso> <fst_path> <new_file>` — replace a file in a GC ISO
  by appending (32KiB-aligned) and rewriting its FST entry. Old data stays in place, so
  savestates made on the original ISO keep reading the OLD movie — **fresh boot required
  to see the new one.**

RVZ→ISO via `DolphinTool.exe convert -f iso`.

## Built artifacts (in `kris-documents\games\dolphin\`)

- `Super Mario Sunshine (USA) [HD portals 4x].iso` — patched, previews at 512×576
  (per-portal 512×192, 16× the pixels).
- `EX128x144_hd4x.thp`, `EX128x144_hd2x.thp` — the rebuilt movies, for re-patching.

## Validation status

- File structure round-trips: all 300 frames walk + decode, marker layout matches the
  original convention (one difference: original uses THPConv-optimized Huffman tables,
  ours are standard Annex-K — 416 vs 281 bytes; not implicated in any failure so far).
- **4× CONFIRMED TOO BIG (2026-08-04): instant crash on plaza load = the game's own
  `abort in "JKRHeap.cpp" on line 694`** (alloc failure; log captured in the patched
  build's `Binary/x64/dolphin.log` — note the user launches the *patched* Dolphin, whose
  portable User dir lives at `dolphin-src\Binary\x64\User`, and file logging is enabled
  there). thpInit asked for ~1.9MB; stock needs ~121KB.
- Root cause is structural: scene loading runs inside `TApplication::mHeap`, created with
  a **hardcoded 0x500000 (5MB)** (`Application.cpp:221-223`, `new(-0x20) u8[0x500000]`).
  So Dolphin's MEM1-size override does NOT help — the heap constant, not the arena, is
  the ceiling. Enlarging the game heap needs a code patch of that constant (root heap is
  arena-sized per `JKRExpHeap::createRoot(1,...)`, so slack likely exists — unverified).
- The ISO (renamed `Super Mario Sunshine (USA) [HD portals].iso`) now carries the
  **2× q85** movie (256×288; ring 10×18784=188KB + textures 331KB ≈ 523KB total).
  Untested in-game as of this writing.
- Fallback ladder if 2× also aborts: (a) `EX128x144_1x_diag.thp` — same-res re-encode,
  ~stock memory footprint, isolates encoding-vs-memory conclusively; (b) patch the
  0x500000 constant via Gecko to buy headroom and restore 4×.
- **Decode cost at 2×** is 4× stock pixels on the emulated CPU thread (~30 decodes/s in
  plaza). Watch VPS at 180fps.
- Quality ceiling: Lanczos+unsharp only reduces blockiness — user confirmed "can't tell
  if it looks better" in-game. **AI pass done 2026-08-04:** Real-ESRGAN ncnn-vulkan
  (official xinntao release zip, in scratchpad `resrgan/`; re-download from
  github.com/xinntao/Real-ESRGAN/releases v0.2.5.0 if needed). Model shootout on frame
  150: `realesrgan-x4plus` >> `realesr-animevideov3` (waxy) for this content. Pipeline:
  extract 300 PNGs → x4plus 4× → `thp_from_frames.py` (in `scripts/thp/`) downsamples
  to target and assembles. ISO now carries **AI 2×** (256×288 q85, ~552KB need — only
  ~30KB above the Lanczos 2× that loaded fine). `EX128x144_ai4x.thp` (512×576, ~2MB
  need) is pre-built in the games dir awaiting a game-heap enlargement patch
  (the 0x500000 constant) if 4× is ever wanted.

## Game-heap enlargement (2026-08-04, enables 4×)

`TApplication::initialize` USA `0x802A74E8` (`lis r3,0x50` → `new(-0x20) u8[0x500000]`)
and `0x802A74FC` (`lis r4,0x50` → `JKRExpHeap::create` size). Found via lis-immediate
scan; this region is USA = PAL + 0x8168 (cross-checked with `TMarDirector::direct`
USA 0x80299838 / PAL 0x802916D0). Patched 5MB → **7MB** two ways simultaneously:

1. **DOL patch inside the HD ISO** (authoritative; applies at boot before initialize
   runs): words at dol_off+v2f(va), verified 0x3C600050/0x3C800050 before writing.
2. **Gecko `$GameHeap 7MB (HD portals)`** (`042A74E8 3C600070` / `042A74FC 3C800070`),
   added+enabled in all three INIs via the dolphin-gecko skill. NOTE: Gecko 04-writes
   may apply *after* initialize already ran (code-handler timing) — that's why the DOL
   patch exists; the Gecko is redundancy/documentation and is harmless on the stock RVZ.

**4× result with 7MB heap: still JKRHeap-aborts at plaza load** (2026-08-04). Boot and
menu fine (so the 7MB block itself allocated — root tail had the slack), but the abort
backtrace differs from the 5MB crash: the movie's 2.1MB apparently fit and a *later*
scene allocation died. +2.0MB heap vs +1.98MB movie growth = zero margin. Deliberately
did NOT raise to 8MB: root heap must retain several MB for MovieDirector's fullscreen
cutscene THP buffers (rsetup allocates them transiently) — starving that would break
cutscenes in non-obvious ways. **Settled on AI 3× (384×432): ring 10×47296=461KB +
tex 729KB ≈ 1.2MB, ~1MB slack under the 7MB heap.** This is the ISO's current movie.
Per-portal: 384×144 = 9× stock pixels. If even more is ever wanted: shrink ring via
lower JPEG quality before touching the heap constant again.

## Recapture plan (user's idea, agreed as the quality ceiling)

Original movie shot structure (frame-diff analysis): **Bianco = 1 continuous pan;
Ricco = 3 shots (cuts ~f60, ~f140); Gelato ≈ 6 shots (~f60, ~f112, ~f140, ~f267,
~f292, some dissolves)**. Contact sheets: scratchpad `shots_{bianco,ricco,gelato}.png`
(regenerate from frames_up/ crops; bands y=0-192/192-384/384-576 at 4×).
Workflow: Dolphin Free Look, fly away from Mario, crop mid-frame 8:3 band (dodges the
top-screen HUD), Dolphin frame dump at 3× IR, ~10s per shot → crop/downscale to
512×192 strips → stack 3 levels/frame → `thp_from_frames.py`. AI-source flicker note:
`realesrgan-x4plus` shimmers frame-to-frame (user noticed); `realesr-animevideov3` is
temporally stable but waxier — recapture sidesteps both.

## Non-findings worth remembering

- `data/scene/dolpicN.szs → mapobj/efdokangate.*` is the pipe-warp effect, not the M gates.
- `TMareGate` (MapObjDolpic.cpp) is the Noki Bay gate light/sound only.
- The Dolphin hires-texture route would technically work but is strictly worse here:
  the THP frames dump as ~900 per-frame Y/U/V I8 planes with content hashes; replacing
  the disc file is cleaner, works at any emu settings, and survives texture-cache safety
  modes. The UHD texture pack only covers the M goop/mask, never the movie.
