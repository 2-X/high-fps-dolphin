"""Static configuration for the Super Mario Sunshine high-FPS launcher.

Everything the launcher needs to know about *where things live* and *what the
knobs mean* is here. No behaviour — just paths, enums, and the QOL catalog.

Two engines are supported, because on this Mac two GMSE01 discs exist:
  - "stock"  : plain pristine-GMSE01.iso + the fpspatch Gecko high-fps bundle.
               FPS is arbitrary (fpspatch generates a bundle per target), FOV is
               a `$FOV N` Gecko code, EmulationSpeed = FPS/60. Offline only.
  - "bse"    : the BSMSO / Better-Sunshine-Engine disc. FPS is a *native* BSE
               setting poked into RAM (set_bse_fps.py / bridge.py) — the engine
               rewrites the stock framerate global every frame, so the fpspatch
               Gecko bundle must NOT be enabled here. FOV is still a `$FOV N`
               Gecko code. Offline OR online (server + bridge).

---- local overrides --------------------------------------------------------
Machine-specific paths can be overridden without touching this file two ways:

  1. sunshine/launcher/config.local.json  (gitignored; created from the .example)
     {
       "iso_offline":  "/path/to/Super Mario Sunshine (USA).rvz",
       "iso_dir":      "/path/to/bsmso-work",
       "dolphin_app":  "/path/to/Dolphin.app",
       "dolphin_user": "/Users/you/Library/Application Support/Dolphin"
     }

  2. Environment variables (highest priority):
       SMS_ISO_OFFLINE   SMS_ISO_DIR   SMS_DOLPHIN_APP   SMS_DOLPHIN_USER

Precedence: env var > config.local.json > default (hardcoded below).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# ---- repo layout -----------------------------------------------------------
REPO = Path(__file__).resolve().parents[3]          # …/high-fps-dolphin
SUNSHINE = REPO / "sunshine"
LAUNCHER_DIR = SUNSHINE / "launcher"

FPSPATCH = SUNSHINE / "research" / "scripts" / "fpspatch.py"
GECKO = REPO / ".claude" / "skills" / "dolphin-gecko" / "scripts" / "gecko.py"
MAC_ONLINE = SUNSHINE / "bsmso" / "mac-online"
SET_BSE_FPS = MAC_ONLINE / "set_bse_fps.py"
BRIDGE = MAC_ONLINE / "bridge.py"
GHOST = MAC_ONLINE / "ghost_bot.py"
RUN_SERVER = MAC_ONLINE / "run_server.sh"

# ---- local override layer --------------------------------------------------
# Read config.local.json once at import time (file is optional / gitignored).
_LOCAL_JSON = LAUNCHER_DIR / "config.local.json"
_local: dict = {}
if _LOCAL_JSON.exists():
    try:
        _local = json.loads(_LOCAL_JSON.read_text())
    except Exception as _e:
        import warnings
        warnings.warn(f"[smslaunch] Could not parse {_LOCAL_JSON}: {_e}")


def _path(env_var: str, local_key: str, default: Path) -> Path:
    """Resolve a path constant: env > config.local.json > default."""
    if env_var in os.environ:
        return Path(os.environ[env_var]).expanduser()
    if local_key in _local:
        return Path(_local[local_key]).expanduser()
    return default


# ---- Dolphin paths (machine-specific — override via config.local.json) -----
DOLPHIN_APP = _path(
    "SMS_DOLPHIN_APP",
    "dolphin_app",
    REPO / "dolphin" / "build" / "Binaries" / "Dolphin.app",
)
DOLPHIN_USER = _path(
    "SMS_DOLPHIN_USER",
    "dolphin_user",
    Path.home() / "Library" / "Application Support" / "Dolphin",
)

# ---- Dolphin user config ---------------------------------------------------
LIVE_INI = DOLPHIN_USER / "GameSettings" / "GMSE01.ini"      # per-game Gecko/Core
DOLPHIN_INI = DOLPHIN_USER / "Config" / "Dolphin.ini"        # global (MEM1 override)

# ---- launcher state --------------------------------------------------------
PROFILES_JSON = LAUNCHER_DIR / "profiles.json"
PROFILES_LOCAL_JSON = LAUNCHER_DIR / "profiles.local.json"   # gitignored user copy
LAST_JSON = LAUNCHER_DIR / "last.json"
VENV_PY = LAUNCHER_DIR / ".venv" / "bin" / "python"

# ---- discs (machine-specific — override via config.local.json) -------------
# OFFLINE = the plain Super Mario Sunshine disc (GMSE01) + our stock high-fps
# Gecko kit. ONLINE = the BSMSO / Better Sunshine Engine disc.
ISO_OFFLINE = _path(
    "SMS_ISO_OFFLINE",
    "iso_offline",
    Path("/Applications/gamecube/Super Mario Sunshine (USA).rvz"),
)
ISO_DIR = _path(
    "SMS_ISO_DIR",
    "iso_dir",
    Path("/Applications/gamecube/bsmso-work"),
)
ISO_ONLINE = ISO_DIR / "BSMSO-GMSE01.iso"                 # BSE, FPS 30/60/120
ISO_ONLINE_HIGHFPS = ISO_DIR / "BSMSO-GMSE01-highfps.iso"  # fork, adds 240/280/320

# Online (BSE) FPS is a native engine setting — only these values exist.
BSE_FPS_VALUES = [30, 60, 120, 240, 280, 320]
BSE_FORK_ONLY = {240, 280, 320}                  # need the highfps fork disc

# Offline (stock/fpspatch): any multiple of 60, G = FPS/60 an integer >= 2.
STOCK_FPS_SUGGESTED = [120, 180, 240, 360]

# ---- HD textures ("HD portals") — optional per-profile toggle --------------
# The pruned qashto/razius UHD pack we hand-picked: Delfino M-portal textures
# (incl. the THP preview movie planes), FLUDD/lives/coins HUD, digits, shine
# icons, episode-select wordmarks/logos. Vendored in-repo. Both discs are
# GMSE01, so Dolphin loads it by game id for offline AND online alike.
#   * Dolphin uses Load/Textures/<gameid>/ IF it exists, else the 3-char
#     Load/Textures/GMS/ (HiresTextures.cpp GetTextureDirectoriesWithGameId).
#     So a GMSE01 dir cleanly SHADOWS the older full GMS pack — no double-load.
#   * We install it as a symlink (no 226MB copy; the git copy is the install).
#   * HiresTextures/CacheHiresTextures are set per-game in GMSE01.ini
#     [Video_Settings] (maps to GFX/Settings) so the toggle is scoped to SMS.
PRUNED_PACK = SUNSHINE / "textures" / "GMSE01-pruned"
HIRES_DEST = DOLPHIN_USER / "Load" / "Textures" / "GMSE01"


def engine_for(mode: str) -> str:
    """offline -> the stock fpspatch kit; online/solo -> the BSE engine.
    `solo` is the BSE disc booted single-player (no server) — the only way to get
    the BetterSunshineMoveset.kxe moves (Hover Burst, SMO Dive…) offline, since
    that moveset is a Kuribo module that needs the BSE runtime, not a Gecko code."""
    return "bse" if mode in ("online", "solo") else "stock"


def iso_for(mode: str, fps: int) -> Path:
    if mode == "offline":
        return ISO_OFFLINE
    # online + solo both boot the BSE disc (fork disc for the 240/280/320 rates).
    return ISO_ONLINE_HIGHFPS if fps in BSE_FORK_ONLY else ISO_ONLINE


# ---- aspect ----------------------------------------------------------------
# `ratio` = width/height, used to convert the user's horizontal FOV to the
# vertical fovy the $FOV Gecko actually sets. `bse` = native gAspectRatioSetting
# enum; `video` = Dolphin per-game display AspectRatio keys.
ASPECTS = {
    "mac":  {"label": "16:10 (MBP 16\" fullscreen)", "ratio": 16 / 10, "bse": 2,
             "video": {"AspectRatio": "4", "CustomAspectRatioWidth": "16",
                       "CustomAspectRatioHeight": "10"}},
    "tv":   {"label": "16:9 (external TV/monitor)", "ratio": 16 / 9, "bse": 3,
             "video": {"AspectRatio": "1"}},
    "none": {"label": "4:3 (no widescreen)", "ratio": 4 / 3, "bse": 0,
             "video": {"AspectRatio": "0"}},   # Auto -> native 4:3
}
# aspects that actually apply a widescreen code (offline) — 4:3 applies none.
WIDESCREEN_ASPECTS = {"mac", "tv"}

# ---- code title patterns ---------------------------------------------------
# Titles as they appear in [Gecko] (without the leading '$').
FPS_BUNDLE_TITLE = "SMS {fps}fps bundle (fpspatch, no-ForceOpen)"
FPS_BUNDLE_RE = re.compile(r"^SMS (\d+)fps bundle \(fpspatch, no-ForceOpen\)$")
FOV_TITLE = "FOV {fov}"
FOV_RE = re.compile(r"^FOV (\d+)$")
# BSE variant: the generic FOV code's C_MTXPerspective caller allow-list is
# tuned for the stock disc — under BSMSO some projection consumers (the
# heat-haze shimmer pass) miss it and draw at a mismatched FOV. BSE gets a
# 3-line code that stores fovy at the source (mProjectionFovy @0x80023218).
FOV_TITLE_BSE = "FOV {fov} BSE (mProjectionFovy)"
FOV_BSE_RE = re.compile(r"^FOV (\d+) BSE \(mProjectionFovy\)$")
# Menu d-pad repeat under BSE: reset() sets tick-count delay/interval sized
# for a 30Hz pad ticker; BSE ticks it at the full render rate -> FPS/30x-fast
# scroll. v1 (runtime-guarded on the framerate global) FAILED because reset()
# runs at boot BEFORE the external FPS poke lands, so the guard read 0.5f and
# never scaled — and the config is set once, process-global. v2 is STATIC:
# the launcher generates absolute tick counts for the profile's FPS (no
# runtime guard), generated+enabled per-launch like the FOV code.
MENU_REPEAT_TITLE_BSE = "Menu key-repeat BSE-{fps} v2 (static)"
MENU_REPEAT_BSE_RE = re.compile(r"^Menu key-repeat BSE-(\d+) v2 \(static\)$")

# ---- "Pause while jumping" — a fixed one-line write shared by both discs -----
# Vanilla SMS refuses to open the pause menu mid-air (plays the "nope" buzzer).
# TMarDirector::updateGameMode gates the pause on checkActionThing3(), which is
# false only while the JUMPING status bit is set; NOPing the one gate branch at
# 0x80297AD8 makes the jumping case fall through to STATE_UNK5 (open pause).
# The gate is base main.dol code that BSE does NOT relocate, so this single 04
# write serves offline (stock) AND online (BSE) alike. Framerate-independent.
# Full RE: research/codes/pause-while-jumping-v1.txt.
PAUSE_JUMP_TITLE = "Pause while jumping v1"
PAUSE_JUMP_CODE = "04297AD8 60000000"

# ---- QOL toggles (user-facing) ---------------------------------------------
# ONLY genuine quality-of-life / preference codes live here — the things you'd
# actually want to turn on or off (camera, controls, save box, aim). The
# high-fps *correctness* fixes are not toggles; they're applied automatically
# (BASELINE_FIXES below) so the game just works. Each entry resolves to whatever
# full [Gecko] title matches the regex at runtime (None -> unavailable/greyed),
# which survives title drift and avoids the silent "enabled title doesn't match
# a code title -> never ticks" trap.
#   key, label, default-on, {engine: regex-or-None}
QOL_CATALOG = [
    ("camera",     "Camera look-up (+60°)",     True,
     {"stock": r"Camera look-up extension v10", "bse": r"Camera look-up extension v10"}),
    ("fludd",      "FLUDD aim invert",          True,
     {"stock": r"FLUDD Aim Invert v2", "bse": r"FLUDD Aim Invert v3"}),
    # Stock-only: the "Save?" box this reorders is the blue-coin one, and the
    # BSMSO/online build has no blue-coin save dialog (blue coins sync online).
    ("savebox",    "Blue coin save: Continue on top", True,
     {"stock": r"SaveBox: Continue on top", "bse": None}),
    ("tank",       "Tank controls",             False,
     {"stock": r"Tank Controls v8", "bse": r"Tank Controls v8"}),
    # Pause the game mid-jump (vanilla blocks it + buzzes). Same code both discs.
    # Default OFF so it never silently alters the deliberate "vanilla"/no-fix
    # profiles on backfill; the body is auto-installed by launcher.apply().
    ("pausejump",  "Pause while jumping (mid-air)", False,
     {"stock": r"Pause while jumping v1", "bse": r"Pause while jumping v1"}),
]
QOL_KEYS = [k for k, *_ in QOL_CATALOG]

# ---- widescreen (driven by the Aspect dropdown, NOT a QOL toggle) -----------
# Offline (stock disc) needs the projection widescreen Gecko for the chosen aspect
# (`$Widescreen` = 16:9, `$Widescreen 16:10` = generated variant — see codegen)
# PLUS the level-entry wipe fix that stretches the black "curtain" fill to fill
# the frame PLUS the `$Widescreen 2D fix <aspect>` code (codegen.gen_widescreen_2d)
# that repositions the four things the classic code leaves 4:3: the demo wipe/mask
# panes, the shine-select menu masks, its gradient background, and its root pane.
# The 2D fix is COMPLEMENTARY to the wipe fix v2 — v2 scales the TSMSFader solid
# fill (fade transitions); the 2D fix's demo-mask block scales the separate
# TConsoleStr textured wipe curtain + side masks. Keep both.
# Online = BSE renders widescreen natively, so no Gecko is used.
WIDESCREEN_WIPE_FIX = r"Widescreen wipe fix v2"    # aspect-independent curtain fix

# ---- baseline high-fps correctness fixes (always on, ONLINE/BSE only) --------
# The framerate-specific bug fixes the BSE disc needs to run right at high FPS.
# Auto-enabled whenever the matching code exists — never a user toggle. Offline
# doesn't use these: the fpspatch bundle already bakes the same fixes in.
# (noki/petey are intentionally absent — the BSE builds were crashy/unconfirmed;
# this matches the currently shipping working enabled set.)
# `verified` = confirmed correct in-game under BSE. Unverified fixes are NOT
# auto-enabled (quarantine). 2026-08-14 in-game A/B CONFIRMED: `Raw anim-rate
# x0.25` froze water-slide/bonk-star/level-entry-warp anims under BSE (BSE
# natively compensates those rate consumers; quartering them again ~= frozen).
# With it disabled — and Particle parity actually installed for the first
# time (bracket-title fix) — all effects verified correct in-game.
#   key, regex, verified
BASELINE_FIXES = [
    ("particle",  r"Particle parity BSE",                    True),
    ("starfix",   r"HUD StarFix v4 BSE",                     True),
    ("wipe",      r"Wipe pace 30Hz gate BSE",                True),
    ("se",        r"SE frame-process 30Hz gate BSE",         True),
    ("shimmer",   r"Heat-haze shimmer pace",                 True),
    ("gameclock", r"Game-clock fix v15 BSE",                 True),
    ("anmrate",   r"Raw anim-rate x0.25 fixes BSE",          False),
    ("poink",     r"Poink premature-explosion gate v14 BSE", True),
    # DO NOT wire the "Animal x4" codes here: verdict from the Aug-12 kit chat,
    # re-confirmed 2026-08-14 — the stock-kit x4 assumption is WRONG under BSE
    # (birds overshoot, "flying wayyyy too fast"). Linear bird speeds
    # self-compensate under BSE; only the SQUARED accel term lags (walking
    # birds slow, flying fine) — fixed by the x2 accel-site code below.
    ("birdaccel", r"Bird walk accel x2 BSE",                  True),
    # Dune Bud spray on the BSMSO disc: vanilla code creates the sand-dust
    # JPA emitter (resource 0x55) and stores scale fields through the result
    # with NO null check -> "Invalid write 0x154/0x158 PC 801d2bcc" every
    # spray. Guard skips the store block when the emitter is null.
    # NOTE 2026-08-14 (late): the original "repacked archive lacks the
    # resource" diagnosis is WRONG — every disc archive is byte-identical to
    # pristine. 0x55 is the actor's own lazy registration of
    # /scene/mapObj/SandBomb.jpa (Gelato stage arcs), skipped when the
    # global once-flag 0x803FD0BD is stale for the current scene's manager.
    # See research/codes/dunebud-dust-v1.txt + mac-online/dunebud_watch.py.
    ("dunebud",   r"DuneBud emitter null-guard BSE",          True),
    # Restores the dust: registry-check instead of once-flag at 0x801d27a4.
    # NEEDS-TEST in Gelato on the BSE disc; flip to True after an in-game
    # pass (keep the null-guard on regardless).
    ("dunebudreg", r"DuneBud dust re-register BSE",           False),
    ("bluecoin",  r"Blue-coin lifetime v6-BSE",              True),
]


def emulation_speed(fps: int) -> float:
    return round(fps / 60.0, 6)


# ---- FOV: users think horizontal, the Gecko sets vertical fovy --------------
import math

FOV_VMIN, FOV_VMAX = 40, 110         # what the $FOV code template can represent
HFOV_MIN, HFOV_MAX = 55, 140         # sane horizontal input range


def hfov_to_vfov(hfov: float, aspect_key: str) -> int:
    """Convert a horizontal FOV (deg) to the integer vertical fovy the $FOV
    Gecko sets, for the profile's display aspect. Clamped to the code's range."""
    ratio = ASPECTS[aspect_key]["ratio"]
    v = math.degrees(2 * math.atan(math.tan(math.radians(hfov) / 2) / ratio))
    return max(FOV_VMIN, min(FOV_VMAX, round(v)))


def vfov_to_hfov(vfov: float, aspect_key: str) -> int:
    ratio = ASPECTS[aspect_key]["ratio"]
    h = math.degrees(2 * math.atan(math.tan(math.radians(vfov) / 2) * ratio))
    return round(h)
