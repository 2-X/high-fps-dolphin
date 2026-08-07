#!/usr/bin/env python3
"""fpspatch.py — generate the Super Mario Sunshine (GMSE01) high-FPS Gecko bundle
for ANY target framerate.

The key finding behind this tool: the working high-fps bundle is almost entirely
**framerate-independent**. Retargeting from 120 to 180 to 240 changes exactly two
things:

  1. the "framerate global" at 0x804167B8  →  float(FPS/60)   (one Gecko word)
  2. Dolphin's EmulationSpeed              →  FPS/60

Everything else is either (a) a hook that READS that global and therefore
auto-scales, or (b) a parity/distance-based fix that is correct at every rate:

  * particle/emitter rate  → 1-in-G substep gate → exactly 60 Hz at any integer
    G. NOTE this one IS rate-dependent and is regenerated per FPS: the older
    hand-written block used a fixed 1-in-2 parity mask, which is only 60 Hz at
    G=2 (90 Hz at 180fps, 120 Hz at 240fps). Both it and the even older "+0.5"
    blocks from TRUE-FIX v2 (2x too fast at 120 — the level-load
    "flash-invisible on reconstitute" bug) are superseded by _rate_gate().
  * M-portal glow          → XZ-distance proximity reimpl (no rate constant)
  * M-portal ForceOpen     → calls the real startOpen (no rate constant)
  * game-clock fix (v15)   → divides OSCheckStopwatch ticks by FPS/60 (races,
    countdowns, verdict times — the clocks are timebase-based and run G-times
    fast; see timerfix() below). Auto-scales: shift for 2/4, /3 division for 180.

So "do we need a per-FPS patcher?" → yes, but a tiny one: pick FPS, it stamps the
one constant and assembles the rest. Genuinely per-FPS *deeper* rate bugs (splash
gravity rate², truncation stalls — the v13 backlog) are not in the core bundle;
add them here as FPS-specific fixes when they land.

Usage:
  fpspatch.py 120                 # print the 120fps bundle + EmulationSpeed
  fpspatch.py 180 -o out.txt      # write the 180fps bundle to a file
  fpspatch.py 240 --no-forceopen  # v3-style: respect story locks (no ForceOpen)
  fpspatch.py 120 --check         # structural-validate every C2 block
"""
import argparse, struct, sys

# ---- FPS-INDEPENDENT building blocks (verified from the shipping TRUE-FIX v2) ----

def base(fr_word):
    # 044167B8 = the framerate global = float(FPS/60); the C20066EC effect-loop
    # hook reads it, so the whole base auto-scales off this one word.
    return f"""044167B8 {fr_word}
042FCB24 60000000
C20066EC 00000002
C2C28028 EC2105B2
FEC00890 00000000"""

# ---- generic 1-in-G substep gate --------------------------------------------
# EmitterViewObj.cpp: for(i=SMSGetAnmFrameRate(); i>0; --i) emitter->calc().
# SMSGetAnmFrameRate() returns 1/G, so fctiwz truncates it to 0 substeps of work;
# injecting +1.0 on a chosen substep is what actually advances the emitter. The
# substep clock ticks at 60*G Hz, so to hold the emitter at its native 60 Hz the
# +1.0 must land on exactly 1 substep in G.
#
# The shipping 120fps block hardcoded `andi. r0,r3,1` — a fixed 1-in-2 gate that
# yields 60*G/2 = 30*G Hz. That is 60 Hz ONLY at G=2; it runs emitters 1.5x too
# fast at 180fps and 2x too fast at 240fps. (The previous docstring's claim that
# parity was "correct at 120 AND 180 (parity, not a const)" was wrong — a fixed
# /2 is just as rate-specific as the "+0.5" constant it replaced.)
#
# _rate_gate emits a true 1-in-G test, leaving CR0 set so `bne` == "skip":
#   * G a power of two -> `andi. r0,r3,G-1` (byte-identical to the old block at
#     G=2, so the proven 120fps bundle is unchanged)
#   * otherwise        -> ctr - (ctr/G)*G, an exact modulo. Required for G=3
#     (180fps): no AND mask can express mod 3.

