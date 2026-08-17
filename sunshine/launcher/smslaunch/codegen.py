"""Generate the two kinds of code the launcher can build on demand:

  * FPS high-fps bundle  — delegated to fpspatch.py (`<fps> --bare`).
  * FOV `$FOV N` Gecko    — templated from the known-good $FOV 60 code by
                            swapping the two `lis` immediates that carry the
                            field-of-view float (upper16 of IEEE-754 float(N)).

Both are pure: they return (title, code_text). Callers decide whether the code
already exists (reuse) and how to write it into the INI.
"""
from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

from . import config as C
from .inieditor import Ini

# ---- FOV template ----------------------------------------------------------
# This is the shipped, working `$FOV 60` code (two C2 hooks: C_MTXPerspective
# allow-list @0x8034A404 and the clip-check @0x802260CC). The field-of-view
# angle appears twice, once per C2 hook, as the immediate of a `lis`:
#   hook 1 (@0x8034A404):  3D40 4270  -> lis r10, 0x4270   (0x42700000 == 60.0f)
#   hook 2 (@0x802260CC):  3D80 4270  -> lis r12, 0x4270
# Verified byte-for-byte against the live shipped $FOV 60. The `3D80 4260` (56.0)
# and `3D80 4220` (40.0) words nearby are FIXED clamp thresholds and must NOT
# move. Generating $FOV N swaps the 0x4270 immediate in BOTH lis words for
# upper16(float(N)), keeping the two registers.
_FOV60 = """\
C234A404 00000011
7D8802A6 3D6C7FFE
2C0B3230 41820064
2C0B5A08 4182005C
3D6C7FFD 2C0B2D90
41820050 2C0B308C
41820048 3D6C7FE7
2C0B4014 4182003C
3D6C7FDD 2C0BBAA0
41820030 3D6C7FD1
2C0B7260 4182000C
2C0B76A0 40820028
D021FFF8 8161FFF8
556B843E 396BBDE0
280B003F 41810010
3D404270 9141FFF8
C021FFF8 7C0802A6
60000000 00000000
C22260CC 00000008
7C0802A6 3D804220
9181FFF8 C001FFF8
FC010000 41800024
3D804260 9181FFF8
C001FFF8 FC010000
40800010 3D804270
9181FFF8 C021FFF8
60000000 00000000"""

_FOV_MIN, _FOV_MAX = 40, 110


def _fov_upper16(fov: int) -> int:
    u = struct.unpack(">I", struct.pack(">f", float(fov)))[0]
    if u & 0xFFFF:
        raise ValueError(f"FOV {fov}: float has nonzero low16 (0x{u:08X}); "
                         "not representable by the lis-only template")
    return (u >> 16) & 0xFFFF


def gen_fov(fov: int) -> tuple[str, str]:
    if not (_FOV_MIN <= fov <= _FOV_MAX):
        raise ValueError(f"FOV {fov} out of supported range {_FOV_MIN}-{_FOV_MAX}")
    half = f"{_fov_upper16(fov):04X}"
    # exactly one of each lis-word must be present, or the template has drifted
    if _FOV60.count("3D404270") != 1 or _FOV60.count("3D804270") != 1:
        raise AssertionError("FOV template drift: expected one 3D40/one 3D80 token")
    code = (_FOV60.replace("3D404270", f"3D40{half}")
                  .replace("3D804270", f"3D80{half}"))
    return C.FOV_TITLE.format(fov=fov), code


# ---- FOV, BSE variant ------------------------------------------------------
# Under BSMSO the generic template's C_MTXPerspective caller allow-list (LR
# compares tuned for the stock disc) misses some projection consumers — the
# heat-haze shimmer pass draws at a mismatched FOV. The BSE variant instead
# stores the fovy at its source: the mProjectionFovy store @0x80023218
# (templated from the hand-verified `$FOV 60 BSE (mProjectionFovy store)`).
#   3D60 4270 -> lis r11, upper16(float(fov));  917D0048 stw r11,0x48(r29);
#   C03D0048  lfs f1,0x48(r29)  (reload so the caller uses the new value).
_FOV_BSE_60 = """\
C2023218 00000002
3D604270 917D0048
C03D0048 00000000"""


