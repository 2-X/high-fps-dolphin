"""Minimal, safe editor for Dolphin's per-game GMSE01.ini.

Dolphin rewrites this file from memory when it quits after you touch per-game
settings, so every mutation here refuses to run while Dolphin is alive and backs
the file up first (same contract as the dolphin-gecko skill's gecko.py).

Only the operations the launcher needs live here: introspect [Gecko] titles,
resolve a QOL regex to the real full title, add/replace a code block, set the
*exact* [Gecko_Enabled] set, and poke [Core] / [Video_Settings] keys.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_SECT = re.compile(r"^\[(?P<name>[^\]]+)\]\s*$", re.M)
_HEXPAIR = re.compile(r"^[0-9A-Fa-f]{8} [0-9A-Fa-f]{8}$")


class DolphinRunning(RuntimeError):
    pass


def dolphin_name(title: str) -> str:
    """The name Dolphin actually matches [Gecko_Enabled] lines against.

    Dolphin parses `$Name [creator]` by splitting at the first '[' and
    whitespace-stripping (GeckoCodeConfig.cpp), but compares enabled lines
    VERBATIM against that stripped name (CheatCodes.h). A bracketed suffix
    written into [Gecko_Enabled] therefore never matches — the code is
    silently never enabled. Every enabled-line we write must go through this.
    """
    return title.split("[", 1)[0].strip()


def dolphin_running() -> bool:
    # Exact process-name match — helpers launched from this repo (bridge.py,
    # ghost_bot.py, this launcher) would false-match a `pgrep -f dolphin`.
    return subprocess.run(["pgrep", "-x", "Dolphin"],
                          capture_output=True, text=True).returncode == 0


class Ini:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.text = self.path.read_text(encoding="utf-8", errors="replace")

    # ---- section plumbing --------------------------------------------------
    def _spans(self):
        marks = [(m.group("name"), m.start()) for m in _SECT.finditer(self.text)]
        out = []
        for i, (name, start) in enumerate(marks):
            end = marks[i + 1][1] if i + 1 < len(marks) else len(self.text)
            out.append((name, start, end))
        return out

    def _span(self, name):
        for n, s, e in self._spans():
            if n == name:
                return s, e
        return None

    def _ensure_section(self, name):
        if self._span(name):
            return
        if not self.text.endswith("\n"):
            self.text += "\n"
        self.text += f"[{name}]\n"

    # ---- introspection -----------------------------------------------------
    def titles(self, section="Gecko"):
        span = self._span(section)
        if not span:
            return []
        body = self.text[span[0]:span[1]]
        return [ln[1:].strip() for ln in body.splitlines() if ln.startswith("$")]

    def enabled(self):
        return self.titles("Gecko_Enabled")

    def resolve(self, pattern: str):
        """Return the single full [Gecko] title matching `pattern` (regex,
        searched), preferring an exact whole-title match. None if no/????
        ambiguous match."""
        if not pattern:
            return None
        rx = re.compile(pattern)
        hits = [t for t in self.titles() if rx.search(t)]
        if not hits:
            return None
        exact = [t for t in hits if re.fullmatch(pattern, t)]
        if len(exact) == 1:
            return exact[0]
        return hits[0] if len(hits) == 1 else (exact[0] if exact else hits[0])

    def core_get(self, key, default=None):
        span = self._span("Core")
        if not span:
            return default
        for ln in self.text[span[0]:span[1]].splitlines():
            m = re.match(rf"\s*{re.escape(key)}\s*=\s*(.*)$", ln)
            if m:
                return m.group(1).strip()
        return default

    # ---- mutation ----------------------------------------------------------
    def _remove_block(self, title, section="Gecko"):
        span = self._span(section)
        if not span:
            return False
        s, e = span
        lines = self.text[s:e].splitlines(keepends=True)
        out, removed, i = [], False, 0
        while i < len(lines):
            ln = lines[i]
            if ln.startswith("$") and ln[1:].strip() == title:
                removed = True
                i += 1
                while i < len(lines) and not lines[i].startswith(("$", "[")):
                    i += 1
                continue
            out.append(ln)
            i += 1
        self.text = self.text[:s] + "".join(out) + self.text[e:]
        return removed

    def add_code(self, title, code_text, *, replace=True):
        """Insert (or replace) a `$title` block of hex pairs into [Gecko]."""
        good = []
        for ln in code_text.replace("\r\n", "\n").split("\n"):
            ln = ln.strip()
            if not ln:
                continue
            if not _HEXPAIR.fullmatch(ln):
                raise ValueError(f"bad code line: {ln!r}")
            good.append(ln.upper())
        if replace:
            self._remove_block(title)
        self._ensure_section("Gecko")
        s, e = self._span("Gecko")
        block = f"${title}\n" + "\n".join(good) + "\n"
        seg = self.text[s:e].rstrip("\n") + "\n" + block
        self.text = self.text[:s] + seg + self.text[e:]

    def remove_code(self, title, section="Gecko"):
        """Delete a `$title` block (and its body) from `section`. Returns True
        if a block was removed. Used to evict superseded (vN-1) code bodies."""
        return self._remove_block(title, section)

    def set_enabled(self, full_titles):
        """Replace [Gecko_Enabled] with exactly these titles (order kept),
        normalized to the name Dolphin matches on (bracket suffix stripped).
        This is how the launcher guarantees mutually-exclusive engine setups —
        e.g. the fpspatch bundle is never left enabled under BSE."""
        self._ensure_section("Gecko_Enabled")
        s, e = self._span("Gecko_Enabled")
        body = "[Gecko_Enabled]\n" + "".join(f"${dolphin_name(t)}\n"
                                             for t in full_titles)
        # rebuild the section (header lives at s..first newline); replace whole span
        self.text = self.text[:s] + body + self.text[e:]

    def set_core(self, key, value):
        self._ensure_section("Core")
        s, e = self._span("Core")
        seg = self.text[s:e]
        pat = re.compile(rf"^(\s*{re.escape(key)}\s*=).*$", re.M)
        if pat.search(seg):
            seg = pat.sub(rf"\g<1> {value}", seg, count=1)
        else:
            seg = seg.rstrip("\n") + f"\n{key} = {value}\n"
        self.text = self.text[:s] + seg + self.text[e:]

    def set_video(self, want: dict):
        """Set [Video_Settings] keys, dropping the managed ones first so they're
        rewritten fresh from `want` (aspect + the HD-texture hires toggle)."""
        self._ensure_section("Video_Settings")
        s, e = self._span("Video_Settings")
        drop = {"AspectRatio", "AspectMode",
                "CustomAspectRatioWidth", "CustomAspectRatioHeight",
                "HiresTextures", "CacheHiresTextures"}
        kept = []
        for ln in self.text[s:e].splitlines():
            if ln.strip().startswith("[") or not ln.strip():
                continue
            k = ln.split("=", 1)[0].strip()
            if k in drop:
                continue
            kept.append(ln)
        body = "[Video_Settings]\n" + "".join(x + "\n" for x in kept)
        body += "".join(f"{k} = {v}\n" for k, v in want.items())
        self.text = self.text[:s] + body + self.text[e:]

    # ---- persistence -------------------------------------------------------
    def save(self, *, force=False):
        if not force and dolphin_running():
            raise DolphinRunning(
                "Dolphin is running — it rewrites GMSE01.ini on quit. "
                "Quit Dolphin first.")
        shutil.copyfile(self.path, str(self.path) + ".bak")
        text = self.text.replace("\r\n", "\n").rstrip("\n") + "\n"
        self.path.write_text(text, encoding="utf-8")