def _li(rD, imm):        return (14 << 26) | (rD << 21) | (imm & 0xFFFF)
def _andi_(rA, rS, imm): return (28 << 26) | (rS << 21) | (rA << 16) | (imm & 0xFFFF)
def _divwu(rD, rA, rB):  return (31 << 26) | (rD << 21) | (rA << 16) | (rB << 11) | (459 << 1)
def _mullw(rD, rA, rB):  return (31 << 26) | (rD << 21) | (rA << 16) | (rB << 11) | (235 << 1)
def _subf_(rD, rA, rB):  return (31 << 26) | (rD << 21) | (rA << 16) | (rB << 11) | (40 << 1) | 1

def _rate_gate(g, ctr=3, tmp=0, tmp2=4):
    """Instructions setting CR0 from (ctr mod g); a following `bne` skips the work.
    `ctr` holds the substep counter on entry and is preserved."""
    if g & (g - 1) == 0:                       # power of two -> single mask
        return [_andi_(tmp, ctr, g - 1)]
    return [_li(tmp2, g),                      # li    r4,G
            _divwu(tmp, ctr, tmp2),            # divwu r0,r3,r4   q = ctr/G
            _mullw(tmp, tmp, tmp2),            # mullw r0,r0,r4   q*G
            _subf_(tmp, tmp, ctr)]             # subf. r0,r0,r3   ctr - q*G = ctr%G

LWZ_DIRECTOR = 0x806D9FB8   # lwz   r3,-0x6048(r13)   gpMarDirector
CMPLWI_R3_0  = 0x28030000   # cmplwi r3,0
LWZ_UNK5C    = 0x8063005C   # lwz   r3,0x5C(r3)       substep counter
LFS_ONE      = 0xC002DD68   # lfs   f0,-0x2298(r2)    1.0f
FADDS_F1_F0  = 0xEC21002A   # fadds f1,f1,f0
FCTIWZ_F0_F1 = 0xFC00081E   # the overwritten original instruction
NOP          = 0x60000000

def _parity_block(hook, g):
    gate = _rate_gate(g)
    # layout: [dir load, cmplwi, beq->ADD] [unk5C load, gate..., bne->SKIP] [ADD] [SKIP]
    words = ([LWZ_DIRECTOR, CMPLWI_R3_0, 0] + [LWZ_UNK5C] + gate + [0]
             + [LFS_ONE, FADDS_F1_F0] + [FCTIWZ_F0_F1])
    i_beq, i_bne = 2, 4 + len(gate)
    i_add = i_bne + 1                          # null director falls here: do the add
    i_skip = i_add + 2
    words[i_beq] = 0x41820000 | (((i_add - i_beq) * 4) & 0xFFFC)   # beq -> ADD
    words[i_bne] = 0x40820000 | (((i_skip - i_bne) * 4) & 0xFFFC)  # bne -> SKIP
    words += [NOP, NOP]                        # preserve the proven 120fps cave layout
    if len(words) % 2 == 0:
        words.append(NOP)                      # keep the branch-back on its own slot
    words.append(0x00000000)                   # handler clobbers the last word
    out = [f"{hook} {len(words) // 2:08X}"]
    for i in range(0, len(words), 2):
        out.append(f"{words[i]:08X} {words[i + 1]:08X}")
    return "\n".join(out)

def particles(g):
    return "\n".join(_parity_block(h, g) for h in ("C22887A8", "C2288D30", "C2288DEC"))

FORCEOPEN = """C21EB034 00000007
88030070 700B0001
40820020 7D6802A6
3D80801E 618CBFD4
7D8903A6 4E800421
7D6803A6 7FE3FB78
88030070 60000000
60000000 00000000"""

