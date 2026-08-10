#!/usr/bin/env python3
"""coinhook_assemble.py — assemble the SMS blue-coin timer parity C2 hook.

Run with a venv that has capstone (e.g. /tmp/smsre_venv/bin/python).

This is the FIELD-CORRECT assembler used during the blue-coin-timer investigation.
The encoders here get PPC field orders right (andi. is rA,rS,imm NOT rS,rA,imm;
beq/bne use the proven 0x4182xxxx/0x4082xxxx opcodes from the repo's parity block).
Hand-encoding these is error-prone — always use this script's encoders.

Mechanism (all verified against research/main.dol AND the running HD-portals ISO's
extracted dol — byte-identical at the hook site):
  TCoin::perform (USA 0x801BE7CC) runs every CUE_MOVE substep. When
  isStateTimerEngaged() (mStateTimer>0, field @ TItem+0x104), it does:
    0x801BE878  lwz  r3, 0x104(r29)      # load mStateTimer
    0x801BE87C  addi r0, r3, -1          # --mStateTimer
    0x801BE880  stw  r0, 0x104(r29)      # <-- HOOK ANCHOR (replaced by C2)
    0x801BE884  b    0x801BE908          # (handler branches back here)
  mStateTimer seeded from unk14C=480 (TItem::initMapObj). At 120fps the substep
  runs 4x/frame -> 480-tick lifetime drains in ~1 real sec instead of ~16.

AT THE HOOK ANCHOR (0x801BE880), entry register state:
  r0  = newTimer (oldTimer-1)          -- DEAD after this site (rewritten 0x801BE908)
  r3  = oldTimer                       -- DEAD after this site (rewritten 0x801BE924)
  r29 = this (TCoin*)                  -- LIVE (used throughout TCoin::perform)
  r4  = DO NOT USE (clobbering crashes; see HANDOFF)
  r5  = caller-saved, dead (moved to r31 at 0x801BE7DC) -- SAFE
  r6..r12 = unused in this function -- SAFE
  r28,r30 = live locals (hold cue/state) -- DO NOT USE
  r31 = live (graphics arg) -- DO NOT USE

THE CRITICAL LESSON (root cause of v1/v2/v3a crashes):
  The Gecko C2 handler overwrites the LAST word of the block with its branch-back.
  Every OTHER 00000000 word in the block is a REAL CAVE WORD and gets EXECUTED if
  execution falls into it. 0x00000000 is not a valid PPC instruction ->
  "IntCPU: Unknown instruction 00000000 at PC = 800026xx".
  => EVERY code path through the block MUST end with an explicit branch (b) to the
     final pad word. NEVER fall through into a 00000000. See build_v4().
"""
import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

# ---- PPC encoders (field-correct) ----
def lis(rD, imm):    return (15<<26)|(rD<<21)|(imm & 0xFFFF)
def lwz(rD, d, rA):  return (32<<26)|(rD<<21)|(rA<<16)|(d & 0xFFFF)
def stw(rS, d, rA):  return (36<<26)|(rS<<21)|(rA<<16)|(d & 0xFFFF)
def cmplwi(rA, imm): return (10<<26)|(0<<21)|(rA<<16)|(imm & 0xFFFF)   # cr0
def cmpwi(rA, imm):  return (11<<26)|(0<<21)|(rA<<16)|(imm & 0xFFFF)   # cr0 signed
def cmpw(rA, rB):    return (31<<26)|(0<<23)|(0<<21)|(rA<<16)|(rB<<11) # cmp crf0,0,rA,rB
def andi_(rS, rA, i):return (28<<26)|(rS<<21)|(rA<<16)|(i & 0xFFFF)    # andi. rA,rS,imm
def beq(o): return 0x41820000 | (o & 0xFFFC)
def bne(o): return 0x40820000 | (o & 0xFFFC)
def b(o):   return 0x48000000 | (o & 0xFFFC)
NOP = 0x60000000


