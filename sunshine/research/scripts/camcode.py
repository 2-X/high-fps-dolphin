#!/usr/bin/env python3
"""Build the $Camera vertical-look extension Gecko code (USA GMSE01).

Mechanism (see HANDOFF notes / decomp src/Camera/cameragc.cpp):
  The C-stick vertical camera is a 0..1 ratio (CPolarSubCamera+0xA8) lerped
  between per-camera-kind XAngleMin(~5 deg)..XAngleMax(~55 deg). The floor
  clamp at ratio 0 is why you can barely look up. Distance/cushion/etc. lerp
  on the SAME ratio, so widening the ratio range or XAngleMin would warp
  zoom/framing. Instead:

  Hook B  rotateX_ByStickY_ @ 0x8002510C (stfs f0,0xA8(r31); f0 = UNclamped
          new ratio): bank the below-floor overflow into an extra-pitch
          accumulator E (angle units, cap ~60 deg), pin ratio at floor while
          E > 0, and drain E first when the stick pulls back down.
  Hook A  calcSlopeAngleX_ tail @ 0x80024D1C (sth r0,0(r30); r0 = final
          target pitch): subtract E before the game's own +-87 deg clamp.

  v2 adds flat-ground sky-gazing. The camera-ground revision
  (execGroundCheck_, keeps camera >= ground + 144/30) eats the downward swing
  on open ground. Compensate with the exact stolen height:
  Hook D  execGroundCheck_ @ 0x80020408 (stfs f1,0x84(r30): the revision
          store; f1 = raised y, f0 = intended y): when E > 0, record
          deficit = f1 - f0 in scratch. E == 0 -> stock behavior untouched.
  Hook C  calcPosAndAt_ @ 0x80024828 (bl execCameraInbetween; lookat copy at
          0x228(r1)): add deficit to lookat y, zero it (consumed per frame;
          straight-line from the ground check so never stale). The bl is
          re-emitted as lis/mtctr/bctrl because the C2 cave relocates the
          block (relative bl would retarget).

  Scratch block 0x800016F0 (free between OS low-mem and the Gecko handler at
  0x80001800), guarded by magic 'CMEX' so first run initializes:
    +0x00 E (f32)   +0x04 magic   +0x08 K=9106.0f (ratio->angle scale)
    +0x0C 0.05f drain cap   +0x10 fctiwz temp (8B)   +0x18 E cap (f32)
    +0x1C ground-revision deficit (f32, consumed each frame by hook C)
    +0x20 last camera mode (v4: bank zeroed on any mode change)

Usage: camcode.py [--cap DEG] > code.txt   (default cap 60 deg extra)
"""
import struct, sys

SCRATCH = 0x800016F0
MAGIC   = 0x434D4558  # 'CMEX'
K       = 9106.0      # default XAngleMax-XAngleMin range: ratio->s16-angle
DRAIN   = 0.05        # max ratio-units of E drained per frame (smooth unwind)
CAP_DEG = 60.0
for i, a in enumerate(sys.argv):
    if a == "--cap":
        CAP_DEG = float(sys.argv[i + 1])
CAP = CAP_DEG / 180.0 * 32768.0  # s16 angle units

def f32(x):
    return struct.unpack(">I", struct.pack(">f", x))[0]

def hi(w): return (w >> 16) & 0xFFFF
def lo(w): return w & 0xFFFF

