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
