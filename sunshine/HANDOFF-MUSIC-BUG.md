# HANDOFF: level-BGM "coin toss" silence at 120fps (for a fresh look)

**Facts only. This is a hard bug — every game-side audio value is byte-identical
between an audible and a silent level, so the divergence is below the game state,
in Dolphin's audio pipeline. Read all of §2 before proposing a fix.**

## 0. Symptom (user-observed, reproducible)

- Super Mario Sunshine (USA, GMSE01), patched Dolphin, **EmulationSpeed 2.0 = 120fps**.
- Entering a **level** (repro: Bianco Hills), the level BGM **plays ~50% of the time**.
  It's a coin toss per level *load*. When it fails, it's **total silence for the whole
  level session** — not a transient dropout or glitch. Re-entering re-rolls the dice
  (observed sequences: "silent, silent, music"; "music×3, silent"; "silent, music").
- Delfino Plaza BGM is fine, and its music cutting out during an active goop hazard is
  **vanilla state-driven behavior**, NOT this bug.
- SFX / coins audibility during a silent level: **not yet characterized** — worth checking
  (is it ALL audio, or only BGM/synth voices?).

## 1. Environment

- Apple M2 Max, macOS 15 (arm64). Dolphin built from `dolphin-patches/high-fps-dolphin.patch`
  at the pinned commit; ad-hoc signed, re-signed with `get-task-allow` (so live memory
  tooling attaches with no sudo). Running the HD-portals ISO.
- Audio config (current): `DSPHLE=True`, `DSPThread=False` (experiment, see §3),
  `AudioStretch=True` (experiment, see §3), `AudioPreservePitch=True`,
  `AudioBufferSize=136`, backend Cubeb, GFX Metal. **PC-parity defaults were
  `DSPThread=True`, `AudioStretch=False`** — revert if you want the clean baseline.
- The build's audio-tempo patch (`Source/Core/Core/HW/SystemTimers.cpp`,
  `GetAudioDMACallbackPeriod`): when `EmulationSpeed > 1`, it multiplies the AI audio
  DMA callback period by the speed, so audio plays at correct wall-clock tempo instead
  of 2× fast. **Net effect: the audio DMA callback fires at half the emulated-time
  frequency at 120fps.** Patch body is trivially correct (see the .patch); the *timing
  consequence* is the suspect, not the arithmetic.

## 2. What is RULED OUT (live memory capture — this is the crux)

Tooling: `research/scripts/bgmwatch.py` (+ `gcmem.py` Mach backend, `bgmlog2.py`).
Captured a genuinely SILENT level entry and compared, field by field, against audible
entries. **Every readable game-side audio value is identical:**

| Field | Addr | Silent | Audible |
|---|---|---|---|
| BGM slot populated / track active | `MSBgm*[3] = 0x803E9C80` → `+0x14` JAISound, `act` | **yes, act=1** | yes, act=1 |
| Sequencer cursor / wait advancing | TTrack `cur`,`wait` | **advancing** | advancing |
| Global BGM volume | `SM_MAIN_VOLUME = 0x8040C1C0` f32 | **0.750** | 0.750 |
| Sound-engine enable + fade block | `gpMSound = 0x8040D05C` `+0x70..0xE0` | **identical** (`+A8=0x16d`, fade handles `+7C/+80=0`) | identical |
| Per-track volume | TTrack `+0x3ac` ≈ **0.906**; JAISound `+0x40..0x54` = 0 | same | same |

Conclusions that follow:
- **NOT** "startBGM never fires" — the track loads and is active on silent loads too.
- **NOT** a sequencer/tempo freeze — cursor+wait advance identically.
- **NOT** master volume, **NOT** the MSound enable/fade toggles, **NOT** per-track volume.
- ⇒ The silence is **not represented anywhere in GC memory**. The game issues the same
  note/voice/volume state both times. The divergence is in **Dolphin's DSP-HLE AX voice
  mixing and/or the AI output stream** at level-load — which is NOT visible from MEM1.

## 3. Config experiments tried — NONE fixed it

- Enabled the 180-bundle BGM tempo guard `$C231B8C8` (hooks `0x8031B8C8`, the audio
  tempo/rate region). No effect — wrong subsystem (it scales tempo, not output).
- `DSPThread True → False` (kill async DSP-thread race). No effect.
- `AudioStretch False → True` (decouple audio output from emulation timing). No effect.

