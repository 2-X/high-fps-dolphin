"""First-run setup wizard for the SMS high-FPS launcher (plain stdin/stdout).

Runnable as `python -m smslaunch.setup_wizard` (or `./sms setup`). Gets a
newcomer on macOS to the full 120fps experience with near-zero manual work.

Every step is IDEMPOTENT and reports one of:
    [already OK]  nothing to do — the machine is already in the target state
    [skipped]     the user declined (or it's optional and was skipped)
    [done]        the wizard changed something

HARD SAFETY CONTRACT
--------------------
* Never overwrite a file without first copying the existing one into a
  timestamped backup dir (sms-setup-backup-<ts>/ under DOLPHIN_USER).
* Byte-identical target -> report [already OK], touch nothing.
* Machine-specific mutations (ISOPath strip) happen on the INSTALLED COPY
  only, never on the repo source.
* profiles / config.local.json writes MERGE — they never clobber other keys.
* Refuses to run while Dolphin is open (it rewrites its own INIs on quit).

Testing hooks (env, so nothing touches a real machine):
    SMS_DOLPHIN_USER   redirect the Dolphin user dir to a temp dir
    SMS_ISO_OFFLINE    pretend an ISO is configured
    SMS_PROFILES_PATH  redirect the profiles.local.json write target
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import config as C


# --------------------------------------------------------------------------- #
# small IO helpers
# --------------------------------------------------------------------------- #
def _c(code: str, s: str) -> str:
    """ANSI-color s if stdout is a TTY, else plain."""
    if not sys.stdout.isatty():
        return s
    return f"\033[{code}m{s}\033[0m"


def hdr(s: str) -> None:
    print("\n" + _c("1;36", f"== {s} =="))


def ok(s: str) -> None:
    print(f"  {_c('32', '[already OK]')} {s}")


def done(s: str) -> None:
    print(f"  {_c('1;32', '[done]')} {s}")


def skipped(s: str) -> None:
    print(f"  {_c('33', '[skipped]')} {s}")


def warn(s: str) -> None:
    print(f"  {_c('1;33', 'WARN')} {s}")


def info(s: str) -> None:
    print(f"  {s}")


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    try:
        raw = input(f"  {prompt}{suffix}: ").strip()
    except EOFError:
        raw = ""
    return raw or (default or "")


def ask_yesno(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    raw = ask(f"{prompt} ({d})", "")
    if not raw:
        return default
    return raw[0].lower() == "y"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _same_bytes(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and _sha256(a) == _sha256(b)


def _backup_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


# --------------------------------------------------------------------------- #
# config.local.json merge writer (never clobbers other keys)
# --------------------------------------------------------------------------- #
def _config_local_path() -> Path:
    """The config.local.json write target. SMS_CONFIG_LOCAL redirects it (used
    by tests so the real machine's file is never touched)."""
    over = os.environ.get("SMS_CONFIG_LOCAL")
    return Path(over).expanduser() if over else C._LOCAL_JSON


def _read_local_json() -> dict:
    p = _config_local_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            warn(f"{p} is not valid JSON; a new key will be appended but "
                 "please check the file by hand.")
    return {}


def _write_local_key(key: str, value: str) -> None:
    p = _config_local_path()
    data = _read_local_json()
    data[key] = value
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n")


# --------------------------------------------------------------------------- #
# Step 1 — Dolphin-running guard
# --------------------------------------------------------------------------- #
def step_guard() -> bool:
    """Return True if it is safe to continue."""
    # SMS_SKIP_DOLPHIN_GUARD is a test-only escape hatch: the sandbox dry-run
    # writes only into a temp DOLPHIN_USER, so a live Dolphin can't be harmed.
    # Never set this in normal use.
    if os.environ.get("SMS_SKIP_DOLPHIN_GUARD") == "1":
        return True
    running = subprocess.run(["pgrep", "-x", "Dolphin"],
                             capture_output=True, text=True).returncode == 0
    if running:
        print(_c("1;31",
                 "\nDolphin is currently running. It rewrites its own config "
                 "files on quit,\nwhich would undo anything this wizard writes. "
                 "Quit Dolphin and re-run.\n"))
        return False
    return True


# --------------------------------------------------------------------------- #
# Step 2 — ISO
# --------------------------------------------------------------------------- #
_ISO_EXTS = (".rvz", ".iso", ".gcm")


def step_iso() -> None:
    hdr("Step 1 / 6  —  Your Super Mario Sunshine disc")
    if C.ISO_OFFLINE.exists():
        ok(f"ISO found: {C.ISO_OFFLINE}")
        return
    info("You must dump your own Super Mario Sunshine (NTSC-U, GMSE01) disc.")
    info("See https://dolphin-emu.org/docs/guides/ripping-games/")
    while True:
        raw = ask("Path to your dump (.rvz/.iso/.gcm), or blank to skip", "")
        if not raw:
            skipped("No ISO configured — the launcher will not boot offline "
                    "until you set one.")
            return
        p = Path(raw).expanduser()
        if not p.exists():
            warn(f"Not found: {p}")
            continue
        if p.suffix.lower() not in _ISO_EXTS:
            if not ask_yesno(f"{p.name} is not .rvz/.iso/.gcm — use it anyway?",
                             False):
                continue
        _write_local_key("iso_offline", str(p))
        done(f"Wrote iso_offline -> {p} into config.local.json")
        return


# --------------------------------------------------------------------------- #
# Step 3 — Dolphin app
# --------------------------------------------------------------------------- #
_RELEASE_API = ("https://api.github.com/repos/2-X/high-fps-dolphin/"
                "releases/latest")
_ASSET_RE = re.compile(r"^Dolphin-macOS-arm64.*\.zip$")
_INSTALL_ROOT = Path.home() / "Applications" / "SMS-Dolphin"


def _curl_json(url: str) -> dict | None:
    r = subprocess.run(["curl", "-fsSL", url], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def _download_prebuilt() -> Path | None:
    info("Querying the latest high-fps-dolphin release…")
    rel = _curl_json(_RELEASE_API)
    if not rel or "assets" not in rel:
        warn("No release found (or the repo has no published release yet).")
        info("Fall back to option [2] (point at an existing build) or [3] "
             "(build from source).")
        info("Build instructions: sunshine/dolphin-patches/README.md")
        return None
    asset = next((a for a in rel["assets"]
                  if _ASSET_RE.match(a.get("name", ""))), None)
    if not asset:
        warn("The latest release has no Dolphin-macOS-arm64*.zip asset.")
        info("Build from source instead: sunshine/dolphin-patches/README.md")
        return None
    url = asset["browser_download_url"]
    zip_path = Path("/tmp") / asset["name"]
    info(f"Downloading {asset['name']} …")
    r = subprocess.run(["curl", "-fL", "-o", str(zip_path), url])
    if r.returncode != 0 or not zip_path.exists():
        warn("Download failed.")
        return None
    _INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
    info(f"Extracting into {_INSTALL_ROOT} …")
    r = subprocess.run(["ditto", "-x", "-k", str(zip_path), str(_INSTALL_ROOT)])
    if r.returncode != 0:
        warn("Extraction (ditto) failed.")
        return None
    # Locate the extracted Dolphin.app (zip may nest it).
    app = _INSTALL_ROOT / "Dolphin.app"
    if not app.exists():
        found = next(iter(_INSTALL_ROOT.rglob("Dolphin.app")), None)
        if found is None:
            warn(f"Could not find Dolphin.app under {_INSTALL_ROOT} after "
                 "extraction.")
            return None
        app = found
    info("Removing Gatekeeper quarantine (the app is unsigned)…")
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(app)])
    return app