# ---- encoders ----
def lis(d, imm):        return 0x3C000000 | d << 21 | (imm & 0xFFFF)
def ori(a, s, imm):     return 0x60000000 | s << 21 | a << 16 | (imm & 0xFFFF)
def li(d, imm):         return 0x38000000 | d << 21 | (imm & 0xFFFF)
def addi(d, a, imm):    return 0x38000000 | d << 21 | a << 16 | (imm & 0xFFFF)
def lwz(d, off, a):     return 0x80000000 | d << 21 | a << 16 | (off & 0xFFFF)
def lhz(d, off, a):     return 0xA0000000 | d << 21 | a << 16 | (off & 0xFFFF)
def stw(s, off, a):     return 0x90000000 | s << 21 | a << 16 | (off & 0xFFFF)
def sth(s, off, a):     return 0xB0000000 | s << 21 | a << 16 | (off & 0xFFFF)
def lfs(d, off, a):     return 0xC0000000 | d << 21 | a << 16 | (off & 0xFFFF)
def stfs(s, off, a):    return 0xD0000000 | s << 21 | a << 16 | (off & 0xFFFF)
def stfd(s, off, a):    return 0xD8000000 | s << 21 | a << 16 | (off & 0xFFFF)
def cmpw(a, b):         return 0x7C000000 | a << 16 | b << 11
def subf(d, a, b):      return 0x7C000050 | d << 21 | a << 16 | b << 11
def fsubs(d, a, b):     return 0xEC000028 | d << 21 | a << 16 | b << 11
def fnmsubs(d, a, c, b):return 0xEC00003C | d << 21 | a << 16 | b << 11 | c << 6
def fmr(d, b):          return 0xFC000090 | d << 21 | b << 11
def fcmpu(a, b):        return 0xFC000000 | a << 16 | b << 11
def fctiwz(d, b):       return 0xFC00001E | d << 21 | b << 11
def fadds(d, a, b):     return 0xEC00002A | d << 21 | a << 16 | b << 11
def mtctr(s):           return 0x7C0903A6 | s << 21
BCTRL = 0x4E800421
BCTR  = 0x4E800420
def bgt(off):           return 0x41810000 | (off & 0xFFFC)
def beq(off):           return 0x41820000 | (off & 0xFFFC)
def bne(off):           return 0x40820000 | (off & 0xFFFC)
def bge(off):           return 0x40800000 | (off & 0xFFFC)
def ble(off):           return 0x40810000 | (off & 0xFFFC)
def b(off):             return 0x48000000 | (off & 0x3FFFFFC)

def branches(seq):
    """resolve ('beq','label') tuples against ('label:',) markers"""
    labels, out = {}, []
    pc = 0
    for it in seq:
        if isinstance(it, str):
            labels[it] = pc
        else:
            out.append(it); pc += 1
    ins = []
    for i, it in enumerate(out):
        if isinstance(it, tuple):
            fn, lab = it
            ins.append(fn((labels[lab] - i) * 4))
        else:
            ins.append(it)
    return ins

KW, DW, CW = f32(K), f32(DRAIN), f32(CAP)

GP_CAMERA = 0x8040D0A8   # CPolarSubCamera* — the MAIN camera. A second camera
# object also runs these functions every frame (seen live: its calcSlopeAngleX_
# alternates modes 5/18/45 with the main cam's), which made v3/v4's cross-frame
# state checks zero the bank every frame. Every hook is gated: this==gpCamera.

def guard(this_reg, tmp, skiplabel):
    # lis tmp,0x8041 ; lwz tmp,-0x2F58(tmp) ; cmpw tmp,this ; bne skip
    return [lis(tmp, 0x8041), lwz(tmp, 0xD0A8, tmp), cmpw(tmp, this_reg), (bne, skiplabel)]