## 4. Hypotheses to test (ranked)

1. **DSP-HLE AX voice-setup race at level-load.** The game's JAISeq issues AX voice
   commands via DSP mail; if voice allocation/param upload at scene-init races with the
   HLE AX mixer while the console runs 2× real-time, voices aren't mixed → silence, even
   though the game-side sequencer (all we can read) runs fine. **Instrument
   `Core/DSP/DSPHLE/UCodes/AX*` (voice count / VPB setup) and log audible-vs-silent at a
   level load.** This is the leading theory because it's exactly the layer MEM1 can't see.
2. **AI stream (re)start vs the 2×-slowed DMA period.** At scene change SMS reconfigures
   the AI sample-rate divisor; `GetAudioDMACallbackPeriod` recomputes. Check the AI stream
   enable / DMA scheduling state at a silent vs audible load.
3. **The audio-tempo patch is implicated.** Definitive isolation test: **run at
   EmulationSpeed 2.0 with the patch's `if (speed>1) period*=speed` DISABLED** (audio will
   be 2× fast, but if the coin-toss vanishes the patch's DMA-period doubling is the cause).

## 5. Cheap isolation tests before deep instrumentation

- **Stock-speed baseline:** EmulationSpeed 1.0, fps Gecko disabled — does BGM ever drop on
  level load? (Establishes whether this is strictly high-fps-induced.)
- **DSP-LLE** (needs `dsp_rom.bin`/`dsp_coef.bin` dumps): does the coin-toss disappear under
  LLE? If yes → it's an HLE-AX timing bug.
- **Higher `AudioBufferSize`** (256/512) and/or larger `AudioStretchMaxLatency`: unlikely
  (symptom is whole-level silence, not a transient underrun) but cheap.

## 6. Tooling & addresses (all verified this session)

