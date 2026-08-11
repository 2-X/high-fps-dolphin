# M-portal level previews: mechanism + HD upscale pipeline (2026-08-04)

**⚰️ RETIRED 2026-08-11 — superseded by the UHD texture pack route.** The qashto/razius
SMS UHD pack (contrary to the note below) DOES ship the full preview movie as 900 hires
I8 Y/U/V plane textures, and the user judged it far better than our AI bake ("ours is so
bad by comparison"). The `[HD portals].iso` was sent to the Recycle Bin at the user's
request; **the canonical game is now the stock `Super Mario Sunshine (USA).rvz` + the
pruned texture pack** (`%APPDATA%\Dolphin Emulator\Load\Textures\GMSE01\`, see
`sunshine-hd-texture-prune.md`). The pack's plane hashes key off the STOCK movie, which
is exactly why the stock RVZ is required. The THP RE below (player pacing, heap limits,
addresses) remains valid and the `thp_pace` fpspatch block still applies — hires
replacement changes pixels, not playback pacing. The GameHeap 7MB codes are now inert
but harmless. Rebuild recipe if ever needed: thp-assets/ + isopatch.py + stock RVZ.

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
  build's `Binary/x64/dolphin.log` — note the user launches the *patched* Dolphin
  (`Dolphin b6d8bc2`); as of 2026-08-10 it is NOT portable — the live user dir is
  `%APPDATA%\Dolphin Emulator\`, not `dolphin-src\Binary\x64\User`).
  thpInit asked for ~1.9MB; stock needs ~121KB.
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

## ✅ ROOT CAUSE = DOUBLE JPEG ENCODE; FIX = single-encode from fresh ESRGAN (2026-08-06)

The bad flashing was the **extra JPEG generation**, confirmed in-game: a plain passthrough
(decode known-good THP → re-encode, no filter) flashed just as badly as the denoise/dither
builds. Every Mac-side rebuild decoded the already-JPEG'd movie and re-encoded = DOUBLE
encode. The known-good movie flashes only "a few" times because it was encoded ONCE from
the Real-ESRGAN PNGs. Density/dither was a red herring (falsified — see below).

**The fix (no PC needed — the 4090 was overkill for 300 tiny frames):** regenerate pristine
frames locally and encode ONCE.
- Real-ESRGAN runs on the M2 Max via Metal/Vulkan. Got the official macOS ncnn build:
  `sunshine/research/tools/resrgan/realesrgan-ncnn-vulkan` (chmod +x, xattr -d quarantine).
  Needs a user-added Bash allow rule `Bash(<abspath>/realesrgan-ncnn-vulkan:*)` in
  `.claude/settings.local.json` — INVOKE BY ABSOLUTE PATH as the first token or the rule
  won't match (no `time`/relative-path/`cd &&` prefix).
- Pipeline: stock THP → `thp_to_frames.py` → 300×128×144 PNGs →
  `realesrgan-ncnn-vulkan -n realesrgan-x4plus -s 4 -f png` (folder mode) → 512×576 pristine
  → Lanczos downscale to 384×432 → gentle spatial denoise `hqdn3d=3:2:0:0` (top-band grain)
  → `thp_from_frames.py ... 384 432 85` (the SINGLE encode).
- Density PROOF this reproduces known-good: fresh single-encode no-denoise = min7620/mean37808
  /stdev4846 ≈ known-good min7668/mean37778/stdev4845. With gentle denoise = min8792/maxbuf
  46400 (SAFER than known-good: higher min, under 47296 ceiling).
- SHIPPED to live ISO `thp-assets/EX128x144_final.thp` (11047952B), patched from clean
  pre-denoise backup, byte-verified. **Fresh boot.** Backup `...pre-denoise.iso` = grainy.
- **USER-CONFIRMED IN-GAME (2026-08-06): "much better", only "a bit of flickering still".**
  So double-encode WAS the bad flash; single-encode is the fix. Residual flicker = the
  inherent few-frame transition flashes + x4plus temporal shimmer (only recapture kills
  those). (Also: user booted the wrong ISO once — Fable's `CANDIDATE-passthru.iso`, since
  deleted; keep the folder to ONE testable ISO to avoid confusion.)
## ⚠️ "flickering" = WHOLE-FRAME BROWN FLASH (decode failure), NOT shimmer (2026-08-06)

User clarified the residual "flickering" is the whole frame going solid BROWN intermittently
— i.e. the original tan/nude DECODE flash, not x4plus temporal crawl. The entire de-flicker
/shimmer investigation below was aimed at the WRONG problem (shimmer work reverted).
Single-encode reduced the brown flashes ("much better") but didn't kill them.
LEADING HYPOTHESIS: at 120fps (2x sim) the game can't decode the 384×432 (9x stock pixels)
THP frame in time → shows an unfilled/garbage buffer = brown. The **2× (256×288) version was
the one the user originally validated as "amazing"** — brown appeared after moving to 3×.
ACTION: shipped a fresh single-encode **2× (256×288)** build from pristine ESRGAN frames
(`preview-work/esr256` → q90 → `thp-assets/EX128x144_final.thp`, 7297328B, ring 282KB+tex
324KB ≈ 606KB, ~44% of the 3× decode load). Awaiting in-game check.
2× result (user): brown flashes got SMALLER but MORE FREQUENT on all portals → decode time
is a lever. Halving header fps 29.97→14.985 (header offset 16, BE f32, no re-encode) helped
Bianco ("looks the best", browns ONCE) but Ricco/Gelato still flickered a lot; user disliked
the slowdown.

## Fable takeover: per-band cut/blank correlation (2026-08-06)

KEY EVIDENCE: all three portals sample ONE shared THP (per the RE above), yet flicker rates
differ per portal → the trigger is per-band CONTENT, and it correlates exactly:
Bianco 2 hard cuts (browns once — deterministically at the global f139/140 cut),
Ricco 42 cut-frames (worst flicker), Gelato 10 cuts + 3 blank placeholder bands (bad).
Deterministic once-per-loop browning ≠ random race. Read: race losses are only VISIBLE when
a frame differs sharply from its neighbor (cut) or is a flat placeholder (blank).
FIX SHIPPED: `preview-work/fix_cuts.py` on pristine esr256 — per band: rebuild blank frames
by interpolating non-blank neighbors; crossfade isolated cut spikes (6-frame fades,
wrap-aware → also softens the windmill loop snap from diff 45→14); sustained motion runs
left alone. Result: 0 blanks, 0 isolated spikes, tightest density ever (min 19232, stdev
2259 — no outlier frames at all). Single-encode 256×288 q90 @ 29.97fps (full speed
restored). Live as `EX128x144_final.thp` (7312560B). Awaiting boot.
**DEFINITIVE test RESULT (user, 2026-08-06): STOCK at 120fps does NOT flicker.** So the
flash is NOT hack-inherent — it's tied to our upscaled movies, with decode load (pixel
count) the dominant suspect: 2×=4× and 3×=9× stock pixels; even the cut/blank-smoothed 2×
still flickered. User leaned "keep it stock."
FINAL LADDER STEP SHIPPED: **1× ESRGAN-clean** — the smoothed pristine frames downscaled to
STOCK 128×144 (identical pixel-decode load; q75 → maxframe 5728 vs stock 3360, ring 55KB).
Visibly cleaner/sharper than stock at same res; keeps blank-rebuilds + softened loop.
Round-trip verified (300/300 clean). Live as `thp-assets/EX128x144_1x_clean.thp` (1480912B).
If THIS still flickers → the PIL/Annex-K encode itself is the trigger; restore true stock
(`preview-work/stock/EX128x144_stock.thp`) and stop — only a game-side THPPlayer patch
could go further. HD builds preserved: `EX128x144_sharp.thp` (3×), `EX128x144_final.thp`
(2× smoothed) for any future revisit (e.g. if a game-side decode-pacing patch ever lands).

## De-flicker pass (2026-08-06 — MISDIRECTED, was chasing shimmer not the brown flash)

User: "get rid of ALL flickering." The residual flicker = x4plus **temporal shimmer**
(hallucinated high-freq micro-texture crawling frame-to-frame). Findings:
- Temporal denoisers (atadenoise, hqdn3d-temporal) DON'T help — the video is in constant
  motion (pan + cuts), so there are no static regions to stabilize; motion-adaptive temporal
  filters correctly leave moving pixels alone → shimmer untouched (measured: M2 shimmer
  metric ~flat). Dead end.
- `realesr-animevideov3` (the temporally-stable model) **SEGFAULTS** on this M2 Max/MoltenVK
  (exit 139, any tile size). Unavailable.
- WHAT WORKS: the shimmer IS high-freq texture, so strong EDGE-PRESERVING SPATIAL smoothing
  removes the crawling texture while keeping edges. Shimmer metric M2 (temporal Δ of
  Laplacian): x4plus=18.7 → nlmeans s=8 =12.3 → **nlmeans s=20+hqdn3d (chosen)=5.7** →
  Lanczos-only floor=3.4. It's a genuine sharpness↔flicker tradeoff (they're the same
  high-freq content). Chose nlmeans++ (~70% shimmer cut, keeps AI edges); Lanczos-only is
  the softer zero-flicker fallback if user still sees crawl.
- Recipe: `nlmeans=s=20:r=9:p=5,hqdn3d=3:2:3:3` on the pristine esr384 x4plus frames, then
  `thp_from_frames ... 384 432 88` (q88 to hold min imgsz 7840 > known-good 7668 despite the
  smoothing). maxbuf 31744 (ring 310KB, lots of heap slack). SINGLE-encode.
- SHIPPED live as `thp-assets/EX128x144_final.thp`. Sharper prior build preserved as
  `thp-assets/EX128x144_sharp.thp` (x4plus+gentle-dn, min 8792) for A/B revert.
  Metric to reproduce shimmer measurement: temporal Δ of per-frame Laplacian over the 300.

- Windmill loop: user chose to LEAVE AS-IS (stock loop, windmill snaps back) — this build is
  FINAL as of 2026-08-06. Loop options offered (seam dissolve / windmill-lock stabilize /
  as-is); if ever revisited, do it on the pristine `preview-work/esr384*` frames BEFORE the
  single encode. The full pipeline to reproduce/extend is `preview-work/` (stock_frames →
  esr_out → esr384 → esr384_dn) + `tools/resrgan/`.

## ⚠️ DENSITY THEORY FALSIFIED IN-GAME (2026-08-06)

The "sparse frames → decode race → tan flash; denser = safer" theory below is **WRONG**.
The integrated 3-fix build (min imgsz 9788, DENSER than known-good, 0 frames under floor)
flashed **WAY MORE** in-game, not less. Adding checkerboard-Nyquist dither made it worse —
so the flash is almost certainly about specific JPEG *content* the game decoder mishandles
(the high-freq dither likely creates more of it), NOT frame byte-size/timing. Whatever the
real cause: (a) our re-encode itself may be the trigger — the ONLY confirmed-good movie is
the ORIGINAL grainy `EX128x144_ai3x.thp` that was never round-tripped through our
decode→reencode; every rebuild flashes to some degree; (b) suspect the standard Annex-K
Huffman tables (416B) vs stock THPConv-optimized (281B), or PIL's DQT/quantization, or a
marker-layout detail the game's fixed decoder is picky about. NEXT INVESTIGATOR: do a true
A/B — re-encode the grainy frames with NO other change and test in-game; if THAT flashes,
the re-encode/encoder is the culprit (pursue matching stock's exact JPEG tables), not
denoise or density. The loop fix (C) also "skips" per the user — the letterbox-phase loop
point reads as a skip, not satisfying. Live ISO REVERTED to known-good grainy.
User idea for the loop: AI-regenerate the windmill in the correct position per frame
(e.g. mark desired position in red as a guide) rather than re-timing. Handed off to Fable.

## Denoise is NOT viable via re-encode (2026-08-06, CONCLUSIVE — SUPERSEDED, see above)

**Do not try to denoise this movie by decode→filter→re-encode. It flashes a garbage
("nude"/tan) buffer in-game and MORE denoise = WORSE.** Two builds shipped and both
regressed; reverted the live ISO to the known-good grainy ai3x
(`Super Mario Sunshine (USA) [HD portals].iso`, movie sha 5fbde4c0…, 11341296 bytes;
backup `...pre-denoise.iso`).

Root cause (proven by extracting the STOCK THP from `Super Mario Sunshine (USA).rvz` with
the project's `dolphin/build/Binaries/dolphin-tool extract -s data/EX128x144_q0.thp`):
- The flash is **frame-density dependent, not temporal** (my first temporal-blend guess was
  wrong — a pure spatial denoise flashed *worse*). Per-frame JPEG image-size distribution:
  grainy-that-WORKS = min 7668 / stdev 4845; spatial-denoise-that-FLASHES = min 4600 /
  stdev 10739. Denoising creates near-empty flat frames.
- The game's fixed-function THP/GX JPEG decoder + the 120fps sim-hack decode timing races
  on fast-decoding sparse frames and shows an unfilled Y/U/V buffer (tan). Dense frames
  decode slowly enough to stay ahead; grain is effectively load-bearing pacing.
- Encoder path is NOT the culprit: the known-good grainy movie was built by the same
  `thp_from_frames.py` (PIL standard Annex-K Huffman, 416B DHT vs stock's 281B optimized) —
  only the pixel content differs. So it's the flatness, not the tables/normalize.
- No denoise setting escapes it: higher JPEG quality can't add data back to flat regions,
  it only inflates detailed frames → stdev gets *worse* (q92→14663, q97→21001) and maxbuf
  balloons (q97→83744, eating heap slack). Grain and "dense frames" are the same thing here.

New decoder tool added: `scripts/thp/thp_to_frames.py`.

**KEY GOTCHA — re-encode loses a JPEG generation:** decoding the shipped THP and
re-encoding the SAME frames at q85 drops min imgsz 7668→3292 and puts 33/300 frames under
the 7668 flash floor. So ANY rebuild (even a no-op) needs a density-restore pass or it
flashes. Fix = checkerboard-Nyquist dither into flat 8×8 blocks (std<1.5) of only the
sparse frames, escalating amplitude until imgsz clears ~9000 — imperceptible (±2–3 levels
on flat gray placeholder bands only). See `preview-work/B_flash/boost.py`.

## Three-fix integrated build (2026-08-06, SHIPPED to live ISO)

Fanned out 3 subagents over `preview-work/` (stable decoded frames + stock ref):
- **A windmill noise:** spatial-only `hqdn3d=4:3:0:0` on the TOP (Bianco) band only
  (144/432 rows → tiny density impact). Removes stone/grass grain, no ghosting.
- **B flash fix:** the density-restore dither above (mandatory, see gotcha).
- **C perfect loop:** Bianco pan is monotonic-left (0→−248px), so ping-pong rejected
  (would reverse camera). Found natural loop src292→src59 (seam MAD 45.5→7.02), resampled
  src range [59,292] into 300 top-band strips anchored to exact endpoints. ONLY the top
  band is re-timed; Ricco/Gelato bands stay on their original 0..299 timeline (bands are
  independent). Tradeoff: clean loop point sits in the letterboxed pan phase, so the
  windmill pans to gray at the seam (continuous, not a jump) — subjective; ping-pong is
  the alternative if user dislikes the gray.
Integration order per frame: C top band → A denoise → composite over untouched mid/bottom
→ B boost. Script: `preview-work/INTEGRATED/integrate.py`. Synergy: C's loop replaced blank
letterbox top-bands with detail, so only 9/300 frames still needed B's boost.
Result `thp-assets/EX128x144_final.thp`: min imgsz 9788 (>known-good 7668), 0 frames under
floor, maxbuf 46336 (<47296, smaller footprint than the known-good movie). Patched live via
isopatch from the clean pre-denoise backup, byte-verified inside the ISO. **Fresh boot.**
Backup `...pre-denoise.iso` = original grainy. Awaiting user in-game confirm.

**The ultimate quality ceiling is still the Free Look RECAPTURE below** (real detail =
naturally dense frames, no grain AND no flat-frame race, and a chance at a windmill-visible
loop).

## Denoise pass (2026-08-06, SUPERSEDED — see conclusion above)

User flagged the shipped AI 3× previews as grainy. No original source frames or
Real-ESRGAN present on the Mac, so reprocessed the shipped movie in place:
`thp-assets/EX128x144_ai3x.thp` → decode → ffmpeg denoise → re-encode.

- New tool `scripts/thp/thp_to_frames.py` — inverse of `thp_from_frames.py`; decodes a
  video-only THP to `frame_%05d.png` (reuses the `thp2jpg` de-stuff from `thp_upscale.py`).
- Pipeline (needs the repo venv `research/.venv-thp` for Pillow; ffmpeg 7.1 at /usr/local):
  `thp_to_frames.py ai3x.thp orig/` → `ffmpeg -vf "hqdn3d=4:3:6:4.5,unsharp=3:3:0.3:3:3:0"`
  → `thp_from_frames.py ai3x.thp clean/ ai3x_dn.thp 384 432 85`.
- **DO NOT use hqdn3d's temporal term on this movie.** First attempt used
  `hqdn3d=4:3:6:4.5` (luma_tmp=6). In-game that flashed a "nude"/tan color between frames.
  Diagnosis: the movie is high-motion throughout (a frame-diff cut scan flags ~160/300
  frames), so temporal averaging blends constantly-moving frames into ghost/transition
  frames; the game's fixed-function THP/GX JPEG decoder renders those worse than PIL does
  (PIL decode of our THP showed NO tan frames — structure was byte-identical to the
  known-good shipped movie, so it's the game decoder reacting to the transitional pixels).
- **Fix = SPATIAL-ONLY denoise:** `hqdn3d=5:4:0:0,unsharp=3:3:0.35:3:3:0` (temporal terms
  `:0:0` = no cross-frame blending at all). Each frame processed independently → cannot
  produce a between-frame artifact. Still removes the grain (the actual complaint). The
  x4plus temporal shimmer remains (pre-existing) — only recapture removes that.
  A heavier `nlmeans` spatial variant went waxy (same failure mode as animevideov3) —
  rejected. Balanced spatial hqdn3d is the keeper.
- Result `thp-assets/EX128x144_ai3x_dn.thp`: maxframe 46080 → ring 450KB + tex 729KB,
  i.e. slightly *smaller* runtime footprint than the shipped 47296/461KB, so it fits the
  7MB heap with ~1MB slack (no heap change needed). File 7.9MB vs 11.3MB.
- **SHIPPED into the live ISO (2026-08-06):** patched `data/EX128x144_q0.thp` in
  `/Applications/gamecube/Super Mario Sunshine (USA) [HD portals].iso` via `isopatch.py`
  (spatial-only rebuild, 11341296→7878320 bytes at 0x57B30000; superseded the earlier
  temporal-denoise build that flashed), byte-verified from inside the ISO, then swapped
  over the original filename so Dolphin's library entry is unchanged. Rollback copy kept:
  `...[HD portals].pre-denoise.iso` (the old AI-3x-grainy movie). **Fresh boot required** —
  savestates keep reading the old movie. Runtime footprint is smaller than the known-good
  shipped movie, so plaza load is safe (no re-test of the JKRHeap ceiling needed).

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

## ⚠️ ADDRESS CORRECTION (2026-08-10): ModelGate TU shift is +0x8128, NOT +0x8000

Verified against the real TModelGate vtable @0x803D3F9C + GMSP01 symbols.txt:
perform = USA **0x801EB014** (size 0xAA8; the doc's 0x801EAEEC is the tail of the prior
fn), loadAfter = USA **0x801EC048** (0x801EBF20 is mid-function), startOpen 0x801EBFD4,
receiveMessage 0x801EBBDC, screenBlur 0x801EBD84. Other TU shifts: THPPlayer USA =
PAL − 0xB8 (GetVideoInfo 0x8001E9EC ✓), MActor/particle-mgr USA = PAL + 0x8274,
VI USA = PAL + 0x7DA4. The `0x801EC168 bl THPPlayerGetVideoInfo` above was right only
because it was found empirically (it's inside the real loadAfter).

## Mirage/shimmer pacing under fpspatch (2026-08-10 — FIXED, `thp_pace` in fpspatch.py)

UPDATE same session: the proposed fix below was implemented as `thp_pace(fps)` in
fpspatch.py (default-on at integer G, `--no-thp-pace` to omit, `--check` enforces
structure/discriminator/divisor 5994·G), shipped in all four regenerated
`codes/bare*.txt` and installed to the live INI via the watcher pattern. Cave verified
vs main.dol: hook word 0x38C0176A, r31=player base (set @0x8001EB14), audioExist zeroed
@0x8001F860 & only set when an audio component exists. Awaiting in-game confirm.

User report at 240fps: "shimmer more active than it should be, heat mirage pulsates
faster than normal." Full disassembly verdict:

- **The warp/ripple itself is CORRECTLY compensated.** The mirage is real anim files —
  each gate binds `05_gate0N.btk` (UV-scroll ripple) + `.brk` (color pulse) + `.bpk`
  (open) via MActor::setBtk/setBrk in loadAfter (0x801EC1F8/0x801EC210, name table
  0x803D3F38). Every MActor binder stores SMSGetAnmFrameRate into J3DFrameCtrl.mRate at
  bind time (e.g. 0x802385A0-A4) and MActor::perform (0x802391BC) advances on cue&2 only
  → stub 0.5 × 120 Hz = stock 2.0 × 30 Hz = 60 anim-frames/s at every G. 1×.
- perform's CALC_ANIM section has a raw 8-phase TEV stepper (+0xB9/+0xBC/+0xBE, jump
  table 0x803D4050) that would be 4× fast, but it's gated on this+0xB8==1 and the ONLY
  writer in the whole text section is loadAfter's `stb 0` (0x801EC1CC) — dead/vestigial.
- Minor raw 4×/120Hz bits (glow fade steps 0x801EB518/0x801EB540, sparkle counter,
  sound retriggers, wind-haze JPA requests 0x131-0x134) — particle emits are deduped by
  (id,owner) in TMarioParticleManager::emitAndBindToMtxPtr and JPA calc is already
  60Hz-gated by _rate_gate, so haze density ≈ stock. Not the user's pulse.
- **CULPRIT: THP playback is G× FAST.** THPPlayer paces off the VI post-retrace callback
  (PlayControl USA 0x8001EC24, registered @0x8001F2A4): 64-bit retrace count × 2997 /
  5994 (NTSC divisor `li r6,0x176A` @**0x8001EBDC**; PAL 0x1388 @0x8001EBA4) picks the
  display frame (cmp @0x8001EBF4, dispTextureSet stored @0x8001EE3C → player global
  0x803EC160 +0xF8). EmulationSpeed=G makes emulated VI run 59.94×G fields per WALL
  second → movie plays 29.97×G fps: 2×/3×/4×/6× at G=2/3/4/6. Explains BOTH halves of
  the report: x4plus temporal shimmer crawls per movie frame (4× at 240), and the
  "mirage pulsing" is the stock-paced warp over 4×-churning content. Bonus: decode load
  is also G× (~120 decodes/s at G=4) — the same decode-race pressure behind the brown
  flashes above; repacing would cut it 4×.

**Proposed fix `thp_pace` (constant-rescale family, like the anmrate blocks):** C2 @
0x8001EBDC — if framerate global 0x804167B8 != 0.5f keep `li r6,0x176A`, else r6 =
5994·G via lis/ori (5994×6 overflows signed li). **Discriminator: require player+0xA7
(no-audio flag; r31 = player base in this helper, set @0x8001EB14) == 0** so fullscreen
cutscene THPs (audio-mastered, audio rides AI/DSP at G×) keep their sync — the gate
preview THP has no audio. Rejected alt: gating the retrace increment (0x8001ECA8) —
messier 64-bit carry, hits audio movies too. --check: pre-patch word @0x8001EBDC ==
0x38C0176A, divisor == 5994·G, gate word == float(G). Optional cosmetic follow-up: 1-in-4
gate on perform's CALC_ANIM body (branch @0x801EB374) for the 4× glow decay/sparkle/
sound bits — but PROXIMITY_GLOW's C2 @0x801EBA60 lives inside that block (dropping its
refresh to 30 Hz is harmless, it's a state pin). Ship thp_pace alone first, re-test
perception. Disassembly artifacts (dol.py/ppcdis.py/scan.py + extracted main.dol) were
session-scratchpad only.

## Non-findings worth remembering

- `data/scene/dolpicN.szs → mapobj/efdokangate.*` is the pipe-warp effect, not the M gates.
- `TMareGate` (MapObjDolpic.cpp) is the Noki Bay gate light/sound only.
- The Dolphin hires-texture route would technically work but is strictly worse here:
  the THP frames dump as ~900 per-frame Y/U/V I8 planes with content hashes; replacing
  the disc file is cleaner, works at any emu settings, and survives texture-cache safety
  modes. The UHD texture pack only covers the M goop/mask, never the movie.