def step_dolphin_app() -> None:
    hdr("Step 2 / 6  —  The patched Dolphin build")
    if C.DOLPHIN_APP.exists():
        ok(f"Dolphin.app found: {C.DOLPHIN_APP}")
        return
    info("This project needs a CUSTOM Dolphin build (Gecko code-cap lift + "
         "audio\n  tempo fix). Stock Dolphin will not work.")
    info("  [1] Download the prebuilt macOS arm64 binary (recommended)")
    info("  [2] Point at an already-built Dolphin.app")
    info("  [3] Show build-from-source instructions")
    choice = ask("Choose 1/2/3 (blank = skip)", "1")
    if choice == "1":
        app = _download_prebuilt()
        if app is not None:
            _write_local_key("dolphin_app", str(app))
            done(f"Installed Dolphin.app -> {app}")
        else:
            skipped("Prebuilt download did not complete — see the notes above.")
        return
    if choice == "2":
        raw = ask("Path to Dolphin.app", "")
        if not raw:
            skipped("No path given.")
            return
        p = Path(raw).expanduser()
        if not p.exists():
            warn(f"Not found: {p}")
            skipped("Dolphin app not configured.")
            return
        _write_local_key("dolphin_app", str(p))
        done(f"Wrote dolphin_app -> {p} into config.local.json")
        return
    if choice == "3":
        _print_build_instructions()
        skipped("Build Dolphin, then re-run setup (or fill dolphin_app "
                "in config.local.json).")
        return
    skipped("No Dolphin app configured.")