# ---- Menu key-repeat, BSE variant ------------------------------------------
# TMarioGamePad::reset (USA 0x802A897C) sets the d-pad repeat delay/interval
# as TICK COUNTS (10/3, sized for a 30Hz pad ticker) at the single
# JUTGamePad::setButtonRepeat call. Under BSE the ticker runs at the full
# render rate, so menus scroll FPS/30x too fast. We hook the `addi r4,r4,0xf`
# right before the call (0x802A89C8), where r5=delay/r6=interval are final,
# and overwrite them with counts scaled for the launch FPS. STATIC on purpose:
# a runtime guard on the framerate global fails here because reset() runs at
# boot before the external FPS poke lands (see research/codes/
# menu-repeat-bse-v1.txt for the full RE + the v1 post-mortem).
def gen_menu_repeat_bse(fps: int) -> tuple[str, str]:
    if fps % 30 == 0:
        delay, interval = 10 * fps // 30, 3 * fps // 30
    else:
        delay, interval = round(10 * fps / 30), round(3 * fps / 30)
    if not (0 < delay < 0x8000 and 0 < interval < 0x8000):
        raise ValueError(f"menu repeat counts out of li range for fps {fps}")
    code = (f"C22A89C8 00000002\n"
            f"{0x38A00000 | delay:08X} {0x38C00000 | interval:08X}\n"   # li r5/r6
            f"3884000F 00000000")                                        # addi r4,r4,0xf
    return C.MENU_REPEAT_TITLE_BSE.format(fps=fps), code


def gen_fov_bse(fov: int) -> tuple[str, str]:
    if not (_FOV_MIN <= fov <= _FOV_MAX):
        raise ValueError(f"FOV {fov} out of supported range {_FOV_MIN}-{_FOV_MAX}")
    half = f"{_fov_upper16(fov):04X}"
    if _FOV_BSE_60.count("3D604270") != 1:
        raise AssertionError("BSE FOV template drift: expected one 3D60 token")
    code = _FOV_BSE_60.replace("3D604270", f"3D60{half}")
    return C.FOV_TITLE_BSE.format(fov=fov), code


# ---- Widescreen -----------------------------------------------------------
# The shipped gamemasterplc `$Widescreen` code. Its ONE aspect-ratio constant is
#   04412408 3FE38E39   ->  write 1.7777... (= 16/9) to the projection aspect.
# Everything else (800.0/700.0 writes, the C2 HUD hooks) is aspect-tolerant HUD/2D
# anchoring machinery. Generating a 16:10 variant swaps only that constant to
#   3FCCCCCD  (= 1.6 = 16/10).  Verified byte-for-byte against the live $Widescreen.
_WIDESCREEN_16_9 = """\
04416758 44480000
044123E8 442F0000
04416620 442F0000
04176AA4 C002B83C
0429B974 C002B83C
04176C40 C002B83C
04176FF4 C002B83C
04177198 C002B83C
04412408 3FE38E39
04416B74 3F9A7643
0429610C 380002EA
042960A0 3860FF96
C214EF74 00000002
3B20FFA9 93380004
931F0140 00000000
C214EE24 00000002
3B20FFA9 93380004
931F0108 00000000
C214F09C 00000002
3860FFA9 90780004
931F0160 00000000
C214F308 00000002
3BA00251 93B80004
931F02F8 00000000
C214F70C 00000002
3860FFA9 90780004
931F0400 00000000
C214F830 00000002
3860FFA9 90780004
931F042C 00000000
C214F93C 00000002
3860FFA9 90780004
931F0450 00000000
C214D8EC 00000002
38800251 9081056C
807F02A0 00000000
0414E7D4 3880023C
C22CB330 00000004
2C00019F 40820008
38000203 2C00018D
40820008 380001F1
901F0014 00000000
C2156004 00000004
809F0018 38A0EC78
90A40014 7CA500D0
90A4001C 38800000
60000000 00000000
C214F114 00000002
3BA00258 93B80004
931F01C4 00000000
C2363138 00000009
80ED8D08 800701E8
540C24B6 2C030000
41820030 7C032A14
7C006000 41820024
5580F87E 7C601850
1C630003 1CA50003
7C631670 54A5F0BE
7C630194 7C630214
60000000 00000000"""

# aspect-ratio constant per aspect key (the 04412408 write value)
WS_ASPECT_WORD = {"tv": "3FE38E39", "mac": "3FCCCCCD"}   # 16:9 / 16:10
WS_TITLE = {"tv": "Widescreen", "mac": "Widescreen 16:10"}