# ---- Game-clock fix (v15): race/countdown timers ----------------------------
# SMS clocks (blooper race, Piantissimo, time-limit countdowns, verdict times)
# are OS-tick STOPWATCH based, not frame counters: every one reads the director
# event stopwatch (gpMarDirector+0xE8) through OSCheckStopwatch @0x80348114
# (exactly 4 callers, all this stopwatch). The emulated timebase advances
# EmulationSpeed-times real time, so clocks run G=FPS/60 times too fast.
# Fix: hook the single exit (blr @0x80348180, r3:r4 = total ticks) and divide
# the 64-bit tick count by G, gated on the framerate global containing exactly
# float(G) (stock 0.5f -> gate fails -> no-op without the fps code).

def _rlwinm(a, s, sh, mb, me):
    return 21 << 26 | s << 21 | a << 16 | sh << 11 | mb << 6 | me << 1

def _rlwimi(a, s, sh, mb, me):
    return 20 << 26 | s << 21 | a << 16 | sh << 11 | mb << 6 | me << 1

def timerfix(fps):
    """C2 block scaling OSCheckStopwatch's 64-bit tick result by 60/fps.
    Returns None when fps/60 is not an integer > 1 (no exact fix)."""
    g = fps / 60.0
    if g <= 1 or g != int(g):
        return None
    g = int(g)
    gate = struct.unpack(">I", struct.pack(">f", float(g)))[0]
    words = [0x3CA08041, 0x80A567B8]                 # lis r5,0x8041; lwz r5,0x67B8(r5)
    words.append(0x3CC00000 | (gate >> 16))          # lis r6,hi16(float G)
    if gate & 0xFFFF:
        words.append(0x60C60000 | (gate & 0xFFFF))   # ori r6,r6,lo16
    words.append(0x7C053000)                         # cmpw r5,r6
    if g & (g - 1) == 0:                             # power of two: 64-bit >> sh
        sh = g.bit_length() - 1
        body = [
            _rlwinm(4, 4, 32 - sh, sh, 31),          # srwi r4,r4,sh
            _rlwimi(4, 3, 32 - sh, 0, sh - 1),       # lo top bits <- hi low bits
            _rlwinm(3, 3, 32 - sh, sh, 31),          # srwi r3,r3,sh
        ]
    else:                                            # base-2^16 long division by g
        body = [
            0x38C00000 | g,                          # li    r6,g
            0x7CE33396,                              # divwu r7,r3,r6   q_hi
            0x7D0731D6,                              # mullw r8,r7,r6
            0x7D081850,                              # subf  r8,r8,r3   rem
            0x7CE33B78,                              # mr    r3,r7
            _rlwinm(7, 4, 16, 16, 31),               # r7 = lo>>16
            _rlwimi(7, 8, 16, 0, 15),                # r7 |= rem<<16
            0x7D073396,                              # divwu r8,r7,r6   q1
            0x7CA831D6,                              # mullw r5,r8,r6
            0x7CA53850,                              # subf  r5,r5,r7   rem2
            _rlwinm(7, 4, 0, 16, 31),                # r7 = lo & 0xFFFF
            _rlwimi(7, 5, 16, 0, 15),                # r7 |= rem2<<16
            0x7CA73396,                              # divwu r5,r7,r6   q0
            0x38850000,                              # addi  r4,r5,0
            _rlwimi(4, 8, 16, 0, 15),                # r4 |= q1<<16
        ]
    words.append(0x40820000 | (len(body) + 1) * 4)   # bne -> blr
    words += body
    words.append(0x4E800020)                         # blr (replaces original)
    if len(words) % 2 == 0:
        words.append(0x60000000)                     # keep pad on its own slot
    words.append(0x00000000)                         # handler clobbers last word
    lines = [f"C2348180 {len(words) // 2:08X}"]
    for i in range(0, len(words), 2):
        lines.append(f"{words[i]:08X} {words[i + 1]:08X}")
    return "\n".join(lines)


