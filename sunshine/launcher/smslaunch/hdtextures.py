"""Install / uninstall the pruned "HD portals" UHD texture pack.

The pack (Delfino M-portal textures incl. the THP preview planes, FLUDD/lives/
coins HUD, digits, shine icons, episode-select wordmarks) is vendored in-repo at
`sunshine/textures/GMSE01-pruned/`. Dolphin loads hires textures from
`Load/Textures/<gameid>/`; both the offline (stock) and online (BSMSO) discs are
GMSE01, so one install covers both. A `GMSE01` directory also shadows any older
full `GMS` pack (Dolphin uses the region-specific dir if it exists, else the
3-char one) — so the pruned pack cleanly wins with no double-load.

We install by symlink (the git copy IS the install — no 226MB duplicate), and
never clobber a real user-created directory. Enabling/disabling the textures
themselves is a per-game GMSE01.ini `[Video_Settings]` HiresTextures toggle,
handled by the caller (launcher.apply) alongside the aspect keys.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import config as C


def _noop(_m):
    pass


# The per-game GFX keys that turn the pack on/off. Live in GMSE01.ini
# [Video_Settings] (maps to GFX/Settings), scoping hires textures to SMS.
def video_settings(on: bool) -> dict:
    v = "True" if on else "False"
    return {"HiresTextures": v, "CacheHiresTextures": v}


def _is_link(dest: Path) -> bool:
    """Symlink on any OS, or an NTFS junction on Windows. Junctions are the
    unprivileged Windows equivalent (plain symlinks need admin/Developer Mode);
    Dolphin follows both identically. Python 3.12+ has os.path.isjunction."""
    if dest.is_symlink():
        return True
    isj = getattr(os.path, "isjunction", None)
    return bool(isj and isj(dest))


def status() -> str:
    """'linked' | 'linked-elsewhere' | 'realdir' | 'missing' — what currently
    sits at Load/Textures/GMSE01."""
    dest = C.HIRES_DEST
    if _is_link(dest):
        try:
            return "linked" if dest.resolve() == C.PRUNED_PACK.resolve() \
                   else "linked-elsewhere"
        except OSError:
            return "linked-elsewhere"
    if dest.exists():
        return "realdir"
    return "missing"


def ensure_installed(*, log=_noop) -> None:
    """Make Load/Textures/GMSE01 point at the vendored pruned pack. Idempotent;
    refuses to touch a real (non-symlink) directory the user may have put there."""
    if not C.PRUNED_PACK.is_dir():
        raise FileNotFoundError(f"pruned texture pack missing: {C.PRUNED_PACK}")
    dest = C.HIRES_DEST
    st = status()
    if st == "linked":
        log(f"HD texture pack already installed ({dest.name} → GMSE01-pruned).")
        return
    if st == "realdir":
        # Don't delete a real folder the user populated by hand.
        raise FileExistsError(
            f"{dest} is a real directory (not our symlink) — leaving it alone. "
            "Move/remove it yourself if you want the launcher to manage it.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _is_link(dest):                          # stale/wrong link — replace it
        dest.unlink()
    try:
        os.symlink(C.PRUNED_PACK, dest)
    except OSError:
        # Windows: plain symlinks need admin/Developer Mode. Fall back to an
        # NTFS junction — unprivileged, and Dolphin follows it identically.
        if os.name != "nt":
            raise
        import subprocess
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dest),
                            str(C.PRUNED_PACK.resolve())],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise OSError(f"junction fallback failed: {r.stderr.strip()}")
    n = sum(1 for _ in C.PRUNED_PACK.rglob("*.dds"))
    log(f"Installed HD texture pack: {dest} → GMSE01-pruned ({n} .dds).")


def apply(on: bool, *, log=_noop) -> dict:
    """Ensure the pack is present when enabling, and return the [Video_Settings]
    keys the caller should write. Disabling never removes files — it just flips
    the per-game HiresTextures toggle off (fast + reversible)."""
    if on:
        ensure_installed(log=log)
        log("HD portals ON — HiresTextures enabled for SMS.")
    else:
        log("HD portals OFF — HiresTextures disabled for SMS "
            "(pack left on disk).")
    return video_settings(on)