def gen_widescreen(aspect_key: str) -> tuple[str, str]:
    """Return (title, code) for the widescreen Gecko at this aspect. 16:9 is the
    shipped `$Widescreen`; 16:10 swaps only the aspect constant."""
    if _WIDESCREEN_16_9.count("04412408 3FE38E39") != 1:
        raise AssertionError("Widescreen template drift: aspect word not unique")
    word = WS_ASPECT_WORD[aspect_key]
    code = _WIDESCREEN_16_9.replace("04412408 3FE38E39", f"04412408 {word}")
    return WS_TITLE[aspect_key], code


def existing_widescreen_titles(ini: Ini) -> list[str]:
    return [t for t in ini.titles() if t in WS_TITLE.values()]


# ---- World-aspect override (the REAL 3D projection aspect) -------------------
# The classic `$Widescreen` code above does NOT widen the 3D world — every one of
# its writes is 2D/HUD/ortho (800/700/-100) or the shine-select MENU aspect
# (0x80412408, read only @0x80176E58). The 3D world's widescreen normally comes
# from *Dolphin's* built-in Widescreen Hack, which is hardwired to 16:9 and
# ignores the custom display aspect — so a 16:10 display gets a 16:9 world
# stretched vertically (thin/tall). See [[sunshine-widescreen-2d-fix]].
#
# To render the world at a TRUE arbitrary aspect we drive it from a Gecko instead
# of the hack (and turn the hack off — see launcher). The main-camera projection
# is built by C_MTXPerspective @0x8034A404; its aspect arg (f2) is saved to the
# non-volatile f29 at 0x8034A424 and consumed once at 0x8034A454
#   fdivs f1,f4,f29   -> proj[0][0] = cot(fov/2)/aspect   (DOL-verified)
# so overriding f29 for exactly the world callers sets the world aspect. We hook
# 0x8034A424 (the `fmr f29,f2`) and, for the SAME caller allow-list the $FOV code
# already validates (LR compared against the world-camera return addresses
# 0x80023230/0x80025A08/0x80032D90/0x8003308C/0x80194014/0x8022BAA0/0x802F7260/
# 0x802F76A0), load our aspect into f29; non-matching callers keep `fmr f29,f2`.
# NTSC-U (GMSE01) only. Self-verified branch layout — see tests/build note below.
#
# f2 arg is dead after 0x8034A424 (only f29 is read downstream), so f29 is the
# complete and sufficient override point. LR is intact here: the prologue
# (0x8034A404..0x8034A424) contains no `bl`, and the $FOV C2 at the entry reads
# LR the same way and works — so both hooks see the caller's return address.
WORLD_ASPECT_WORD = {"tv": 0x3FE38E39, "mac": 0x3FCCCCCD}   # 16:9 / 16:10 as f32
WORLD_ASPECT_TITLE = {"tv": "World aspect 16:9", "mac": "World aspect 16:10"}


def gen_world_aspect(aspect_key: str) -> tuple[str, str]:
    """Return (title, code) for the C2 that forces the 3D world projection aspect
    for `aspect_key`. Pairs with Dolphin's Widescreen Hack turned OFF."""
    val = WORLD_ASPECT_WORD[aspect_key]
    hi, lo = (val >> 16) & 0xFFFF, val & 0xFFFF
    words = [
        0x7D8802A6, 0x3D6C7FFE,          # mflr r12 ; addis r11,r12,0x7FFE
        0x2C0B3230, 0x4182004C,          # cmpwi r11,0x3230 ; beq MATCHED
        0x2C0B5A08, 0x41820044,          # cmpwi 0x5A08     ; beq MATCHED
        0x3D6C7FFD, 0x2C0B2D90,          # addis 0x7FFD     ; cmpwi 0x2D90
        0x41820038, 0x2C0B308C,          # beq MATCHED      ; cmpwi 0x308C
        0x41820030, 0x3D6C7FE7,          # beq MATCHED      ; addis 0x7FE7
        0x2C0B4014, 0x41820024,          # cmpwi 0x4014     ; beq MATCHED
        0x3D6C7FDD, 0x2C0BBAA0,          # addis 0x7FDD     ; cmpwi 0xBAA0
        0x41820018, 0x3D6C7FD1,          # beq MATCHED      ; addis 0x7FD1
        0x2C0B7260, 0x4182000C,          # cmpwi 0x7260     ; beq MATCHED
        0x2C0B76A0, 0x40820018,          # cmpwi 0x76A0     ; bne NOTMATCHED
        (0x3D400000 | hi), (0x614A0000 | lo),   # MATCHED: lis r10,hi ; ori r10,r10,lo
        0x9141FFF8, 0xC3A1FFF8,          # stw r10,-8(r1) ; lfs f29,-8(r1)
        0x48000008, 0xFFA01090,          # b DONE ; NOTMATCHED: fmr f29,f2
        0x60000000, 0x00000000,          # nop ; <branch-back>
    ]
    _verify_world_aspect(words, val)
    lines = [f"C234A424 {len(words) // 2:08X}"]
    for i in range(0, len(words), 2):
        lines.append(f"{words[i]:08X} {words[i + 1]:08X}")
    return WORLD_ASPECT_TITLE[aspect_key], "\n".join(lines)


