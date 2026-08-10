#!/usr/bin/env python3
"""fpspatch.py — generate the Super Mario Sunshine (GMSE01) high-FPS Gecko bundle
for ANY target framerate.

Set G = FPS/60. Retargeting rescales FOUR independent things, and an earlier
version of this docstring was wrong to claim it was only the framerate word —
that assumption is exactly how the fixed 1-in-2 particle gate shipped at 180fps:

  1. the "framerate global" at 0x804167B8  →  float(G), plus EmulationSpeed = G
  2. the emitter gate                      →  1 substep in G      (_rate_gate)
  3. substep granularity                   →  stock 600/5 scaled by G
  4. the Noki pollution gate               →  1 frame in FPS/30 (= 2G, not G)
  5. the shine-select screen gate         →  1 frame in ceil(G/2) (select_gate)

Rate-INDEPENDENT, and correct as-is at every G:
  * hooks that READ the framerate global and self-scale — the 15 raw anim-rate
    /(2G) fixes, and the game-clock fix (v15), which divides OSCheckStopwatch
    ticks by G (shift for powers of two, long division for 180)
  * M-portal glow (XZ-distance reimpl) and ForceOpen (calls the real startOpen)
  * BGM DSP voice-limiter kill + tempo guard; the HUD stars fix
  * the Poink gate — its bare `cmpwi 40` looks rate-tied but flyTimer runs on
    substep-invariant spine ticks, so 40 keeps its stock meaning at every G
  * the cogwheel rope-creak SE gate — its bare 1-in-4 looks rate-tied but the
    substep clock it divides is pinned at 120 Hz at every G, so 1-in-4 is the
    native 30/sec everywhere (same reasoning as the Poink 40)
  * the skid-turn freshness fix — its bare 4-tick face delay is the stock 30 Hz
    pad staleness expressed in 120 Hz sim ticks, constant at every G (same
    reasoning again); it self-gates on the framerate global != 0.5f

Deliberately NOT generalized: the blue-coin lifetime fix, calibrated against this
machine's measured substep rate rather than derived from G, so it is emitted only
at 120fps.

Usage:
  fpspatch.py 120                  # print the 120fps bundle + EmulationSpeed
  fpspatch.py 180 -o out.txt       # write the 180fps bundle to a file
  fpspatch.py 240 --no-forceopen   # v3-style: respect story locks (no ForceOpen)
  fpspatch.py 180 --check          # validate structure, decoding and constants
  fpspatch.py 180 --emit-ini       # full GMSE01.ini fragment, ready to merge
  fpspatch.py 180 --bare -o c.txt  # hex only, for gecko.py add --code-file
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


# ---- SMSGetAnmFrameRate stub (v11) ------------------------------------------
# 0x802A7BD8 is SMSGetAnmFrameRate() = 60.0f / SMSGetVSyncTimesPerSec(), i.e.
# 60/(60*G) = 1/G, with 215 callers. Stubbing its prologue to `lfs f1,-0x7FD8(r2)
# ; blr` makes it return a hard 0.5f.
#
# That is correct BECAUSE substep_granularity pins the sim: with numerator 600G
# and quantum 5G, each direct() adds 600G/(60G) = 10 (always an exact divide) and
# each substep costs 5G, so the sim runs 60G * 10/(5G) = 120 Hz at EVERY G. The
# right return is therefore 60/120 = 0.5 regardless of framerate, whereas the
# stock formula would give 1/G and run anims 1.5x slow at 180fps.
#
# So it is a no-op at G=2 (1/G is already 0.5) and a real fix at G>=3 — which is
# why v11 introduced it for the 180fps line. It is only valid alongside the
# substep retune, hence build() ties it to `substep`.
ANMRATE_STUB = """042A7BD8 C0228028
042A7BDC 4E800020"""

# ---- Input latch (v9) -------------------------------------------------------
# TApplication::gameLoop @0x802A5F50 calls TMarioGamePad::read() @0x802A8054
# once per DISPLAYED frame, so at high FPS a press/release edge is reported
# several times per sim step. This hook skips the pad read on frames that will
# not advance the sim and zeroes mTrigger(+0x1C)/mRelease(+0x20) on all four
# pads, leaving held state (mButton) intact — mirroring what stock direct()
# already does for its own non-first substeps.
#
# The 0x803DF0C8 compare is TMarDirector's VTABLE address (a runtime type check
# so the gate is inert on logo/menu/movie directors), not a rate value.
#
# The threshold is the one rate-dependent constant. A frame runs a substep when
# remainder + 10 >= quantum, i.e. remainder >= 5G - 10. The shipped v9 hardcoded
# 5, which is exactly 5*3-10 — correct at G=3 and nowhere else. CONFIRMED
# IN-GAME at G=3 (PC, 2026-08-09): the 180fps bundle shipped WITHOUT this block
# and the dropped-inputs bug returned immediately (~6/10 edge presses lost);
# re-adding the identical block fixed it — so this is default-on now, not
# opt-in. At G=2 the threshold is 0 and the remainder is always 0 (every frame
# runs a substep), so there are no skip frames to guard: the gate is
# unreachable, and emitting it would only waste cave words — return None.
# Only valid alongside substep_granularity(g), which pins budget=10/quantum=5G.
#
# select_n (the shine-select divisor, see select_gate below) adds a SECOND
# director case: when the vtable is TSelectDir's instead, pad reads are held to
# 1 frame in select_n, phase-locked to select_gate's counter. The predicate
# tests (ctr+1) % select_n because this hook runs BEFORE TSelectDir::direct in
# the frame (gameLoop: read() -> updateMeaning -> mDirector->direct()) and it
# is select_gate that increments ctr — so both gates pass on the same physical
# frame and every trigger edge is consumed by exactly one menu tick.
def input_latch(g, select_n=None):
    thresh = 5 * g - 10
    if thresh <= 0:
        return None
    if not select_n:
        words = [0x807F0004, 0x2C030000, 0x4182005C,  # mDirector; null -> read()
                 0x80830000, 0x3CA0803D, 0x60A5F0C8,  # vptr vs TMarDirector vtable
                 0x7C042800, 0x40820048,              # not TMarDirector -> read()
                 0x80830054,                          # lwz r4,0x54(r3)  accumulator
                 0x2C040000 | (thresh & 0xFFFF),      # cmpwi r4,5G-10
                 0x4080003C,                          # bge -> read()
                 0x38C00000]                          # li r6,0
        for off in (0x20, 0x24, 0x28, 0x2C):          # mGamePads[0..3]
            words += [0x80BF0000 | off, 0x90C5001C, 0x90C50020]
        words += [0x48000014,                         # b -> after the call
                  0x3D80802A, 0x618C8054, 0x7D8903A6, 0x4E800421]   # bctrl read()
        return _c2(0x802A600C, words)
    sgate = _rate_gate(select_n, ctr=4, tmp=0, tmp2=6)
    L = len(sgate)
    i_sel, i_zero, i_read, i_after = 12, 20 + L, 34 + L, 38 + L
    def beq(i, t):  return 0x41820000 | (((t - i) * 4) & 0xFFFC)
    def bge(i, t):  return 0x40800000 | (((t - i) * 4) & 0xFFFC)
    def bne(i, t):  return 0x40820000 | (((t - i) * 4) & 0xFFFC)
    def b(i, t):    return 0x48000000 | (((t - i) * 4) & 0x03FFFFFC)
    words = [0x807F0004, 0x2C030000, beq(2, i_read),  # mDirector; null -> read()
             0x80830000, 0x3CA0803D, 0x60A5F0C8,      # vptr vs TMarDirector vtable
             0x7C042800, bne(7, i_sel),               # not TMarDirector -> SEL
             0x80830054,                              # lwz r4,0x54(r3)  accumulator
             0x2C040000 | (thresh & 0xFFFF),          # cmpwi r4,5G-10
             bge(10, i_read),                         # substep frame -> read()
             b(11, i_zero)]                           # skip frame -> zero triggers
    words += [0x3CA00000 | (SELECT_DIR_VTABLE >> 16),          # SEL:
              0x60A50000 | (SELECT_DIR_VTABLE & 0xFFFF),       # TSelectDir vtable
              0x7C042800, bne(15, i_read),            # other director -> read()
              0x3CA08000,                             # lis r5,0x8000
              0x80000000 | (4 << 21) | (5 << 16) | SELECT_CTR,  # lwz r4,ctr
              0x38840001]                             # addi r4,r4,1  (predicted)
    words += sgate                                    # cr0 <- (ctr+1) % select_n
    words.append(beq(19 + L, i_read))                 # pass frame -> read()
    assert len(words) == i_zero
    words.append(0x38C00000)                          # li r6,0
    for off in (0x20, 0x24, 0x28, 0x2C):              # mGamePads[0..3]
        words += [0x80BF0000 | off, 0x90C5001C, 0x90C50020]
    words.append(b(33 + L, i_after))                  # b -> after the call
    assert len(words) == i_read
    words += [0x3D80802A, 0x618C8054, 0x7D8903A6, 0x4E800421]   # bctrl read()
    return _c2(0x802A600C, words)


# ---- Shine-select (in-stage episode select) cadence gate --------------------
# The episode/shine select screen is run by TSelectDir — a SEPARATE director:
# its direct() (USA 0x80175EC4) calls plain JDrama::TDirector::direct()
# (USA 0x802F7D28, the bl at 0x80175FE8), which fires CUE_MOVE|CUE_CALC_ANIM on
# the menu once per RENDERED frame. None of the TMarDirector gating applies, so
# the menu logic runs at 30 Hz stock but 60*G Hz under the bundle — and its
# stick-repeat timing, thresholds of the form N * (this+0x14C) ticks where
# +0x14C = 1.0/SMSGetAnmFrameRate() (computed at USA 0x801744D0, one of the §8
# "reciprocal" sites), is doubly wrong because the v11 stub pins the rate at
# 0.5. Same story for the pad's own button-repeat (TMarioGamePad::reset:
# delay 20/rate, interval 6/rate = 40/12 ticks under the stub) since read()
# free-runs at render rate on this director. Net effect at 360fps: repeat
# delay ~0.11s at 30 steps/sec — one tap of left/right skips most of the ring.
#
# Fix: hold the select-screen SIM tick (pad read via input_latch's TSelectDir
# case + the CUE_MOVE|CUE_CALC_ANIM testPerform pass inside TDirector::direct)
# to 1 frame in ceil(G/2) — a 120 Hz cadence, exactly what every
# 0.5-stub-derived constant is calibrated for (the sim substep rate). At that
# cadence the menu's 40-tick repeat delay is 0.33s at 10 steps/sec — bit-exact
# stock timing — and CALC_ANIM at 120 Hz x rate 0.5 = 60 anim units/s, also
# stock. The CUE_DRAW pass (the second testPerform, 0x802F7DD0) is NOT gated
# and re-renders the frozen state every frame. Two shipped-and-user-sighted
# traps (2026-08-10) define this shape:
#   v1 skipped the whole TDirector::direct call (hook @0x80175FE8): 2-in-3
#   frames presented with no fresh render — PWM-dimmed a real 360 Hz panel to
#   ~1/3 duty ("reduced gamma") + periodic black blink from the XFB beat.
#   v2 skipped just the MOVE|CALC_ANIM testPerform: the 3D shines FLICKERED
#   translucent — TSelectShineManager enters its J3D models into the draw
#   buffers on CUE_CALC_ANIM (perform +0x37C..0x3F0: set frame from +0x3C,
#   then two virtuals = calc + entry) and the DRAW cue draws then CLEARS the
#   buffers (J3DDrawBuffer frameInit x2 at its tail) — so a draw with no
#   preceding entry draws no shines.
# Hence v3: gated frames still CALL testPerform but with r4 = CUE_CALC_ANIM
# only — entry stays alive every frame, while MOVE (input, repeat timers,
# state machine) holds the 120 Hz cadence. Safe because the CALC_ANIM
# consumers are idempotent appliers, not advancers: the shine manager
# re-stores the SAME +0x3C frame before applying, and TSelectMenu's perform
# ignores CALC_ANIM outright (its non-MOVE path handles only CUE_DRAW).
# The hook lives INSIDE the shared TDirector::direct, so it fires
# for every plain-direct director (menu/logo/movie); the vtable compare keeps
# it inert everywhere but TSelectDir. At G=2 the cadence is already 120 Hz and
# no gate is needed (the select screen was always correct at 120fps). Odd G
# rounds up: G=3 gates 1-in-2 (90 Hz, timings uniformly 4/3 of stock — mild,
# no exact divisor exists). The counter lives in the low arena next to the
# Noki pair; this block INCREMENTS it, the input_latch case only predicts (see
# there), so a --no-input-latch build degrades to fast-but-usable, not frozen.
SELECT_DIR_VTABLE = 0x803C0EF0   # TSelectDir vtable (ctor @0x80177538 stores it)
SELECT_HOOK = 0x802F7DBC         # TDirector::direct's MOVE-pass `bl testPerform`
TESTPERFORM = 0x802FCC94         # TViewObj::testPerform (r3=unk10,r4=3,r5=&gfx set)
SELECT_CTR = 0x16E8              # low arena; 0x16E0/0x16E4 = Noki, 0x16F0 = camera

def _select_divisor(g):
    """1-in-N frame divisor holding the select screen at ~120 Hz; None if 1."""
    n = (g + 1) // 2
    return n if n >= 2 else None

def select_gate(g):
    n = _select_divisor(g)
    if n is None:
        return None
    gate = _rate_gate(n, ctr=11, tmp=0, tmp2=10)
    L = len(gate)
    i_call = 11 + L
    words = [0x819E0000,                              # lwz r12,0(r30)  this->vptr
             0x3D600000 | (SELECT_DIR_VTABLE >> 16),  # lis r11,hi(vtable)
             0x616B0000 | (SELECT_DIR_VTABLE & 0xFFFF),  # ori r11,r11,lo
             0x7C0C5800,                              # cmpw r12,r11
             0x40820000 | (((i_call - 4) * 4) & 0xFFFC),  # other director -> CALL
             0x3D808000,                              # lis r12,0x8000
             0x80000000 | (11 << 21) | (12 << 16) | SELECT_CTR,  # lwz r11,ctr
             0x396B0001,                              # addi r11,r11,1
             0x90000000 | (11 << 21) | (12 << 16) | SELECT_CTR]  # stw r11,ctr
    words += gate                                     # cr0 <- ctr % n
    words += [0x41820008,                             # pass frame -> CALL (cue=3)
              0x38800002,                             # gated: r4 = CUE_CALC_ANIM only
              0x3D800000 | (TESTPERFORM >> 16),       # CALL: lis r12,hi
              0x618C0000 | (TESTPERFORM & 0xFFFF),    # ori r12,r12,lo
              0x7D8903A6, 0x4E800421]                 # mtctr ; bctrl testPerform
    assert words[i_call] == 0x3D800000 | (TESTPERFORM >> 16)
    return _c2(SELECT_HOOK, words)


# ---- Turn-around (skid U-turn) stick-freshness fix ---------------------------
# TMario::running (USA 0x8025ab04 region) enters the skid turn when the inlined
# isRunningTurnning sees |mIntendedYaw - mFaceAngle.y| > 0x471C (~100deg) with
# mForwardVel >= mTurnNeedSp (10.0).  Every term is CUE_MOVE/substep work — 120 Hz
# at every G — so the check itself is rate-invariant.  What is NOT invariant is
# STICK FRESHNESS: stock reads the pad at 30 Hz (one read per rendered frame,
# reused by all 4 substeps), so a physical stick flip lands as one big stale jump
# and the 100deg gap is guaranteed.  Under the bundle the pad is read on every
# substep frame (~120 Hz), the intendedYaw target sweeps smoothly through the
# player's real thumb roll, and doRunning's yaw pursuit (IConverge at
# mRunningRotSp 0x200..0x400/tick ~ 675 deg/s) tracks THROUGH the flip: for a
# normal >~110 ms roll the gap never crosses 0x471C and Mario arcs instead of
# skidding.  (A perfectly center-crossed <100 ms flick still works — which is
# why the bug reads as "sometimes possible, mostly not".)
#
# FIX: run the threshold compare against mFaceAngle.y from FOUR SIM TICKS AGO —
# exactly the 33 ms staleness the stock 30 Hz pad quantization gave the check —
# while leaving the actual steering pursuit (doRunning) fully fresh.  For
# deflections that never exceed the threshold the delayed face trails the
# current one by at most 4*rotSp (~20deg) DURING convergence and by 0 at rest,
# so sub-100deg steering cannot false-trigger; for real flips the extra ~20deg
# of retained lag restores the stock ~130 ms trigger window (vanilla-at-120Hz
# cuts it to ~110 ms).  The delay is the CONSTANT 4, not f(G): sim ticks are
# pinned at 120 Hz at every G (same reasoning as the Poink 40 / cogwheel 4).
#
# Mechanics: hook the inlined check's `lha r3,0x96(r31)` in running() at USA
# 0x8025AF64.  A 4-deep ring of face angles lives in the low arena at 0x80001724
# (0x1720 = last substep-counter value, 0x172C = owning TMario*), indexed by
# gpMarDirector's substep counter (+0x5C, the same word the particle parity gate
# reads).  Ring slot (ctr&3) is read (the value written 4 ticks ago) before
# being overwritten with the current face.  Two guards reseed the whole ring
# with the current face and fall back to vanilla behavior for that tick:
#   * counter delta != 1 — the previous running() tick was not the previous
#     substep (state change, pause, level load): prevents a stale pre-WAIT face
#     from false-triggering a skid on run-start;
#   * owner != r31 — a second TMario (TEMario in the Shadow Mario chase levels)
#     shares the hook: alternating actors reseed each other every tick, so both
#     silently degrade to vanilla instead of cross-contaminating.
# turnning()'s own copy of the check (USA 0x8025A874, the turn-CANCEL predicate)
# is deliberately NOT hooked: face is frozen during the turn, so delayed ==
# current there and stock cancel semantics are preserved.
# Gated on the framerate global != 0.5f, so the block is inert without the
# bundle (r0/r3/r4/r12/cr0 all dead at the hook: r3 is being overwritten, r4 is
# li'd on the next instruction, cr0 is redefined by the cmpwi that follows).
TURNAROUND_HOOK = 0x8025AF64
TURNAROUND_SCRATCH = 0x1720          # low arena: ctr u32, ring u16[4], owner u32

def turnaround_fix():
    S = TURNAROUND_SCRATCH
    return _c2(TURNAROUND_HOOK, [
        0xA87F0096,                        # lha    r3,0x96(r31)   current face (orig)
        0x3D808041,                        # lis    r12,0x8041
        0x800C67B8,                        # lwz    r0,0x67B8(r12) framerate global
        0x3C803F00,                        # lis    r4,0x3F00      0.5f
        0x7C002000,                        # cmpw   r0,r4
        0x41820064,                        # beq    OUT            stock -> inert
        0x818D9FB8,                        # lwz    r12,-0x6048(r13) gpMarDirector
        0x280C0000,                        # cmplwi r12,0
        0x41820058,                        # beq    OUT
        0x808C005C,                        # lwz    r4,0x5C(r12)   substep counter
        0x3D808000,                        # lis    r12,0x8000
        0x800C0000 | S,                    # lwz    r0,lastCtr
        0x908C0000 | S,                    # stw    r4,lastCtr
        0x7C002050,                        # subf   r0,r0,r4       delta
        0x2C000001,                        # cmpwi  r0,1
        0x800C0000 | (S + 0xC),            # lwz    r0,owner       (cr0 survives)
        0x93EC0000 | (S + 0xC),            # stw    r31,owner
        0x40820024,                        # bne    RESEED         gap in RUN ticks
        0x7C00F800,                        # cmpw   r0,r31
        0x4082001C,                        # bne    RESEED         different TMario
        0x54800F7C,                        # rlwinm r0,r4,1,29,30  (ctr&3)*2
        0x7D8C0214,                        # add    r12,r12,r0
        0xA80C0000 | (S + 4),              # lha    r0,ring[idx]   face 4 ticks ago
        0xB06C0000 | (S + 4),              # sth    r3,ring[idx]   store current
        0x7C030378,                        # mr     r3,r0          compare vs delayed
        0x48000014,                        # b      OUT
        0xB06C0000 | (S + 4),              # RESEED: ring[0..3] = current face
        0xB06C0000 | (S + 6),
        0xB06C0000 | (S + 8),
        0xB06C0000 | (S + 0xA),
        NOP,                               # OUT: falls into the branch-back
    ])


# ---- NPC talk-initiation debounce fix ---------------------------------------
# Starting a conversation (B near an NPC) is gated in TMarDirector::movement_game
# (USA 0x8029A788, runs once per SUBSTEP) by a two-phase handshake on
# director+0x128: movement_game sets bit0 ("talk NPC near this tick") and only
# opens the talk window when BIT1 is set AND the B talk-meaning edge (+0xD4 &
# 0x800) fired this frame. Bit0 is promoted to bit1 by the tail of
# changeState (USA 0x802981EC), which runs once per RENDERED frame. Under the
# substep retune those cadences diverge: at G=6 the two skip frames between
# substeps promote-then-CLEAR bit1 before the next movement_game ever runs, so
# the check can never pass — talk initiation is structurally impossible at
# 360fps (and ~50% dropped at 180: the first substep frame after each skip
# frame sees bit1 cleared). Fix: retarget the test at USA 0x8029A908 from bit1
# (rlwinm. r0,r0,0,30,30) to bit0 (rlwinm. r0,r0,0,31,31), which movement_game
# itself just set two instructions earlier. The vanilla "NPC was already near"
# debounce is still enforced upstream: the 0x800 meaning only exists when pad
# flag 0x4 was set at frame start, and only an EARLIER movement_game tick sets
# it. At G=2/stock cadence the change is behaviorally identical (bit1 == "bit0
# last frame" == NPC near, exactly when flag 0x4 is set), so it is emitted
# whenever the substep retune is — rate-independent, no cave words.
TALK_INIT_FIX = "0429A908 540007FF"
TALK_INIT_WORD = 0x540007FF

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

# ---- Noki Bay pollution-counting 30Hz gate ----------------------------------
# ~39% of the emulation thread in Noki Ep.1 is blocked in synchronous GPU->CPU
# readbacks (ReadTexels / GXReadPixMetric / PeekEFBColor) driven by pollution
# degree-counting, which runs once per RENDERED frame. The counting is native
# 30Hz work, so the divisor here is N = FPS/30 = 2G, NOT G: 4 at 120fps, 6 at
# 180, 8 at 240. Gated-out frames blr immediately and hold the last count; the
# visible goop draw (the else branch) is never gated.
#
# Two independent counters in the OS low arena, so no cue-ordering assumptions:
#   0x800016E0 obj counter (ticked once per obj cue), 0x800016E4 tex counter.
# (0x800016F0 is the camera code's scratch — do not collide.)
# The shipping v1 hardcoded `andi. r0,r11,3`, i.e. 1-in-4, correct only at
# 120fps; at 180 that is not even a valid 1-in-6 test. Rebuilt on _rate_gate so
# the branch offsets track the gate length.
NOKI_OBJ_CTR, NOKI_TEX_CTR = 0x16E0, 0x16E4

def noki_gate(fps):
    """Pollution-counting gate at native 30Hz. None when FPS/30 is not integral."""
    if fps % 30 or fps < 60:
        return None
    n = int(fps // 30)
    gate = _rate_gate(n, ctr=11, tmp=0, tmp2=12)   # r4 is live (the cue); r12 is free here
    L = len(gate)
    i_check_tex, i_gate_tex, i_skip, i_cont = 8 + L, 16 + L, 20 + 2 * L, 21 + 2 * L
    def beq(at, to):  return 0x41820000 | (((to - at) * 4) & 0xFFFC)
    def bne(at, to):  return 0x40820000 | (((to - at) * 4) & 0xFFFC)
    def b(at, to):    return 0x48000000 | (((to - at) * 4) & 0x03FFFFFC)
    w  = [0x548C01CF,                          # rlwinm. r12,r4,0,7,7   obj cue?
          beq(1, i_check_tex),
          0x3D808000, 0x80000000 | (11 << 21) | (12 << 16) | NOKI_OBJ_CTR,
          0x396B0001, 0x90000000 | (11 << 21) | (12 << 16) | NOKI_OBJ_CTR]
    w += gate
    w += [bne(6 + L, i_skip), b(7 + L, i_cont),
          0x548C018D,                          # rlwinm. r12,r4,0,6,6   tex cue?
          beq(9 + L, i_cont),
          0x548C863F,                          # rlwinm. r12,r4,16,24,31  layer
          bne(11 + L, i_gate_tex),
          0x3D808000, 0x80000000 | (11 << 21) | (12 << 16) | NOKI_TEX_CTR,
          0x396B0001, 0x90000000 | (11 << 21) | (12 << 16) | NOKI_TEX_CTR,
          0x3D808000, 0x80000000 | (11 << 21) | (12 << 16) | NOKI_TEX_CTR]
    w += gate
    w += [bne(18 + 2 * L, i_skip), b(19 + 2 * L, i_cont),
          0x4E800020,                          # blr — gated out, hold last count
          0x7C0802A6]                          # mflr r0 (the overwritten original)
    return _c2(0x8019D8C8, w)


# ---- Noki gate COMPANION 2: pollution EFB-copy gate (v3, the vanishing-goop fix) --
# The per-layer pipeline built by TMarDirector::initECTGft is
#   drawInit -> counting cue (TPollutionManager::perform, GATED) -> TEfbCtrlTex copy
# The copy is a SEPARATE viewObj: TEfbCtrlTex::perform (USA 0x802f8bac) GXCopyTex's
# the EFB scratch rect into the layer's pollution image EVERY frame, ungated. On
# gated frames the sim never drew the rect, so the copy snapshots black scene EFB
# into the map -> the map zeroes within frames of load ("no goop in the level",
# landed stamps flash 3-7x then die). Proven 2026-08-09 by [hifps] EFBcopy->RAM
# logging: every pollution-map flush (fmt=8/I8) was sum=0 nonzero=0 at full frame
# cadence while the bathwater copy carried real content.
#
# FIX: gate the copy to the SAME cadence and phase as the counting. Hook the
# mImagePtr null-check load in TEfbCtrlTex::perform (USA 0x802F8CF8, verified:
# lwz r0,0x2c(r29); cmplwi 0; beq exit). Pollution instances are discriminated by
# mTexFmt(+0x30) == GX_CTF_R8 (0x28) — set only by initECTGft for pollution layers;
# bathwater (direct GXCopyTex), mirror and stageDisp are untouched. On gated
# frames force r0=0 so perform's OWN null-check skips the copy; RAM keeps the last
# pass-frame map. texCtr is read without incrementing, after the layer-0 counting
# cue already ticked it this frame -> phases match from the first frame.
def noki_copy_gate(fps):
    if fps % 30 or fps < 60:
        return None
    n = int(fps // 30)
    gate = _rate_gate(n, ctr=11, tmp=0, tmp2=12)   # r0/r12 free here; r11 = texCtr
    L = len(gate)
    i_bne, i_beq, i_b = 2, 5 + L, 7 + L
    i_load = 8 + L                                 # original lwz r0,0x2c(r29)
    i_out = 9 + L                                  # falls into the branch-back
    w = [0x819D0030,                               # lwz    r12,0x30(r29)  mTexFmt
         0x280C0028,                               # cmplwi r12,0x28       GX_CTF_R8?
         0x40820000 | (((i_load - i_bne) * 4) & 0xFFFC),
         0x3D808000,                               # lis    r12,0x8000
         0x80000000 | (11 << 21) | (12 << 16) | NOKI_TEX_CTR]  # lwz r11,texCtr
    w += gate                                      # cr0 <- texCtr % n
    w += [0x41820000 | (((i_load - i_beq) * 4) & 0xFFFC),      # beq -> allow copy
          0x38000000,                              # li r0,0: pretend no image
          0x48000000 | (((i_out - i_b) * 4) & 0x03FFFFFC),     # b past the load
          0x801D002C]                              # lwz r0,0x2c(r29) (original)
    return _c2(0x802F8CF8, w)


# ---- Noki gate COMPANION: model-stamp dedupe (v2, the Bianco freeze fix) ----
# Gating TPollutionManager::perform lets pushModelStampTask accumulate G frames
# of tasks, so the SAME J3DModel is queued up to G times. calcViewMtx then calls
# model->entry() once per queue slot, and J3D's entry() is a push-front onto an
# intrusive list: the second entry of the same packet makes packet->next point
# at itself. J3DDrawBuffer::draw() walks that self-loop forever, streaming one
# mat packet into the GX FIFO until Dolphin's vertex batch OOMs (~64GB) — the
# every-time freeze on load in Bianco Ep.1 (any polluted level whose actors
# stamp models; Noki Bay has none, which is why the gate tested clean there).
# Root-caused 2026-08-09 from a live FIFO dump: the ring held one ~95-byte
# packet (CALL DL 80abc880/815fb2e0 + matrix loads) repeating wall-to-wall.
#
# FIX: dedupe at the push. Hook pushModelStampTask (USA 0x8019B120, verified:
# lhz r0,0x28(r3); cmplwi 0x14; bgelr) and scan the queue (slots of 8 at
# this+0x38) for the incoming model ptr (r5); on a hit, blr — identical to the
# stock queue-full early-return. Clobbers only volatile r10-r12; ctr untouched
# (callers may loop on it); exits with r0 = count (the re-executed original).
# fps-independent: duplicates exist whenever the gate batches frames.
def noki_dedupe():
    return _c2(0x8019B120, [
        0xA0030028,   # lhz   r0,0x28(r3)     original insn; count
        0x39630038,   # addi  r11,r3,0x38     cursor = &slot[0].mModel
        0x7C0C0378,   # mr    r12,r0          remaining = count
        0x280C0000,   # loop: cmplwi r12,0
        0x4182001C,   # beq   cont
        0x814B0000,   # lwz   r10,0(r11)
        0x7C0A2840,   # cmplw r10,r5
        0x4D820020,   # beqlr                 duplicate -> skip push
        0x396B0008,   # addi  r11,r11,8
        0x398CFFFF,   # addi  r12,r12,-1
        0x4BFFFFE4,   # b     loop
        0x60000000,   # cont: nop (falls into branch-back)
    ])


# ---- Noki cogwheel-lift rope-creak cadence (the urn pulley SE) ---------------
# TCogwheel::control (USA 0x801da084) requests MSD_SE_OBJ_MR_TSUBO_PULL (0x3060,
# JAL registration name "the rope supporting the Mare urn") on EVERY control()
# tick while the wheel turns (|speed at +0x138| > 0.01), and TCogwheelScale::
# control (0x801da818) requests MSD_SE_OBJ_MR_TSUBO_WATER (0x3061) every tick
# while the pot drains. control() runs once per SUBSTEP (movement() in
# TMarDirector::direct()), i.e. 120 Hz at every G, so the REQUEST rate is
# rate-invariant — but JAudio collapses the request flood into one audible
# (re)trigger per PROCESSED FRAME, so the creak fires at the render rate:
# 30/sec stock, 120/sec at 120fps. That is the "bizarre fast rope ratchet" on
# the Noki Ep.1 urn lifts.
#
# Gate both call sites to 1 substep in 4 on the director's substep counter
# (gpMarDirector+0x5C, the same counter the particle parity gate reads): at
# most one request per 4 substeps = 30/sec at EVERY G. The divisor is the
# CONSTANT 120/30 = 4, not a function of G, because the substep retune pins
# substeps at 120 Hz regardless of framerate (same reasoning as the Poink 40).
# A shared per-object-blind counter would break with two lifts moving at once;
# the global substep counter gives every instance the same 1-in-4 phase.
# Gated ticks jump to the branch target the game itself uses when its own SE
# category check fails (pure epilogue 0x801da22c / merge point 0x801da89c).
# Clobbers only r12/ctr/cr0 — all dead at both hook points (cr0 was consumed
# by the preceding ble, ctr is unused in both functions, r12 is volatile with
# no local use between prologue and the SE bl).
COGWHEEL_HOOKS = (
    # (hook,      game's SE-skip target, overwritten original instruction)
    (0x801DA1E8, 0x801DA22C, 0xC002DA10),   # TCogwheel:      TSUBO_PULL  (lfs f0,-0x25f0(r2))
    (0x801DA860, 0x801DA89C, 0x806D9FBC),   # TCogwheelScale: TSUBO_WATER (lwz r3,-0x6044(r13))
)

def cogwheel_se_gate():
    def block(hook, skip, orig):
        return _c2(hook, [
            0x818D9FB8,                      # lwz    r12,-0x6048(r13)  gpMarDirector
            0x280C0000,                      # cmplwi r12,0             null: fail-open
            0x41820020,                      # beq    CONT
            0x818C005C,                      # lwz    r12,0x5C(r12)     substep counter
            0x718C0003,                      # andi.  r12,r12,3
            0x41820014,                      # beq    CONT              1-in-4: request the SE
            0x3D800000 | (skip >> 16),       # lis    r12,hi(skip)
            0x618C0000 | (skip & 0xFFFF),    # ori    r12,r12,lo(skip)
            0x7D8903A6,                      # mtctr  r12
            0x4E800420,                      # bctr   -> game's own SE-skip path
            orig,                            # CONT: the overwritten original
        ])
    return "\n".join(block(*h) for h in COGWHEEL_HOOKS)


# ---- Test5 morph-wipe EFB-copy reduction (the decompose/recompose lag) ------
# The scene-transition "decompose/recompose" effect is the Hx wipe module's
# Hx_Test5 (USA 0x8017DF74; whole TU maps JP-0xC0388, verified against the fn
# table at 0x803C129C and Hx_CameraInit). Every RENDERED frame in wipe state 2
# it walks the screen in 64x64 tiles (10x8 = 80) and, PER TILE, calls
# Hx_GetFrBuffer (0x80182A20) = GXSetTexCopySrc/Dst + GXCopyTex(clear=TRUE) +
# GXPixModeSync — an EFB copy into the static 8KB tile buffer at 0x803F4440
# (globals 0x803F43C0 + 0x80) — then redraws the tile as a 16-segment swirled
# fan. 80 EFB copies/frame is native-30fps work: 2,400 copies/s by design,
# 28,800/s at 360fps. Each copy is a render-pass switch in Dolphin, so the
# framerate collapses for exactly the ~20 rendered frames the wipe runs
# (Hx_TimerCountDown counts frames, +0x3C = 20), which is why the recompose
# crawls while Mario (substep-scheduled) plays normally underneath. Test4 and
# the fade wipes do no copies; Circle and Door do 1-5 small morph copies per
# frame (__Hx_FrBufferMorf / Hxs_FrBufferMorf2/2B) — all fine. Test5 is the
# only monster.
#
# FIX: double the tile grid to 128x128 (5x4 = 20 copies/frame, a 4x cut) using
# the GX half-scale copy idiom so the 8KB buffer still fits: src rect 128x128,
# GXSetTexCopyDst(64, 64, fmt, mipmap=TRUE) box-filters the copy to the same
# 64x64 texture the fan already samples at normalized coords. Visual delta:
# transition chunks are 2x coarser and tile content is half-res DURING the
# morph only — imperceptible in motion; the final reveal frame hands back the
# normally-rendered scene.
#
# The copy-size change lives in ONE atomic cave (hooking the bl GXSetTexCopySrc
# inside Hx_GetFrBuffer, discriminated by dest == Test5's buffer — the other
# callers pass heap pointers) so a silently-dropped C2 can never pair "src
# widened" with "dst not halved": that pairing would GXCopyTex 16-32KB over the
# 8KB buffer and stomp BSS. Drop modes are all safe: cave dropped -> fully
# stock captures (strides/f22 alone just leave un-animated gaps during the
# wipe); strides dropped -> stock. Registers: r12/ctr free at the hook (GX
# leaf calls, Test5's own r24-r31 are behind GetFrBuffer's frame), r29 = dest
# is GetFrBuffer's own saved nonvolatile so it survives the bctrl — the flag
# is recomputed after the call instead of parked in a volatile.
#
# Emitted at G >= 3: at 120fps the 4x copy rate never measurably dipped (M2
# Max held 119), so the stock 64px look is kept there.
WIPE5_BUF = 0x803F4440          # Test5's static tile buffer (globals + 0x80)
GX_SETTEXCOPYSRC = 0x8035E388   # writes BP 0x49/0x4A (copy src TL/WH)
GX_SETTEXCOPYDST = 0x8035E48C   # (w, h, fmt, mipmap) — mipmap = half-scale
WIPE5_GRAB_HOOK = 0x80182A5C    # Hx_GetFrBuffer's bl GXSetTexCopySrc
WIPE5_RESUME = 0x80182A74       # past the original GXSetTexCopyDst call

def wipe5_opt():
    grab = _c2(WIPE5_GRAB_HOOK, [
        0x3D800000 | (WIPE5_BUF >> 16),        # lis   r12,hi(tile buffer)
        0x618C0000 | (WIPE5_BUF & 0xFFFF),     # ori   r12,r12,lo
        0x7C1D6040,                            # cmplw r29,r12    Test5's capture?
        0x4082000C,                            # bne   CALL       other caller: stock
        _rlwinm(5, 5, 1, 0, 30),               # slwi  r5,r5,1    src w 64 -> 128
        _rlwinm(6, 6, 1, 0, 30),               # slwi  r6,r6,1    src h 64 -> 128
        0x3D800000 | (GX_SETTEXCOPYSRC >> 16), # CALL: lis/ori/mtctr/bctrl
        0x618C0000 | (GX_SETTEXCOPYSRC & 0xFFFF),
        0x7D8903A6, 0x4E800421,                # GXSetTexCopySrc(x, y, srcw, srch)
        0x57C3043E,                            # clrlwi r3,r30,16  dst w = 64 (orig)
        0x57E4043E,                            # clrlwi r4,r31,16  dst h = 64 (orig)
        0x38A00004,                            # li    r5,4        GX_TF_RGB565 (orig)
        0x38C00000,                            # li    r6,0        mipmap off (orig)
        0x3D800000 | (WIPE5_BUF >> 16),        # re-test dest (r29 nonvolatile;
        0x618C0000 | (WIPE5_BUF & 0xFFFF),     #  volatiles died in the bctrl)
        0x7C1D6040,                            # cmplw r29,r12
        0x40820008,                            # bne   DST
        0x38C00001,                            # li    r6,1        half-scale copy
        0x3D800000 | (GX_SETTEXCOPYDST >> 16), # DST: lis/ori/mtctr/bctrl
        0x618C0000 | (GX_SETTEXCOPYDST & 0xFFFF),
        0x7D8903A6, 0x4E800421,                # GXSetTexCopyDst(64, 64, fmt, mip)
        0x3D800000 | (WIPE5_RESUME >> 16),     # resume past the original dst call
        0x618C0000 | (WIPE5_RESUME & 0xFFFF),
        0x7D8903A6, 0x4E800420,                # mtctr; bctr
    ])
    f22 = _c2(0x8017E18C, [0xC2C2B9FC,         # lfs f22,-0x4604(r2) = 32 (orig)
                           _fadds(22, 22, 22)])  # f22 = 64: half-tile offset/radius
    strides = "0417E39C 3B5A0080\n0417E3D8 3B390080"   # x/y tile strides 64 -> 128
    return "\n".join([grab, f22, strides])


# ---- Poink premature-explosion gate (v14, Bianco 5) -------------------------
# Poink's flight is ended early by an anim-cue-driven push to the Explosion
# nerve at flyTimer ~9; stock fires at ~36, far enough to reach Petey. Hook
# TNervePopoExplosion::execute's first-tick block: if the pig is mid-flight
# (+0xF0 bit0x80) and flyTimer(+0x19C) < 40, revert spine+0x14 to the Fly nerve
# and bctr to the epilogue, cancelling the explosion.
#
# RATE-INDEPENDENT despite the bare 40. flyTimer increments per SPINE tick, and
# the substep scheduler holds CUE_MOVE invariant across G — so flyTimer ticks at
# the same wall-clock rate at every framerate and 40 keeps meaning what it meant
# at stock. It is the anim CUE that fires G x too fast, not the timer. (Scaling
# this threshold by G would be wrong; see memory "high-fps bug surface".)
POINK = """C20E5E44 00000009
801F00F0 70000080
41820038 801F019C
2C000028 4080002C
3C008040 6000D95C
901E0014 38000001
901E0020 38600000
3C00800E 60006000
7C0903A6 4E800420
C022A460 00000000"""

# ---- Blue coin lifetime (v6) ------------------------------------------------
# G=2 ONLY, and deliberately not generalized. The gate holds TCoin::perform's
# --mStateTimer on 1 substep in 4, but the 3/4 keep ratio was *calibrated* on
# this machine against a measured ~40/sec substep rate, not derived from G (the
# sim is CPU-bound at roughly 1.33x, so the coin's substep rate is not a clean
# 60*G). Emitting it at another G would silently ship a wrong 20s timer. The
# embedded 3CE04000 gate word (float 2.0) self-disables it anywhere else anyway.
BLUECOIN = """C21BE880 00000008
3CC08041 80C667B8
3CE04000 7C063800
4082001C 80AD9FB8
28050000 41820010
80A5005C 70A50003
4182000C 901D0104
48000008 907D0104
60000000 00000000"""

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
# r2 (SDA2) = 0x80416BA0, verified from __init_registers @0x8000536C and
# corroborated by the dolphin-gecko skill's own note that 0.5f @0x8040EBC8 is
# -0x7FD8(r2). The framerate global 0x804167B8 is therefore -0x3E8(r2).
# THIS WAS -0x3C8, which is 0x804167D8 = a plain 60.0f constant, NOT the global:
# every anmrate block computed rate/(60+60) = rate/120 instead of rate/(2G) —
# roughly 30x too slow at 120fps — and, because 60.0f is a constant, it fired
# even with the fps codes off instead of self-disabling. The in-game-confirmed
# $Petey v16 block used the absolute form (lis/lwz 0x804167B8) and was correct;
# the generator regressed it.
ANMRATE_GLOBAL_DISP = -0x3e8 & 0xFFFF          # framerate global via r2 (SDA2)

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
    # REMOVED — the three "lfs f1,0x1d0(r31) before MActor::setFrameRate" sites
    # 0x802054D4 / 0x802054E8 / 0x80205620. Field +0x1D0 is smoothed toward a
    # target that is ALREADY multiplied by SMSGetAnmFrameRate() (0x80205530
    # `bl 0x802A7BD8` then `fmuls f30,f0,f1`, stored via the helper at
    # 0x80028BD4 hooked in at 0x80205614). Scaling the load again double-divides.
    # animrate-master.md / animrate-disasm.md only ever tagged these SUSPECT,
    # never confirmed — consistent with them being wrong.
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
          stars=True, sun_probe=False, noki=True, poink=True, bluecoin=True,
          cogwheel=True, input_latch_fix=True, select_fix=True, wipe_opt=True,
          turnfix=True):
    g = integer_g(fps)
    gate_g = g or 2                            # non-integer G: fall back to 1-in-2
    parts = [base(framerate_word(fps)), particles(gate_g), PROXIMITY_GLOW]
    if forceopen:
        parts.insert(2, FORCEOPEN)
    if substep:
        # the stub is only valid while the substep retune pins the sim at 120 Hz
        parts += [substep_granularity(gate_g), ANMRATE_STUB]
        # skip frames desync the talk-start handshake — see TALK_INIT_FIX
        parts.append(TALK_INIT_FIX)
        # ~120 Hz pad sampling lets yaw pursuit track through a stick flip and
        # starves the skid-turn threshold — see turnaround_fix (constant 4-tick
        # delay, valid only while the retune pins sim ticks at 120 Hz)
        if turnfix:
            parts.append(turnaround_fix())
        # the shine-select fix rides the same 0.5-stub calibration and needs
        # the pad-latch block for its select case — see select_gate
        sel_n = _select_divisor(gate_g) if (select_fix and input_latch_fix) else None
        if input_latch_fix:
            # the latch predicate reads the retuned accumulator — substep only
            il = input_latch(gate_g, sel_n)
            if il:
                parts.append(il)
        if sel_n:
            parts.append(select_gate(gate_g))
    tf = timerfix(fps)
    if tf:
        parts.append(tf)
    if anmrate_fix:
        parts.append(anmrate())
    if audio:
        parts += [BGM_DSP_LIMIT, BGM_TEMPO_GUARD]
    if stars:
        parts.append(STARFIX)
    if poink:
        parts.append(POINK)
    if cogwheel:
        parts.append(cogwheel_se_gate())       # constant 1-in-4; see COGWHEEL_HOOKS
    if noki:
        ng = noki_gate(fps)
        if ng:
            parts.append(ng)
            parts.append(noki_dedupe())        # REQUIRED companion — see noki_dedupe
            parts.append(noki_copy_gate(fps))  # REQUIRED companion — see noki_copy_gate
    if wipe_opt and gate_g >= 3:               # 120fps keeps the stock 64px look
        parts.append(wipe5_opt())
    if bluecoin and g == 2:                    # calibrated at G=2 only — see BLUECOIN
        parts.append(BLUECOIN)
    if sun_probe:
        parts.append(SUN_PROBE)
    return "\n".join(parts)


def emit_ini(fps, title, bundle):
    """A paste-ready GMSE01.ini fragment: [Core] speed/audio plus the code, listed
    and ticked. AudioPreservePitch fixes pitch; correct *tempo* additionally needs
    the SystemTimers.cpp audio-DMA patch in dolphin-patches/ (it scales the DMA
    period by EmulationSpeed at runtime, so one build is correct at every rate)."""
    m = fps / 60.0
    return (f"# ---- GMSE01.ini fragment for {fps:g}fps — merge into the USER ini at\n"
            f"# ~/Library/Application Support/Dolphin/GameSettings/GMSE01.ini\n"
            f"# Dolphin MUST be fully quit first: it rewrites this file on close.\n"
            f"[Core]\n"
            f"EmulationSpeed = {m:g}\n"
            f"EnableCheats = True\n"
            f"AudioPreservePitch = True\n"
            f"[Gecko]\n"
            f"{title}\n{bundle}\n"
            f"[Gecko_Enabled]\n{title}\n")


def _iter_codes(bundle):
    """Walk a bundle yielding ('C2', addr, body_words) and ('04', addr, value)."""
    words = []
    for line in bundle.splitlines():
        line = line.strip()
        if not line or line[0] in "#$":
            continue
        words.extend(line.split()[:2])
    i = 0
    while i + 1 < len(words):
        w = words[i]
        if w.startswith("C2"):
            n = int(words[i + 1], 16)
            body = [int(x, 16) for x in words[i + 2: i + 2 + 2 * n]]
            yield "C2", 0x80000000 | int(w[2:], 16), body
            i += 2 + 2 * n
        else:
            yield "04", 0x80000000 | int(w[2:], 16), int(words[i + 1], 16)
            i += 2


def _implied_divisor(words, ctr):
    """Recover the 1-in-N divisor a block's gate actually encodes, straight from
    the emitted words — deliberately independent of _rate_gate so the check can
    disagree with the generator."""
    for j, w in enumerate(words):
        if (w >> 26) == 28 and ((w >> 21) & 31) == ctr:          # andi. rX,ctr,N-1
            return (w & 0xFFFF) + 1
        if (w >> 26) == 14 and not ((w >> 16) & 31) and j + 1 < len(words):
            nxt = words[j + 1]                                    # li tmp,N ; divwu _,ctr,tmp
            if (nxt >> 26) == 31 and ((nxt >> 1) & 0x3FF) == 459 and ((nxt >> 16) & 31) == ctr:
                return w & 0xFFFF
    return None


PARTICLE_HOOKS = (0x802887A8, 0x80288D30, 0x80288DEC)
SDA2 = 0x80416BA0              # r2, from __init_registers @0x8000536C
FRAMERATE_GLOBAL = 0x804167B8  # = -0x3E8(r2)

def check(bundle, fps=None):
    """Validate a bundle three ways: C2 block structure, capstone-decodability of
    every cave word, and — when fps is given — that each rate-derived constant
    matches the framerate actually requested."""
    errs, n_c2 = [], 0
    try:
        from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
        md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    except ImportError:
        md = None
        errs.append("NOTE: capstone not installed — instruction decoding skipped")

    codes = {}
    for kind, addr, payload in _iter_codes(bundle):
        codes[(kind, addr)] = payload
        if kind != "C2":
            continue
        n_c2 += 1
        tag = f"C2 @{addr:08X}"
        if not payload:
            errs.append(f"{tag}: empty body"); continue
        if payload[-1] != 0:
            errs.append(f"{tag}: last word {payload[-1]:08X} != 00000000 — the handler "
                        f"clobbers it, so a real instruction would be destroyed")
        # Trap that crashed blue-coin v1..v4: interior padding must be nop, never a
        # second zero word (every path has to converge on the single branch-back).
        for j, w in enumerate(payload[:-1]):
            if w == 0:
                errs.append(f"{tag}: interior 00000000 at word {j} — use 60000000 (nop)")
        if md:
            body = payload[:-1]
            code = b"".join(struct.pack(">I", w) for w in body)
            got = sum(1 for _ in md.disasm(code, 0))
            if got != len(body):
                errs.append(f"{tag}: capstone decoded only {got}/{len(body)} words "
                            f"— undecodable word in the cave")

    if fps is None:
        return n_c2, errs

    g = integer_g(fps)
    gate_g = g or 2
    want_fr = int(framerate_word(fps), 16)
    got_fr = codes.get(("04", 0x804167B8))
    if got_fr is not None and got_fr != want_fr:
        errs.append(f"framerate global: {got_fr:08X} != {want_fr:08X} (float {fps/60:g})")

    for hook in PARTICLE_HOOKS:
        body = codes.get(("C2", hook))
        if body is None:
            continue
        n = _implied_divisor(body, ctr=3)
        if n != gate_g:
            errs.append(f"particle gate @{hook:08X}: encodes 1-in-{n}, expected 1-in-{gate_g} "
                        f"(emitters would run at {60*gate_g/(n or 1):g} Hz, not 60)")

    if ("04", 0x8029985C) in codes:
        for addr, want, what in ((0x8029985C, 0x38600000 | 600 * gate_g, "li r3,600G"),
                                 (0x80299974, 0x38030000 | (-5 * gate_g & 0xFFFF), "addi r0,r3,-5G"),
                                 (0x80299980, 0x2C000000 | 5 * gate_g, "cmpwi r0,5G")):
            if codes.get(("04", addr)) != want:
                errs.append(f"substep {what} @{addr:08X}: {codes[('04', addr)]:08X} != {want:08X}")

    body = codes.get(("C2", 0x8019D8C8))
    if body is not None:
        n, want_n = _implied_divisor(body, ctr=11), int(fps // 30)
        if n != want_n:
            errs.append(f"Noki gate: encodes 1-in-{n}, expected 1-in-{want_n} (FPS/30)")

    # Every anmrate block must reach the framerate global through r2, never a
    # neighbouring constant in the SDA2 pool — the -0x3C8/-0x3E8 slip read 60.0f
    # and silently divided by 120 instead of 2G.
    for site, _, _ in ANMRATE_SITES:
        body = codes.get(("C2", site))
        if body is None:
            continue
        for w in body:
            if (w >> 26) == 48 and ((w >> 16) & 31) == 2:        # lfs frX,d(r2)
                va = SDA2 + struct.unpack(">h", struct.pack(">H", w & 0xFFFF))[0]
                if va != FRAMERATE_GLOBAL:
                    errs.append(f"anmrate @{site:08X}: lfs reads 0x{va:08X}, not the "
                                f"framerate global 0x{FRAMERATE_GLOBAL:08X}")
                break

    if ("C2", 0x801BE880) in codes and g != 2:
        errs.append("blue-coin block emitted at G!=2 — it is calibrated for 120fps only")

    # Test5 morph-wipe optimization: all four pieces must ship together. The
    # dangerous partial is "strides doubled but grab cave absent/mangled" only
    # in the sense of visual gaps (memory safety is carried by the atomic grab
    # cave itself), but a half-emitted set means the generator broke — flag it.
    grab = codes.get(("C2", WIPE5_GRAB_HOOK))
    f22b = codes.get(("C2", 0x8017E18C))
    w5_strides = [codes.get(("04", a)) for a in (0x8017E39C, 0x8017E3D8)]
    if any(x is not None for x in (grab, f22b, *w5_strides)):
        if gate_g < 3:
            errs.append("wipe5 blocks emitted at G<3 — 120fps keeps the stock look")
        if grab is None or f22b is None or None in w5_strides:
            errs.append("wipe5 optimization partially emitted — grab cave, f22 "
                        "double and both stride words must ship together")
        else:
            if w5_strides != [0x3B5A0080, 0x3B390080]:
                errs.append(f"wipe5 strides: {[w and f'{w:08X}' for w in w5_strides]}"
                            f" != ['3B5A0080', '3B390080'] (128px tile steps)")
            for target, what in ((GX_SETTEXCOPYSRC, "GXSetTexCopySrc"),
                                 (GX_SETTEXCOPYDST, "GXSetTexCopyDst"),
                                 (WIPE5_RESUME, "resume point")):
                if (0x618C0000 | (target & 0xFFFF)) not in grab:
                    errs.append(f"wipe5 grab cave: missing lis/ori of {what} "
                                f"0x{target:08X}")
            if 0x38C00001 not in grab:
                errs.append("wipe5 grab cave: half-scale flag li r6,1 missing — "
                            "a 128x128 full-res copy would overflow the 8KB "
                            "tile buffer at 0x803F4440")
            if f22b[0] != 0xC2C2B9FC or _fadds(22, 22, 22) not in f22b:
                errs.append("wipe5 f22 block must re-exec lfs f22,-0x4604(r2) "
                            "then double it (fan offset/radius 32 -> 64)")

    # Talk-initiation debounce: with the substep retune present, the stock
    # bit1 test at 0x8029A908 is starved by skip frames (impossible at G=6,
    # ~50% dropped at G=3) — the bundle must carry the bit0 retarget.
    if ("04", 0x8029985C) in codes:
        got = codes.get(("04", 0x8029A908))
        if got != TALK_INIT_WORD:
            errs.append(f"talk-init fix @0x8029A908: "
                        f"{got is not None and f'{got:08X}' or 'MISSING'} != "
                        f"{TALK_INIT_WORD:08X} — NPC dialogue cannot start on "
                        f"skip-frame-desynced ticks (impossible at 360fps)")

    # Turn-around freshness fix: with the substep retune present the pad samples
    # at ~120 Hz and yaw pursuit tracks through stick flips, so the bundle must
    # carry the delayed-face compare. Structure: the 0.5f gate, the ring index
    # rlwinm, and the constant-4 ring (a G-scaled delay here would be WRONG —
    # sim ticks are 120 Hz at every G).
    body = codes.get(("C2", TURNAROUND_HOOK))
    if body is not None:
        if body[0] != 0xA87F0096:
            errs.append(f"turnaround fix @{TURNAROUND_HOOK:08X}: first word "
                        f"{body[0]:08X} != the re-executed original lha r3,0x96(r31)")
        if 0x3C803F00 not in body:
            errs.append(f"turnaround fix @{TURNAROUND_HOOK:08X}: missing the 0.5f "
                        f"stock gate — the block would corrupt the check with the "
                        f"fps codes off")
        if 0x54800F7C not in body:
            errs.append(f"turnaround fix @{TURNAROUND_HOOK:08X}: missing the "
                        f"(ctr&3)*2 ring index — the delay must be the constant 4 "
                        f"ticks (stock 30 Hz staleness), never scaled by G")
    elif ("04", 0x8029985C) in codes:
        errs.append("turnaround freshness fix MISSING with the substep retune "
                    "present — 120 Hz pad sampling starves the skid-turn "
                    "threshold (turn-around run nearly impossible)")

    # Input pad-latch gate (v9): a frame runs a substep when remainder >= 5G-10,
    # so the gate's cmpwi must carry exactly that threshold. Its absence at G>=3
    # (with the substep retune present) is the shipped-2026-08-09 regression:
    # pad latch advances every rendered frame, sim consumes 2 of 3 -> ~1 in 3
    # edge inputs silently eaten.
    body = codes.get(("C2", 0x802A600C))
    latch_thresh = 5 * gate_g - 10
    if body is not None:
        if latch_thresh <= 0:
            errs.append(f"input latch emitted at G={gate_g} — threshold 5G-10 <= 0 "
                        f"means there are no skip frames; the block is dead cave weight")
        elif (0x2C040000 | (latch_thresh & 0xFFFF)) not in body:
            got = next((w for w in body if (w >> 16) == 0x2C04), None)
            errs.append(f"input latch @0x802A600C: threshold word "
                        f"{got and f'{got:08X}'} != cmpwi r4,{latch_thresh} "
                        f"(5G-10 at G={gate_g})")
    elif latch_thresh > 0 and ("04", 0x8029985C) in codes:
        errs.append(f"input latch MISSING at G={gate_g} with the substep retune "
                    f"present — edge inputs will drop on skip frames (the "
                    f"2026-08-09 dropped-inputs regression)")

    # Shine-select cadence gate: both halves must agree. The MOVE-pass gate
    # (C2 inside TDirector::direct) encodes 1-in-ceil(G/2) on the low-arena
    # counter, must re-target TViewObj::testPerform, and must carry the vptr
    # type check; the input-latch block must carry the TSelectDir vtable case
    # so pad reads stay phase-locked to the menu tick.
    sel_body = codes.get(("C2", SELECT_HOOK))
    latch_body = codes.get(("C2", 0x802A600C))
    sel_n = _select_divisor(gate_g)
    sel_vt_ori = 0x60A50000 | (SELECT_DIR_VTABLE & 0xFFFF)
    if sel_body is not None:
        n = _implied_divisor(sel_body, ctr=11)
        if n != sel_n:
            errs.append(f"select gate @{SELECT_HOOK:08X}: encodes 1-in-{n}, expected "
                        f"1-in-{sel_n} (ceil(G/2) at G={gate_g})")
        target = None
        for j, w in enumerate(sel_body[:-1]):
            if (w >> 26) == 15 and ((w >> 21) & 31) == 12 and j + 1 < len(sel_body):
                nxt = sel_body[j + 1]
                if (nxt >> 26) == 24 and ((nxt >> 21) & 31) == 12:
                    target = ((w & 0xFFFF) << 16) | (nxt & 0xFFFF)
        if target != TESTPERFORM:
            errs.append(f"select gate @{SELECT_HOOK:08X}: call target "
                        f"{target and f'{target:08X}'} != TViewObj::testPerform "
                        f"{TESTPERFORM:08X}")
        if 0x819E0000 not in sel_body:
            errs.append(f"select gate @{SELECT_HOOK:08X}: missing the vptr load "
                        f"lwz r12,0(r30) — without the director type check the "
                        f"gate throttles EVERY plain-direct director (logo/menu/"
                        f"movie)")
        if 0x38800002 not in sel_body:
            errs.append(f"select gate @{SELECT_HOOK:08X}: missing `li r4,2` — "
                        f"gated frames must still testPerform with CUE_CALC_ANIM "
                        f"or the J3D shines flicker translucent (draw buffers "
                        f"cleared each draw, entered only on CALC_ANIM; the "
                        f"v2 regression)")
        if latch_body is None or sel_vt_ori not in latch_body:
            errs.append(f"select gate present but the input-latch block has no "
                        f"TSelectDir case — pad repeat free-runs at render rate "
                        f"and menu edges are consumed off-phase")
    elif latch_body is not None and sel_vt_ori in latch_body:
        errs.append(f"input latch has the TSelectDir case but the select gate "
                    f"@{SELECT_HOOK:08X} is missing — its counter never advances, "
                    f"so pad reads freeze on whatever phase the counter holds")
    elif sel_n and ("04", 0x8029985C) in codes and latch_body is not None:
        errs.append(f"shine-select gate MISSING at G={gate_g} with the substep "
                    f"retune present — the episode-select screen runs {2 * gate_g}x "
                    f"stock cadence with ~3x-fast repeat (unusable at 360fps)")

    # Cogwheel SE gate: the divisor is a CONSTANT 4 at every fps (substeps are
    # pinned at 120 Hz; 120/30 native = 4), and each gated path must exit through
    # the game's own SE-skip target, encoded as lis/ori of that exact address.
    for hook, skip, orig in COGWHEEL_HOOKS:
        body = codes.get(("C2", hook))
        if body is None:
            continue
        n = _implied_divisor(body, ctr=12)
        if n != 4:
            errs.append(f"cogwheel gate @{hook:08X}: encodes 1-in-{n}, expected the "
                        f"constant 1-in-4 (substeps are 120 Hz at every G)")
        target = None
        for j, w in enumerate(body[:-1]):
            if (w >> 26) == 15 and ((w >> 21) & 31) == 12 and j + 1 < len(body):
                nxt = body[j + 1]                     # lis r12,hi ; ori r12,r12,lo
                if (nxt >> 26) == 24 and ((nxt >> 21) & 31) == 12:
                    target = ((w & 0xFFFF) << 16) | (nxt & 0xFFFF)
        if target != skip:
            errs.append(f"cogwheel gate @{hook:08X}: skip target {target and f'{target:08X}'}"
                        f" != the game's own SE-skip path {skip:08X}")
        if body[-2] != orig:
            errs.append(f"cogwheel gate @{hook:08X}: overwritten-original slot holds "
                        f"{body[-2]:08X}, expected {orig:08X}")

    return n_c2, errs


def main():
    ap = argparse.ArgumentParser(description="Generate the SMS high-FPS Gecko bundle for a target framerate.")
    ap.add_argument("fps", type=float, help="target framerate (e.g. 120, 180, 240; must be a multiple of 60 for exact particle parity)")
    ap.add_argument("-o", "--out", help="write bundle to file (default: stdout)")
    ap.add_argument("--no-forceopen", action="store_true", help="v3-style: omit ForceOpen so story-locked M gates stay closed")
    ap.add_argument("--no-anmrate", action="store_true", help="omit the 15 raw anim-rate /(2G) fixes (incl. Petey, ex-v16)")
    ap.add_argument("--no-substep", action="store_true", help="omit substep granularity (stock*G); sim takes one step per frame")
    ap.add_argument("--no-audio", action="store_true", help="omit the BGM fixes (DSP voice-limiter kill + tempo guard)")
    ap.add_argument("--no-stars", action="store_true", help="omit the HUD perpetual-stars fix (v4)")
    ap.add_argument("--no-noki", action="store_true", help="omit the Noki pollution-counting gate (native 30Hz, divisor FPS/30)")
    ap.add_argument("--no-poink", action="store_true", help="omit the Poink premature-explosion gate (v14)")
    ap.add_argument("--no-bluecoin", action="store_true", help="omit the blue-coin lifetime fix (only ever emitted at 120fps)")
    ap.add_argument("--no-cogwheel", action="store_true", help="omit the Noki urn-lift rope-creak SE cadence gate (constant 1-in-4 substeps)")
    ap.add_argument("--no-input-latch", action="store_true", help="omit the v9 pad-latch gate (pad reads locked to sim frames; confirmed in-game at 180fps 2026-08-09 — omitting it drops ~1 in 3 edge inputs at G>=3; also disables the shine-select fix, which needs the latch block)")
    ap.add_argument("--no-select", action="store_true", help="omit the shine-select screen cadence gate (episode select runs at render rate: ~3x-fast cursor repeat at 360fps)")
    ap.add_argument("--no-wipeopt", action="store_true", help="omit the Test5 morph-wipe EFB-copy reduction (decompose/recompose transitions run 80 EFB copies/frame and tank the framerate at G>=3)")
    ap.add_argument("--no-turnfix", action="store_true", help="omit the skid-turn stick-freshness fix (120Hz pad sampling lets yaw pursuit track through a stick flip; the turn-around run threshold then almost never trips)")
    ap.add_argument("--sun-probe", action="store_true", help="NOP the sun lens-flare EFB probe (measured no gain; breaks the flare)")
    ap.add_argument("--bare", action="store_true", help="emit hex pairs only, ready for gecko.py --code-file")
    ap.add_argument("--emit-ini", action="store_true", help="emit a full GMSE01.ini fragment ([Core] + [Gecko] + [Gecko_Enabled])")
    ap.add_argument("--check", action="store_true", help="validate structure, decodability and rate constants, then exit")
    a = ap.parse_args()

    m = a.fps / 60.0
    title = f"$SMS {a.fps:g}fps bundle (fpspatch{'' if not a.no_forceopen else ', no-ForceOpen'})"
    bundle = build(a.fps, forceopen=not a.no_forceopen, anmrate_fix=not a.no_anmrate,
                   substep=not a.no_substep, audio=not a.no_audio,
                   stars=not a.no_stars, sun_probe=a.sun_probe,
                   noki=not a.no_noki, poink=not a.no_poink,
                   bluecoin=not a.no_bluecoin, cogwheel=not a.no_cogwheel,
                   input_latch_fix=not a.no_input_latch,
                   select_fix=not a.no_select, wipe_opt=not a.no_wipeopt,
                   turnfix=not a.no_turnfix)

    if a.check:
        nblocks, errs = check(bundle, a.fps)
        cave = sum(len(p) for k, _, p in _iter_codes(bundle) if k == "C2")
        print(f"{a.fps:g}fps bundle: {nblocks} C2 blocks checked "
              f"(structure + decode + rate constants)")
        print(f"  C2 cave usage: {cave} words / {cave * 4} bytes — Dolphin's cave is "
              f"small and overflow fails SILENTLY (codes just don't run). If blocks "
              f"stop taking effect, drop optional ones (--no-stars, --no-poink, "
              f"--no-bluecoin) before suspecting the code itself.")
        for e in errs:
            print("  ERROR:", e)
        print("OK" if not errs else "FAILED")
        sys.exit(0 if not errs else 1)

    if integer_g(a.fps) is None:
        print(f"# WARNING: {a.fps:g}/60 is not an integer >= 2 — the emitter and substep "
              f"gates fall back to 1-in-2 and will NOT hold 60 Hz at this rate.",
              file=sys.stderr)

    if a.bare:
        # hex pairs only — gecko.py's `add` rejects any other line
        text = bundle + "\n"
    elif a.emit_ini:
        text = emit_ini(a.fps, title, bundle)
    else:
        header = (f"# ---- paste into GameSettings/GMSE01.ini [Gecko], enable the title in "
                  f"[Gecko_Enabled] ----\n"
                  f"# ALSO set EmulationSpeed = {m:g} in BOTH Dolphin.ini and GMSE01.ini "
                  f"[Core] (per-game overrides).\n"
                  f"# framerate global 0x804167B8 = {framerate_word(a.fps)} (= float {m:g})\n")
        text = f"{header}{title}\n{bundle}\n"

    if a.out:
        open(a.out, "w").write(text)
        print(f"wrote {a.out}  (EmulationSpeed to set: {m:g})", file=sys.stderr)
        if a.bare:
            print(f"install with:  python3 sunshine/gecko/skill/gecko.py add "
                  f'--title "{title[1:]}" --code-file {a.out} --enable', file=sys.stderr)
            print("Dolphin MUST be fully quit first — it rewrites the INI on close.",
                  file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
