# SMS high-fps family-B — MASTER worklist (source ∪ binary)

Function work-items: **168** (127 BINARY/USA-addr, 41 SOURCE/named).  By severity: PARAM=13, MISUSE=16, COMPUTED=56, CONSTANT=72, REVIEW=11.

**One row = one function to fix** (a single C2 hook usually covers all its sites, like v16). Ranked worst-severity first; within a severity, USA (fix-ready) before JP (named hint).

> **Overlap:** a decompiled-TU function appears twice — once BINARY (USA addr, no name) and once SOURCE (named, JP hint) — because the two address spaces can't be auto-joined. Confirm they're the same function when you open the USA address; fix once. Stub-TU functions (popo, bosspakkun, …) appear ONLY as BINARY rows.

| sev | from | func addr | name / key | sites | representative detail |
|---|---|---|---|---|---|
| PARAM | BINARY | `0x8013c30c` (USA fix-ready) | `—` | 3 | raw rate <- lfs +0x1e4(r5) (4x fast at 120fps) |
| PARAM | BINARY | `0x80205354` (USA fix-ready) | `—` | 3 | raw rate <- lfs +0x1d0(r31) (4x fast at 120fps) |
| PARAM | BINARY | `0x80244800` (USA fix-ready) | `—` | 2 | raw rate <- lfs +0xc(r5) (4x fast at 120fps) |
| PARAM | BINARY | `0x8009548c` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x16c(r3) (4x fast at 120fps) |
| PARAM | BINARY | `0x801175fc` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x188(r31) (4x fast at 120fps) |
| PARAM | BINARY | `0x801176bc` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x188(r31) (4x fast at 120fps) |
| PARAM | BINARY | `0x8013b668` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x1bc(r5) (4x fast at 120fps) |
| PARAM | BINARY | `0x8013c1cc` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x194(r3) (4x fast at 120fps) |
| PARAM | BINARY | `0x8013c490` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x298(r5) (4x fast at 120fps) |
| PARAM | BINARY | `0x8013c52c` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x1d0(r5) (4x fast at 120fps) |
| PARAM | BINARY | `0x8013c5c8` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x1a8(r5) (4x fast at 120fps) |
| PARAM | BINARY | `0x8026fe38` (USA fix-ready) | `—` | 1 | raw rate <- lfs +0x120(r1) (4x fast at 120fps) |
| PARAM | SOURCE | `0x8026fc2c` (JP hint) | `THinokuri2::changeBck` | 2 | raw param rate (getSaveParam()->mSLWalkSpeedRateLv0.get()) |
| MISUSE | SOURCE | `0x80365c6c` (JP hint) | `TAnimalBase::execWalk` | 5 | arithmetic on rate: ...SLMaxMarchSpeed.get() * <<>>SMSGetAnmFrameRate();... |
| MISUSE | SOURCE | `0x802eb298` (JP hint) | `TBEelTears::getBasNameTable` | 3 | arithmetic on rate: ...tFrameRate(-frameRate * <<>>SMSGetAnmFrameRate(), 0);... |
| MISUSE | SOURCE | — (JP hint) | `TBossManta::startWalkAnim` | 2 | arithmetic on rate: ...rameRate[mGeneration] * <<>>SMSGetAnmFrameRate(), 0);... |
| MISUSE | SOURCE | — (JP hint) | `TBossManta::startDamageAnim` | 2 | arithmetic on rate: ...rameRate[mGeneration] * <<>>SMSGetAnmFrameRate(), 0);... |
| MISUSE | SOURCE | `0x8016ad74` (JP hint) | `TBaseNPC::perform` | 2 | compared as timing: ...f32 rate = <<>>SMSGetAnmFrameRate();... |
| MISUSE | SOURCE | `0x80199fe0` (JP hint) | `TManhole::touchPlayer` | 2 | arithmetic on rate: ...meCtrl(0)->getFrame() + <<>>SMSGetAnmFrameRate());... |
| MISUSE | SOURCE | `0x801466f4` (JP hint) | `TSplashManager::load` | 2 | arithmetic on rate: ...unk638 = (<<>>SMSGetAnmFrameRate() * -0.5f) *... |
| MISUSE | SOURCE | `0x800fc380` (JP hint) | `TMarioGamePad::reset` | 2 | arithmetic on rate: ...peat(0xf00000f, 20.0f / <<>>SMSGetAnmFrameRate(),... |
| MISUSE | SOURCE | `0x80366ba0` (JP hint) | `TAnimalBase::init` | 1 | arithmetic on rate: ...TurnSpeed = turnSpeed * <<>>SMSGetAnmFrameRate();... |
| MISUSE | SOURCE | `0x80313eac` (JP hint) | `TBGTentacle::setAttackTarget` | 1 | arithmetic on rate: ...ner->getAttackSpeed() * <<>>SMSGetAnmFrameRate());... |
| MISUSE | SOURCE | `0x80261928` (JP hint) | `TBossEel::setBckAnm` | 1 | arithmetic on rate: ...trl(0)->setRate(0.25f * <<>>SMSGetAnmFrameRate());... |
| MISUSE | SOURCE | `0x800cf318` (JP hint) | `TMultiBtk::setNthData` | 1 | arithmetic on rate: ...unk0c[n].setRate(0.5f * <<>>SMSGetAnmFrameRate());... |
| MISUSE | SOURCE | `0x801d9230` (JP hint) | `TLampTrapSpike::control` | 1 | arithmetic on rate: ...ctrl->setRate(-<<>>SMSGetAnmFrameRate());... |
| MISUSE | SOURCE | `0x800dc368` (JP hint) | `TEmitterViewObj::perform` | 1 | compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i... |
| MISUSE | SOURCE | `0x800dc2ac` (JP hint) | `TEmitterIndirectViewObj::perform` | 1 | compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i... |
| MISUSE | SOURCE | `0x800dbd30` (JP hint) | `TMarioParticleManager::perform` | 1 | compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i... |
| COMPUTED | BINARY | `0x801d2880` (USA fix-ready) | `—` | 5 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d1fb8` (USA fix-ready) | `—` | 4 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8012b928` (USA fix-ready) | `—` | 4 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d06ec` (USA fix-ready) | `—` | 3 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d1250` (USA fix-ready) | `—` | 3 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011f798` (USA fix-ready) | `—` | 3 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8012bc1c` (USA fix-ready) | `—` | 3 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8012bfd0` (USA fix-ready) | `—` | 3 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d0d10` (USA fix-ready) | `—` | 2 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d1bb4` (USA fix-ready) | `—` | 2 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d8ba4` (USA fix-ready) | `—` | 2 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800e8898` (USA fix-ready) | `—` | 2 | computed raw rate (fdivs f0,f2); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d24f0` (USA fix-ready) | `—` | 2 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d2c78` (USA fix-ready) | `—` | 2 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d2f18` (USA fix-ready) | `—` | 2 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d9734` (USA fix-ready) | `—` | 2 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801f761c` (USA fix-ready) | `—` | 2 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8004e328` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800abee4` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800ae188` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f2,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d04f4` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d262c` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d2a38` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d2eac` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d32b4` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x800d872c` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x80113548` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011397c` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x80113b6c` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011579c` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011c57c` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011c9c0` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011cc38` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011cf04` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011d4b8` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011db64` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011e044` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8011f9d8` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x8012c1ac` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f31,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x80136a04` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f0,f0); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d23fc` (USA fix-ready) | `—` | 1 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d2dfc` (USA fix-ready) | `—` | 1 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d32fc` (USA fix-ready) | `—` | 1 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d6938` (USA fix-ready) | `—` | 1 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801d9460` (USA fix-ready) | `—` | 1 | computed raw rate (fadds f31,f30); no AnmFrameRate feed |
| COMPUTED | BINARY | `0x801eb014` (USA fix-ready) | `—` | 1 | computed raw rate (fmuls f2,f0); no AnmFrameRate feed |
| COMPUTED | SOURCE | `0x80169a78` (JP hint) | `TBaseNPC::walkAnmRateChange_` | 3 | raw/computed rate (unk1D0) |
| COMPUTED | SOURCE | `0x802e8b84` (JP hint) | `TBossEelTooth::perform` | 2 | raw/computed rate () |
| COMPUTED | SOURCE | `0x80247440` (JP hint) | `TPaneScalingControl::setupAnm` | 2 | raw/computed rate (speed) |
| COMPUTED | SOURCE | `0x80126948` (JP hint) | `TMario::setAnimation` | 2 | raw/computed rate (rate * 0.5f) |
| COMPUTED | SOURCE | `0x8012688c` (JP hint) | `TMario::setReverseAnimation` | 2 | raw/computed rate (rate * -0.5f) |
| COMPUTED | SOURCE | `0x80124084` (JP hint) | `TMario::addUpper` | 2 | raw/computed rate (mPumpAnmRate) |
| COMPUTED | SOURCE | `0x80123a10` (JP hint) | `TMario::calcAnim` | 2 | raw/computed rate () |
| COMPUTED | SOURCE | `0x80113938` (JP hint) | `linSetAnmRate` | 2 | raw/computed rate (arg1.getDataFloat()) |
| COMPUTED | SOURCE | `0x801a154c` (JP hint) | `TDonchou::calcRootMatrix` | 1 | raw/computed rate (0.5f * fc->getRate()) |
| COMPUTED | SOURCE | `0x8014f1a0` (JP hint) | `TYoshi::thinkAnimation` | 1 | raw/computed rate (nextFrame) |
| CONSTANT | BINARY | `0x801bc12c` (USA fix-ready) | `—` | 8 | raw rate <- constant 0.06 (4x fast at 120fps)  [r2-0x2bd0=0x80413fb0] |
| CONSTANT | BINARY | `0x80036f84` (USA fix-ready) | `—` | 4 | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| CONSTANT | BINARY | `0x80037500` (USA fix-ready) | `—` | 4 | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| CONSTANT | BINARY | `0x801bbef0` (USA fix-ready) | `—` | 4 | raw rate <- constant 0.06 (4x fast at 120fps)  [r2-0x2bd0=0x80413fb0] |
| CONSTANT | BINARY | `0x801bc5a8` (USA fix-ready) | `—` | 4 | raw rate <- constant 0.06 (4x fast at 120fps)  [r2-0x2bd0=0x80413fb0] |
| CONSTANT | BINARY | `0x801edd00` (USA fix-ready) | `—` | 4 | raw rate <- constant 0.1 (4x fast at 120fps)  [r2-0x2220=0x80414960] |
| CONSTANT | BINARY | `0x80201840` (USA fix-ready) | `—` | 4 | raw rate <- constant 45 (4x fast at 120fps)  [r2-0x1dc0=0x80414dc0] |
| CONSTANT | BINARY | `0x802405f8` (USA fix-ready) | `—` | 4 | raw rate <- constant 0.99 (4x fast at 120fps)  [r2-0x1468=0x80415718] |
| CONSTANT | BINARY | `0x80240a58` (USA fix-ready) | `—` | 4 | raw rate <- constant 0.99 (4x fast at 120fps)  [r2-0x1468=0x80415718] |
| CONSTANT | BINARY | `0x800364f4` (USA fix-ready) | `—` | 3 | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| CONSTANT | BINARY | `0x80036a74` (USA fix-ready) | `—` | 3 | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x74e0=0x8040f6a0] |
| CONSTANT | BINARY | `0x800a5fc8` (USA fix-ready) | `—` | 3 | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| CONSTANT | BINARY | `0x800c8f7c` (USA fix-ready) | `—` | 3 | raw rate <- constant 900 (4x fast at 120fps)  [r2-0x5ff0=0x80410b90] |
| CONSTANT | BINARY | `0x800e6870` (USA fix-ready) | `—` | 3 | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| CONSTANT | BINARY | `0x80271a10` (USA fix-ready) | `—` | 3 | raw rate <- constant 20 (4x fast at 120fps)  [r2-0xaf0=0x80416090] |
| CONSTANT | BINARY | `0x8006a3a0` (USA fix-ready) | `—` | 2 | raw rate <- constant 200 (4x fast at 120fps)  [r2-0x6c08=0x8040ff78] |
| CONSTANT | BINARY | `0x800a4900` (USA fix-ready) | `—` | 2 | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| CONSTANT | BINARY | `0x800c255c` (USA fix-ready) | `—` | 2 | raw rate <- constant 50 (4x fast at 120fps)  [r2-0x6130=0x80410a50] |
| CONSTANT | BINARY | `0x800c8958` (USA fix-ready) | `—` | 2 | raw rate <- constant 900 (4x fast at 120fps)  [r2-0x5ff0=0x80410b90] |
| CONSTANT | BINARY | `0x800d4b64` (USA fix-ready) | `—` | 2 | raw rate <- constant 10000 (4x fast at 120fps)  [r2-0x5dd4=0x80410dac] |
| CONSTANT | BINARY | `0x800e65ac` (USA fix-ready) | `—` | 2 | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| CONSTANT | BINARY | `0x800f319c` (USA fix-ready) | `—` | 2 | raw rate <- constant 2.39882e+11 (4x fast at 120fps)  [r2-0x5900=0x80411280] |
| CONSTANT | BINARY | `0x801b0738` (USA fix-ready) | `—` | 2 | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| CONSTANT | BINARY | `0x801b09d4` (USA fix-ready) | `—` | 2 | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| CONSTANT | BINARY | `0x801bc898` (USA fix-ready) | `—` | 2 | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x2bb0=0x80413fd0] |
| CONSTANT | BINARY | `0x8021a118` (USA fix-ready) | `—` | 2 | raw rate <- constant 1.81792e+31 (4x fast at 120fps)  [r2-0x18e8=0x80415298] |
| CONSTANT | BINARY | `0x80246578` (USA fix-ready) | `—` | 2 | raw rate <- constant nan (4x fast at 120fps)  [r2-0x110c=0x80415a74] |
| CONSTANT | BINARY | `0x80270b00` (USA fix-ready) | `—` | 2 | raw rate <- constant 0.00549316 (4x fast at 120fps)  [r2-0xb30=0x80416050] |
| CONSTANT | BINARY | `0x80047104` (USA fix-ready) | `—` | 1 | raw rate <- constant -90 (4x fast at 120fps)  [r2-0x6fd0=0x8040fbb0] |
| CONSTANT | BINARY | `0x8004a494` (USA fix-ready) | `—` | 1 | raw rate <- constant -90 (4x fast at 120fps)  [r2-0x6fd0=0x8040fbb0] |
| CONSTANT | BINARY | `0x8007d518` (USA fix-ready) | `—` | 1 | raw rate <- constant 1900 (4x fast at 120fps)  [r2-0x699c=0x804101e4] |
| CONSTANT | BINARY | `0x800826d8` (USA fix-ready) | `—` | 1 | raw rate <- constant 720 (4x fast at 120fps)  [r2-0x68e8=0x80410298] |
| CONSTANT | BINARY | `0x80082944` (USA fix-ready) | `—` | 1 | raw rate <- constant 720 (4x fast at 120fps)  [r2-0x68e8=0x80410298] |
| CONSTANT | BINARY | `0x800a5db8` (USA fix-ready) | `—` | 1 | raw rate <- constant 3.05176e-05 (4x fast at 120fps)  [r2-0x64d0=0x804106b0] |
| CONSTANT | BINARY | `0x800b3410` (USA fix-ready) | `—` | 1 | raw rate <- constant 2000 (4x fast at 120fps)  [r2-0x62b0=0x804108d0] |
| CONSTANT | BINARY | `0x800b5174` (USA fix-ready) | `—` | 1 | raw rate <- constant 2000 (4x fast at 120fps)  [r2-0x62b0=0x804108d0] |
| CONSTANT | BINARY | `0x800b69d4` (USA fix-ready) | `—` | 1 | raw rate <- constant 0.7 (4x fast at 120fps)  [r2-0x61ec=0x80410994] |
| CONSTANT | BINARY | `0x800b6dfc` (USA fix-ready) | `—` | 1 | raw rate <- constant 50 (4x fast at 120fps)  [r2-0x61e8=0x80410998] |
| CONSTANT | BINARY | `0x800badb4` (USA fix-ready) | `—` | 1 | raw rate <- constant -2 (4x fast at 120fps)  [r2-0x61b8=0x804109c8] |
| CONSTANT | BINARY | `0x800bd8f8` (USA fix-ready) | `—` | 1 | raw rate <- constant 50 (4x fast at 120fps)  [r2-0x6130=0x80410a50] |
| CONSTANT | BINARY | `0x800cdb70` (USA fix-ready) | `—` | 1 | raw rate <- constant 1.89887e+28 (4x fast at 120fps)  [r2-0x5f80=0x80410c00] |
| CONSTANT | BINARY | `0x800d6a70` (USA fix-ready) | `—` | 1 | raw rate <- constant 4.25404e+24 (4x fast at 120fps)  [r2-0x5e40=0x80410d40] |
| CONSTANT | BINARY | `0x800d73b4` (USA fix-ready) | `—` | 1 | raw rate <- constant 4.25404e+24 (4x fast at 120fps)  [r2-0x5e40=0x80410d40] |
| CONSTANT | BINARY | `0x800e05cc` (USA fix-ready) | `—` | 1 | raw rate <- constant 360 (4x fast at 120fps)  [r2-0x5c40=0x80410f40] |
| CONSTANT | BINARY | `0x800e2438` (USA fix-ready) | `—` | 1 | raw rate <- constant 360 (4x fast at 120fps)  [r2-0x5c40=0x80410f40] |
| CONSTANT | BINARY | `0x800e5e18` (USA fix-ready) | `—` | 1 | raw rate <- constant 1.2 (4x fast at 120fps)  [r2-0x5ba0=0x80410fe0] |
| CONSTANT | BINARY | `0x800f3004` (USA fix-ready) | `—` | 1 | raw rate <- constant 2.39882e+11 (4x fast at 120fps)  [r2-0x5900=0x80411280] |
| CONSTANT | BINARY | `0x8010e5f4` (USA fix-ready) | `—` | 1 | raw rate <- constant 2 (4x fast at 120fps)  [r2-0x54b0=0x804116d0] |
| CONSTANT | BINARY | `0x80117780` (USA fix-ready) | `—` | 1 | raw rate <- constant 97.5 (4x fast at 120fps)  [r2-0x52c0=0x804118c0] |
| CONSTANT | BINARY | `0x8012cffc` (USA fix-ready) | `—` | 1 | raw rate <- constant 4.23226e+21 (4x fast at 120fps)  [r2-0x501c=0x80411b64] |
| CONSTANT | BINARY | `0x8013c664` (USA fix-ready) | `—` | 1 | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x4d90=0x80411df0] |
| CONSTANT | BINARY | `0x8013c91c` (USA fix-ready) | `—` | 1 | raw rate <- constant 176 (4x fast at 120fps)  [r2-0x4d90=0x80411df0] |
| CONSTANT | BINARY | `0x801b0bf8` (USA fix-ready) | `—` | 1 | raw rate <- constant 7.00716e+22 (4x fast at 120fps)  [r2-0x3e28=0x80412d58] |
| CONSTANT | BINARY | `0x801c1bc0` (USA fix-ready) | `—` | 1 | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x2b20=0x80414060] |
| CONSTANT | BINARY | `0x801cd40c` (USA fix-ready) | `—` | 1 | raw rate <- constant 400 (4x fast at 120fps)  [r2-0x28d0=0x804142b0] |
| CONSTANT | BINARY | `0x801ec048` (USA fix-ready) | `—` | 1 | raw rate <- constant 1 (4x fast at 120fps)  [r2-0x2294=0x804148ec] |
| CONSTANT | BINARY | `0x801fb988` (USA fix-ready) | `—` | 1 | raw rate <- constant 200 (4x fast at 120fps)  [r2-0x1fb8=0x80414bc8] |
| CONSTANT | BINARY | `0x8027097c` (USA fix-ready) | `—` | 1 | raw rate <- constant 0.00549316 (4x fast at 120fps)  [r2-0xb30=0x80416050] |
| CONSTANT | BINARY | `0x80284db8` (USA fix-ready) | `—` | 1 | raw rate <- constant 30 (4x fast at 120fps)  [r2-0x6c0=0x804164c0] |
| CONSTANT | SOURCE | `0x80147f4c` (JP hint) | `TYoshi::init` | 4 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x80247440` (JP hint) | `TBalloonControl::setupAnm` | 2 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x8011f738` (JP hint) | `TMario::toroccoStart` | 2 | raw literal rate 0.5f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x8012582c` (JP hint) | `TMario::initModel` | 2 | raw literal rate 0.5f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x80124238` (JP hint) | `TMario::setUpperDamageRun` | 2 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x8014ef78` (JP hint) | `TYoshi::thinkUpper` | 2 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x802884c0` (JP hint) | `TBossGessoManager::load` | 1 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x80247440` (JP hint) | `TPatternAnmControl::setupAnm` | 1 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | — (JP hint) | `TOptionSoundUnit` | 1 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x8018880c` (JP hint) | `TMapObjBase::makeObjAppeared` | 1 | raw literal rate 1.0f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x80164248` (JP hint) | `TMario::getGesso` | 1 | raw literal rate 0.5f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x8014fcd8` (JP hint) | `TYoshi::thinkBtp` | 1 | raw literal rate 0.5f (4x fast at 120fps) |
| CONSTANT | SOURCE | `0x800efc08` (JP hint) | `TMarDirector::setup2` | 1 | raw literal rate 120.0f (4x fast at 120fps) |
| REVIEW | BINARY | `0x801c216c` (USA fix-ready) | `—` | 2 | computed rate (fadds f31,f1); AnmFrameRate in block — verify scaling/rate² |
| REVIEW | BINARY | `0x802123e0` (USA fix-ready) | `—` | 2 | rate f31 source not resolved in block |
| REVIEW | BINARY | `0x8000af8c` (USA fix-ready) | `—` | 1 | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| REVIEW | BINARY | `0x8000bb7c` (USA fix-ready) | `—` | 1 | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| REVIEW | BINARY | `0x8004ef94` (USA fix-ready) | `—` | 1 | computed rate (fadds f1,f0); AnmFrameRate in block — verify scaling/rate² |
| REVIEW | BINARY | `0x80097ba8` (USA fix-ready) | `—` | 1 | rate f31 source not resolved in block |
| REVIEW | BINARY | `0x800f2144` (USA fix-ready) | `—` | 1 | rate f31 source not resolved in block |
| REVIEW | BINARY | `0x801c9734` (USA fix-ready) | `—` | 1 | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| REVIEW | BINARY | `0x801d4068` (USA fix-ready) | `—` | 1 | computed rate (fmuls f1,f0); AnmFrameRate in block — verify scaling/rate² |
| REVIEW | BINARY | `0x802064b0` (USA fix-ready) | `—` | 1 | rate f1 source not resolved in block |
| REVIEW | SOURCE | `0x800fb64c` (JP hint) | `SMSGetVSyncTimesPerSec` | 1 | ...f32 <<>>SMSGetAnmFrameRate() { return 60... |

## Per-site detail (top PARAM + MISUSE work-items)


### PARAM · BINARY · `0x8013c30c` `0x8013c30c`
- `0x8013c3ac` — raw rate <- lfs +0x1e4(r5) (4x fast at 120fps)
- `0x8013c408` — raw rate <- lfs +0x1e4(r5) (4x fast at 120fps)
- `0x8013c46c` — raw rate <- lfs +0x1e4(r5) (4x fast at 120fps)

### PARAM · BINARY · `0x80205354` `0x80205354`
- `0x802054d8` — raw rate <- lfs +0x1d0(r31) (4x fast at 120fps)
- `0x802054ec` — raw rate <- lfs +0x1d0(r31) (4x fast at 120fps)
- `0x80205624` — raw rate <- lfs +0x1d0(r31) (4x fast at 120fps)

### PARAM · BINARY · `0x80244800` `0x80244800`
- `0x80244b88` — raw rate <- lfs +0xc(r5) (4x fast at 120fps)
- `0x80244bc8` — raw rate <- constant nan (4x fast at 120fps)  [r2-0x110c=0x80415a74]

### PARAM · BINARY · `0x8009548c` `0x8009548c`
- `0x800955cc` — raw rate <- lfs +0x16c(r3) (4x fast at 120fps)

### PARAM · BINARY · `0x801175fc` `0x801175fc`
- `0x8011763c` — raw rate <- lfs +0x188(r31) (4x fast at 120fps)

### PARAM · BINARY · `0x801176bc` `0x801176bc`
- `0x801176ec` — raw rate <- lfs +0x188(r31) (4x fast at 120fps)

### PARAM · BINARY · `0x8013b668` `0x8013b668`
- `0x8013b6c4` — raw rate <- lfs +0x1bc(r5) (4x fast at 120fps)

### PARAM · BINARY · `0x8013c1cc` `0x8013c1cc`
- `0x8013c24c` — raw rate <- lfs +0x194(r3) (4x fast at 120fps)

### PARAM · BINARY · `0x8013c490` `0x8013c490`
- `0x8013c4e8` — raw rate <- lfs +0x298(r5) (4x fast at 120fps)

### PARAM · BINARY · `0x8013c52c` `0x8013c52c`
- `0x8013c584` — raw rate <- lfs +0x1d0(r5) (4x fast at 120fps)

### PARAM · BINARY · `0x8013c5c8` `0x8013c5c8`
- `0x8013c620` — raw rate <- lfs +0x1a8(r5) (4x fast at 120fps)

### PARAM · BINARY · `0x8026fe38` `0x8026fe38`
- `0x80270204` — raw rate <- lfs +0x120(r1) (4x fast at 120fps)

### PARAM · SOURCE · `0x8026fc2c` `THinokuri2::changeBck`
- `Enemy/hinokuri2.cpp:748` — raw param rate (getSaveParam()->mSLWalkSpeedRateLv0.get())  `pJVar7->setRate(getSaveParam()->mSLWalkSpeedRateLv0.get());`
- `Enemy/hinokuri2.cpp:750` — raw literal rate 1.0f (4x fast at 120fps)  `pJVar7->setRate(1.0f);`

### MISUSE · SOURCE · `0x80365c6c` `TAnimalBase::execWalk`
- `Animal/AnimalBase.cpp:271` — arithmetic on rate: ...SLMaxMarchSpeed.get() * <<>>SMSGetAnmFrameRate();...  `f32 speed = save->mSLMaxMarchSpeed.get() * SMSGetAnmFrameRate();`
- `Animal/AnimalBase.cpp:272` — arithmetic on rate: ...->mSLMarchAccel.get() * <<>>SMSGetAnmFrameRate()...  `f32 accel = save->mSLMarchAccel.get() * SMSGetAnmFrameRate()`
- `Animal/AnimalBase.cpp:276` — arithmetic on rate: ...SLMarchDecrease.get() * <<>>SMSGetAnmFrameRate()...  `f32 decel = save->mSLMarchDecrease.get() * SMSGetAnmFrameRate()`
- `Animal/AnimalBase.cpp:283` — arithmetic on rate: ...nSpeed    = waitSpeed * <<>>SMSGetAnmFrameRate();...  `mTurnSpeed    = waitSpeed * SMSGetAnmFrameRate();`
- `Animal/AnimalBase.cpp:286` — arithmetic on rate: ...nSpeed    = walkSpeed * <<>>SMSGetAnmFrameRate();...  `mTurnSpeed    = walkSpeed * SMSGetAnmFrameRate();`

### MISUSE · SOURCE · `0x802eb298` `TBEelTears::getBasNameTable`
- `Enemy/bosseel.cpp:545` — arithmetic on rate: ...tFrameRate(-frameRate * <<>>SMSGetAnmFrameRate(), 0);...  `actor->setFrameRate(-frameRate * SMSGetAnmFrameRate(), 0);`
- `Enemy/bosseel.cpp:550` — arithmetic on rate: ...etFrameRate(frameRate * <<>>SMSGetAnmFrameRate(), 0);...  `actor->setFrameRate(frameRate * SMSGetAnmFrameRate(), 0);`
- `Enemy/bosseel.cpp:602` — arithmetic on rate: ...etFrameRate(frameRate * <<>>SMSGetAnmFrameRate(), 0);...  `actor->setFrameRate(frameRate * SMSGetAnmFrameRate(), 0);`

### MISUSE · SOURCE · `` `TBossManta::startWalkAnim`
- `Enemy/bossManta.cpp:369` — arithmetic on rate: ...rameRate[mGeneration] * <<>>SMSGetAnmFrameRate(), 0);...  `TBossManta::sFrameRate[mGeneration] * SMSGetAnmFrameRate(), 0);`
- `Enemy/bossManta.cpp:368` — raw/computed rate ()  `getMActor()->setFrameRate(`

