# SMS high-fps family-B — binary disasm sweep (stub-TU coverage)

DOL: `/Users/kbrethower/code/high-fps-dolphin/sunshine/research/main.dol`  ·  anchors: setFrameRate `0x80238e7c`, getFrameCtrl `0x80238f08`, AnmFrameRate `0x802a7bd8`

Counts: **SUSPECT** 205, **REVIEW** 14, **CLEAN** 65

Heuristic classifier — confirm each SUSPECT/REVIEW at its USA address. Sites here that also appear in `animrate-audit` are cross-validation; sites in **stub TUs** (popo, bosspakkun, …) appear ONLY here.

## ★ Highest priority — runtime object-param rates (Petey-class), 16

A rate loaded from an object/param field (e.g. `mSLVomitAnmRate` at +0x16c) and set raw — tuned for 30Hz, so 4x fast at 120fps. Petey v16 (`0x800955cc`) is in this list. Fix shape: gate on the framerate global and scale, exactly like v16.

| class | USA addr | enclosing func | kind | note |
|---|---|---|---|---|
| **SUSPECT** | `0x800955cc` | `0x8009548c` | getFrameCtrl+stfs | raw rate <- lfs +0x16c(r3) (4x fast at 120fps) |
| **SUSPECT** | `0x8011763c` | `0x801175fc` | getFrameCtrl+stfs | raw rate <- lfs +0x188(r31) (4x fast at 120fps) |
| **SUSPECT** | `0x801176ec` | `0x801176bc` | getFrameCtrl+stfs | raw rate <- lfs +0x188(r31) (4x fast at 120fps) |
| **SUSPECT** | `0x8013b6c4` | `0x8013b668` | getFrameCtrl+stfs | raw rate <- lfs +0x1bc(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x8013c24c` | `0x8013c1cc` | getFrameCtrl+stfs | raw rate <- lfs +0x194(r3) (4x fast at 120fps) |
| **SUSPECT** | `0x8013c3ac` | `0x8013c30c` | getFrameCtrl+stfs | raw rate <- lfs +0x1e4(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x8013c408` | `0x8013c30c` | getFrameCtrl+stfs | raw rate <- lfs +0x1e4(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x8013c46c` | `0x8013c30c` | getFrameCtrl+stfs | raw rate <- lfs +0x1e4(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x8013c4e8` | `0x8013c490` | getFrameCtrl+stfs | raw rate <- lfs +0x298(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x8013c584` | `0x8013c52c` | getFrameCtrl+stfs | raw rate <- lfs +0x1d0(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x8013c620` | `0x8013c5c8` | getFrameCtrl+stfs | raw rate <- lfs +0x1a8(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x802054d8` | `0x80205354` | setFrameRate | raw rate <- lfs +0x1d0(r31) (4x fast at 120fps) |
| **SUSPECT** | `0x802054ec` | `0x80205354` | setFrameRate | raw rate <- lfs +0x1d0(r31) (4x fast at 120fps) |
| **SUSPECT** | `0x80205624` | `0x80205354` | setFrameRate | raw rate <- lfs +0x1d0(r31) (4x fast at 120fps) |
| **SUSPECT** | `0x80244b88` | `0x80244800` | getFrameCtrl+stfs | raw rate <- lfs +0xc(r5) (4x fast at 120fps) |
| **SUSPECT** | `0x80270204` | `0x8026fe38` | getFrameCtrl+stfs | raw rate <- lfs +0x120(r1) (4x fast at 120fps) |

## SUSPECT — computed & baked-constant raw rates (4x fast)

| class | USA addr | enclosing func | kind | note |
|---|---|---|---|---|
| **SUSPECT** | `0x8004e3d4` | `0x8004e328` | setFrameRate | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800abf4c` | `0x800abee4` | setFrameRate | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800ae20c` | `0x800ae188` | getFrameCtrl+stfs | computed raw rate (fmuls f2,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d05b4` | `0x800d04f4` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d07b8` | `0x800d06ec` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d08b0` | `0x800d06ec` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d0b78` | `0x800d06ec` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d0e24` | `0x800d0d10` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d1140` | `0x800d0d10` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d1308` | `0x800d1250` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d1494` | `0x800d1250` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d15d8` | `0x800d1250` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d1cb0` | `0x800d1bb4` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d1d80` | `0x800d1bb4` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d2094` | `0x800d1fb8` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d237c` | `0x800d1fb8` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d2450` | `0x800d1fb8` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d2510` | `0x800d1fb8` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d2728` | `0x800d262c` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d2af0` | `0x800d2a38` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d2fa4` | `0x800d2eac` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d3368` | `0x800d32b4` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d87c8` | `0x800d872c` | setFrameRate | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d8c5c` | `0x800d8ba4` | setFrameRate | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800d8c94` | `0x800d8ba4` | setFrameRate | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800e8a2c` | `0x800e8898` | getFrameCtrl+stfs | computed raw rate (fdivs f0,f2); no AnmFrameRate feed |
| **SUSPECT** | `0x8011365c` | `0x80113548` | setFrameRate | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x801139d4` | `0x8011397c` | setFrameRate | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x80113c44` | `0x80113b6c` | setFrameRate | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x801157f8` | `0x8011579c` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011c680` | `0x8011c57c` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011cac4` | `0x8011c9c0` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011cd78` | `0x8011cc38` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011d028` | `0x8011cf04` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011d9dc` | `0x8011d4b8` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011dc68` | `0x8011db64` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011e148` | `0x8011e044` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011f8b0` | `0x8011f798` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011f98c` | `0x8011f798` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8011fac0` | `0x8011f9d8` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012b9bc` | `0x8012b928` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012ba08` | `0x8012b928` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012ba8c` | `0x8012b928` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012bafc` | `0x8012b928` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012bec8` | `0x8012bc1c` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012bf14` | `0x8012bc1c` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012bf48` | `0x8012bc1c` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012c02c` | `0x8012bfd0` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012c098` | `0x8012bfd0` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x8012c21c` | `0x8012c1ac` | getFrameCtrl+stfs | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x80136a68` | `0x80136a04` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2450` | `0x801d23fc` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2538` | `0x801d24f0` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2564` | `0x801d24f0` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2950` | `0x801d2880` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2980` | `0x801d2880` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d29ac` | `0x801d2880` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2cc4` | `0x801d2c78` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2cf0` | `0x801d2c78` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2e4c` | `0x801d2dfc` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2f60` | `0x801d2f18` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d2f8c` | `0x801d2f18` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d341c` | `0x801d32fc` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d6a44` | `0x801d6938` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d953c` | `0x801d9460` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801d9880` | `0x801d9734` | getFrameCtrl+stfs | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| **SUSPECT** | `0x801eba7c` | `0x801eb014` | getFrameCtrl+stfs | computed raw rate (fmuls f2,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x801f76c0` | `0x801f761c` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x801f76dc` | `0x801f761c` | getFrameCtrl+stfs | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| **SUSPECT** | `0x800365d8` | `0x800364f4` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x800365ec` | `0x800364f4` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x800365fc` | `0x800364f4` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80036b64` | `0x80036a74` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80036b78` | `0x80036a74` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80036b88` | `0x80036a74` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80037080` | `0x80036f84` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80037094` | `0x80036f84` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x800370a8` | `0x80036f84` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x800370b8` | `0x80036f84` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x800375fc` | `0x80037500` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80037610` | `0x80037500` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80037624` | `0x80037500` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80037634` | `0x80037500` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| **SUSPECT** | `0x80047430` | `0x80047104` | getFrameCtrl+stfs | raw rate <- constant -90 (4x fast at 120fps)  [r2-0x6fd0=0x8040fbb0] |
| **SUSPECT** | `0x8004a4cc` | `0x8004a494` | getFrameCtrl+stfs | raw rate <- constant -90 (4x fast at 120fps)  [r2-0x6fd0=0x8040fbb0] |
| **SUSPECT** | `0x8006a3f0` | `0x8006a3a0` | setFrameRate | raw rate <- constant 200 (4x fast at 120fps)  [r2-0x6c08=0x8040ff78] |
| **SUSPECT** | `0x8006a418` | `0x8006a3a0` | setFrameRate | raw rate <- constant 200 (4x fast at 120fps)  [r2-0x6c08=0x8040ff78] |
| **SUSPECT** | `0x8007d690` | `0x8007d518` | setFrameRate | raw rate <- constant 1900 (4x fast at 120fps)  [r2-0x699c=0x804101e4] |
| **SUSPECT** | `0x800828ec` | `0x800826d8` | getFrameCtrl+stfs | raw rate <- constant 720 (4x fast at 120fps)  [r2-0x68e8=0x80410298] |
| **SUSPECT** | `0x80082bcc` | `0x80082944` | getFrameCtrl+stfs | raw rate <- constant 720 (4x fast at 120fps)  [r2-0x68e8=0x80410298] |
| **SUSPECT** | `0x800a49d0` | `0x800a4900` | getFrameCtrl+stfs | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| **SUSPECT** | `0x800a4d18` | `0x800a4900` | getFrameCtrl+stfs | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| **SUSPECT** | `0x800a5df4` | `0x800a5db8` | getFrameCtrl+stfs | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| **SUSPECT** | `0x800a616c` | `0x800a5fc8` | getFrameCtrl+stfs | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| **SUSPECT** | `0x800a6194` | `0x800a5fc8` | getFrameCtrl+stfs | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| **SUSPECT** | `0x800a6274` | `0x800a5fc8` | getFrameCtrl+stfs | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| **SUSPECT** | `0x800b3448` | `0x800b3410` | getFrameCtrl+stfs | raw rate <- constant 2000 (4x fast at 120fps)  [r2-0x62b0=0x804108d0] |
| **SUSPECT** | `0x800b51ac` | `0x800b5174` | getFrameCtrl+stfs | raw rate <- constant 2000 (4x fast at 120fps)  [r2-0x62b0=0x804108d0] |
| **SUSPECT** | `0x800b6a54` | `0x800b69d4` | setFrameRate | raw rate <- constant 0.7 (4x fast at 120fps)  [r2-0x61ec=0x80410994] |
| **SUSPECT** | `0x800b6f88` | `0x800b6dfc` | getFrameCtrl+stfs | raw rate <- constant 50 (4x fast at 120fps)  [r2-0x61e8=0x80410998] |
| **SUSPECT** | `0x800bae24` | `0x800badb4` | setFrameRate | raw rate <- constant -2 (4x fast at 120fps)  [r2-0x61b8=0x804109c8] |
| **SUSPECT** | `0x800bd954` | `0x800bd8f8` | setFrameRate | raw rate <- constant 50 (4x fast at 120fps)  [r2-0x6130=0x80410a50] |
| **SUSPECT** | `0x800c27fc` | `0x800c255c` | setFrameRate | raw rate <- constant 50 (4x fast at 120fps)  [r2-0x6130=0x80410a50] |
| **SUSPECT** | `0x800c2810` | `0x800c255c` | getFrameCtrl+stfs | raw rate <- constant 50 (4x fast at 120fps)  [r2-0x6130=0x80410a50] |
| **SUSPECT** | `0x800c89d8` | `0x800c8958` | setFrameRate | raw rate <- constant 900 (4x fast at 120fps)  [r2-0x5ff0=0x80410b90] |
| **SUSPECT** | `0x800c8a34` | `0x800c8958` | setFrameRate | raw rate <- constant 900 (4x fast at 120fps)  [r2-0x5ff0=0x80410b90] |
| **SUSPECT** | `0x800c8fe8` | `0x800c8f7c` | setFrameRate | raw rate <- constant 900 (4x fast at 120fps)  [r2-0x5ff0=0x80410b90] |
| **SUSPECT** | `0x800c9004` | `0x800c8f7c` | setFrameRate | raw rate <- constant 900 (4x fast at 120fps)  [r2-0x5ff0=0x80410b90] |
| **SUSPECT** | `0x800c9190` | `0x800c8f7c` | setFrameRate | raw rate <- constant 900 (4x fast at 120fps)  [r2-0x5ff0=0x80410b90] |
| **SUSPECT** | `0x800cdd1c` | `0x800cdb70` | setFrameRate | raw rate <- constant 1.89887e+28 (4x fast at 120fps)  [r2-0x5f80=0x80410c00] |
| **SUSPECT** | `0x800d50c8` | `0x800d4b64` | getFrameCtrl+stfs | raw rate <- constant 10000 (4x fast at 120fps)  [r2-0x5dd4=0x80410dac] |
| **SUSPECT** | `0x800d50dc` | `0x800d4b64` | getFrameCtrl+stfs | raw rate <- constant 10000 (4x fast at 120fps)  [r2-0x5dd4=0x80410dac] |
| **SUSPECT** | `0x800d6c30` | `0x800d6a70` | setFrameRate | raw rate <- constant 4.25404e+24 (4x fast at 120fps)  [r2-0x5e40=0x80410d40] |
| **SUSPECT** | `0x800d74bc` | `0x800d73b4` | setFrameRate | raw rate <- constant 4.25404e+24 (4x fast at 120fps)  [r2-0x5e40=0x80410d40] |
| **SUSPECT** | `0x800e0870` | `0x800e05cc` | setFrameRate | raw rate <- constant 360 (4x fast at 120fps)  [r2-0x5c40=0x80410f40] |
| **SUSPECT** | `0x800e2600` | `0x800e2438` | setFrameRate | raw rate <- constant 360 (4x fast at 120fps)  [r2-0x5c40=0x80410f40] |
| **SUSPECT** | `0x800e5e74` | `0x800e5e18` | setFrameRate | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| **SUSPECT** | `0x800e66c0` | `0x800e65ac` | getFrameCtrl+stfs | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| **SUSPECT** | `0x800e66c8` | `0x800e65ac` | setFrameRate | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| **SUSPECT** | `0x800e68c8` | `0x800e6870` | setFrameRate | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| **SUSPECT** | `0x800e6904` | `0x800e6870` | getFrameCtrl+stfs | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| **SUSPECT** | `0x800e6914` | `0x800e6870` | setFrameRate | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| **SUSPECT** | `0x800e8b7c` | `0x800e8898` | getFrameCtrl+stfs | raw rate <- constant 20 (4x fast at 120fps)  [r2-0x5b2c=0x80411054] |
| **SUSPECT** | `0x800f3130` | `0x800f3004` | getFrameCtrl+stfs | raw rate <- constant 2.39882e+11 (4x fast at 120fps)  [r2-0x5900=0x80411280] |
| **SUSPECT** | `0x800f32c8` | `0x800f319c` | getFrameCtrl+stfs | raw rate <- constant 2.39882e+11 (4x fast at 120fps)  [r2-0x5900=0x80411280] |
| **SUSPECT** | `0x800f3380` | `0x800f319c` | getFrameCtrl+stfs | raw rate <- constant 2.39882e+11 (4x fast at 120fps)  [r2-0x5900=0x80411280] |
| **SUSPECT** | `0x8010e62c` | `0x8010e5f4` | getFrameCtrl+stfs | raw rate <- constant 2 (4x fast at 120fps)  [r2-0x54b0=0x804116d0] |
| **SUSPECT** | `0x801177ec` | `0x80117780` | getFrameCtrl+stfs | raw rate <- constant 97.5 (4x fast at 120fps)  [r2-0x52c0=0x804118c0] |
| **SUSPECT** | `0x8011f9b8` | `0x8011f798` | getFrameCtrl+stfs | raw rate <- constant 0.0942478 (4x fast at 120fps)  [r2-0x521c=0x80411964] |
| **SUSPECT** | `0x8012c0ac` | `0x8012bfd0` | getFrameCtrl+stfs | raw rate <- constant 0.05 (4x fast at 120fps)  [r2-0x5010=0x80411b70] |
| **SUSPECT** | `0x8012d034` | `0x8012cffc` | getFrameCtrl+stfs | raw rate <- constant 4.23226e+21 (4x fast at 120fps)  [r2-0x501c=0x80411b64] |
| **SUSPECT** | `0x8013c6cc` | `0x8013c664` | getFrameCtrl+stfs | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x4d90=0x80411df0] |
| **SUSPECT** | `0x8013c980` | `0x8013c91c` | getFrameCtrl+stfs | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x4d90=0x80411df0] |
| **SUSPECT** | `0x801b07c4` | `0x801b0738` | getFrameCtrl+stfs | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| **SUSPECT** | `0x801b07dc` | `0x801b0738` | getFrameCtrl+stfs | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| **SUSPECT** | `0x801b0ac8` | `0x801b09d4` | getFrameCtrl+stfs | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| **SUSPECT** | `0x801b0ae0` | `0x801b09d4` | getFrameCtrl+stfs | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| **SUSPECT** | `0x801b0c58` | `0x801b0bf8` | getFrameCtrl+stfs | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| **SUSPECT** | `0x801bc0b0` | `0x801bbef0` | getFrameCtrl+stfs | raw rate <- constant 0.06 (4x fast at 120fps)  [r2-0x2bd0=0x80413fb0] |
| **SUSPECT** | `0x801bc0e0` | `0x801bbef0` | getFrameCtrl+stfs | raw rate <- constant 1.14303e+33 (4x fast at 120fps)  [r2-0x2bc0=0x80413fc0] |
| **SUSPECT** | `0x801bc0f8` | `0x801bbef0` | getFrameCtrl+stfs | raw rate <- constant 9.44473e+21 (4x fast at 120fps)  [r2-0x2bbc=0x80413fc4] |
| **SUSPECT** | `0x801bc110` | `0x801bbef0` | getFrameCtrl+stfs | raw rate <- constant 0.02 (4x fast at 120fps)  [r2-0x2bb8=0x80413fc8] |
| **SUSPECT** | `0x801bc234` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 0.06 (4x fast at 120fps)  [r2-0x2bd0=0x80413fb0] |
| **SUSPECT** | `0x801bc264` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 1.14303e+33 (4x fast at 120fps)  [r2-0x2bc0=0x80413fc0] |
| **SUSPECT** | `0x801bc27c` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 9.44473e+21 (4x fast at 120fps)  [r2-0x2bbc=0x80413fc4] |
| **SUSPECT** | `0x801bc294` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 0.02 (4x fast at 120fps)  [r2-0x2bb8=0x80413fc8] |
| **SUSPECT** | `0x801bc31c` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 0.06 (4x fast at 120fps)  [r2-0x2bd0=0x80413fb0] |
| **SUSPECT** | `0x801bc34c` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 1.14303e+33 (4x fast at 120fps)  [r2-0x2bc0=0x80413fc0] |
| **SUSPECT** | `0x801bc364` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 9.44473e+21 (4x fast at 120fps)  [r2-0x2bbc=0x80413fc4] |
| **SUSPECT** | `0x801bc37c` | `0x801bc12c` | getFrameCtrl+stfs | raw rate <- constant 0.02 (4x fast at 120fps)  [r2-0x2bb8=0x80413fc8] |
| **SUSPECT** | `0x801bc654` | `0x801bc5a8` | getFrameCtrl+stfs | raw rate <- constant 0.06 (4x fast at 120fps)  [r2-0x2bd0=0x80413fb0] |
| **SUSPECT** | `0x801bc684` | `0x801bc5a8` | getFrameCtrl+stfs | raw rate <- constant 1.14303e+33 (4x fast at 120fps)  [r2-0x2bc0=0x80413fc0] |
| **SUSPECT** | `0x801bc69c` | `0x801bc5a8` | getFrameCtrl+stfs | raw rate <- constant 9.44473e+21 (4x fast at 120fps)  [r2-0x2bbc=0x80413fc4] |
| **SUSPECT** | `0x801bc6b4` | `0x801bc5a8` | getFrameCtrl+stfs | raw rate <- constant 0.02 (4x fast at 120fps)  [r2-0x2bb8=0x80413fc8] |
| **SUSPECT** | `0x801bc920` | `0x801bc898` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x2bb0=0x80413fd0] |
| **SUSPECT** | `0x801bc9d4` | `0x801bc898` | getFrameCtrl+stfs | raw rate <- constant 30 (4x fast at 120fps)  [r2-0x2ba8=0x80413fd8] |
| **SUSPECT** | `0x801c1be8` | `0x801c1bc0` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x2b20=0x80414060] |
| **SUSPECT** | `0x801cd4e8` | `0x801cd40c` | getFrameCtrl+stfs | raw rate <- constant 400 (4x fast at 120fps)  [r2-0x28d0=0x804142b0] |
| **SUSPECT** | `0x801d97b4` | `0x801d9734` | getFrameCtrl+stfs | raw rate <- constant -180 (4x fast at 120fps)  [r2-0x267c=0x80414504] |
| **SUSPECT** | `0x801ec224` | `0x801ec048` | getFrameCtrl+stfs | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x2294=0x804148ec] |
| **SUSPECT** | `0x801edd68` | `0x801edd00` | setFrameRate | raw rate <- constant 0.1 (4x fast at 120fps)  [r2-0x2220=0x80414960] |
| **SUSPECT** | `0x801edd7c` | `0x801edd00` | getFrameCtrl+stfs | raw rate <- constant 0.1 (4x fast at 120fps)  [r2-0x2220=0x80414960] |
| **SUSPECT** | `0x801eddc4` | `0x801edd00` | setFrameRate | raw rate <- constant 0.1 (4x fast at 120fps)  [r2-0x2220=0x80414960] |
| **SUSPECT** | `0x801eddd8` | `0x801edd00` | getFrameCtrl+stfs | raw rate <- constant 0.1 (4x fast at 120fps)  [r2-0x2220=0x80414960] |
| **SUSPECT** | `0x801fbc5c` | `0x801fb988` | getFrameCtrl+stfs | raw rate <- constant 200 (4x fast at 120fps)  [r2-0x1fb8=0x80414bc8] |
| **SUSPECT** | `0x802018d4` | `0x80201840` | getFrameCtrl+stfs | raw rate <- constant 45 (4x fast at 120fps)  [r2-0x1dc0=0x80414dc0] |
| **SUSPECT** | `0x80201980` | `0x80201840` | getFrameCtrl+stfs | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x1dd0=0x80414db0] |
| **SUSPECT** | `0x80201b54` | `0x80201840` | getFrameCtrl+stfs | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x1dd0=0x80414db0] |
| **SUSPECT** | `0x80201bdc` | `0x80201840` | getFrameCtrl+stfs | raw rate <- constant 45 (4x fast at 120fps)  [r2-0x1dc0=0x80414dc0] |
| **SUSPECT** | `0x8021a2bc` | `0x8021a118` | setFrameRate | raw rate <- constant 1.81792e+31 (4x fast at 120fps)  [r2-0x18e8=0x80415298] |
| **SUSPECT** | `0x8021a314` | `0x8021a118` | setFrameRate | raw rate <- constant 1.81792e+31 (4x fast at 120fps)  [r2-0x18e8=0x80415298] |
| **SUSPECT** | `0x80240654` | `0x802405f8` | getFrameCtrl+stfs | raw rate <- constant 0.99 (4x fast at 120fps)  [r2-0x1468=0x80415718] |
| **SUSPECT** | `0x80240664` | `0x802405f8` | getFrameCtrl+stfs | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x1498=0x804156e8] |
| **SUSPECT** | `0x80240690` | `0x802405f8` | getFrameCtrl+stfs | raw rate <- constant 0.99 (4x fast at 120fps)  [r2-0x1468=0x80415718] |
| **SUSPECT** | `0x802406a0` | `0x802405f8` | getFrameCtrl+stfs | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x1498=0x804156e8] |
| **SUSPECT** | `0x80240adc` | `0x80240a58` | getFrameCtrl+stfs | raw rate <- constant 0.99 (4x fast at 120fps)  [r2-0x1468=0x80415718] |
| **SUSPECT** | `0x80240aec` | `0x80240a58` | getFrameCtrl+stfs | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x1498=0x804156e8] |
| **SUSPECT** | `0x80240b18` | `0x80240a58` | getFrameCtrl+stfs | raw rate <- constant 0.99 (4x fast at 120fps)  [r2-0x1468=0x80415718] |
| **SUSPECT** | `0x80240b28` | `0x80240a58` | getFrameCtrl+stfs | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x1498=0x804156e8] |
| **SUSPECT** | `0x80244bc8` | `0x80244800` | getFrameCtrl+stfs | raw rate <- constant nan (4x fast at 120fps)  [r2-0x110c=0x80415a74] |
| **SUSPECT** | `0x802472a8` | `0x80246578` | getFrameCtrl+stfs | raw rate <- constant nan (4x fast at 120fps)  [r2-0x110c=0x80415a74] |
| **SUSPECT** | `0x802473a8` | `0x80246578` | getFrameCtrl+stfs | raw rate <- constant nan (4x fast at 120fps)  [r2-0x110c=0x80415a74] |
| **SUSPECT** | `0x80270a0c` | `0x8027097c` | getFrameCtrl+stfs | raw rate <- constant 0.00549316 (4x fast at 120fps)  [r2-0xb30=0x80416050] |
| **SUSPECT** | `0x802710fc` | `0x80270b00` | getFrameCtrl+stfs | raw rate <- constant 0.00549316 (4x fast at 120fps)  [r2-0xb30=0x80416050] |
| **SUSPECT** | `0x8027110c` | `0x80270b00` | getFrameCtrl+stfs | raw rate <- constant 0.00549316 (4x fast at 120fps)  [r2-0xb30=0x80416050] |
| **SUSPECT** | `0x80271ab4` | `0x80271a10` | getFrameCtrl+stfs | raw rate <- constant 20 (4x fast at 120fps)  [r2-0xaf0=0x80416090] |
| **SUSPECT** | `0x80271ac8` | `0x80271a10` | getFrameCtrl+stfs | raw rate <- constant 20 (4x fast at 120fps)  [r2-0xaf0=0x80416090] |
| **SUSPECT** | `0x80271b84` | `0x80271a10` | getFrameCtrl+stfs | raw rate <- constant 20 (4x fast at 120fps)  [r2-0xaf0=0x80416090] |
| **SUSPECT** | `0x80284ec0` | `0x80284db8` | getFrameCtrl+stfs | raw rate <- constant 30 (4x fast at 120fps)  [r2-0x6c0=0x804164c0] |

