#!/usr/bin/env python3
"""animrate_audit.py — static audit of the SMS high-fps "family-B" bug surface.

BACKGROUND (why this script exists)
-----------------------------------
At high fps the substep scheduler holds CUE_MOVE (physics + nerve/spine timers)
INVARIANT — those are already correct, so there is nothing to fix there. The one
leaking clock is the ANIMATION path: CUE_CALC_ANIM fires ~4x too often at 120fps.
The engine is *supposed* to cancel that out by making animation rates flow through
SMSGetAnmFrameRate() (forced to 0.5 by the fps bundle: 30x2 == 120x0.5 == 60
anim-units/s). Every high-fps animation bug found so far is a LEAK in that scheme:

  * raw anim-rate setters that bypass SMSGetAnmFrameRate — e.g. TBossPakkun::
    changeBck stuffing the raw mSLVomitAnmRate param into frameCtrl->rate (v16).
  * consumers that read SMSGetAnmFrameRate() and use it as a *timing quantity*
    (arithmetic / comparison / accumulation) rather than as a playback rate.

This script enumerates BOTH leak classes from the decomp so we stop finding them
one boss at a time. It is READ-ONLY. It does not touch the ROM, the INI, or fpspatch.

WHAT IT CLASSIFIES
------------------
1. Rate setters:  setFrameRate(RATE,i) | setRate(RATE) | ->rate = RATE | ->mRate = RATE
     CLEAN      RATE flows through SMSGetAnmFrameRate()   -> auto-compensated
     CLEAN      RATE is exactly 0 / 0.0f                  -> pause (0*anything == 0)
     SUSPECT    anything else (literal 1.0f, param mSL*, variable, expr)
                -> a RAW rate; advances 4x too fast at 120fps. Family-B bug candidate.
2. SMSGetAnmFrameRate() call-sites:
     PLAYBACK   result feeds a rate setter on the same line   -> auto-compensated
     MISUSE     result used in arithmetic/comparison/assignment -> timing misuse, bug
                candidate (reads the rate as if it were "frames elapsed").

Each row is tagged with its enclosing function and, best-effort, that function's
JP (GMSJ01) mangled symbol + address + size from config/GMSJ01/symbols.txt.
The JP address is a HINT: USA (GMSE01) is a per-TU fingerprint step (USA = JP - k),
which the fix chat does after picking a target from this table.

USAGE
-----
  animrate_audit.py                     # defaults to ~/code/sms, writes md+csv next to research/
  animrate_audit.py --root ~/code/sms --out ../animrate-audit
  animrate_audit.py --only suspect      # print only actionable rows to stdout
"""
import argparse, os, re, csv, sys

# ---- patterns -------------------------------------------------------------

ANM = "SMSGetAnmFrameRate"

# a rate-setter callsite; we capture the call kind and the raw argument text
RE_SETFRAMERATE = re.compile(r'\bsetFrameRate\s*\(')
RE_SETRATE      = re.compile(r'\bsetRate\s*\(')
RE_RATE_ASSIGN  = re.compile(r'->\s*(m?[Rr]ate)\s*=\s*([^;]+);')

RE_ANM_CALL     = re.compile(ANM + r'\s*\(\s*\)')

# an enclosing-function header: starts at column 0, has "(", not a control kw,
# not a bare declaration ending in ';'. Capture Class::method or bare name.
RE_FUNC_HEADER  = re.compile(r'^[A-Za-z_][^=;{}]*?\b(?:(\w+)::)?(\w+)\s*\([^;]*$')
KEYWORDS = {"if","for","while","switch","return","else","do","sizeof","new",
            "delete","case","typedef","struct","class","enum","template",
            "static_cast","reinterpret_cast","const_cast","dynamic_cast"}

# a rate arg is CLEAN only if it is exactly zero, or routes through AnmFrameRate.
RE_ZERO = re.compile(r'^-?0(\.0*f?)?$')