def _resolve(ins):
    """Fill in branch displacements from labels. Returns list of words.

    Two-pass: (1) record label -> index, (2) emit words, resolving branches.
    Note: labels themselves do NOT occupy a word in the output (they're positions
    in the *instruction stream*, and a branch-to-label targets the instruction
    that follows the label)."""
    # First, compute the OUTPUT index of each label = number of real/branch insns
    # emitted before it (labels contribute nothing to output).
    out_idx_of_label = {}
    n = 0
    for row in ins:
        if row[1] == "LABEL":
            out_idx_of_label[row[2]] = n
        else:
            n += 1
    # Second pass: emit, resolving branches by output index.
    out = []
    i_out = 0
    for row in ins:
        if row[1] == "LABEL":
            continue
        if row[0] is None:
            kind, target = row[1], row[2]
            disp = (out_idx_of_label[target] - i_out) * 4
            if kind == "beq": out.append(beq(disp))
            elif kind == "bne": out.append(bne(disp))
            elif kind == "b": out.append(b(disp))
            else: raise ValueError(kind)
        else:
            out.append(row[0])
        i_out += 1
    return out


def emit_block(words, title):
    """Pretty-print + emit as Gecko C2 lines. Ensures even word count + trailing 0."""
    if len(words) % 2: words.append(0)
    print(f"\n=== {title} ===")
    for i, w in enumerate(words):
        for ins in md.disasm(struct.pack(">I", w), 0):
            note = " <- PAD (handler overwrites with branch-back)" if i == len(words)-1 else ""
            print(f"  {i:2} +{i*4:02X} {w:08X}  {ins.mnemonic} {ins.op_str}{note}")
    assert words[-1] == 0, "last word must be 00000000 (branch-back pad)"
    # INVARIANT (the v1..v4 crash bug): the ONLY 00000000 in the block must be
    # the final word (the handler overwrites it with the branch-back). Any other
    # 00000000 is a live cave word; falling into / branching to it => crash
    # ("Unknown instruction 00000000"). Use 0x60000000 (nop) for real padding.
    bad = [i for i, w in enumerate(words[:-1]) if w == 0]
    assert not bad, (f"DEAD 00000000 word(s) at index {bad} — every path must "
                     f"converge on the LAST word (branch-back). Use nop (60000000) "
                     f"for interior padding, and branch to the final word only.")
    print(f"\nGecko C2 (install via gecko.py add --title '<title>' --code ...):\n"
          f"C21BE880 {len(words)//2:08X}")
    for i in range(0, len(words), 2):
        print(f"{words[i]:08X} {words[i+1]:08X}")


def _emit(ins):
    """Resolve + enforce the layout invariant (even words, single trailing 0).

    The KEY fix vs. the old build_v4: the caller's LAST real instruction must
    fall through into the single trailing branch-back word — never branch to a
    separate 00000000. If padding is needed for an even word count, insert a nop
    (60000000) BEFORE the branch-back word, not a second 00000000."""
    ins = list(ins)
    ins.append([None, "LABEL", "__pad__"])
    ins.append([0x00000000, "insn"])          # the single branch-back word (last)
    words = _resolve(ins)
    if len(words) % 2:
        # need one more word for an even count; the branch-back word must stay
        # LAST, so insert a harmless nop just before it (never a 2nd 00000000).
        words = words[:-1] + [NOP, 0x00000000]
    return words


def build_v4():
    """v4 (CORRECTED) — ungated parity, last store falls through to branch-back.

    The old v4 crashed: both stores did `b pad` where `pad` was a 00000000 that
    was NOT the handler's branch-back word (the handler overwrites the LAST word;
    `pad` pointed one word earlier). Fix: the odd-substep store is placed LAST so
    it FALLS THROUGH into the branch-back word (exactly like the working no-op
    probe). Only the even/decrement path needs an explicit `b end`.

      lwz    r5, gpMarDirector(r13)
      cmplwi r5, 0
      beq    STORE_DEC          # no director -> normal decrement
      lwz    r5, 0x5C(r5)       # unk5C substep counter
      andi.  r0, r5, 1
      bne    HOLD               # odd substep -> hold (no decrement)
    STORE_DEC:
      stw    r0, 0x104(r29)     # even/no-director: real --mStateTimer
      b      END
    HOLD:
      stw    r3, 0x104(r29)     # hold old value, fall through to branch-back
    END: 00000000               # handler overwrites with branch-back -> 0x801BE884

    UNGATED: halves the decrement at ALL framerates. Correct at 120fps; at stock
    30fps it makes coins last 2x too long. Use build_v5_gated() to ship.
    """
    ins = []
    def e(w): ins.append([w, "insn"])
    def br(kind, target): ins.append([None, kind, target])
    def L(name): ins.append([None, "LABEL", name])

    e(lwz(5, -0x6048, 13))            # lwz r5, gpMarDirector(r13)
    e(cmplwi(5, 0))
    br("beq", "STORE_DEC")
    e(lwz(5, 0x5C, 5))
    e(andi_(5, 5, 1))                 # andi. r5,r5,1  (test in r5 — r0/r3 MUST survive)
    br("bne", "HOLD")
    L("STORE_DEC")
    e(stw(0, 0x104, 29))              # ORIGINAL: stw r0,0x104(r29)  (r0=oldTimer-1)
    br("b", "__pad__")
    L("HOLD")
    e(stw(3, 0x104, 29))              # hold: stw r3,0x104(r29) -> falls into pad
    return _emit(ins)