## REVIEW — computed / unresolved

| class | USA addr | enclosing func | kind | note |
|---|---|---|---|---|
| **REVIEW** | `0x8000aff0` | `0x8000af8c` | getFrameCtrl+stfs | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x8000bbf0` | `0x8000bb7c` | getFrameCtrl+stfs | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x8004f028` | `0x8004ef94` | getFrameCtrl+stfs | computed rate (fadds f1,f0); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x80098050` | `0x80097ba8` | getFrameCtrl+stfs | rate f31 source not resolved in block |
| **REVIEW** | `0x800f2768` | `0x800f2144` | getFrameCtrl+stfs | rate f31 source not resolved in block |
| **REVIEW** | `0x801c2204` | `0x801c216c` | getFrameCtrl+stfs | computed rate (fadds f31,f1); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x801c22b8` | `0x801c216c` | getFrameCtrl+stfs | computed rate (fadds f31,f1); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x801c9940` | `0x801c9734` | getFrameCtrl+stfs | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x801d2908` | `0x801d2880` | getFrameCtrl+stfs | computed rate (fsubs f2,f1); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x801d291c` | `0x801d2880` | getFrameCtrl+stfs | computed rate (fsubs f2,f1); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x801d412c` | `0x801d4068` | getFrameCtrl+stfs | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| **REVIEW** | `0x80206830` | `0x802064b0` | setFrameRate | rate f1 source not resolved in block |
| **REVIEW** | `0x80212520` | `0x802123e0` | getFrameCtrl+stfs | rate f31 source not resolved in block |
| **REVIEW** | `0x80212530` | `0x802123e0` | getFrameCtrl+stfs | rate f31 source not resolved in block |

## CLEAN — 65 sites (see CSV)