def _c2(addr, words):
    """Format a C2 block: pad so the handler-clobbered 00000000 lands last."""
    words = list(words)
    if len(words) % 2 == 0:
        words.append(NOP)                      # keep the branch-back on its own slot
    words.append(0x00000000)
    out = [f"C2{addr & 0x01FFFFFF:06X} {len(words) // 2:08X}"]
    for i in range(0, len(words), 2):
        out.append(f"{words[i]:08X} {words[i + 1]:08X}")
    return "\n".join(out)


# ---- Substep granularity (the 180fps v8 lineage) ----------------------------
# TMarDirector's substep scheduler runs a fixed-point accumulator whose stock
# constants are 600 and 5 (verified against research/main.dol):
#   0x8029985C  li    r3,600        38600258
#   0x80299974  addi  r0,r3,-5      3803FFFB
#   0x80299980  cmpwi r0,5          2C000005
# Scaling both by G subdivides each native tick into G substeps, which is what
# makes the sim advance smoothly at G x 60 Hz instead of taking one giant step
# per frame. The shipping "$180fps v8" bundle used 1800/-15/15 — exactly stock*G
# at G=3 — so the rule is simply stock*G, with no other constant involved.
# The C2 @0x80299958 carries the same 5*G threshold and skips the substep when
# the accumulator has not yet earned one.

def substep_granularity(g):
    tick, thresh = 600 * g, 5 * g
    words = [0x801A0054,                       # lwz   r0,0x54(r26)   accumulator
             0x2C000000 | thresh,              # cmpwi r0,5G
             0x40800024,                       # bge   -> original insn (skip 9)
             0xA01A004C,                       # lhz   r0,0x4C(r26)
             0x60004000,                       # ori   r0,r0,0x4000   zero-substep flag
             0xB01A004C,                       # sth   r0,0x4C(r26)
             0x3BA00000,                       # li    r29,0
             0x3D808029, 0x618C9C00,           # lis/ori r12,0x80299C00
             0x7D8903A6, 0x4E800420,           # mtctr r12 ; bctr  -> epilogue
             0x3B9C0001]                       # addi  r28,r28,1     (original insn)
    return "\n".join([
        f"0429985C {0x38600000 | tick:08X}",           # li    r3,600G
        f"04299974 {0x38030000 | (-thresh & 0xFFFF):08X}",  # addi  r0,r3,-5G
        f"04299980 {0x2C000000 | thresh:08X}",         # cmpwi r0,5G
        _c2(0x80299958, words),
    ])


# ---- BGM tempo guard (v12) --------------------------------------------------
# JASystem outer tempo proportion reads 0.0 across some scene transitions and
# the sequence stalls; substitute 1.0. Pure value guard, no rate constant.
BGM_TEMPO_GUARD = """C231B8C8 00000003
C0030018 C1A2FA18
FC006800 40820008
C0028018 00000000"""

# DSP voice-limiter kill: DSP_LIMIT_RATIO (f32 @0x8040CDB4) misfires under the
# 2x-slowed audio DMA period and silences every sequenced BGM note on birth.
# Zeroing it removes the load-shedding heuristic. Rate-independent.
BGM_DSP_LIMIT = "0440CDB4 00000000"

# Sun lens-flare occlusion sampler: 17 synchronous GXPeekZ EFB readbacks per
# frame, N x too often at high FPS. NOP the single call. Rate-independent.
# OPT-IN ONLY (--sun-probe): profiling showed this recovers no measurable frame
# time (the Noki stall was the pollution readback, not this) and it does break
# the flare, which then draws through geometry. Kept for reference, off by
# default. See PERF-PLAYBOOK.md "MEASURE FIRST".
SUN_PROBE = "0402E28C 60000000"