### MISUSE · SOURCE · `` `TBossManta::startDamageAnim`
- `Enemy/bossManta.cpp:376` — arithmetic on rate: ...rameRate[mGeneration] * <<>>SMSGetAnmFrameRate(), 0);...  `TBossManta::sFrameRate[mGeneration] * SMSGetAnmFrameRate(), 0);`
- `Enemy/bossManta.cpp:375` — raw/computed rate ()  `getMActor()->setFrameRate(`

### MISUSE · SOURCE · `0x8016ad74` `TBaseNPC::perform`
- `NPC/NpcBase.cpp:692` — compared as timing: ...f32 rate = <<>>SMSGetAnmFrameRate();...  `f32 rate = SMSGetAnmFrameRate();`
- `NPC/NpcBase.cpp:693` — raw/computed rate ()  `mMActor->setFrameRate(`

### MISUSE · SOURCE · `0x80199fe0` `TManhole::touchPlayer`
- `MoveBG/MapObjTown.cpp:86` — arithmetic on rate: ...meCtrl(0)->getFrame() + <<>>SMSGetAnmFrameRate());...  `getMActor()->getFrameCtrl(0)->getFrame() + SMSGetAnmFrameRate());`
- `MoveBG/MapObjTown.cpp:98` — arithmetic on rate: ...meCtrl(0)->getFrame() + <<>>SMSGetAnmFrameRate());...  `getMActor()->getFrameCtrl(0)->getFrame() + SMSGetAnmFrameRate());`