# ---- Hook B: rotateX_ByStickY_ @ 0x8002510C ----
# live: f0 = unclamped new ratio, r31 = this, r3 = this (must survive)
hookB = branches([
    *guard(31, 5, "done"),
    # v9: skip banking in modes that call rotateX_ByStickY_ from MOVEMENT
    # stick (not C-stick) and discard the polar pitch downstream — else the
    # bank fills invisibly and pushing forward has to drain the surplus:
    #   JET_COASTER (0x2E) — TCameraJetCoaster::calcRotation feeds mCompSPos[5]
    #     into rotateX_ByStickY_ (CameraJetCoaster.cpp:114) then overrides
    #     the polar result with its rail pitch (Mecha Bowser fight regression,
    #     user-reported)
    #   SLIDER (0x2A) — same rail-camera pattern
    # v4's mode-change zeroing (hook A) clears any pre-existing E on entry.
    # v10: gate on CALLER (return address at 0x2C(r1), saved by
    # rotateX_ByStickY_'s prologue mflr+stw 4(r1) + stwu r1,-0x28(r1)).
    # Only bank when called from CameraNormal (0x8002A1E4) or ctrlLButton
    # (0x800293B8); skip TCameraJetCoaster caller (return 0x80031108) which
    # feeds MOVEMENT stick Y and discards the polar pitch. Mode-based gate
    # in v9 missed because the JetCoaster call may pass a non-CPolarSubCamera
    # this, so r31+0x50 doesn't reliably index mMode.
    lwz(5, 0x2C, 1),                     # return address of the caller
    lis(6, 0x8003), ori(6, 6, 0x1108),   # JetCoaster call site return
    cmpw(5, 6), (beq, "done"),
    lis(5, 0x8000), ori(5, 5, SCRATCH & 0xFFFF),
    lwz(6, 4, 5),
    lis(7, hi(MAGIC)), ori(7, 7, lo(MAGIC)),
    cmpw(6, 7), (beq, "ready"),
    li(6, 0),            stw(6, 0x00, 5),      # E = 0.0f
    stw(6, 0x1C, 5),                           # deficit = 0.0f
    stw(6, 0x20, 5),                           # last-mode = 0
    stw(6, 0x28, 5), stw(6, 0x2C, 5), stw(6, 0x30, 5),   # dbg: dCnt dLast cCnt
    stw(6, 0x34, 5), stw(6, 0x38, 5), stw(6, 0x3C, 5),   # dbg: cLast aCnt eCnt
    lis(6, hi(KW)),  ori(6, 6, lo(KW)),  stw(6, 0x08, 5),
    lis(6, hi(DW)),  ori(6, 6, lo(DW)),  stw(6, 0x0C, 5),
    lis(6, hi(CW)),  ori(6, 6, lo(CW)),  stw(6, 0x18, 5),
    stw(7, 0x04, 5),                           # magic last
    "ready",
    lfs(2, 0x00, 5),      # f2 = E
    lfs(3, 0x08, 5),      # f3 = K
    fsubs(4, 2, 2),       # f4 = 0.0
    fcmpu(0, 4), (bge, "notbelow"),
    # pushed below floor: E += (-ratio)*K, pin ratio, cap E
    fnmsubs(2, 0, 3, 2),  # f2 = f2 - f0*f3
    fmr(0, 4),
    lfs(5, 0x18, 5),      # cap
    fcmpu(2, 5), (ble, "store"),
    fmr(2, 5), (b, "store"),
    "notbelow",
    fcmpu(2, 4), (ble, "done"),   # E <= 0: stock behavior
    fcmpu(0, 4), (ble, "done"),   # no upward ratio motion: hold
    # stick easing back: drain E first (rate-limited), keep ratio pinned
    lfs(5, 0x0C, 5),
    fcmpu(0, 5), (ble, "drain"),
    fmr(0, 5),
    "drain",
    fnmsubs(2, 0, 3, 2),  # f2 = f2 - f0*f3  (f0>0 -> decreases)
    fmr(0, 4),
    fcmpu(2, 4), (bge, "store"),
    fmr(2, 4),
    "store",
    stfs(2, 0x00, 5),
    "done",
    stfs(0, 0xA8, 31),    # original instruction
])