# ---- HUD perpetual-stars fix (v4 = v2 + v3 + watchdog) ----------------------
# Pause/unpause leaks JPA emitters three separate ways: the coin-counter and
# pause-menu emitters are orphaned in pauseOut (v2); TPauseMenu2 re-creates the
# item sparkle every bounce loop without deleting the old one (v3); and banner
# emitters whose cleanup milestone is skipped strand forever (v4 watchdog).
# All three are rate-independent. Note the watchdog's 600.0f age threshold
# (0x44160000) is 10s only if emitters actually age at 60 Hz — which is exactly
# what _rate_gate() now guarantees at every G. Under the old fixed 1-in-2 gate
# it was 10s at 120fps but 6.7s at 180fps.
STARFIX = """C214A850 00000007
809D0124 8064011C
60630001 9064011C
806D9FB8 806300AC
80630110 28030000
41820010 8083011C
60840001 9083011C
809D0144 00000000
C2155D8C 00000004
80DF0110 28060000
41820010 80E6011C
60E70001 90E6011C
806DA024 00000000
C2324EB8 00000009
806DA024 7C03E840
40820034 807E01E8
2C030000 40820028
807E011C 70600001
4082001C 809E0010
3C004416 7C040040
4081000C 60630001
907E011C 7FC3F378
60000000 00000000"""

PROXIMITY_GLOW = """C21EBA60 0000000C
816D9F4C C04B0000
C01F0010 EC420028
EDA200B2 C04B0008
C01F0018 EC420028
EDA268BA C002DDCC
EC000032 C0428028
EC0000B2 FC0D0000
40800018 C042DD68
D05F00D0 A97F00C8
B17F00CA 48000008
C05F00D0 60000000
60000000 00000000"""


# ---- Animation-rate fix (family-B "raw rate" leaks) -------------------------
# Anims whose frame-rate is set from a RAW param/const instead of through
# SMSGetAnmFrameRate() advance 4x too fast at 120fps (calc_anim fires 4x more;
# the API return, forced to 1/G, would have compensated). The correct, fps-general,
# SELF-DISABLING scale for a raw rate R is  R * SMSGetAnmFrameRate()/2 = R/(2G),
# where G = the framerate global (FPS/60).  At stock G=0.5 -> 2G=1.0 -> no-op, so
# these hooks need no gate.  At 120fps (G=2) -> R/4 == the proven v16 x0.25, so this
# SUPERSEDES the hand-written v16 Petey block (0x800955cc is in the list below).
#
# The scale math injected at each hooked instruction (rate FPR fR, scratch FPR fS):
#     lfs   fS, -0x3c8(r2)          ; fS = G   (r2 SDA -> framerate global 0x804167B8)
#     fadds fS, fS, fS              ; fS = 2G
#     fdivs fR, fR, fS             ; fR = R/(2G)
# store-mode  hooks the game's `stfs fR,0xc(r3)`  -> [scale] + [orig stfs]
# load-mode   hooks the `lfs f1,off(rX)` before a MActor::setFrameRate call
#             -> [orig lfs] + [scale f1]  (the original bl then stores the scaled f1)
#
# Sites confirmed by disasm sweep (animrate_disasm.py) + per-site verification.
# The stack-load site 0x80270204 (rate <- 0x120(r1), THinokuri2-area) is EXCLUDED:
# its provenance is a stack spill, not a param — needs manual confirmation first.
ANMRATE_GLOBAL_DISP = -0x3c8 & 0xFFFF          # framerate global via r2 (SDA)

def _lfs(frD, rA, d):   return (48 << 26) | (frD << 21) | (rA << 16) | (d & 0xFFFF)
def _stfs(frS, rA, d):  return (52 << 26) | (frS << 21) | (rA << 16) | (d & 0xFFFF)
def _fadds(d, a, b):    return (59 << 26) | (d << 21) | (a << 16) | (b << 11) | (21 << 1)
def _fdivs(d, a, b):    return (59 << 26) | (d << 21) | (a << 16) | (b << 11) | (18 << 1)