- `research/scripts/gcmem.py` — cross-platform live GC memory (macOS Mach backend
  `task_for_pid`+`mach_vm_read`; needs Dolphin re-signed with get-task-allow, which it is).
  **MEM1 is only readable while a level is actively emulating** — the signature is absent
  at menus/idle (that's why probes "fail" when the game is paused).
- `research/scripts/bgmwatch.py` — per-entry BGM slot/vol/MSound/track-vol logger →
  `bgmwatch.txt`. `bgmstate.py`, `bgmlog2.py` — deeper BGM/track dumps.
- Addresses: `SM_BGM_IN_TRACK=0x803E9C80` (MSBgm*[3]); `SM_MAIN_VOLUME=0x8040C1C0`;
  `gpMSound=0x8040D05C`; JAISound = `MSBgm+0x14`; TTrack via `JAISound+0x38`→idx into
  root-track array `0x8040E6C0`; TTrack `+0x3b0` = tempo rate (0.5995 for tempo 120 @120fps),
  `+0x3ac`≈0.906. Audio-tempo patch: `SystemTimers.cpp:GetAudioDMACallbackPeriod`.
- Decomp cross-ref for the sound engine: `MSound`/`MSBgm`/`JAISound` (JSystem JAudio);
  see `HANDOFF-INPUT-BUG.md` §11.4/§12.2 for the scene-transition BGM path
  (`MSMainProc::onStageBgm` → fade all → `startStageBGM` → `initSound` → `startBGM`).

**Bottom line for Fable:** the game is provably innocent — it sets up the same BGM state
every time. The 50/50 lives in Dolphin's DSP-HLE/AI audio path at scene load, interacting
with the 2× DMA-period tempo patch. Start at §4.1 (AX voice instrumentation) or the §4.3
patch-off isolation test; the game-memory angle is exhausted.

---

## 7. Fable findings, 2026-08-06 (code investigation + instrumented build)

### 7.1 Correction to §4.1: SMS is NOT an AX-ucode game

GMSE01's DSP ucode (CRC `0x56D36052`) maps to Dolphin's **Zelda-family ucode**
(`Source/Core/Core/HW/DSPHLE/UCodes/Zelda.cpp`, flags `SYNC_PER_FRAME | NO_CMD_0D`).
There are no AX VPBs to instrument; the mixing layer is `ZeldaUCode` +
`ZeldaAudioRenderer`. All instrumentation now lives there.

### 7.2 Two HLE-side states that match the symptom exactly (invisible to MEM1)

Both are pure Dolphin-side ucode-protocol state — the game can be byte-identical in
MEM1 while these diverge, and both re-roll on the next level load:

1. **Sticky HALTED state.** A sync mail arriving when the HLE thinks rendering is not
   active → `MailState::HALTED` (`Zelda.cpp`, "Sync mail received when rendering was
   not active. Halting."). HALTED silently ignores **all** subsequent mails → total
   audio death until the ucode is reloaded. SMS reloads/yields the audio ucode at
   scene changes (card-task yield dance, see `UCodes.h` DSP_FRAME_END comment), which
   is why the next load can recover.
2. **Sync-phase flip-flop desync.** With `SYNC_PER_FRAME`, the game sends two sync
   mails per audio frame carrying 64 voice-skip bits (2×32); `m_sync_flags_second_half`
   alternates per mail. One lost/extra mail across the scene-change ucode swap and the
   halves land swapped **for the whole session** → a stable subset of voices (BGM synth
   voices) never mixed while others (SFX) still play. This variant predicts *BGM-only*
   silence; §0's open "are SFX audible?" question discriminates between #1 and #2.

Also: a stray sync mail in WAITING state whose low half is *nonzero* gets misread as a
command-header mail (`m_mail_expected_cmd_mails = mail & 0xFFFF`) → garbage protocol
desync. Which of the three you get depends on the mail's bits — a literal coin toss.

### 7.3 Instrumented build (deployed to `dolphin/build/Binaries/Dolphin.app`)

Rebuilt + re-signed (get-task-allow preserved). All markers grep-able as `[hifps]`,
log category DSPHLE:
- **Mixer heartbeat** (NOTICE, every 256 audio frames): `frames= voices added= skipped=
  ... sync_second_half=`. Silent level + healthy heartbeat + `added=0` ⇒ skip-flag
  desync (#2). No heartbeat at all ⇒ rendering stopped (#1 / halted).
- **Stray-sync detector** (WARN): WAITING-state mail with implausible command length
  (>16) ⇒ the misread-sync-mail desync, with the mail value.
- **cmd02 output-volume change log** (NOTICE): catches a DSP-side master volume 0
  that game memory can't see.
- Pre-existing NOTICE/WARN lines already cover HALT transitions and ucode swaps.

New env toggle for the §4.3 isolation test: **`HIFPS_NO_AUDIO_SLOWDOWN=1`** disables
the DMA-period scaling at runtime (audio 2× fast; if the coin-toss vanishes, the
scaling is implicated). No rebuild needed for the A/B.

### 7.4 Repro procedure (next session)

1. Quit Dolphin, run `research/audiolog.sh` (enables DSPHLE+AI file logging; refuses
   to run while Dolphin is open because Dolphin rewrites Logger.ini on quit).
2. Relaunch, enter Bianco repeatedly until a silent load; note SFX audibility (§0 gap).
3. `research/audiolog.sh grep` — compare a silent window's `[hifps]` heartbeat/warnings
   against an audible one. Expected outcomes map directly to §7.2 #1 vs #2 vs misread-cmd.
4. Optional A/B: relaunch with `HIFPS_NO_AUDIO_SLOWDOWN=1` and count ~10 level entries.

The distribution patch `dolphin-patches/high-fps-dolphin.patch` has been regenerated
and includes the instrumentation + toggle (7 files).

## 8. BREAKTHROUGH session, 2026-08-06 late (live VPB capture on an all-silent session)

User repro'd a session with NO music anywhere (menus, plaza, levels) but ALL SFX
working — plus one oddity: the level load-screen music played. Live analysis of that
running session (no restart), via lldb runtime log-enable + `scripts/vpbdump.py`
(new tool: locates the Zelda-ucode VPB array in MEM1 by channel-ID pattern scan,
dumps all 64 voices):

- **"Game provably innocent" (§2) is OVERTURNED.** The old probes checked the
  sequencer/master-volume layers only. The VPBs (game-written, MEM1) diverge hard.
- VPB array found @ `0x805f87e0` (this session). ~20-25 enabled voices in 2 groups:
  - **SFX voices**: `use_dolby_volume=1` (positional path), nonzero pitch
    `resampling_ratio`, ARAM cursor advancing, sample bases in low ARAM
    (0x69xxxx-0xABxxxx bank). These are audible.
  - **BGM voices** (~12): `dolby=0`, mixed via channels[] to frontL/frontR,
    sample bases in high ARAM (0xEFxxxx-0xF3xxxx instrument bank), loop flags on
    sustained notes — but **resampling_ratio=0, ALL channel volumes 0 (target and
    current), ARAM cursor never advances**. Rendered as silence every frame.
  - Note slots churn (new notes allocated with fresh sample addresses) — the
    sequencer IS starting notes; only pitch/volume never take effect.
- **HW watchpoint on a BGM voice's ratio word**: the game writes REAL pitches
  (0x0B03, then 0x09D0) and then writes 0. So the game starts the note with real
  parameters and then something (in-game logic) kills it — for every BGM note, all
  session. HLE StoreVPB writeback (words 0-0x7F only) was considered as a clobber
  and ruled unlikely: with DSPThread=False the whole per-voice Fetch->mix->Store is
  atomic inside the game's mailbox-write instruction.

**Leading theory now:** JAudio's DSP-channel keep-up/kill logic (JASDSPChannel /
JASDriver state machine) declares sequenced channels dead — plausibly a
DSP-frame-sync bookkeeping check thrown off by the tempo patch's halved AI-DMA
cadence — and kills each started note. SFX use the positional path that skips
whatever check kills the sequenced notes. The load-screen music playing hints that
path bypasses the affected layer too (different driver mode during loads?).

**Next steps (in order):**
1. Decomp dive (JASystem/JAudio, e.g. tww/SMS decomp): find JASDSPChannel status
   word / kill path; identify what condition zeroes a started channel. Map the
   zero-writer PC: one more SHORT watchpoint run (<=5s, it lags the game hard —
   warn the user) capturing writer PCs, then translate JIT PC -> PPC PC.
2. §4.3 isolation A/B: relaunch with `HIFPS_NO_AUDIO_SLOWDOWN=1` (audio 2x fast)
   and count level entries until confident. If the kill-logic theory is right,
   the coin-toss should vanish.
3. Stock-speed baseline (EmulationSpeed 1.0): never actually done; cheap sanity.
4. `vpbdump.py` on an AUDIBLE session for the healthy-VPB baseline (expect nonzero
   ratio/volumes on the 0xF0xxxx-bank voices).

## 9. ROOT CAUSE FOUND + FIX (2026-08-06, continued)

Step 1 above was completed via the doldecomp/sms decomp without another watchpoint
run. `JASystem::TDSPChannel::updateAll()`
(`src/JSystem/JAudio/JASystem/JASDSPChannel.cpp`) contains a **DSP load-shedding
heuristic**:

```cpp
static f32 DSP_LIMIT_RATIO = 1.1f;
// per DSP frame:
OSTick var3 = OSGetTick() - old_time;          // tick gap between DSP frames
u32 var2 = 7 - AudioThread::getDSPSyncCount();
history[var2] = var3;
if (var2)                                       // DSP behind
    if (f32(history[0]) / var3 < DSP_LIMIT_RATIO)
        breakLowerActive(126);                  // kill lowest-prio voice <= 126
```

On hardware this sheds DSP load. Under the high-fps build, the audio-tempo patch
halves the DSP frame cadence relative to emulated time, so this ratio test
chronically misfires and `forceStop()`s every sequenced BGM note at birth (the
zero-writes seen in §8; callback status 3 = forced-stop). SFX survive on
priority/positional paths. The `history[0]` baseline (only rewritten at full
sync) makes the failure bistable → the per-load coin toss and sticky
whole-session silence.

**USA (GMSE01) addresses, all verified by disasm of `research/main.dol`:**
- `TDSPChannel::updateAll` = `0x80314c60`; kill compare at `0x80314ce4`
  (`fcmpo` then `bge 0x80314d48`; inlined breakLowerActive checks prio `<= 0x7E`).
- `history[10]` = `0x803e2fc0`; `old_time` = r13-0x5c10.
- **`DSP_LIMIT_RATIO` = `0x8040CDB4`** (f32 1.1; loaded via `lfs f0,-0x740c(r13)`,
  r13=0x804141C0).

**FIX: write f32 0.0 to `0x8040CDB4`** → `history[0]/var3 < 0.0` can never be
true (operands non-negative; div-by-0 → +inf, NaN compares unordered) → limiter
never kills. Harmless under emulation: HLE mixing is free on the host CPU, and
the voice pool is capped at 64 anyway.

- Verified LIVE: `mach_vm_write` of 0.0 into a running silent session (value was
  1.1 pre-write, 0.0 readback). 
- Permanent Gecko one-liner: `$BGMFix DSP voice-limiter (120fps music kill)`,
  code `0440CDB4 00000000` (04-write applies every frame). Added to the user
  GMSE01.ini after Dolphin quit.

Superseded: §4's hypotheses (HLE/AI side) are all dead — the HLE was innocent;
the §7 instrumentation + §8 vpbdump were the path to the answer. The
`HIFPS_NO_AUDIO_SLOWDOWN` toggle and `[hifps]` logging remain in the build as
diagnostics.

## 10. SECOND KILLER at 240fps (2026-08-10, PC): SE-request flood thrashes the voice pool

User report at 240 (PC, all §9 fixes verified applied): **music never plays;
occasionally catches when re-entering Delfino Plaza.** Same VPB kill-at-birth
signature as §8, but a DIFFERENT killer — `DSP_LIMIT_RATIO` read back 0.0 live.

**Live evidence (240fps session, `vpbdump.py` + a 60Hz sampler):**
- Game side textbook-healthy (§2 profile): BGM slot active, sequencer advancing
  at the correct wall-clock rate (0.699 for tempo 140), mainVol 0.75.
- DSP voice pool **pinned at 64/64** and churning: ~55 of 64 voices were a
  different sound instance 6s later.
- **~306 SFX-bank voice births/sec** (stock plaza is a few dozen); BGM-bank
  births ~30/sec and **every one had resampling_ratio == 0** — steal-killed at
  birth (`getLogicalChannel`/`breakLower` → `forceStop`, prio ≤ 126).

**Mechanism.** `MSound::mainLoop` (USA **0x80014DA8**, sole caller
TApplication::gameLoop @0x802A62DC) is the whole per-frame audio pump:
frameLoopDyna set-sound refresh, `JAIBasic::startFrameInterfaceWork` (USA
0x80301C1C → processFrameWork 0x80301C3C: SE request processing, continuous-SE
life countdown, fades), MSModBgm. All native-30Hz work. Stock invariant: FOUR
120Hz-substep SE requests collapse into every processed frame. At 240 the pump
runs 240Hz vs 120Hz requests = **0.5 requests/frame** — every continuous SE hits
a processed frame with no keep-alive, expires, restarts → the birth storm →
pool saturation → every allocation steals → sequenced BGM (lowest prio) never
survives its first frame. Plaza re-entry briefly quiets the storm = the
occasional catch. 180 survives at 0.67 requests/frame (half the flicker rate,
under the 64-voice ceiling); the cogwheel rope-creak (fpspatch) was this same
class patched per-site.

**FIX: `audio_pump_gate` in fpspatch (default-on, FPS%30==0):** gate
MSound::mainLoop to 1 rendered frame in FPS/30 = native 30Hz. C2 at the entry
instruction (mflr r0); gated frames `blr` straight back to gameLoop (LR intact
at entry — Noki-gate trick), pass frames re-exec mflr. Counter = low arena
0x800016F8. Restores the stock 4-requests-per-processed-frame invariant at
every G; direct startBGM/startSound calls don't route through mainLoop, so
starts still land ≤33ms (stock latency). `--check` enforces divisor, counter,
blr and the mflr tail. Installed to all bare*.txt 2026-08-10.

**VERIFIED LIVE post-fix (same evening, user's 240 session after relaunch):**
counter 0x800016F8 ticking at exactly 240/s (hook live, gate 1-in-8); BGM-bank
voice births went from 121/121 ratio==0 (all killed at birth) to **0/134** —
dolby=0 voices now show real ratios, matching target/current channel volumes
(frontL/R + revU sends, proper stereo spread) and advancing ARAM cursors: the
§8 healthy-VPB baseline. Sequenced BGM is mixing at 240fps.
Residual observation, not chased: SFX births ~193/s (down from 306/s) with the
pool still hovering near 64 in the plaza — possibly legitimate plaza ambience
demand, possibly a per-rendered-frame requester (not substep-paced) still
flooding. If SE dropouts/steal artifacts are ever audible, measure THAT with
the vpb birth-rate sampler before touching anything.