def balanced_arg(s, open_idx):
    """given s and index of '(', return the substring inside the outermost parens."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return s[open_idx+1:i]
    return s[open_idx+1:]  # unterminated (multiline) — take the rest


def first_arg(argtext):
    """first top-level comma-separated argument."""
    depth = 0
    for i, c in enumerate(argtext):
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == ',' and depth == 0:
            return argtext[:i].strip()
    return argtext.strip()


def classify_rate(rate):
    r = rate.strip()
    if ANM in r:
        return "CLEAN", "flows through SMSGetAnmFrameRate"
    if RE_ZERO.match(r):
        return "CLEAN", "pause (0)"
    # a bare 1.0f / 2.0f / literal, a param, a variable, or an expression:
    if re.match(r'^-?\d+(\.\d*)?f?$', r):
        return "SUSPECT", f"raw literal rate {r} (4x fast at 120fps)"
    if "mSL" in r or ".get()" in r or "getSaveParam" in r or "Param" in r:
        return "SUSPECT", f"raw param rate ({r})"
    return "SUSPECT", f"raw/computed rate ({r})"


def classify_anm_use(line, col):
    """is this SMSGetAnmFrameRate() call a playback feed (clean) or timing misuse?"""
    # playback: the call is the (first) argument to a rate setter on this line
    if re.search(r'\bset(Frame)?Rate\s*\(\s*' + ANM, line):
        return "CLEAN", "feeds rate setter (playback)"
    if re.search(r'->\s*m?[Rr]ate\s*=\s*' + ANM + r'\s*\(\s*\)\s*;', line):
        return "CLEAN", "assigned as frameCtrl rate (playback)"
    # look at the characters immediately around the call for operators
    tail = line[col:]
    head = line[:col]
    ctx = head[-24:] + "<<>>" + tail[:32]
    if re.search(r'[*/+\-]\s*' + ANM, line) or re.search(ANM + r'\s*\(\s*\)\s*[*/+\-]', line):
        return "MISUSE", f"arithmetic on rate: ...{ctx.strip()}..."
    if re.search(r'[<>=!]=?\s*' + ANM, line) or re.search(ANM + r'\s*\(\s*\)\s*[<>=!]', line):
        return "MISUSE", f"compared as timing: ...{ctx.strip()}..."
    # assigned into a non-rate variable -> likely stored as a per-tick delta
    m = re.search(r'(\w+)\s*=\s*' + ANM + r'\s*\(\s*\)\s*;', line)
    if m and not re.search(r'[Rr]ate|[Ss]peed', m.group(1)):
        return "MISUSE", f"stored into '{m.group(1)}' (not a rate var)"
    return "REVIEW", f"...{ctx.strip()}..."


# ---- symbol map (JP) ------------------------------------------------------

def load_symbols(path):
    """method -> list of (mangled, addr, size). keyed by demangled method name."""
    by_method = {}
    if not os.path.exists(path):
        return by_method
    rx = re.compile(r'^(\w+)__(\S+?)\s*=\s*\.text:(0x[0-9A-Fa-f]+);.*?size:(0x[0-9A-Fa-f]+)')
    for line in open(path, encoding="utf-8", errors="replace"):
        m = rx.match(line)
        if not m:
            continue
        method, mangled_tail, addr, size = m.groups()
        by_method.setdefault(method, []).append(
            (method + "__" + mangled_tail, int(addr, 16), int(size, 16)))
    return by_method


def resolve_symbol(by_method, cls, method):
    cands = by_method.get(method, [])
    if not cands:
        return None
    if cls:
        # mangling embeds the class as <len><ClassName>; require the name substring
        narrowed = [c for c in cands if cls in c[0]]
        if len(narrowed) == 1:
            return narrowed[0]
        if narrowed:
            return narrowed[0] + ("",) if False else narrowed[0]  # ambiguous, take first
    if len(cands) == 1:
        return cands[0]
    return cands[0]  # ambiguous; first is a hint


# ---- file scan ------------------------------------------------------------

def function_headers(lines):
    """return sorted list of (line_index, cls, method) for definition headers."""
    hdrs = []
    for i, ln in enumerate(lines):
        if ln[:1] in (" ", "\t", "#", "/", "*", "}", ""):
            continue
        m = RE_FUNC_HEADER.match(ln)
        if not m:
            continue
        method = m.group(2)
        if method in KEYWORDS:
            continue
        # avoid plain prototypes (end with ';') and macro lines
        if ln.rstrip().endswith(";"):
            continue
        hdrs.append((i, m.group(1), method))
    return hdrs


def enclosing(hdrs, idx):
    cls = method = None
    for i, c, m in hdrs:
        if i <= idx:
            cls, method = c, m
        else:
            break
    return cls, method


def scan_file(path, rel):
    text = open(path, encoding="utf-8", errors="replace").read()
    lines = text.splitlines()
    hdrs = function_headers(lines)
    rows = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        # --- rate setters ---
        for rx, kind in ((RE_SETFRAMERATE, "setFrameRate"), (RE_SETRATE, "setRate")):
            for m in rx.finditer(line):
                cls, meth = enclosing(hdrs, i)
                # skip the library setter's own definition (MActor::setFrameRate,
                # J3DFrameCtrl::setRate) — a passthrough of its float param, not a bug.
                if meth in ("setFrameRate", "setRate", "setNthData"):
                    continue
                arg = first_arg(balanced_arg(line, m.end()-1))
                cl, why = classify_rate(arg)
                rows.append(dict(kind="setter", call=kind, klass=cl, reason=why,
                                 file=rel, line=i+1, cls=cls, method=meth,
                                 code=stripped[:160]))
        for m in RE_RATE_ASSIGN.finditer(line):
            arg = m.group(2)
            cl, why = classify_rate(arg)
            cls, meth = enclosing(hdrs, i)
            rows.append(dict(kind="setter", call="->" + m.group(1) + "=", klass=cl,
                             reason=why, file=rel, line=i+1, cls=cls, method=meth,
                             code=stripped[:160]))

        # --- SMSGetAnmFrameRate consumers ---
        for m in RE_ANM_CALL.finditer(line):
            cl, why = classify_anm_use(line, m.start())
            cls, meth = enclosing(hdrs, i)
            rows.append(dict(kind="anm-use", call=ANM, klass=cl, reason=why,
                             file=rel, line=i+1, cls=cls, method=meth,
                             code=stripped[:160]))
    return rows


# ---- main -----------------------------------------------------------------

RANK = {"SUSPECT": 0, "MISUSE": 1, "REVIEW": 2, "CLEAN": 3, "PLAYBACK": 3}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.expanduser("~/code/sms"),
                    help="decomp checkout root (default ~/code/sms)")
    ap.add_argument("--symbols", default=None,
                    help="JP symbol map (default <root>/config/GMSJ01/symbols.txt)")
    ap.add_argument("--out", default=None,
                    help="output basename; writes .md and .csv (default: research/animrate-audit)")
    ap.add_argument("--only", choices=["suspect", "misuse", "actionable", "all"],
                    default="all", help="filter stdout summary")
    a = ap.parse_args()

    src = os.path.join(a.root, "src")
    if not os.path.isdir(src):
        sys.exit(f"no src/ under {a.root} — pass --root to the decomp checkout")
    symbols = a.symbols or os.path.join(a.root, "config", "GMSJ01", "symbols.txt")
    by_method = load_symbols(symbols)

    rows = []
    stubs = []  # decompiled-but-empty TUs the source audit is BLIND to
    for dirpath, _, files in os.walk(src):
        for fn in files:
            if fn.endswith((".cpp", ".c")):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, src)
                nonblank = sum(1 for l in open(full, encoding="utf-8",
                               errors="replace") if l.strip()
                               and not l.strip().startswith(("//", "#", "/*", "*")))
                if nonblank < 5:
                    stubs.append(rel)
                    continue
                rows.extend(scan_file(full, rel))

    # resolve JP symbols (hint) for every row
    for r in rows:
        sym = resolve_symbol(by_method, r["cls"], r["method"]) if r["method"] else None
        if sym:
            r["sym"], r["addr"], r["size"] = sym[0], sym[1], sym[2]
        else:
            r["sym"], r["addr"], r["size"] = "", None, None

    rows.sort(key=lambda r: (RANK.get(r["klass"], 4), r["file"], r["line"]))

    # counts
    from collections import Counter
    c = Counter(r["klass"] for r in rows)
    actionable = [r for r in rows if r["klass"] in ("SUSPECT", "MISUSE")]

    base = a.out or os.path.join(os.path.dirname(src), "..",
                                 "sunshine", "research", "animrate-audit")
    base = os.path.abspath(base)
    # if run from inside the repo, prefer the research dir
    if a.out is None:
        guess = os.path.join(os.getcwd(), "sunshine", "research", "animrate-audit")
        if os.path.isdir(os.path.dirname(guess)):
            base = guess

    # --- CSV ---
    with open(base + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class","kind","call","file","line","enclosing","jp_sym",
                    "jp_addr","jp_size","reason","code"])
        for r in rows:
            w.writerow([r["klass"], r["kind"], r["call"], r["file"], r["line"],
                        (f'{r["cls"]}::' if r["cls"] else "") + (r["method"] or ""),
                        r["sym"], f'{r["addr"]:#x}' if r["addr"] else "",
                        f'{r["size"]:#x}' if r["size"] else "", r["reason"], r["code"]])

    # --- Markdown ---
    def table(rs):
        out = ["| class | site | enclosing | JP addr (hint) | why | code |",
               "|---|---|---|---|---|---|"]
        for r in rs:
            enc = (f'{r["cls"]}::' if r["cls"] else "") + (r["method"] or "?")
            jp = f'`{r["addr"]:#x}`' if r["addr"] else "—"
            code = r["code"].replace("|", "\\|")
            out.append(f'| **{r["klass"]}** | {r["file"]}:{r["line"]} | `{enc}` '
                       f'| {jp} | {r["reason"]} | `{code}` |')
        return "\n".join(out)

    with open(base + ".md", "w") as f:
        f.write("# SMS high-fps family-B audit (animation-rate leaks)\n\n")
        f.write(f"Source: `{a.root}`  ·  symbols: `{os.path.relpath(symbols, a.root)}`"
                f"  ·  {'symbols loaded' if by_method else 'NO SYMBOLS (addr hints blank)'}\n\n")
        f.write("Counts: " + ", ".join(f"**{k}** {c[k]}" for k in
                ["SUSPECT","MISUSE","REVIEW","CLEAN"] if c[k]) + "\n\n")
        f.write("JP addresses are hints — resolve USA (GMSE01) per-TU (USA = JP − k) "
                "before writing a Gecko fix.\n\n")
        f.write("## Actionable — raw rate setters (SUSPECT)\n\n")
        f.write(table([r for r in rows if r["klass"] == "SUSPECT"]) + "\n\n")
        f.write("## Actionable — SMSGetAnmFrameRate timing misuse (MISUSE)\n\n")
        f.write(table([r for r in rows if r["klass"] == "MISUSE"]) + "\n\n")
        f.write("## Needs eyes — ambiguous AnmFrameRate use (REVIEW)\n\n")
        f.write(table([r for r in rows if r["klass"] == "REVIEW"]) + "\n\n")
        f.write(f"## Clean (auto-compensated / pause) — {c['CLEAN']} rows, see CSV\n\n")
        f.write("## Blind spots — stub TUs the source audit CANNOT see\n\n")
        f.write("These `.cpp` are empty stubs in the decomp, so any raw-rate setter "
                "they contain is invisible here and must be found via the binary-disasm "
                "path (disassemble `main.dol`, find `bl` sites to `MActor::setFrameRate` "
                "/ `J3DFrameCtrl::setRate` inside each TU's address range). Poink v14 and "
                "Petey v16 both live in stub TUs — proof the disasm sweep is required, "
                "not optional.\n\n")
        for s in sorted(stubs):
            f.write(f"- `{s}`\n")

    # --- stdout summary ---
    print(f"scanned {a.root}/src : {len(rows)} anim-rate sites")
    print("  " + "  ".join(f"{k}={c[k]}" for k in ["SUSPECT","MISUSE","REVIEW","CLEAN"]))
    print(f"  actionable (SUSPECT+MISUSE): {len(actionable)}")
    print(f"  blind-spot stub TUs (need disasm path): {len(stubs)}"
          + (f"  incl. {', '.join(s for s in stubs if os.path.basename(s) in ('popo.cpp','bosspakkun.cpp'))}"
             if any(os.path.basename(s) in ('popo.cpp','bosspakkun.cpp') for s in stubs) else ""))
    print(f"  wrote {base}.md and {base}.csv")
    if not by_method:
        print("  WARNING: no symbols loaded — JP address hints are blank")

    show = {"suspect": ["SUSPECT"], "misuse": ["MISUSE"],
            "actionable": ["SUSPECT","MISUSE"], "all": []}[a.only]
    if show:
        print()
        for r in [r for r in rows if r["klass"] in show]:
            enc = (f'{r["cls"]}::' if r["cls"] else "") + (r["method"] or "?")
            jp = f'{r["addr"]:#x}' if r["addr"] else "—"
            print(f'  [{r["klass"]}] {r["file"]}:{r["line"]}  {enc}  jp={jp}  {r["reason"]}')


if __name__ == "__main__":
    main()