# (hook_addr, mode, orig_instruction_word)
ANMRATE_SITES = [
    # getFrameCtrl + inline stfs  (rate = the stfs source FPR)
    (0x800955CC, "store", 0xD3E3000C),   # TBossPakkun::changeBck (Petey) — was v16
    (0x8013C3AC, "store", 0xD3E3000C),   # 0x8013c30c cluster (one enemy, per-anim rates)
    (0x8013C408, "store", 0xD3E3000C),
    (0x8013C46C, "store", 0xD3E3000C),
    (0x8013C24C, "store", 0xD3E3000C),   # 0x8013c1cc
    (0x8013C4E8, "store", 0xD3E3000C),   # 0x8013c490
    (0x8013C584, "store", 0xD3E3000C),   # 0x8013c52c
    (0x8013C620, "store", 0xD3E3000C),   # 0x8013c5c8
    (0x8013B6C4, "store", 0xD3E3000C),   # 0x8013b668
    (0x80244B88, "store", 0xD3E3000C),   # 0x80244800
    (0x8011763C, "store", 0xD003000C),   # 0x801175fc (rate in f0)
    (0x801176EC, "store", 0xD003000C),   # 0x801176bc (rate in f0)
    # lfs f1 before MActor::setFrameRate  (rate = f1)
    (0x802054D4, "load", 0xC03F01D0),    # 0x80205354 cluster, +0x1d0(r31)
    (0x802054E8, "load", 0xC03F01D0),
    (0x80205620, "load", 0xC03F01D0),
]

def _anmrate_block(addr, mode, orig):
    if mode == "store":
        rate = (orig >> 21) & 31                 # stfs source FPR
        scratch = 1 if rate == 0 else 0          # a dead volatile != rate
        words = [_lfs(scratch, 2, ANMRATE_GLOBAL_DISP),
                 _fadds(scratch, scratch, scratch),
                 _fdivs(rate, rate, scratch),
                 orig]                            # original store, now of scaled rate
    else:                                        # load-mode: scale f1 after the lfs
        rate, scratch = 1, 0
        words = [orig,                            # original lfs f1,off(rX)
                 _lfs(scratch, 2, ANMRATE_GLOBAL_DISP),
                 _fadds(scratch, scratch, scratch),
                 _fdivs(rate, rate, scratch)]
    words += [0x60000000, 0x00000000]            # nop + handler-clobbered last word
    out = [f"C2{addr & 0x01FFFFFF:06X} {len(words) // 2:08X}"]   # e.g. 0x800955CC -> C20955CC
    for i in range(0, len(words), 2):
        out.append(f"{words[i]:08X} {words[i + 1]:08X}")
    return "\n".join(out)

def anmrate():
    return "\n".join(_anmrate_block(a, m, o) for a, m, o in ANMRATE_SITES)


def framerate_word(fps):
    """float(FPS/60) as an 8-hex-digit big-endian word for the 04 write."""
    return struct.pack(">f", fps / 60.0).hex().upper()


def integer_g(fps):
    """G = FPS/60 as an int when it is exact, else None (no exact gate exists)."""
    g = fps / 60.0
    return int(round(g)) if g >= 2 and abs(g - round(g)) < 1e-9 else None


def build(fps, forceopen=True, anmrate_fix=True, substep=True, audio=True,
          stars=True, sun_probe=False):
    g = integer_g(fps)
    gate_g = g or 2                            # non-integer G: fall back to 1-in-2
    parts = [base(framerate_word(fps)), particles(gate_g), PROXIMITY_GLOW]
    if forceopen:
        parts.insert(2, FORCEOPEN)
    if substep:
        parts.append(substep_granularity(gate_g))
    tf = timerfix(fps)
    if tf:
        parts.append(tf)
    if anmrate_fix:
        parts.append(anmrate())
    if audio:
        parts += [BGM_DSP_LIMIT, BGM_TEMPO_GUARD]
    if stars:
        parts.append(STARFIX)
    if sun_probe:
        parts.append(SUN_PROBE)
    return "\n".join(parts)