### MISUSE · SOURCE · `0x801466f4` `TSplashManager::load`
- `Player/SplashManager.cpp:24` — arithmetic on rate: ...unk638 = (<<>>SMSGetAnmFrameRate() * -0.5f) *...  `unk638 = (SMSGetAnmFrameRate() * -0.5f) * SMSGetAnmFrameRate();`
- `Player/SplashManager.cpp:24` — arithmetic on rate: ...mFrameRate() * -0.5f) * <<>>SMSGetAnmFrameRate();...  `unk638 = (SMSGetAnmFrameRate() * -0.5f) * SMSGetAnmFrameRate();`

### MISUSE · SOURCE · `0x800fc380` `TMarioGamePad::reset`
- `System/MarioGamePad.cpp:8` — arithmetic on rate: ...peat(0xf00000f, 20.0f / <<>>SMSGetAnmFrameRate(),...  `setButtonRepeat(0xf00000f, 20.0f / SMSGetAnmFrameRate(),`
- `System/MarioGamePad.cpp:9` — arithmetic on rate: ...6.0f / <<>>SMSGetAnmFrameRate());...  `6.0f / SMSGetAnmFrameRate());`

### MISUSE · SOURCE · `0x80366ba0` `TAnimalBase::init`
- `Animal/AnimalBase.cpp:75` — arithmetic on rate: ...TurnSpeed = turnSpeed * <<>>SMSGetAnmFrameRate();...  `mTurnSpeed = turnSpeed * SMSGetAnmFrameRate();`