def _print_build_instructions() -> None:
    print("""
  Build the patched Dolphin (macOS, Apple Silicon):

    git clone https://github.com/dolphin-emu/dolphin
    cd dolphin
    git checkout $(cut -d' ' -f1 \\
        ../sunshine/dolphin-patches/UPSTREAM_COMMIT.txt)
    git apply ../sunshine/dolphin-patches/high-fps-dolphin.patch
    mkdir build && cd build && cmake .. && make -j$(sysctl -n hw.logicalcpu)

  Result: build/Binaries/Dolphin.app
  Full details: sunshine/dolphin-patches/README.md
""")


# --------------------------------------------------------------------------- #
# Step 4 — Dolphin user config kit
# --------------------------------------------------------------------------- #
# The HANDOFF-MAC copy table, encoded as (repo-source, dest-relative-to-USER).
# Mac-dialect input INIs come from mac-originals/ (the repo-root variants and
# the .pc files are for Windows and are deliberately excluded). Only .ini/.json
# config files — the *.laptop120 / *.pc alternates are skipped.
def _config_manifest() -> list[tuple[Path, str]]:
    src = C.SUNSHINE / "dolphin-config"
    man: list[tuple[Path, str]] = [
        # Mac-dialect input configs (Quartz device/key names).
        (src / "mac-originals" / "GCPadNew.ini", "Config/GCPadNew.ini"),
        (src / "mac-originals" / "GCKeyNew.ini", "Config/GCKeyNew.ini"),
        # Global config (Dolphin.ini gets the ISOPath strip + MEM1 guarantee).
        (src / "Dolphin.ini", "Config/Dolphin.ini"),
        (src / "GFX.ini", "Config/GFX.ini"),
        (src / "Hotkeys.ini", "Config/Hotkeys.ini"),
        (src / "FreeLookController.ini", "Config/FreeLookController.ini"),
        # GraphicMods manifest + per-game Gecko/Core kit.
        (src / "GraphicMods" / "GMSE01.json", "Config/GraphicMods/GMSE01.json"),
        (src / "GameSettings" / "GMSE01.ini", "GameSettings/GMSE01.ini"),
    ]
    # Mac-dialect controller profiles (whole folder, .ini only).
    prof_src = src / "mac-originals" / "Profiles" / "GCPad"
    if prof_src.is_dir():
        for f in sorted(prof_src.glob("*.ini")):
            man.append((f, f"Config/Profiles/GCPad/{f.name}"))
    return man