def check(bundle):
    """Structural-validate: every C2 header's line count matches, and each C2
    block ends in 00000000 (the code-handler clobbers the last word — trap #2)."""
    lines = [l.split()[:2] for l in bundle.splitlines() if l.strip()]
    words = []
    for l in lines:
        words.extend(l)
    i, errs, nblocks = 0, [], 0
    while i < len(words):
        w = words[i]
        if w.startswith("C2"):
            nblocks += 1
            n = int(words[i + 1], 16)                 # 8-byte lines that follow
            body = words[i + 2 : i + 2 + 2 * n]
            if len(body) != 2 * n:
                errs.append(f"{w}: truncated (want {2*n} body words, got {len(body)})")
            elif body[-1] != "00000000":
                errs.append(f"{w}: last word {body[-1]} != 00000000 (handler will clobber a real instr)")
            i += 2 + 2 * n
        elif w.startswith("04"):
            i += 2
        else:
            i += 2
    return nblocks, errs


def main():
    ap = argparse.ArgumentParser(description="Generate the SMS high-FPS Gecko bundle for a target framerate.")
    ap.add_argument("fps", type=float, help="target framerate (e.g. 120, 180, 240; must be a multiple of 60 for exact particle parity)")
    ap.add_argument("-o", "--out", help="write bundle to file (default: stdout)")
    ap.add_argument("--no-forceopen", action="store_true", help="v3-style: omit ForceOpen so story-locked M gates stay closed")
    ap.add_argument("--no-anmrate", action="store_true", help="omit the 15 raw anim-rate /(2G) fixes (incl. Petey, ex-v16)")
    ap.add_argument("--no-substep", action="store_true", help="omit substep granularity (stock*G); sim takes one step per frame")
    ap.add_argument("--no-audio", action="store_true", help="omit the BGM fixes (DSP voice-limiter kill + tempo guard)")
    ap.add_argument("--no-stars", action="store_true", help="omit the HUD perpetual-stars fix (v4)")
    ap.add_argument("--sun-probe", action="store_true", help="NOP the sun lens-flare EFB probe (measured no gain; breaks the flare)")
    ap.add_argument("--check", action="store_true", help="structural-validate the C2 blocks and exit")
    a = ap.parse_args()

    m = a.fps / 60.0
    title = f"$SMS {a.fps:g}fps bundle (fpspatch{'' if not a.no_forceopen else ', no-ForceOpen'})"
    bundle = build(a.fps, forceopen=not a.no_forceopen, anmrate_fix=not a.no_anmrate,
                   substep=not a.no_substep, audio=not a.no_audio,
                   stars=not a.no_stars, sun_probe=a.sun_probe)

    if a.check:
        nblocks, errs = check(bundle)
        print(f"{a.fps:g}fps bundle: {nblocks} C2 blocks checked")
        for e in errs:
            print("  ERROR:", e)
        print("OK" if not errs else "FAILED")
        sys.exit(0 if not errs else 1)

    if integer_g(a.fps) is None:
        print(f"# WARNING: {a.fps:g}/60 is not an integer >= 2 — the emitter and substep "
              f"gates fall back to 1-in-2 and will NOT hold 60 Hz at this rate.",
              file=sys.stderr)

    header = (f"# ---- paste into GameSettings/GMSE01.ini [Gecko], enable the title in "
              f"[Gecko_Enabled] ----\n"
              f"# ALSO set EmulationSpeed = {m:g} in BOTH Dolphin.ini and GMSE01.ini "
              f"[Core] (per-game overrides).\n"
              f"# framerate global 0x804167B8 = {framerate_word(a.fps)} (= float {m:g})\n")
    text = f"{header}{title}\n{bundle}\n"
    if a.out:
        open(a.out, "w").write(text)
        print(f"wrote {a.out}  (EmulationSpeed to set: {m:g})", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
