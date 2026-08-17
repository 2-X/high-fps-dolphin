# SMS high-fps family-B audit (animation-rate leaks)

Source: `/Users/kbrethower/code/sms`  ·  symbols: `config/GMSJ01/symbols.txt`  ·  symbols loaded

Counts: **SUSPECT** 44, **MISUSE** 25, **REVIEW** 2, **CLEAN** 141

JP addresses are hints: resolve USA (GMSE01) per-TU (USA = JP − k) before writing a Gecko fix.

## Actionable - raw rate setters (SUSPECT)

| class | site | enclosing | JP addr (hint) | why | code |
|---|---|---|---|---|---|
| **SUSPECT** | Enemy/bossManta.cpp:368 | `TBossManta::startWalkAnim` | - | raw/computed rate () | `getMActor()->setFrameRate(` |
| **SUSPECT** | Enemy/bossManta.cpp:375 | `TBossManta::startDamageAnim` | - | raw/computed rate () | `getMActor()->setFrameRate(` |
| **SUSPECT** | Enemy/bosseel.cpp:902 | `TBossEelTooth::perform` | `0x802e8b84` | raw/computed rate () | `mSharedParts->getMActor()->setFrameRate(` |
| **SUSPECT** | Enemy/bossgesso.cpp:1597 | `TBossGessoManager::load` | `0x802884c0` | raw literal rate 1.0f (4x fast at 120fps) | `ctrl4->setRate(1.0f);` |
| **SUSPECT** | Enemy/hinokuri2.cpp:748 | `THinokuri2::changeBck` | `0x8026fc2c` | raw param rate (getSaveParam()->mSLWalkSpeedRateLv0.get()) | `pJVar7->setRate(getSaveParam()->mSLWalkSpeedRateLv0.get());` |
| **SUSPECT** | Enemy/hinokuri2.cpp:750 | `THinokuri2::changeBck` | `0x8026fc2c` | raw literal rate 1.0f (4x fast at 120fps) | `pJVar7->setRate(1.0f);` |
| **SUSPECT** | GC2D/Option.cpp:176 | `TBalloonControl::setupAnm` | `0x80247440` | raw literal rate 1.0f (4x fast at 120fps) | `mFrameCtrl.setRate(1.0f);` |
| **SUSPECT** | GC2D/Option.cpp:179 | `TBalloonControl::setupAnm` | `0x80247440` | raw literal rate 1.0f (4x fast at 120fps) | `void TBalloonControl::startAnm() { mFrameCtrl.setRate(1.0f); }` |
| **SUSPECT** | GC2D/Option.cpp:202 | `TPaneScalingControl::setupAnm` | `0x80247440` | raw/computed rate (speed) | `mFrameCtrl.setRate(speed);` |
| **SUSPECT** | GC2D/Option.cpp:205 | `TPaneScalingControl::setupAnm` | `0x80247440` | raw literal rate 1.0f (4x fast at 120fps) | `void TPaneScalingControl::startAnm() { mFrameCtrl.setRate(1.0f); }` |
| **SUSPECT** | GC2D/Option.cpp:261 | `TPatternAnmControl::setupAnm` | `0x80247440` | raw literal rate 1.0f (4x fast at 120fps) | `mFrameCtrl.setRate(1.0f);` |
| **SUSPECT** | GC2D/Option.cpp:531 | `TOptionSoundUnit` | - | raw literal rate 1.0f (4x fast at 120fps) | `mMusicFrameCtrl.setRate(1.0f);` |
| **SUSPECT** | MoveBG/MapObjBase.cpp:341 | `TMapObjBase::makeObjAppeared` | `0x8018880c` | raw literal rate 1.0f (4x fast at 120fps) | `ctrl->setRate(1.0f);` |
| **SUSPECT** | MoveBG/MapObjSirena.cpp:886 | `TDonchou::calcRootMatrix` | `0x801a154c` | raw/computed rate (0.5f * fc->getRate()) | `fc->setRate(0.5f * fc->getRate());` |
| **SUSPECT** | NPC/NpcAnm.cpp:289 | `TBaseNPC::walkAnmRateChange_` | `0x80169a78` | raw/computed rate (unk1D0) | `mMActor->setFrameRate(unk1D0, 0);` |
| **SUSPECT** | NPC/NpcAnm.cpp:291 | `TBaseNPC::walkAnmRateChange_` | `0x80169a78` | raw/computed rate (unk1D0) | `mMActor->setFrameRate(unk1D0, 0);` |
| **SUSPECT** | NPC/NpcAnm.cpp:339 | `TBaseNPC::walkAnmRateChange_` | `0x80169a78` | raw/computed rate (unk1D0) | `mMActor->setFrameRate(unk1D0, 0);` |
| **SUSPECT** | NPC/NpcBase.cpp:693 | `TBaseNPC::perform` | `0x8016ad74` | raw/computed rate () | `mMActor->setFrameRate(` |
| **SUSPECT** | Player/MarioAutodemo.cpp:354 | `TMario::toroccoStart` | `0x8011f738` | raw literal rate 0.5f (4x fast at 120fps) | `mPinaRail->getFrameCtrl(0)->setRate(0.5f);` |
| **SUSPECT** | Player/MarioAutodemo.cpp:360 | `TMario::toroccoStart` | `0x8011f738` | raw literal rate 0.5f (4x fast at 120fps) | `mKoopaRail->getFrameCtrl(0)->setRate(0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1065 | `TMario::setAnimation` | `0x80126948` | raw/computed rate (rate * 0.5f) | `getMotionFrameCtrl().setRate(rate * 0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1066 | `TMario::setAnimation` | `0x80126948` | raw/computed rate (rate * 0.5f) | `mModel->getFrameCtrl(2).setRate(rate * 0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1080 | `TMario::setReverseAnimation` | `0x8012688c` | raw/computed rate (rate * -0.5f) | `motionFrameCtrl.setRate(rate * -0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1084 | `TMario::setReverseAnimation` | `0x8012688c` | raw/computed rate (rate * -0.5f) | `otherFrameCtrl.setRate(rate * -0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1348 | `TMario::initModel` | `0x8012582c` | raw literal rate 0.5f (4x fast at 120fps) | `mPinaRail->getFrameCtrl(0)->setRate(0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1373 | `TMario::initModel` | `0x8012582c` | raw literal rate 0.5f (4x fast at 120fps) | `mKoopaRail->getFrameCtrl(0)->setRate(0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1851 | `TMario::setUpperDamageRun` | `0x80124238` | raw literal rate 1.0f (4x fast at 120fps) | `frameCtrl.setRate(1.0f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1852 | `TMario::setUpperDamageRun` | `0x80124238` | raw literal rate 0.5f (4x fast at 120fps) | `frameCtrl.setRate(0.5f);` |
| **SUSPECT** | Player/MarioDraw.cpp:1889 | `TMario::addUpper` | `0x80124084` | raw/computed rate (mPumpAnmRate) | `frameCtrl.setRate(mPumpAnmRate);` |
| **SUSPECT** | Player/MarioDraw.cpp:1894 | `TMario::addUpper` | `0x80124084` | raw/computed rate (-mPumpAnmRate) | `frameCtrl.setRate(-mPumpAnmRate);` |
| **SUSPECT** | Player/MarioDraw.cpp:1964 | `TMario::calcAnim` | `0x80123a10` | raw/computed rate () | `yoshiActor->getFrameCtrl(0)->setRate(` |
| **SUSPECT** | Player/MarioDraw.cpp:1974 | `TMario::calcAnim` | `0x80123a10` | raw literal rate 0.5f (4x fast at 120fps) | `yoshiActor->getFrameCtrl(0)->setRate(0.5f);` |
| **SUSPECT** | Player/MarioReceiveMsg.cpp:62 | `TMario::getGesso` | `0x80164248` | raw literal rate 0.5f (4x fast at 120fps) | `mSurfGesso->getFrameCtrl(0)->setRate(0.5f);` |
| **SUSPECT** | Player/Yoshi.cpp:145 | `TYoshi::init` | `0x80147f4c` | raw literal rate 1.0f (4x fast at 120fps) | `unk5C.setRate(1.0f);` |
| **SUSPECT** | Player/Yoshi.cpp:147 | `TYoshi::init` | `0x80147f4c` | raw literal rate 0.5f (4x fast at 120fps) | `unk5C.setRate(0.5f);` |
| **SUSPECT** | Player/Yoshi.cpp:192 | `TYoshi::init` | `0x80147f4c` | raw literal rate 0.5f (4x fast at 120fps) | `mActor->getFrameCtrl(0)->setRate(0.5f);` |
| **SUSPECT** | Player/Yoshi.cpp:193 | `TYoshi::init` | `0x80147f4c` | raw literal rate 0.5f (4x fast at 120fps) | `mActor->getFrameCtrl(3)->setRate(0.5f);` |
| **SUSPECT** | Player/Yoshi.cpp:286 | `TYoshi::thinkBtp` | `0x8014fcd8` | raw literal rate 0.5f (4x fast at 120fps) | `frameCtrl->setRate(0.5f);` |
| **SUSPECT** | Player/Yoshi.cpp:611 | `TYoshi::thinkAnimation` | `0x8014f1a0` | raw/computed rate (nextFrame) | `mActor->getFrameCtrl(0)->setRate(nextFrame);` |
| **SUSPECT** | Player/Yoshi.cpp:646 | `TYoshi::thinkUpper` | `0x8014ef78` | raw literal rate 1.0f (4x fast at 120fps) | `unk5C.setRate(1.0f);` |
| **SUSPECT** | Player/Yoshi.cpp:657 | `TYoshi::thinkUpper` | `0x8014ef78` | raw literal rate 1.0f (4x fast at 120fps) | `unk5C.setRate(1.0f);` |
| **SUSPECT** | Strategic/liveinterp.cpp:432 | `linSetAnmRate` | `0x80113938` | raw/computed rate (arg1.getDataFloat()) | `owner->getMActor()->setFrameRate(arg1.getDataFloat(), 0);` |
| **SUSPECT** | Strategic/liveinterp.cpp:435 | `linSetAnmRate` | `0x80113938` | raw/computed rate (arg1.getDataFloat()) | `owner->getMActor()->setFrameRate(arg1.getDataFloat(), 3);` |
| **SUSPECT** | System/MarDirectorSetup2.cpp:68 | `TMarDirector::setup2` | `0x800efc08` | raw literal rate 120.0f (4x fast at 120fps) | `unkDC->mRate = 120.0f;` |

## Actionable - SMSGetAnmFrameRate timing misuse (MISUSE)

| class | site | enclosing | JP addr (hint) | why | code |
|---|---|---|---|---|---|
| **MISUSE** | Animal/AnimalBase.cpp:75 | `TAnimalBase::init` | `0x80366ba0` | arithmetic on rate: ...TurnSpeed = turnSpeed * <<>>SMSGetAnmFrameRate();... | `mTurnSpeed = turnSpeed * SMSGetAnmFrameRate();` |
| **MISUSE** | Animal/AnimalBase.cpp:271 | `TAnimalBase::execWalk` | `0x80365c6c` | arithmetic on rate: ...SLMaxMarchSpeed.get() * <<>>SMSGetAnmFrameRate();... | `f32 speed = save->mSLMaxMarchSpeed.get() * SMSGetAnmFrameRate();` |
| **MISUSE** | Animal/AnimalBase.cpp:272 | `TAnimalBase::execWalk` | `0x80365c6c` | arithmetic on rate: ...->mSLMarchAccel.get() * <<>>SMSGetAnmFrameRate()... | `f32 accel = save->mSLMarchAccel.get() * SMSGetAnmFrameRate()` |
| **MISUSE** | Animal/AnimalBase.cpp:276 | `TAnimalBase::execWalk` | `0x80365c6c` | arithmetic on rate: ...SLMarchDecrease.get() * <<>>SMSGetAnmFrameRate()... | `f32 decel = save->mSLMarchDecrease.get() * SMSGetAnmFrameRate()` |
| **MISUSE** | Animal/AnimalBase.cpp:283 | `TAnimalBase::execWalk` | `0x80365c6c` | arithmetic on rate: ...nSpeed    = waitSpeed * <<>>SMSGetAnmFrameRate();... | `mTurnSpeed    = waitSpeed * SMSGetAnmFrameRate();` |
| **MISUSE** | Animal/AnimalBase.cpp:286 | `TAnimalBase::execWalk` | `0x80365c6c` | arithmetic on rate: ...nSpeed    = walkSpeed * <<>>SMSGetAnmFrameRate();... | `mTurnSpeed    = walkSpeed * SMSGetAnmFrameRate();` |
| **MISUSE** | Enemy/bgtentacle.cpp:755 | `TBGTentacle::setAttackTarget` | `0x80313eac` | arithmetic on rate: ...ner->getAttackSpeed() * <<>>SMSGetAnmFrameRate());... | `ctrl->setRate(mOwner->getAttackSpeed() * SMSGetAnmFrameRate());` |
| **MISUSE** | Enemy/bossManta.cpp:369 | `TBossManta::startWalkAnim` | - | arithmetic on rate: ...rameRate[mGeneration] * <<>>SMSGetAnmFrameRate(), 0);... | `TBossManta::sFrameRate[mGeneration] * SMSGetAnmFrameRate(), 0);` |
| **MISUSE** | Enemy/bossManta.cpp:376 | `TBossManta::startDamageAnim` | - | arithmetic on rate: ...rameRate[mGeneration] * <<>>SMSGetAnmFrameRate(), 0);... | `TBossManta::sFrameRate[mGeneration] * SMSGetAnmFrameRate(), 0);` |
| **MISUSE** | Enemy/bosseel.cpp:545 | `TBEelTears::getBasNameTable` | `0x802eb298` | arithmetic on rate: ...tFrameRate(-frameRate * <<>>SMSGetAnmFrameRate(), 0);... | `actor->setFrameRate(-frameRate * SMSGetAnmFrameRate(), 0);` |
| **MISUSE** | Enemy/bosseel.cpp:550 | `TBEelTears::getBasNameTable` | `0x802eb298` | arithmetic on rate: ...etFrameRate(frameRate * <<>>SMSGetAnmFrameRate(), 0);... | `actor->setFrameRate(frameRate * SMSGetAnmFrameRate(), 0);` |
| **MISUSE** | Enemy/bosseel.cpp:602 | `TBEelTears::getBasNameTable` | `0x802eb298` | arithmetic on rate: ...etFrameRate(frameRate * <<>>SMSGetAnmFrameRate(), 0);... | `actor->setFrameRate(frameRate * SMSGetAnmFrameRate(), 0);` |
| **MISUSE** | Enemy/bosseel.cpp:1923 | `TBossEel::setBckAnm` | `0x80261928` | arithmetic on rate: ...trl(0)->setRate(0.25f * <<>>SMSGetAnmFrameRate());... | `getMActor()->getFrameCtrl(0)->setRate(0.25f * SMSGetAnmFrameRate());` |
| **MISUSE** | MarioUtil/ModelUtil.cpp:38 | `TMultiBtk::setNthData` | `0x800cf318` | arithmetic on rate: ...unk0c[n].setRate(0.5f * <<>>SMSGetAnmFrameRate());... | `unk0c[n].setRate(0.5f * SMSGetAnmFrameRate());` |
| **MISUSE** | MoveBG/MapObjTown.cpp:86 | `TManhole::touchPlayer` | `0x80199fe0` | arithmetic on rate: ...meCtrl(0)->getFrame() + <<>>SMSGetAnmFrameRate());... | `getMActor()->getFrameCtrl(0)->getFrame() + SMSGetAnmFrameRate());` |
| **MISUSE** | MoveBG/MapObjTown.cpp:98 | `TManhole::touchPlayer` | `0x80199fe0` | arithmetic on rate: ...meCtrl(0)->getFrame() + <<>>SMSGetAnmFrameRate());... | `getMActor()->getFrameCtrl(0)->getFrame() + SMSGetAnmFrameRate());` |
| **MISUSE** | MoveBG/MapObjTrap.cpp:169 | `TLampTrapSpike::control` | `0x801d9230` | arithmetic on rate: ...ctrl->setRate(-<<>>SMSGetAnmFrameRate());... | `ctrl->setRate(-SMSGetAnmFrameRate());` |
| **MISUSE** | NPC/NpcBase.cpp:692 | `TBaseNPC::perform` | `0x8016ad74` | compared as timing: ...f32 rate = <<>>SMSGetAnmFrameRate();... | `f32 rate = SMSGetAnmFrameRate();` |
| **MISUSE** | Player/SplashManager.cpp:24 | `TSplashManager::load` | `0x801466f4` | arithmetic on rate: ...unk638 = (<<>>SMSGetAnmFrameRate() * -0.5f) *... | `unk638 = (SMSGetAnmFrameRate() * -0.5f) * SMSGetAnmFrameRate();` |
| **MISUSE** | Player/SplashManager.cpp:24 | `TSplashManager::load` | `0x801466f4` | arithmetic on rate: ...mFrameRate() * -0.5f) * <<>>SMSGetAnmFrameRate();... | `unk638 = (SMSGetAnmFrameRate() * -0.5f) * SMSGetAnmFrameRate();` |
| **MISUSE** | System/EmitterViewObj.cpp:29 | `TEmitterViewObj::perform` | `0x800dc368` | compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i... | `for (int i = SMSGetAnmFrameRate(); i > 0; --i)` |
| **MISUSE** | System/EmitterViewObj.cpp:42 | `TEmitterIndirectViewObj::perform` | `0x800dc2ac` | compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i... | `for (int i = SMSGetAnmFrameRate(); i > 0; --i)` |
| **MISUSE** | System/EmitterViewObj.cpp:110 | `TMarioParticleManager::perform` | `0x800dbd30` | compared as timing: ...for (int i = <<>>SMSGetAnmFrameRate(); i > 0; --i... | `for (int i = SMSGetAnmFrameRate(); i > 0; --i)` |
| **MISUSE** | System/MarioGamePad.cpp:8 | `TMarioGamePad::reset` | `0x800fc380` | arithmetic on rate: ...peat(0xf00000f, 20.0f / <<>>SMSGetAnmFrameRate(),... | `setButtonRepeat(0xf00000f, 20.0f / SMSGetAnmFrameRate(),` |
| **MISUSE** | System/MarioGamePad.cpp:9 | `TMarioGamePad::reset` | `0x800fc380` | arithmetic on rate: ...6.0f / <<>>SMSGetAnmFrameRate());... | `6.0f / SMSGetAnmFrameRate());` |

## Needs eyes - ambiguous AnmFrameRate use (REVIEW)

| class | site | enclosing | JP addr (hint) | why | code |
|---|---|---|---|---|---|
| **REVIEW** | Enemy/bosseel.cpp:903 | `TBossEelTooth::perform` | `0x802e8b84` | ...<<>>SMSGetAnmFrameRate(), 0);... | `SMSGetAnmFrameRate(), 0);` |
| **REVIEW** | System/Application.cpp:92 | `SMSGetVSyncTimesPerSec` | `0x800fb64c` | ...f32 <<>>SMSGetAnmFrameRate() { return 60... | `f32 SMSGetAnmFrameRate() { return 60.0f / SMSGetVSyncTimesPerSec(); }` |

## Clean (auto-compensated / pause) - 141 rows, see CSV

## Blind spots - stub TUs the source audit CANNOT see

These `.cpp` are empty stubs in the decomp, so any raw-rate setter they contain is invisible here and must be found via the binary-disasm path (disassemble `main.dol`, find `bl` sites to `MActor::setFrameRate` / `J3DFrameCtrl::setRate` inside each TU's address range). Poink v14 and Petey v16 both live in stub TUs. Proof the disasm sweep is required, not optional.

- `Animal/BeeHive.cpp`
- `Animal/Bird.cpp`
- `Enemy/BathtubBinder.cpp`
- `Enemy/BathtubPeach.cpp`
- `Enemy/BossHanachanAnm.cpp`
- `Enemy/BossHanachanEffect.cpp`
- `Enemy/BossHanachanMain.cpp`
- `Enemy/BossHanachanNerve.cpp`
- `Enemy/BossHanachanParts.cpp`
- `Enemy/BossHanachanSave.cpp`
- `Enemy/BossHanachanSound.cpp`
- `Enemy/BossHanachanSub.cpp`
- `Enemy/DemoBossHanachanBase.cpp`
- `Enemy/Kazekun.cpp`
- `Enemy/Koopa.cpp`
- `Enemy/Kukku.cpp`
- `Enemy/SleepBossHanachan.cpp`
- `Enemy/TabePuku.cpp`
- `Enemy/amiNoko.cpp`
- `Enemy/bombhei.cpp`
- `Enemy/bosspakkun.cpp`
- `Enemy/bosstelesa.cpp`
- `Enemy/bosswanwan.cpp`
- `Enemy/cannon.cpp`
- `Enemy/chuuhana.cpp`
- `Enemy/effectEnemy.cpp`
- `Enemy/elecNokonoko.cpp`
- `Enemy/feetinv.cpp`
- `Enemy/fruitsboat.cpp`
- `Enemy/hanasambo.cpp`
- `Enemy/hauntLeg.cpp`
- `Enemy/igaiga.cpp`
- `Enemy/killer.cpp`
- `Enemy/koopajr.cpp`
- `Enemy/limitkoopa.cpp`
- `Enemy/limitkoopajr.cpp`
- `Enemy/pakkun.cpp`
- `Enemy/popo.cpp`
- `Enemy/rocket.cpp`
- `Enemy/seal.cpp`
- `Enemy/tinkoopa.cpp`
- `Enemy/tobiPuku.cpp`
- `Enemy/wireTrap.cpp`
- `Enemy/yunbo.cpp`
- `GC2D/Guide.cpp`
- `GC2D/SelectMenu.cpp`
- `GC2D/SelectShine2.cpp`
- `GC2D/Talk2D2.cpp`
- `GC2D/hx_wiper.c`
- `JSystem/J3D/J3DGraphLoader/J3DClusterLoader.cpp`
- `JSystem/JAudio/JADebug/JADHioNode.cpp`
- `JSystem/JAudio/JAInterface/JAIDebug.cpp`
- `JSystem/JAudio/JASystem/JASInstEffect.cpp`
- `JSystem/JKernel/JKRFileCache.cpp`
- `JSystem/JUtility/JUTDbPrint.cpp`
- `JSystem/JUtility/JUTVideo.cpp`
- `Map/StickyStainManager.cpp`
- `MarioUtil/ShadowUtil.cpp`
- `MoveBG/MapObjBall.cpp`
- `MoveBG/MapObjBianco.cpp`
- `MoveBG/MapObjFence.cpp`
- `MoveBG/MapObjFlag.cpp`
- `MoveBG/MapObjMamma.cpp`
- `MoveBG/MapObjMare.cpp`
- `MoveBG/MapObjMonte.cpp`
- `MoveBG/MapObjPinna.cpp`
- `MoveBG/MapObjRicco.cpp`
- `MoveBG/MapObjSample.cpp`
- `MoveBG/MapObjWave.cpp`
- `MoveBG/ModelGate.cpp`
- `Player/Atom.cpp`
- `PowerPC_EABI_Support/Msl/MSL_C/MSL_Common/errno.c`
- `PowerPC_EABI_Support/Msl/MSL_C/MSL_Common/float.c`
- `PowerPC_EABI_Support/Msl/MSL_C/MSL_Common/misc_io.c`
- `PowerPC_EABI_Support/Msl/MSL_C/MSL_Common_Embedded/Math/Double_precision/e_asin.c`
- `PowerPC_EABI_Support/Msl/MSL_C/MSL_Common_Embedded/Math/Single_precision/hyperbolicsf.c`
- `PowerPC_EABI_Support/Msl/MSL_C/PPC_EABI/critical_regions.ppc_eabi.c`
- `Strategic/binder.cpp`
- `TRK_MINNOW_DOLPHIN/debugger/embedded/MetroTRK/Os/dolphin/usr_put.c`
- `TRK_MINNOW_DOLPHIN/debugger/embedded/MetroTRK/Portable/msg.c`
- `TRK_MINNOW_DOLPHIN/debugger/embedded/MetroTRK/Portable/mutex_TRK.c`
- `dolphin/card/CARDNet.c`
- `dolphin/dsp/dsp_debug.c`
- `dolphin/gx/GXStubs.c`
- `dolphin/odenotstub/odenotstub.c`