# ---- Hook A: calcSlopeAngleX_ tail @ 0x80024D1C ----
# live: r0 = final pitch, r30 = out ptr, r29 = this; r3-r5, f0-f3 free
# v3: while E > 0 the stick path (hook B) keeps the ratio pinned at exactly 0,
# so ratio > 0.05 here means the GAME wrote it (dive, wall-check unk28=unk30,
# mode recompute...). The view visibly snaps to stock then; zero E (and the
# deficit) so stick-up re-banks immediately instead of sitting saturated.
# v4: the ratio threshold missed the dive case — mode changes (e.g.
# CAMERA_MODE_DIVING) recompute the ratio to a small positive value below
# 0.05, leaving E saturated but unapplied. Track mMode (+0x50) in scratch
# +0x20 instead: ANY camera-mode change zeroes the bank (matches the native
# view snap on every game-driven transition). Ratio check kept for
# same-mode external writes (wall-check unk28=unk30).
hookA = branches([
    *guard(29, 3, "orig"),
    lis(3, 0x8000), ori(3, 3, SCRATCH & 0xFFFF),
    lwz(4, 4, 3),
    lis(5, hi(MAGIC)), ori(5, 5, lo(MAGIC)),
    cmpw(4, 5), (bne, "orig"),
    lwz(4, 0x50, 29),     # mMode
    lwz(5, 0x20, 3),      # last seen mode
    cmpw(4, 5), (beq, "samemode"),
    stw(4, 0x20, 3),      # mode changed: remember it,
    li(4, 0),             # snap the bank to match the native view snap
    stw(4, 0x00, 3),
    stw(4, 0x1C, 3), (b, "orig"),
    "samemode",
    lfs(0, 0x00, 3),      # E
    fsubs(1, 0, 0),       # 0.0
    fcmpu(0, 1), (ble, "orig"),   # E<=0: stock
    lfs(2, 0xA8, 29),     # current X-rot ratio
    lfs(3, 0x0C, 3),      # 0.05 threshold (= drain const)
    fcmpu(2, 3), (ble, "apply"),
    li(4, 0),             # externally bumped: snap the bank to match the view
    stw(4, 0x00, 3),
    stw(4, 0x1C, 3), (b, "orig"),
    "apply",
    fctiwz(1, 0),
    stfd(1, 0x10, 3),
    lwz(4, 0x14, 3),
    subf(0, 4, 0),        # pitch -= E
    # v6: while extended, force CAMERA_FLAG_UNK100 (u16 unk64 @+0x64, cleared
    # by the game each frame before this hook). Suppresses the cushion
    # "moment definite" hold in calcPosAndAt_, which otherwise reuses the
    # PREVIOUS camera position (discarding the extended pitch) whenever the
    # camera has settled close with ratio pinned at 0 and no yaw input —
    # the post-land-dive stuck state (hysteretic until dist grows again).
    lhz(4, 0x64, 29),
    ori(4, 4, 0x100),
    sth(4, 0x64, 29),
    # v8: clear the ground-check LOCKOUT (unk278, set to >=120 frames when
    # the camera gets too high above the target — a land dive trips it).
    # While it's nonzero isNeedGroundCheck_ returns false -> no revision ->
    # no deficit -> no lookat raise = the stuck flat view (proven live:
    # u18y extended to -55 while atY stayed flat). Only while E is applied.
    li(4, 0),
    sth(4, 0x278, 29),
    lwz(4, 0x38, 3), addi(4, 4, 1), stw(4, 0x38, 3),   # dbg aCnt
    "orig",
    sth(0, 0, 30),        # original instruction
])

# ---- Hook D: execGroundCheck_ revision store @ 0x80020408 ----
# live: f1 = raised y (groundY+groundOff), f0 = intended y, r30 = this
# free: r3, r4, r5, f2, f3, cr0 (r3 dead until mr r3,r31 in epilogue)
hookD = branches([
    *guard(30, 3, "orig"),
    lis(3, 0x8000), ori(3, 3, SCRATCH & 0xFFFF),
    lwz(4, 4, 3),
    lis(5, hi(MAGIC)), ori(5, 5, lo(MAGIC)),
    cmpw(4, 5), (bne, "orig"),
    lfs(2, 0x00, 3),      # E
    fsubs(3, 2, 2),       # 0.0
    fcmpu(2, 3), (ble, "orig"),   # E<=0: stock
    lwz(4, 0x28, 3), addi(4, 4, 1), stw(4, 0x28, 3),   # dbg dCnt = skip count
    (b, "skip"),          # E>0: BYPASS the ground-raise store entirely
    "orig",
    stfs(1, 0x84, 30),    # original instruction
    "skip",
])