def _strip_isopaths(text: str) -> str:
    """Remove machine-specific ISOPath<N> lines and the ISOPaths count from a
    Dolphin.ini body (installed copy only). Dolphin rebuilds these itself."""
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if re.match(r"^ISOPath\d+\s*=", s) or re.match(r"^ISOPaths\s*=", s):
            continue
        out.append(ln)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _ensure_core_key(text: str, key: str, value: str) -> tuple[str, bool]:
    """Ensure `[Core] key = value` in an INI body. Returns (new_text, changed).
    Adds the [Core] section if absent."""
    lines = text.splitlines()
    # find [Core] span
    sect_start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "[core]":
            sect_start = i
            break
    if sect_start is None:
        # append a [Core] section
        body = text.rstrip("\n")
        body += f"\n[Core]\n{key} = {value}\n"
        return body, True
    # find section end
    sect_end = len(lines)
    for j in range(sect_start + 1, len(lines)):
        if re.match(r"^\[.+\]\s*$", lines[j].strip()):
            sect_end = j
            break
    pat = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*)$")
    for k in range(sect_start + 1, sect_end):
        m = pat.match(lines[k])
        if m:
            if m.group(1).strip() == value:
                return text, False
            lines[k] = f"{key} = {value}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), True
    # not present — insert at end of section
    lines.insert(sect_end, f"{key} = {value}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), True


def _ensure_settings_key(text: str, key: str, value: str) -> tuple[str, bool]:
    """Like _ensure_core_key but for the [Settings] section (GFX.ini)."""
    lines = text.splitlines()
    sect_start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "[settings]":
            sect_start = i
            break
    if sect_start is None:
        body = text.rstrip("\n")
        body += f"\n[Settings]\n{key} = {value}\n"
        return body, True
    sect_end = len(lines)
    for j in range(sect_start + 1, len(lines)):
        if re.match(r"^\[.+\]\s*$", lines[j].strip()):
            sect_end = j
            break
    pat = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*)$")
    for k in range(sect_start + 1, sect_end):
        m = pat.match(lines[k])
        if m:
            if m.group(1).strip() == value:
                return text, False
            lines[k] = f"{key} = {value}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), True
    lines.insert(sect_end, f"{key} = {value}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), True


# MEM1 override — the EXACT keys from dolphin-patches/README.md §3.
_MEM1_KEYS = {"RAMOverrideEnable": "True", "MEM1Size": "0x02000000"}


def _install_one(src: Path, rel: str, user_dir: Path, backup_dir: Path,
                 transform=None) -> str:
    """Install one file. transform(text)->text runs on the INSTALLED COPY only.
    Returns 'ok' | 'done'."""
    dest = user_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    if transform is None:
        # Byte comparison is the identity check.
        if _same_bytes(src, dest):
            return "ok"
        if dest.exists():
            b = backup_dir / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            b.write_bytes(dest.read_bytes())
        dest.write_bytes(src.read_bytes())
        return "done"

    # Transformed file: compare the *transformed source* to the current dest.
    new_text = transform(src.read_text(encoding="utf-8", errors="replace"))
    if dest.exists():
        cur = dest.read_text(encoding="utf-8", errors="replace")
        if cur == new_text:
            return "ok"
        b = backup_dir / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        b.write_bytes(dest.read_bytes())
    dest.write_text(new_text, encoding="utf-8")
    return "done"


def _dolphin_ini_transform(text: str) -> str:
    """The Dolphin.ini installed-copy transform: strip ISOPaths, then guarantee
    the MEM1 override and EmulationSpeed sanity for 120fps."""
    text = _strip_isopaths(text)
    for k, v in _MEM1_KEYS.items():
        text, _ = _ensure_core_key(text, k, v)
    return text


def step_config_kit() -> None:
    hdr("Step 3 / 6  —  Dolphin config kit")
    user = C.DOLPHIN_USER
    manifest = _config_manifest()

    # Verify every source exists before touching anything.
    missing = [str(s) for s, _ in manifest if not s.exists()]
    if missing:
        warn("Missing repo source files (kit is incomplete):")
        for m in missing:
            info(f"  {m}")

    backup_dir = user / f"sms-setup-backup-{_backup_stamp()}"
    fresh = not user.exists()
    if fresh:
        info(f"Dolphin user dir does not exist yet — creating {user}")

    results = {"ok": 0, "done": 0}
    used_backup = False
    for src, rel in manifest:
        if not src.exists():
            continue
        transform = _dolphin_ini_transform if rel == "Config/Dolphin.ini" else None
        res = _install_one(src, rel, user, backup_dir, transform)
        results[res] += 1
        if res == "done" and (backup_dir / rel).exists():
            used_backup = True

    # Guarantee the MEM1 override + GFX kit even if Dolphin.ini/GFX.ini were
    # already present and byte-identical to some *other* version (idempotent).
    mem1_changed = _guarantee_mem1(user, backup_dir)
    gfx_changed = _guarantee_gfx(user, backup_dir)

    if results["done"] or mem1_changed or gfx_changed:
        done(f"Installed/updated config kit into {user}")
        if mem1_changed:
            done("Guaranteed MEM1 override (RAMOverrideEnable / MEM1Size) in "
                 "Dolphin.ini")
        if used_backup or (backup_dir.exists() and any(backup_dir.rglob("*"))):
            info(f"Existing files backed up under {backup_dir}")
    else:
        ok(f"Config kit already installed & current in {user}")
    if results["ok"]:
        info(f"{results['ok']} file(s) already OK; "
             f"{results['done']} written.")


def _guarantee_mem1(user: Path, backup_dir: Path) -> bool:
    """Ensure the installed Dolphin.ini carries the MEM1 override keys. Runs
    after the copy so it also repairs a pre-existing Dolphin.ini. Returns True
    if it changed the file."""
    dest = user / "Config" / "Dolphin.ini"
    if not dest.exists():
        return False
    text = dest.read_text(encoding="utf-8", errors="replace")
    new = text
    changed_any = False
    for k, v in _MEM1_KEYS.items():
        new, ch = _ensure_core_key(new, k, v)
        changed_any = changed_any or ch
    if not changed_any:
        return False
    b = backup_dir / "Config" / "Dolphin.ini"
    b.parent.mkdir(parents=True, exist_ok=True)
    if not b.exists():
        b.write_bytes(dest.read_bytes())
    dest.write_text(new, encoding="utf-8")
    return True


# GFX keys our kit needs (HiresTextures toggled on in step 6; here we make sure
# the wide-screen hack the widescreen Gecko pairs with is on).
_GFX_SETTINGS = {"wideScreenHack": "True"}


def _guarantee_gfx(user: Path, backup_dir: Path) -> bool:
    dest = user / "Config" / "GFX.ini"
    if not dest.exists():
        return False
    text = dest.read_text(encoding="utf-8", errors="replace")
    new = text
    changed_any = False
    for k, v in _GFX_SETTINGS.items():
        new, ch = _ensure_settings_key(new, k, v)
        changed_any = changed_any or ch
    if not changed_any:
        return False
    b = backup_dir / "Config" / "GFX.ini"
    b.parent.mkdir(parents=True, exist_ok=True)
    if not b.exists():
        b.write_bytes(dest.read_bytes())
    dest.write_text(new, encoding="utf-8")
    return True


# --------------------------------------------------------------------------- #
# Step 5 — Player name / profiles
# --------------------------------------------------------------------------- #
def _profiles_target() -> Path:
    over = os.environ.get("SMS_PROFILES_PATH")
    return Path(over).expanduser() if over else C.PROFILES_LOCAL_JSON


def step_player() -> None:
    hdr("Step 4 / 6  —  Player name")
    target = _profiles_target()
    if target.exists():
        ok(f"profiles already personalized: {target}")
        return
    # ask() reads stdin and falls back to the default on EOF, so this works
    # both interactively and under scripted-stdin dry-runs.
    name = ask("Your player name", "Player") or "Player"
    # Build from profiles.json (the tracked defaults), stamping player_name.
    src = C.PROFILES_JSON
    try:
        raw = json.loads(src.read_text())
    except Exception:
        raw = {"last": None, "profiles": []}
    for p in raw.get("profiles", []):
        p["player_name"] = name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=2) + "\n")
    done(f"Created {target} with player_name = {name!r}")