def _verify_world_aspect(words, val):
    """Fail loudly on any hand-assembly drift: branch targets + the f29 load."""
    MATCHED, NOTMATCHED, DONE = 22 * 4, 27 * 4, 28 * 4
    for i, w in enumerate(words):
        byte, op = i * 4, w >> 26
        if op == 16:                                   # bc (beq/bne)
            bo = (w >> 21) & 0x1F
            bd = (w & 0xFFFC) - 0x10000 if (w & 0x8000) else (w & 0xFFFC)
            tgt, want = byte + bd, (MATCHED if bo == 12 else NOTMATCHED)
            if tgt != want:
                raise AssertionError(f"world-aspect branch @word{i} -> {tgt:#x}, want {want:#x}")
        elif op == 18 and i == 26:                     # b DONE
            if byte + (w & 0xFFFC) != DONE:
                raise AssertionError("world-aspect b DONE mis-targeted")
    loaded = ((words[22] & 0xFFFF) << 16) | (words[23] & 0xFFFF)
    if loaded != val:
        raise AssertionError(f"world-aspect f29 load {loaded:#x} != {val:#x}")
    if words[27] != 0xFFA01090:
        raise AssertionError("world-aspect NOTMATCHED must reproduce `fmr f29,f2`")


def existing_world_aspect_titles(ini: Ini) -> list[str]:
    return [t for t in ini.titles() if t in WORLD_ASPECT_TITLE.values()]


# ---- Widescreen 2D fix (the four leftover 4:3 panes) -----------------------
# The classic gamemasterplc `$Widescreen` widens 3D projection, the J2D ortho
# graphs and the HUD panes, but leaves four things pillar-boxed at 4:3:
#   [A] the level-transition wipe "curtain" + its black side masks
#       (TConsoleStr::mDemoWipeExPanes / mDemoMaskExPanes),
#   [B] the shine-select menu's two side masks (TSelectMenu::mMask1/mMask2),
#   [C] the shine-select gradient-background quad's left/right X extents, and
#   [D] the shine-select root pane position.
# This replicates BetterSunshineEngine's src/patches/widescreen.cpp fixes for
# those four as Gecko C2 codes, parameterized by aspect. NTSC-U (GMSE01) only.
#
# All offsets/hook targets are verified against the vanilla main.dol disassembly
# (SDA r2 = 0x80416BA0). Struct offsets (from lib/sms_interface headers, each
# cross-checked against a vanilla load/store near the hook):
#   TExPane:      mPane +0x00, mRect(JUTRect) +0x04 (mX1 +0x04, mX2 +0x0C)
#   J2DPane:      mRect(JUTRect) +0x14 (mX1 +0x14, mX2 +0x1C),
#                 mChildrenList(JSUPtrList).mFirst +0xD0; JSUPtrLink.mItemPtr +0
#   TConsoleStr:  mDemoWipeExPanes[2] +0x28C, mDemoMaskExPanes[2] +0x294
#   TSelectMenu:  mMask1 +0x24, mMask2 +0x28
# Original hook instructions replaced (each a plain bl / lfs, dol-verified):
#   0x801723F0  bl loadAfter (0x802FA6F8)       -> [A] demo wipe/mask panes
#   0x80175F50  bl startMove__11TSelectMenuFv (0x8017443C) -> [B] menu masks
#   0x8017586C  lfs f4,-0x482C(r2) (grad left X=0.0)   -> [C] left X = coverL
#   0x80175884  lfs f1,-0x47DC(r2) (grad right X=600)  -> [C] right X = coverR
#   0x8013F430  bl J2DScreen::draw (0x802CFDA8)  -> [D] root pane position
# v2 calibration: cover blocks [A][B][C] span the classic code's effective
# ortho X range [-100, 700] plus a 20u overshoot margin (see _ws2d_blocks);
# only [D]'s content shift keeps BSE's per-aspect adjustX (16:9->98, 16:10->58).
# Gradient X floats are stashed at scratch 0x800016C0 (unused low arena; the
# fpspatch bundle's scratch starts at 0x800016E0, so no collision even if both
# codes are enabled).

