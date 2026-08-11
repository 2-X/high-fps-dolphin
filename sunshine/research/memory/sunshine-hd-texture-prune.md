# SMS HD texture packs — pruned install (2026-08-10)

Pruned Dolphin hires-texture pack installed at
`%APPDATA%\Dolphin Emulator\Load\Textures\GMSE01\` containing ONLY: M-portal
textures, FLUDD HUD, lives-counter head, coin-counter icon, counter digits.
User explicitly does NOT want the rest of the packs.

## Source packs (qashto/razius "Super Mario Sunshine UHD Texture Pack" v2.1.1)

Canonical community pack (the "1080p" and "4K/UHD" packs are the same project's two
release variants). GitHub release 2.1.1 (Oct 2020),
https://github.com/qashto/Super_Mario_Sunshine_UHD_Texture_Pack (forum thread:
forums.dolphin-emu.org "super-mario-sunshine-uhd-texture-pack").

Downloaded archives KEPT in session scratchpad
`C:\Users\krisb\AppData\Local\Temp\claude\C--code-high-fps-dolphin\743edaee-a408-4700-b81d-71be9588b664\scratchpad\downloads\`:

- `GMS.7z` — 4K/UHD pack, DDS BC7, 941 MB (extracted: `..\ext4k\GMS\Textures\GMS\`)
- `GMS_1080.zip` — 1080p pack, DDS, 149 MB (extracted: `..\ext1080\`)
- `SMS_UHD_Update_Patch_1_DDS.7z` — update patch 1, 67 MB (extracted: `..\extpatch\`)

URLs: `https://github.com/qashto/Super_Mario_Sunshine_UHD_Texture_Pack/releases/download/2.1.1/{GMS.7z,GMS_1080.zip,SMS_UHD_Update_Patch_1_DDS.7z}`

Notes: 1080p and 4K variants contain the IDENTICAL file-name sets (same dump hashes,
different resolutions) → everything kept was taken from the 4K pack; nothing needed the
1080p one. The update patch's `m_warps` files are byte-identical to the 4K base (patch
only updates fonts/title/misc/widescreen-stars, none of which we keep). No 7-Zip on the
box: Win11 `tar` (bsdtar) extracts .7z fine.

## What was kept (133 MB, 954 files, all from the 4K pack)