### MISUSE · SOURCE · `0x80313eac` `TBGTentacle::setAttackTarget`
- `Enemy/bgtentacle.cpp:755` — arithmetic on rate: ...ner->getAttackSpeed() * <<>>SMSGetAnmFrameRate());...  `ctrl->setRate(mOwner->getAttackSpeed() * SMSGetAnmFrameRate());`

### MISUSE · SOURCE · `0x80261928` `TBossEel::setBckAnm`
- `Enemy/bosseel.cpp:1923` — arithmetic on rate: ...trl(0)->setRate(0.25f * <<>>SMSGetAnmFrameRate());...  `getMActor()->getFrameCtrl(0)->setRate(0.25f * SMSGetAnmFrameRate());`

### MISUSE · SOURCE · `0x800cf318` `TMultiBtk::setNthData`
- `MarioUtil/ModelUtil.cpp:38` — arithmetic on rate: ...unk0c[n].setRate(0.5f * <<>>SMSGetAnmFrameRate());...  `unk0c[n].setRate(0.5f * SMSGetAnmFrameRate());`

### MISUSE · SOURCE · `0x801d9230` `TLampTrapSpike::control`
- `MoveBG/MapObjTrap.cpp:169` — arithmetic on rate: ...ctrl->setRate(-<<>>SMSGetAnmFrameRate());...  `ctrl->setRate(-SMSGetAnmFrameRate());`

### MISUSE · SOURCE · `0x800dc368` `TEmitterViewObj::perform`
- `System/EmitterViewObj.cpp:29` — compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i...  `for (int i = SMSGetAnmFrameRate(); i > 0; --i)`

### MISUSE · SOURCE · `0x800dc2ac` `TEmitterIndirectViewObj::perform`
- `System/EmitterViewObj.cpp:42` — compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i...  `for (int i = SMSGetAnmFrameRate(); i > 0; --i)`

### MISUSE · SOURCE · `0x800dbd30` `TMarioParticleManager::perform`
- `System/EmitterViewObj.cpp:110` — compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i...  `for (int i = SMSGetAnmFrameRate(); i > 0; --i)`