_WS2D_SCRATCH = 0x800016C0
_WS2D_LOADAFTER = 0x802FA6F8
_WS2D_STARTMOVE = 0x8017443C
_WS2D_J2DDRAW   = 0x802CFDA8


def _ppc(mn, *a):
    """Minimal PPC encoder for the handful of forms this generator emits."""
    if mn == "lis":   rD, imm = a;        return (15 << 26) | (rD << 21) | (imm & 0xFFFF)
    if mn == "ori":   rA, rS, imm = a;    return (24 << 26) | (rS << 21) | (rA << 16) | (imm & 0xFFFF)
    if mn == "addi":  rD, rA, imm = a;    return (14 << 26) | (rD << 21) | (rA << 16) | (imm & 0xFFFF)
    if mn == "lwz":   rD, rA, d = a;      return (32 << 26) | (rD << 21) | (rA << 16) | (d & 0xFFFF)
    if mn == "stw":   rS, rA, d = a;      return (36 << 26) | (rS << 21) | (rA << 16) | (d & 0xFFFF)
    if mn == "lfs":   fD, rA, d = a;      return (48 << 26) | (fD << 21) | (rA << 16) | (d & 0xFFFF)
    if mn == "stfs":  fS, rA, d = a;      return (52 << 26) | (fS << 21) | (rA << 16) | (d & 0xFFFF)
    if mn == "mflr":  (rD,) = a;          return 0x7C0802A6 | (rD << 21)
    if mn == "mtlr":  (rS,) = a;          return 0x7C0803A6 | (rS << 21)
    if mn == "mtctr": (rS,) = a;          return 0x7C0903A6 | (rS << 21)
    if mn == "bctrl": return 0x4E800421
    raise ValueError(mn)


def _imm32(rD, val):
    return [_ppc("lis", rD, (val >> 16) & 0xFFFF), _ppc("ori", rD, rD, val & 0xFFFF)]


def _call(target):
    # save lr in r12, bctrl to absolute target, restore lr. r12 is volatile and
    # dead at every hook site here (verified: no post-call reader of r12).
    return [_ppc("mflr", 12)] + _imm32(0, target) + [_ppc("mtctr", 0),
                                                     _ppc("bctrl"), _ppc("mtlr", 12)]


def _c2_block(addr, words):
    words = list(words)
    if len(words) % 2 == 0:
        words.append(0x60000000)             # nop pad -> branch-back lands last
    words.append(0x00000000)                 # handler branch-back word
    out = [f"C2{addr & 0x01FFFFFF:06X} {len(words) // 2:08X}"]
    for i in range(0, len(words), 2):
        out.append(f"{words[i]:08X} {words[i + 1]:08X}")
    return "\n".join(out)