- `m_portal\thp_preview_planes\` — **900 files**: the packs DO ship the portal preview
  movie as hires textures — 300× Y planes `tex1_128x144_<hash>_1.dds` + 600× U/V
  `tex1_64x72_<hash>_1.dds` (pack folder `environment/m_warps`). This CORRECTS the
  claim in `sunshine-portal-preview-upscale.md` ("The UHD texture pack only covers the
  M goop/mask, never the movie") — it's the opposite: the pack covers the MOVIE frames
  but NOT the gate mask/goop.
  ⚠️ Hash caveat: these hashes come from the STOCK `EX128x144_q0.thp`. The user's
  `[HD portals].iso` carries a REPLACED movie → decoded Y/U/V bytes differ → different
  hashes → these never trigger on that ISO (harmless). They only apply when running a
  stock-movie ISO/RVZ.
- `m_portal\tex1_72x72_f01ad8ad7d535245_2.dds` — black brush "M" graffiti decal
  (pack `environment/unsorted`), the Shadow-Mario-style M mark; the only M-graffiti
  texture in the packs (visually confirmed).
- `hud_fludd\` — 13 files, entire pack `gui/fludd`: nozzle icons (hover/rocket/turbo),
  water-gauge frame/fill/spray, × marker (visually confirmed).
- `hud_lives\tex1_35x38_47d941afe5ba76d6_5.dds` — Mario-head lives icon (pack
  `gui/icons`). The pack also has a `..._5_alt.dds` variant (inert for Dolphin unless
  renamed over the main one) — left out, in scratchpad if wanted.
- `hud_coins\tex1_30x40_06f47ce9bd931cee_5.dds` — gold-coin counter icon (pack
  `gui/icons`). Red-coin (`6066c75478ca20`) and blue-coin (`8c76342201dcb8`) icons
  exist in the pack but weren't requested.
- `hud_numbers\` — 38 of 41 files from pack `gui/numbers`: all digit glyph sets
  (28x28 orange, 32x32 white, 36x36 yellow-orange, 40x40 green) + both × marks.
  The digit styles are shared across the coin/lives/shine counters and can't be split
  per-counter by hash, so all digits were kept. EXCLUDED: two 52x52 shine-sprite doodle
  icons (`150d2b047e576553`, `8c41b7b3d656f8a7`) and the 50x20 "???" (`307ba6b02583a0f3`)
  — shine counter wasn't requested.

## NOT in the packs (searched all 64x64/32x32/8x8 I4/I8/IA formats, visually swept)

- The 64×64 `P_gate_msk_m2` M-shaped gate mask — absent.
- The 32×32 `P_ms_indwp1_ia` indirect-warp ripple and 32×32 spec sheen — absent.
- So the gate model itself keeps stock textures; only the movie planes + M decal exist.

Deliberately excluded (close calls): `gui/life` (the 8-segment LIFE/health meter +
"LIFE" text — health gauge, not the lives counter), 24x18 pixel Mario head
(`f433fadf757a15`, likely file-select), everything else in the packs.

## Addendum (2026-08-11): episode-select screen textures added on user request

All from the 4K pack, visually verified via DDS contact sheets. Install grew to
167 MB / 1107 files.

- `episode_select\level_titles\` — 26 files, all ENGLISH level-name wordmarks from
  pack `gui/text`, in the game's three styles per world:
  - Big blue-outline episode-select logos (fmt `_5`, ~320-500x50): BIANCO HILLS
    `454x50_df05609140aeab06`, GELATO BEACH `460x50_17ae6a23b59bcca2`, RICCO HARBOR
    `474x50_5e1c3f78243abc9e`, SIRENA BEACH `476x50_a47578f9e9b2bf49`, PINNA PARK
    `360x50_8df98ab91c73fd73`, NOKI BAY `320x50_f131f6b0e80c94d9`, PIANTA VILLAGE
    `500x50_794a9f476d81b933`. (Only these 7 worlds have episode-select screens; no
    `_5` logo exists for Delfino Plaza/Airstrip/Corona.)
  - Medium white-caps (fmt `_2`, ~118-232x26-28) and small white-caps (fmt `_0`,
    ~130-210x20) variants for all 10 areas incl. DELFINO PLAZA, DELFINO AIRSTRIP,
    CORONA MOUNTAIN (small style only for Corona).
  Deliberately skipped: all non-English language variants (never load on the USA
  ISO: PLAYA GELATO, BAIE NOKI, MONTE BIANCO, KAPITEL, ...), the mixed-case
  pause/map labels ("Corona Mountain" thick-outline style), the tiny 64x16 yellow
  location plates, and SUPER MARIO SUNSHINE boot wordmarks.
- `episode_select\wordmarks\` — EPISODE rainbow `114x28_4d3e0661ddb61b36_5`,
  "???" `50x20_307ba6b02583a0f3_5` (moved intent: now wanted), SCORE yellow
  `80x20_d18624c1b46d499b_5`, SCORE white `86x26_ce5aff1cbf2eba90_2`. English only;
  EPISODIO/KAPITEL/PUNTEGGIO/etc. skipped. (A curved "SCORES" records-screen mark
  `89x22_19804174c3d7afff_0` exists in the pack; not installed.)
- `episode_select\letters\` — all 116 files of pack `gui/letters`: the discrete
  UI letter-glyph set (episode/level name letters incl. glow/selected variants,
  colored file-select A/B/C caps, punctuation). UI-only, no gameplay textures.
- `shine_icons\` — previously-excluded shine graphics, now wanted: gold shine
  counter/status icons `26x30_999fa683890afc1f_5`, `32x38_c66879b76711de15_5`,
  `38x46_c26a83dda44dc8b6_5`, partial flash shine `32x64_7499709cce8fe70c_14`
  (all pack `gui/icons`), white shine outline `32x32_46e34569265f7c42_0`
  (pack `gui/misc`), and the two 52x52 doodle-shine sprites
  `150d2b047e576553_2` / `8c41b7b3d656f8a7_2` (pack `gui/numbers`).
- Episode-number glyphs (big green digits) and the white × were ALREADY installed
  in `hud_numbers\` (40x40 green set + both × marks) — nothing further needed.

Not in the packs / not found: no dedicated episode-thumbnail frames or episode-list
banner textures beyond the above (episode preview pictures are live render-to-texture,
not dumpable statics).

## Addendum (2026-08-11 #2): file-select screen + WATER wordmark + GC button note

All from the 4K pack (re-extracted to scratchpad `..\ext4k\` — the earlier extraction had
been cleaned; archives were still there). Visually verified via contact sheets (Pillow
12.x decodes the BC7 DDS directly). Install grew to 177 MB / 1122 files.

- `file_select\` — NEW folder, 14 files:
  - Button wordmarks (white caps, pack `gui/text`, fmt `_2`): START
    `86x26_9bee06d8439a0efe`, COPY `70x26_76b33b6f37ae8f08`, ERASE
    `88x26_df56f15d71e7931b`. NO selected/glow/yellow variants of these exist in the
    packs (yellow style only exists for SCORE/TIME/etc.).
  - Confirm-dialog buttons: YES `58x26_25d908c536081b4f` + all three NO marks
    `40x24_616dc59543c3a842`, `40x26_6a3e2ff2b74956a2`, `40x26_d4575af051d75ed5`
    ("NO" is identical in EN/ES/IT and the hashes can't be told apart; two are dead on
    USA, harmless).
  - Save-file cards (entire pack `gui/save_blocks`, 4 files, fmt `_14` 64x64): wooden
    file blocks with A `e21bd86aa357fc08`, B `6c9094c3bb00af96`, C `5bfe45b44622736f`
    + blank card `d653b96492d5441e`.
  - Menu chrome (pack `gui/menu`): white glove hand cursor `32x46_65d33552004c8a9a_2`
    + variant `32x46_d7c966dd2344803f_2`, white paint-stroke selection highlight
    `180x22_d15419e685bdc648_0`.
  - Deliberately skipped from `gui/menu`: GC controller pic, OPTIONS sign, speakers,
    doodle-Mario, Proll blobs (options screen, not file select).
- `hud_fludd\` — added WATER `80x32_cfda62185dc4dd01_5` (blue bubble caps, pack
  `gui/text`), the water-gauge label; folder now 14 files. Non-English gauge labels
  (WASSER/AGUA/EAU/ACQUA) and Yoshi-juice labels (JUICE/NECTAR/SUCCO/...) skipped.
- GC button prompts: the gray kidney X-button icon `34x44_c9717b966554213f_2` was
  ALREADY installed (it's part of pack `gui/fludd` = our hud_fludd; previously
  mislabeled "× marker" — it is the X button prompt next to the nozzle icon).
  NOT in the packs: any other GC button icons (A/B/Y/Z/L/R prompt glyphs) — swept all
  gui folders (menu/misc/icons/letters/fonts/map/title/life/yoshi/save_blocks); the
  only controller art is the full-controller options picture. SMS's UI only ever shows
  the X prompt, so nothing is missing in practice.

## Addendum (2026-08-11 #3): pause menu, coin icons, TIME, MARIO wordmarks

All from the 4K pack, zoom-verified. Install now 178 MB / 1131 files.

- `pause_menu\` — NEW folder, 3 files (white caps, pack `gui/text`, fmt `_2`):
  CONTINUE `96x26_07ad01cc9aad815b`, SAVE `60x26_163f61548493efbb`, EXIT AREA
  `100x26_d002bb380a37badf`. ⚠️ near-miss: `100x26_44febe02ce5c537c` is Italian
  CONTINUA, not EXIT AREA — verify by render, not by sheet-adjacency. No
  selected/glow variants of these exist; selection is drawn with the white
  paint-stroke highlight already in `file_select\`.
- `hud_coins\` — added red coin `30x40_6066c75478ca20d4_5` and blue coin
  `30x40_8c76342201dcb87d_5` (pack `gui/icons`), joining the gold coin. These are
  the ONLY coin icons in the packs — one texture each, used both by counters and
  the pause menu. No "blue coin with Mario face/M" variant exists anywhere in the
  packs (the plain blue coin is what the pause screen shows).
- `hud_timer\` — NEW folder, 1 file: TIME yellow `68x28_595e067e973ac06d_5`
  (pack `gui/text`). NO white TIME exists — the white/yellow pair convention
  (SCORE) does not extend to TIME; yellow is the only style. Non-English
  TEMPO/TEMPS/TIEMPO/ZEIT skipped.
- `file_select\` — added all three MARIO wordmarks (language-independent, pack
  `gui/text`, fmt `_5`): arched pink `72x34_df435df4c810c026`, straight pink
  `76x22_5f1506130533aa71` (the save-dialog "MARIO A" style), multicolor
  `90x27_973c2944edf640cc`. Folder now 17 files.

## Addendum (2026-08-11 #4): life meter (the "sun in the top right")

Reversed the batch-1 exclusion on user request. All from the 4K pack, contact-sheet
verified. Install now 180 MB / 1150 files.

- `hud_life\` — NEW folder, the COMPLETE pack `gui/life` (19 files). This is the
  sun-dial health meter shown top-right during gameplay:
  - 8 filled petal segments (yellow→orange, fmt `_5`, 24x24–28x28) + the 8 matching
    empty gray segments (fmt `_2`) — each of the 8 petals is a unique shape, so all
    16 are needed.
  - Spiral sun center: filled orange `54x58_87785edd2c5550f9_5` + empty gray
    `54x58_91ea110f64b641e9_2`.
  - "LIFE" yellow wordmark `60x30_0a330a53679495bf_5` — the only LIFE label in the
    packs (no language variants exist; swept the tree for near-size files).
  - No separate water/air-gauge textures exist in the packs — the underwater blue
    tint is applied at render time to these same segment textures, so this set is
    complete.
- "The sun in the top right" IS this life meter (the SMS HUD puts the sun-dial
  top-right; the shine counter sits top-left and was already fully covered by
  `shine_icons\` from addendum #1). Nothing further needed.

## Addendum (2026-08-11 #5): standard text font (glyph sheets)

The pack DOES ship the game's font sheets: the COMPLETE pack `gui/fonts` folder
(5 files, 49 MB) installed to `font\`. Contact-sheet verified (rendered PNGs in
scratchpad `fontsheets\`). Install now 222 MB / 1155 files.

- `font\` — NEW folder:
  - `tex1_512x256_2e07a25ba44f339a_0.dds` + `tex1_512x256_3805b95c880e2ed2_0.dds`
    (I4, 8 MB each) — the rounded upright MESSAGE font (dialogue/episode
    names/menus): full Latin-1 glyph set with GC button glyphs (A/B/X/Y/Z/L/R)
    baked in at the #/$/%/*/@ slots. Near-identical variants — `3805` additionally
    has the C-stick glyph where `2e07` is blank; can't tell which hash is live on
    USA, so both installed per the dead-hash convention.
  - `tex1_512x512_96205d48802d1b68_2.dds` + `tex1_512x512_dc47a26e61d895bb_2.dds`
    (IA4, 16 MB each) — the italic black-OUTLINED dialogue font, two variants:
    `9620` with GC button glyphs replacing #/$/%/*/+/</>/@/¥, `dc47` with the
    plain ASCII characters there. Both installed.
  - `tex1_18x6_56ba5222077adcf4_0.dds` — the three-dot ellipsis / text-continue
    indicator that renders with the font.
- Update patch note: the patch's `gui/fonts` contains only `3805b95c...` and it is
  BYTE-IDENTICAL (MD5) to the 4K base — like m_warps, the patch adds nothing here.
  Base 4K copies installed.

## Remaining step (Dolphin was RUNNING during install — INI untouched)

`Config\GFX.ini` still has `HiresTextures = False`. After Dolphin closes, set in
`[Settings]`: `HiresTextures = True` and `CacheHiresTextures = True` (or tick
Graphics > Advanced > "Load Custom Textures" + "Prefetch Custom Textures" in the UI).
Do NOT edit the INI while Dolphin runs (it rewrites INIs from memory on close).
Texture files themselves are safe to add anytime; Dolphin picks them up on next boot
of GMSE01.