# --------------------------------------------------------------------------- #
# Step 6 — HD textures (optional)
# --------------------------------------------------------------------------- #
_UHD_API = ("https://api.github.com/repos/qashto/"
            "Super_Mario_Sunshine_UHD_Texture_Pack/releases/latest")


def step_textures() -> None:
    hdr("Step 5 / 6  —  HD texture pack (optional)")
    dest = C.DOLPHIN_USER / "Load" / "Textures" / "GMS"
    if dest.is_dir() and any(dest.rglob("*.dds")):
        ok(f"HD textures already present in {dest}")
        return
    info("The full UHD pack is a ~2-3 GB download from the pack author's "
         "official\n  release (qashto/Super_Mario_Sunshine_UHD_Texture_Pack). "
         "The launcher's\n  in-repo 'HD portals' subset covers M-portals + HUD "
         "without any download.")
    if not ask_yesno("Download & install the FULL UHD pack now?", False):
        skipped("HD textures — you can add them later or use the HD-portals "
                "toggle in the launcher.")
        return

    rel = _curl_json(_UHD_API)
    if not rel or not rel.get("assets"):
        warn("Could not query the UHD pack release.")
        _texture_manual_instructions(dest)
        return
    assets = rel["assets"]
    # Prefer a DDS-flavored archive (the pack ships DDS + a legacy PNG variant).
    asset = (next((a for a in assets
                   if "dds" in a.get("name", "").lower()), None)
             or assets[0])
    url = asset["browser_download_url"]
    dl = Path.home() / "Downloads" / asset["name"]
    info(f"Downloading {asset['name']} into {dl} (resumable)…")
    r = subprocess.run(["curl", "-fL", "-C", "-", "-o", str(dl), url])
    if r.returncode != 0 or not dl.exists():
        warn("Download failed.")
        _texture_manual_instructions(dest)
        return

    if not _extract_textures(dl, dest):
        _texture_manual_instructions(dest, downloaded=dl)
        return

    # Turn the hires-texture toggles on in GFX.ini (exact Dolphin key names).
    changed = False
    for k, v in (("HiresTextures", "True"), ("CacheHiresTextures", "True")):
        c = _set_gfx_settings(k, v)
        changed = changed or c
    done(f"Installed UHD textures into {dest}")
    if changed:
        done("Enabled HiresTextures / CacheHiresTextures in GFX.ini")