def _ws2d_blocks(aspect_key: str) -> str:
    # CALIBRATION FIX (v2): the classic gamemasterplc `$Widescreen` we ship is
    # NOT BSE's widescreen patch — it hardcodes an aspect-INDEPENDENT J2D ortho
    # X range and our v1 sized these cover-fixes to BSE's per-aspect range
    # instead, leaving gaps. DOL evidence (vanilla main.dol, r2=0x80416BA0):
    #   The five J2D ctor sites 0x80176AA4 / 0x8029B974 / 0x80176C40 /
    #   0x80176FF4 / 0x80177198 store an ortho box at fields
    #   +0x30(left) +0x34(top) +0x38(right) +0x3C(bottom).  Vanilla site A:
    #   {left=0, top=16, right=600, bottom=464} — the 4:3 ortho box.
    #   Classic `$Widescreen` redirects the +0x30 (left) load to r2-0x47C4
    #   (@0x804123DC = C2C80000 = -100.0) and overwrites the SDA slot feeding
    #   +0x38 (right): @0x804123E8 / @0x80416620 := 442F0000 = 700.0.
    #   -> effective visible ortho X = [-100, 700], width 800, ALL aspects.
    # So the shine-select gradient/masks must cover [-100, 700], not BSE's
    # per-aspect [-adjX, 600+adjX]. v1 gradient-left = -adjX (16:10 -> -58) sat
    # 42u short of -100  == (-58 - -100)/800 = 5.25% black bar on the LEFT
    # (matches screenshot); v1 relative masks reached 600+58=658, 42u short of
    # 700 == 5.25% gap on the RIGHT (matches). Fix: size cover geometry to the
    # classic ortho range plus an overshoot margin (overdraw is harmless for
    # solid cover panes / the full-bleed gradient; undershoot is a visible gap).
    # This is aspect-INDEPENDENT — both variant titles collapse to identical
    # constants (the launcher still keys the two titles on aspect).
    ORTHO_L, ORTHO_R = -100, 700                     # DOL-verified classic range
    MARGIN = 20                                       # overshoot both edges
    coverL = ORTHO_L - MARGIN                          # -120
    coverR = ORTHO_R + MARGIN                          #  720
    # block-D content shift stays BSE's per-aspect adjustX (see [D] note).
    adjX = int(({"tv": 796, "mac": 716}[aspect_key] / 600.0 - 1.0) * 300.0)  # 98 / 58
    left_bits = struct.unpack(">I", struct.pack(">f", float(coverL)))[0]
    right_bits = struct.unpack(">I", struct.pack(">f", float(coverR)))[0]

    # [A] demo wipe/mask panes @0x801723F0 (r31 = consoleStr, live post-call)
    def copy4(dr, sr):                              # J2DPane.mRect(0x14) -> TExPane.mRect(0x04)
        w = []
        for k in range(4):
            w += [_ppc("lwz", 0, sr, 0x14 + 4 * k), _ppc("stw", 0, dr, 0x04 + 4 * k)]
        return w
    a = _call(_WS2D_LOADAFTER)                       # loadAfter(consoleStr): r3=consoleStr at entry
    for i in range(2):                               # wipe[0], wipe[1]: set mX1 & mX2
        a += [_ppc("lwz", 10, 31, 0x28C + 4 * i), _ppc("lwz", 11, 10, 0)]
        a += _imm32(0, coverL & 0xFFFFFFFF) + [_ppc("stw", 0, 11, 0x14)]
        a += _imm32(0, coverR) + [_ppc("stw", 0, 11, 0x1C)]
        a += copy4(10, 11)
    a += [_ppc("lwz", 10, 31, 0x294), _ppc("lwz", 11, 10, 0)]     # mask[0]: only mX1
    a += _imm32(0, coverL & 0xFFFFFFFF) + [_ppc("stw", 0, 11, 0x14)] + copy4(10, 11)
    a += [_ppc("lwz", 10, 31, 0x298), _ppc("lwz", 11, 10, 0)]     # mask[1]: only mX2
    a += _imm32(0, coverR) + [_ppc("stw", 0, 11, 0x1C)] + copy4(10, 11)

    # [B] select-menu masks @0x80175F50 (r3 = menu; r30/r31 nonvol, untouched).
    # v1 expanded each mask relative to its native 4:3 rect (X1-=adjX/X2+=adjX)
    # -> reached only [-adjX, 600+adjX]. Set them to the absolute cover range
    # so both bands span the full classic ortho width.
    def do_mask(p):
        return [_ppc("addi", 9, 0, coverL), _ppc("stw", 9, p, 0x04),   # li r9,coverL; mX1
                _ppc("addi", 9, 0, coverR), _ppc("stw", 9, p, 0x0C),   # li r9,coverR; mX2
                _ppc("lwz", 12, p, 0x00),
                _ppc("lwz", 0, p, 0x04), _ppc("stw", 0, 12, 0x14),
                _ppc("lwz", 0, p, 0x08), _ppc("stw", 0, 12, 0x18),
                _ppc("lwz", 0, p, 0x0C), _ppc("stw", 0, 12, 0x1C),
                _ppc("lwz", 0, p, 0x10), _ppc("stw", 0, 12, 0x20)]
    b = [_ppc("ori", 11, 3, 0), _ppc("lwz", 10, 11, 0x24)] + do_mask(10)
    b += [_ppc("lwz", 10, 11, 0x28)] + do_mask(10)
    b += [_ppc("ori", 3, 11, 0)] + _call(_WS2D_STARTMOVE)

    # [C] gradient X extents: stash float in scratch, lfs into the target FPR
    sc_hi, sc_lo = (_WS2D_SCRATCH >> 16) & 0xFFFF, _WS2D_SCRATCH & 0xFFFF

    def load_fpr(fD, bits):
        head = [_ppc("lis", 0, (bits >> 16) & 0xFFFF)] if (bits & 0xFFFF) == 0 \
            else _imm32(0, bits)
        return head + [_ppc("lis", 11, sc_hi), _ppc("ori", 11, 11, sc_lo),
                       _ppc("stw", 0, 11, 0), _ppc("lfs", fD, 11, 0)]
    c_left = load_fpr(4, left_bits)                  # @0x8017586C  f4 = coverL (-120)
    c_right = load_fpr(1, right_bits)                # @0x80175884  f1 = coverR (720)

    # [D] root pane position @0x8013F430 (r3=screen,r4=x,r5=y,r6=ctx preserved).
    # Content-centering shift, NOT a cover extent — keep BSE's per-aspect
    # adjustX (BSE's patchLevelSelectPosition does move(adjustX,0)); the
    # screenshot shows content centered, so do not regress it on the ortho
    # range. Flagged for eye-test if content drifts off-center at 16:10.
    d = [_ppc("lwz", 11, 3, 0xD0), _ppc("lwz", 11, 11, 0),        # firstChild = mFirst->mItemPtr
         _ppc("lwz", 10, 11, 0x14), _ppc("addi", 10, 10, adjX), _ppc("stw", 10, 11, 0x14),
         _ppc("lwz", 10, 11, 0x1C), _ppc("addi", 10, 10, adjX), _ppc("stw", 10, 11, 0x1C)]
    d += _call(_WS2D_J2DDRAW)

    return "\n".join([
        _c2_block(0x801723F0, a),
        _c2_block(0x80175F50, b),
        _c2_block(0x8017586C, c_left),
        _c2_block(0x80175884, c_right),
        _c2_block(0x8013F430, d),
    ])