# ---- Hook C: calcPosAndAt_ bl execCameraInbetween @ 0x80024828 ----
# live args: r3=mInbetween r4=&pos r5=&at-copy(r1+0x224) r6=&marioPos
# free: r0, r7-r12, f2, f3; LR/CTR clobbered by the call anyway
hookC = branches([
    *guard(31, 7, "call"),
    lis(7, 0x8000), ori(7, 7, SCRATCH & 0xFFFF),
    lwz(8, 4, 7),
    lis(9, hi(MAGIC)), ori(9, 9, lo(MAGIC)),
    cmpw(8, 9), (bne, "call"),
    lfs(2, 0x1C, 7),      # deficit
    lfs(3, 0x228, 1),     # at.y on stack
    fadds(3, 3, 2),
    stfs(3, 0x228, 1),
    stfs(2, 0x34, 7),                                  # dbg cLast (persist)
    lwz(8, 0x30, 7), addi(8, 8, 1), stw(8, 0x30, 7),   # dbg cCnt
    li(8, 0),
    stw(8, 0x1C, 7),      # consume
    "call",
    lis(7, 0x8002), ori(7, 7, 0x682C),
    mtctr(7), BCTRL,      # original bl execCameraInbetween, cave-safe
])

# ---- Hook E: cushion-hold branch @ 0x80024358 in calcPosAndAt_ ----
# Replaces `ble 0x80024384` after fcmpo(cushDist, cushion*dist). The hold path
# rebuilds the camera from the PREVIOUS polar coords (nDist/nVA), discarding
# the extended pitch (v6's flag only disabled the deeper useMid variant).
# While E > 0 on the main camera, force the FREE path (fall through to the
# game's own flag-set + newPos store). The hold target is reached with an
# absolute mtctr/bctr since the cave relocates the block. cr0/f1/f2/r5-r7
# are dead here (verified against 0x8002435C..0x800243A8).
hookE = branches([
    (bgt, "free"),            # stock free-path condition
    lis(5, 0x8041), lwz(5, 0xD0A8, 5),
    cmpw(5, 31), (bne, "hold"),
    lis(5, 0x8000), ori(5, 5, SCRATCH & 0xFFFF),
    lwz(6, 4, 5),
    lis(7, hi(MAGIC)), ori(7, 7, lo(MAGIC)),
    cmpw(6, 7), (bne, "hold"),
    lfs(1, 0x00, 5),          # E
    fsubs(2, 1, 1),
    fcmpu(1, 2), (ble, "hold"),
    lwz(6, 0x3C, 5), addi(6, 6, 1), stw(6, 0x3C, 5),   # dbg eCnt
    (b, "free"),              # E > 0: take the free path
    "hold",
    lis(5, 0x8002), ori(5, 5, 0x4384),
    mtctr(5), BCTR,           # original ble target 0x80024384
    "free",                   # fall through -> handler branch-back (0x8002435C)
])

def c2(addr, ins):
    body = list(ins)
    if len(body) % 2 == 0:
        body += [0x60000000, 0x00000000]
    else:
        body += [0x00000000]
    lines = [f"C2{addr & 0x01FFFFFF:06X} {len(body)//2:08X}"]
    for i in range(0, len(body), 2):
        lines.append(f"{body[i]:08X} {body[i+1]:08X}")
    return lines

out = []
out.append(f"$Camera look-up extension v11 (sky-gaze on flat ground, +{CAP_DEG:.0f}deg)")
out += c2(0x8002510C, hookB)
out += c2(0x80024D1C, hookA)
out += c2(0x80020408, hookD)
out += c2(0x80024828, hookC)
out += c2(0x80024358, hookE)
print("\n".join(out))

# ---- self-check: capstone round-trip ----
if "--check" in sys.argv:
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    for name, ins, base_ in (("hookB", hookB, 0x8002510C), ("hookA", hookA, 0x80024D1C), ("hookD", hookD, 0x80020408), ("hookC", hookC, 0x80024828), ("hookE", hookE, 0x80024358)):
        print(f"\n# {name}:", file=sys.stderr)
        blob = b"".join(struct.pack(">I", w) for w in ins)
        n = 0
        for d in md.disasm(blob, 0):
            print(f"#   {d.address//4:3d}: {d.mnemonic:9s} {d.op_str}", file=sys.stderr)
            n += 1
        assert n == len(ins), f"{name}: capstone decoded {n}/{len(ins)} instructions"