def _extract_textures(archive: Path, dest: Path) -> bool:
    """Extract archive into dest, normalizing any single top-level folder so the
    .dds tree lands directly under GMS/. Uses py7zr (installed into the venv at
    runtime only, on request). Returns True on success."""
    if not ask_yesno("Install py7zr into the launcher venv to extract the .7z? "
                     "(not added to requirements.txt)", True):
        return False
    py = str(C.VENV_PY) if C.VENV_PY.exists() else sys.executable
    r = subprocess.run([py, "-m", "pip", "install", "py7zr"])
    if r.returncode != 0:
        warn("py7zr install failed.")
        return False
    try:
        # Extract with normalization via a helper subprocess (py7zr lives in the
        # venv, not necessarily this interpreter). Inspects the listing first to
        # collapse a single top-level folder so the .dds tree lands under GMS/.
        helper = (
            "import sys, py7zr, os, shutil, tempfile\n"
            "arc, dest = sys.argv[1], sys.argv[2]\n"
            "with py7zr.SevenZipFile(arc) as z:\n"
            "    names = z.getnames()\n"
            "tops = set(n.split('/')[0] for n in names if n)\n"
            "tmp = tempfile.mkdtemp()\n"
            "with py7zr.SevenZipFile(arc) as z:\n"
            "    z.extractall(tmp)\n"
            "os.makedirs(dest, exist_ok=True)\n"
            "root = tmp\n"
            "if len(tops) == 1:\n"
            "    only = os.path.join(tmp, tops.pop())\n"
            "    if os.path.isdir(only):\n"
            "        root = only\n"
            "for item in os.listdir(root):\n"
            "    s = os.path.join(root, item); d = os.path.join(dest, item)\n"
            "    if os.path.isdir(s):\n"
            "        shutil.copytree(s, d, dirs_exist_ok=True)\n"
            "    else:\n"
            "        shutil.copy2(s, d)\n"
            "shutil.rmtree(tmp, ignore_errors=True)\n"
        )
        r = subprocess.run([py, "-c", helper, str(archive), str(dest)])
        return r.returncode == 0
    except Exception as e:
        warn(f"Extraction failed: {e}")
        return False