def build_v5_gated(hold_1_of=4):
    """v5/v6 — the SHIPPABLE final: fps-global gate + rate-gate, correct layout.

    hold_1_of = N (power of 2): decrement on (N-1)/N substeps, hold on 1/N.
      N=2 -> keep 1/2 (the first calibration try; gave 30s).
      N=4 -> keep 3/4 (measured target: 20s stock). <-- default / shipped.


    Adds a self-disabling gate on top of the v4 parity so it is a no-op at any
    framerate except 120fps (where the global 0x804167B8 == 2.0f). Same gate
    idiom as 120v15-timer-fix.txt. Uses r6/r7 for the gate (both dead/safe at
    this site); r4 must NOT be touched (clobbering it crashes — see HANDOFF).

      lis    r6, 0x8041
      lwz    r6, 0x67B8(r6)     # framerate global = float(FPS/60)
      lis    r7, 0x4000         # 2.0f
      cmpw   r6, r7
      bne    STORE_DEC          # not 120fps -> stock decrement (self-disable)
      lwz    r5, gpMarDirector(r13)
      cmplwi r5, 0
      beq    STORE_DEC          # no director -> stock decrement
      lwz    r5, 0x5C(r5)
      andi.  r0, r5, 1
      bne    HOLD               # odd substep -> hold
    STORE_DEC:
      stw    r0, 0x104(r29)
      b      END
    HOLD:
      stw    r3, 0x104(r29)     # falls through to branch-back
    END: 00000000
    """
    ins = []
    def e(w): ins.append([w, "insn"])
    def br(kind, target): ins.append([None, kind, target])
    def L(name): ins.append([None, "LABEL", name])

    e(lis(6, 0x8041))
    e(lwz(6, 0x67B8, 6))              # framerate global word
    e(lis(7, 0x4000))                 # 2.0f
    e(cmpw(6, 7))
    br("bne", "STORE_DEC")           # gate: not 2.0f -> stock behavior
    e(lwz(5, -0x6048, 13))           # gpMarDirector
    e(cmplwi(5, 0))
    br("beq", "STORE_DEC")
    e(lwz(5, 0x5C, 5))
    # Rate calibration (measured in-game): at 120fps the coin's perform substep
    # runs ~40/sec (not a clean 4x; the sim is CPU-bound ~1.33x here). ½-rate
    # (hold_1_of=2) gave 30s vs the 20s stock target, so use ¾-rate: hold on 1 of
    # every `hold_1_of` substeps => keep = (N-1)/N. N=4 -> keep 0.75 -> 20s.
    mask = hold_1_of - 1                          # N must be a power of 2
    e(andi_(5, 5, mask))             # andi. r5,r5,mask  (test in r5 — r0/r3 survive!)
    br("beq", "HOLD")                # (unk5C & mask)==0 -> hold 1 of N (skip --)
    L("STORE_DEC")
    e(stw(0, 0x104, 29))
    br("b", "__pad__")
    L("HOLD")
    e(stw(3, 0x104, 29))
    return _emit(ins)


def build_noop():
    """The no-op probe that PROVED the site is safe (just re-executes the store)."""
    return [stw(0, 0x104, 29), 0x00000000]


if __name__ == "__main__":
    print("v6 GATED (shippable: fps gate + 3/4-rate gate, calibrated to 20s):")
    emit_block(build_v5_gated(hold_1_of=4), "Blue coin timer fix v6 (120fps) [GMSE01]")
    print("\n" + "="*70)
    print("v4 ungated (minimal parity, for isolating the layout fix):")
    emit_block(build_v4(), "Blue coin timer fix v4 ungated [GMSE01]")
    print("\n" + "="*70)
    print("no-op probe (proves the C2 site is structurally safe):")
    emit_block(build_noop(), "no-op probe")