WS2D_TITLE = {"tv": "Widescreen 2D fix v2 16:9", "mac": "Widescreen 2D fix v2 16:10"}
# stale v1 titles the launcher must remove/ignore when it deploys v2.
WS2D_TITLE_STALE = ["Widescreen 2D fix 16:9", "Widescreen 2D fix 16:10"]


def gen_widescreen_2d(aspect_key: str) -> tuple[str, str]:
    """Return (title, code) for the widescreen 2D-leftovers fix at this aspect.
    Replicates BSE's demo-mask / select-menu / gradient / root-pane fixes."""
    return WS2D_TITLE[aspect_key], _ws2d_blocks(aspect_key)


def existing_widescreen_2d_titles(ini: Ini) -> list[str]:
    return [t for t in ini.titles() if t in WS2D_TITLE.values()]


def gen_fps_bundle(fps: int, python=sys.executable) -> tuple[str, str]:
    """Run fpspatch.py <fps> --bare and return (title, hex-pairs)."""
    if fps % 60 or fps // 60 < 2:
        raise ValueError(f"stock FPS must be a multiple of 60 >= 120 (got {fps})")
    # --no-forceopen matches the bundle title: story-locked M gates stay
    # closed (ForceOpen is the old v2-style workaround, not wanted here).
    out = subprocess.run(
        [python, str(C.FPSPATCH), str(fps), "--bare", "--no-forceopen"],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"fpspatch failed:\n{out.stderr or out.stdout}")
    return C.FPS_BUNDLE_TITLE.format(fps=fps), out.stdout.strip()


# ---- "which exist already" -------------------------------------------------
def existing_fps_bundles(ini: Ini) -> list[int]:
    out = []
    for t in ini.titles():
        m = C.FPS_BUNDLE_RE.match(t)
        if m:
            out.append(int(m.group(1)))
    return sorted(set(out))


def existing_fov_codes(ini: Ini) -> list[int]:
    out = []
    for t in ini.titles():
        m = C.FOV_RE.match(t)
        if m:
            out.append(int(m.group(1)))
    return sorted(set(out))


def existing_fov_bse_codes(ini: Ini) -> list[int]:
    out = []
    for t in ini.titles():
        m = C.FOV_BSE_RE.match(t)
        if m:
            out.append(int(m.group(1)))
    return sorted(set(out))