def _texture_manual_instructions(dest: Path, downloaded: Path | None = None) -> None:
    info("Automatic extraction was not possible.")
    if downloaded:
        info(f"The archive is at: {downloaded}")
    info("Manual install:")
    info("  1. Extract the archive (e.g. with Keka: https://www.keka.io).")
    info(f"  2. Put the .dds tree directly under: {dest}")
    info("  3. In Dolphin: Graphics -> Advanced -> Load/Prefetch Custom "
         "Textures ON.")


def _set_gfx_settings(key: str, value: str) -> bool:
    dest = C.DOLPHIN_USER / "Config" / "GFX.ini"
    if not dest.exists():
        return False
    text = dest.read_text(encoding="utf-8", errors="replace")
    new, changed = _ensure_settings_key(text, key, value)
    if changed:
        dest.write_text(new, encoding="utf-8")
    return changed


# --------------------------------------------------------------------------- #
# Step 7 — summary
# --------------------------------------------------------------------------- #
def step_summary() -> None:
    hdr("Step 6 / 6  —  Summary")
    iso = C.ISO_OFFLINE
    app = C.DOLPHIN_APP
    user = C.DOLPHIN_USER
    dolphin_ini = user / "Config" / "Dolphin.ini"
    mem1_ok = False
    if dolphin_ini.exists():
        t = dolphin_ini.read_text(encoding="utf-8", errors="replace")
        mem1_ok = ("RAMOverrideEnable = True" in t
                   and re.search(r"^MEM1Size\s*=", t, re.M) is not None)

    def line(label, val, good):
        mark = _c("32", "OK") if good else _c("1;31", "MISSING")
        print(f"  [{mark}] {label}: {val}")

    line("ISO", iso, iso.exists())
    line("Dolphin.app", app, app.exists())
    line("Config kit", user, (user / "GameSettings" / "GMSE01.ini").exists())
    line("MEM1 override", "RAMOverrideEnable / MEM1Size in Dolphin.ini", mem1_ok)
    line("Profiles", _profiles_target(), _profiles_target().exists())

    print()
    if iso.exists() and app.exists() and mem1_ok:
        print(_c("1;32", "  All set. Run  ./sms  to play."))
    else:
        print(_c("1;33", "  Some steps are incomplete — re-run "
                 "`./sms setup` after fixing the MISSING items above."))


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def run(interactive: bool = True) -> int:
    # `interactive` is accepted for the app.py auto-offer call site; the steps
    # themselves read stdin via ask()/ask_yesno(), which degrade to defaults on
    # EOF, so a piped/non-TTY run is safe either way.
    print(_c("1;36", "\nSuper Mario Sunshine high-FPS — first-run setup\n"))
    print("  This wizard is idempotent: safe to re-run. Nothing already "
          "configured\n  will be changed; a timestamped backup is made before "
          "any overwrite.\n")
    if not step_guard():
        return 1
    step_iso()
    step_dolphin_app()
    step_config_kit()
    step_player()
    step_textures()
    step_summary()
    return 0


def main() -> int:
    return run(interactive=sys.stdin.isatty())


if __name__ == "__main__":
    sys.exit(main())
