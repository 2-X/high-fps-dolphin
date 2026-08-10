#!/usr/bin/env python3
"""animrate_disasm.py — binary companion to animrate_audit.py.

WHY THIS EXISTS
---------------
animrate_audit.py reads the decomp SOURCE, so it is blind to the ~85 stub TUs that
doldecomp hasn't decompiled yet — including popo.cpp and bosspakkun.cpp, where the
Poink-v14 and Petey-v16 animation-rate bugs actually live. This script closes that
gap by sweeping the USA ROM (`main.dol`, GMSE01) directly for the same family-B leak:
animation frame-rates set from a RAW value instead of flowing through
SMSGetAnmFrameRate() (which the fps bundle forces to 0.5 so anim playback stays 60
units/s). A raw rate advances 4x too fast at 120fps — the Petey-barf-window shape.

ANCHORS (discovered from main.dol, not guessed)
-----------------------------------------------
  SMSGetAnmFrameRate   0x802A7BD8   returns the (compensated) rate in f1
  SMSGetVSyncTimesPerSec 0x802A7C48
  MActor::setFrameRate 0x80238E7C   setFrameRate(f1=rate, r4=idx); stfs f1,0x10(ctrl)
  MActor::getFrameCtrl 0x80238F08   returns ctrl; callers then inline `stfs fN,0xc(ctrl)`
  framerate global     0x804167B8   (SDA: -0x3c8(r2), so r2base ~= 0x80416B80)
Override any with flags if a future ROM shifts them.

WHAT IT FINDS
-------------
Two bl-anchored rate-set shapes, each classified by tracing the rate FPR backward
to its nearest writer within the basic block:

  setFrameRate site         rate = f1
  getFrameCtrl + inline stfs rate = the stored FPR

  CLEAN    nearest writer is the result of `bl SMSGetAnmFrameRate` (compensated)
  SUSPECT  nearest writer is a raw `lfs fR, off(rX)` (a param/const) with no
           AnmFrameRate feeding it  -> raw rate, 4x fast. Reports off(rX) as the
           param location (e.g. Petey's +0x16c).
  REVIEW   nearest writer is arithmetic (fmuls/fadds/…) — could be a legit scale or
           a rate² (e.g. splash gravity). Operands printed for a human.

Output mirrors animrate_audit (md + csv) so the two merge into one triage table.
This is a HEURISTIC disassembly classifier — every SUSPECT/REVIEW row is a lead to
confirm at the named USA address, not a proven bug. READ-ONLY.

USAGE
  SMS_DOL=main.dol animrate_disasm.py                 # writes research/animrate-disasm.{md,csv}
  SMS_DOL=main.dol animrate_disasm.py --only suspect
  SMS_DOL=main.dol animrate_disasm.py --usa-map usa_symbols.txt   # optional name resolution
"""
import argparse, os, struct, csv, sys, re
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

ANM_FRAME_RATE = 0x802A7BD8
SET_FRAME_RATE = 0x80238E7C
GET_FRAME_CTRL = 0x80238F08
R2_BASE        = 0x80416B80          # so -0x3c8(r2) == framerate global 0x804167B8
FRAMERATE_GLOBAL = 0x804167B8


class Dol:
    def __init__(self, path):
        d = open(path, "rb").read()
        self.d = d
        th_off = struct.unpack(">7I", d[0x00:0x1C]); th_a = struct.unpack(">7I", d[0x48:0x64])
        th_s = struct.unpack(">7I", d[0x90:0xAC])
        da_off = struct.unpack(">11I", d[0x1C:0x48]); da_a = struct.unpack(">11I", d[0x64:0x90])
        da_s = struct.unpack(">11I", d[0xAC:0xD8])
        self.text = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]
        # all mapped segments (text+data) for reading constants; bss is not in the file
        self.segs = self.text + [(a, a + s, o) for o, a, s in zip(da_off, da_a, da_s) if s]

    def u32(self, va):
        for a0, a1, o in self.text:
            if a0 <= va < a1:
                return struct.unpack(">I", self.d[o + va - a0:o + va - a0 + 4])[0]
        return None

    def read_f32(self, va):
        """read a float from any mapped segment; None if in bss/unmapped."""
        for a0, a1, o in self.segs:
            if a0 <= va < a1:
                return struct.unpack(">f", self.d[o + va - a0:o + va - a0 + 4])[0]
        return None

    def fstart(self, a, floor=0x80003100):
        while a > floor:
            if self.u32(a - 4) == 0x4E800020:  # blr terminating previous func
                return a
            a -= 4
        return floor


def bl_target(w, a):
    if w is None or (w >> 26) != 18 or (w & 3) != 1:  # I-form, LK=1, AA=0
        return None
    off = w & 0x03FFFFFC
    if off & 0x02000000:
        off -= 0x04000000
    return (a + off) & 0xFFFFFFFF


def find_bl_sites(dol, target):
    out = []
    for a0, a1, o in dol.text:
        seg = dol.d[o:o + (a1 - a0)]
        for j in range(0, len(seg) - 4, 4):
            w = struct.unpack(">I", seg[j:j + 4])[0]
            if bl_target(w, a0 + j) == target:
                out.append(a0 + j)
    return out


# ---- lightweight field decoders for the instrs we care about --------------

def is_stfs(w):        # stfs frS, d(rA)   (opcode 52)
    if (w >> 26) != 52: return None
    return dict(frS=(w >> 21) & 31, rA=(w >> 16) & 31, d=sext16(w & 0xFFFF))

def is_lfs(w):         # lfs frD, d(rA)    (opcode 48)
    if (w >> 26) != 48: return None
    return dict(frD=(w >> 21) & 31, rA=(w >> 16) & 31, d=sext16(w & 0xFFFF))

def is_fmr(w):         # fmr frD, frB      (opcode 63, xo=72)
    if (w >> 26) != 63 or ((w >> 1) & 0x3FF) != 72: return None
    return dict(frD=(w >> 21) & 31, frB=(w >> 11) & 31)

FARITH = {21: "fadds", 20: "fsubs", 25: "fmuls", 18: "fdivs"}  # opcode 59 xo (A-form)
def is_farith(w):      # opcode 59, A-form: frD, frA, frB(, frC)
    if (w >> 26) != 59: return None
    xo = (w >> 1) & 0x1F
    if xo not in FARITH: return None
    return dict(op=FARITH[xo], frD=(w >> 21) & 31, frA=(w >> 16) & 31,
                frB=(w >> 11) & 31, frC=(w >> 6) & 31)

def sext16(x):
    return x - 0x10000 if x & 0x8000 else x

def is_branch(w):      # any branch (used as basic-block boundary)
    op = w >> 26
    return op in (16, 18) or (op == 19 and ((w >> 1) & 0x3FF) in (16, 528))


def sda_note(rA, d):
    if rA == 2:
        tgt = (R2_BASE + d) & 0xFFFFFFFF
        if tgt == FRAMERATE_GLOBAL:
            return f"framerate-global(0x804167B8)"
        return f"r2{d:+#x}=0x{tgt:08x}"
    if rA == 13:
        return f"r13{d:+#x}"
    return f"{d:+#x}(r{rA})"


# ---- classify one rate-set site -------------------------------------------

def classify_const(val):
    """a rate loaded from a resolvable constant: 0 is pause (clean), else raw (4x)."""
    if val is None:
        return None
    if abs(val) < 1e-9:
        return "CLEAN", "rate <- constant 0.0 (pause)"
    return "SUSPECT", f"raw rate <- constant {val:g} (4x fast at 120fps)"


def trace_rate(dol, store_addr, rate_fpr, func_start, window=18):
    """Walk backward from store_addr for the nearest writer of rate_fpr.
    Returns (klass, note)."""
    saw_anm = False
    fpr = rate_fpr
    a = store_addr - 4
    steps = 0
    while a >= func_start and steps < window:
        w = dol.u32(a)
        if w is None:
            break
        if bl_target(w, a) == ANM_FRAME_RATE:
            saw_anm = True
            # AnmFrameRate result is f1; if we're currently tracing f1, this is the writer
            if fpr == 1:
                return "CLEAN", "rate = SMSGetAnmFrameRate() (compensated)"
        fm = is_fmr(w)
        if fm and fm["frD"] == fpr:
            fpr = fm["frB"]            # follow the move
            a -= 4; steps += 1; continue
        lf = is_lfs(w)
        if lf and lf["frD"] == fpr:
            src = sda_note(lf["rA"], lf["d"])
            if "framerate-global" in src:
                return "CLEAN", f"rate loaded from {src}"
            # r2/r13-relative or absolute -> a resolvable constant/global: read its value
            if lf["rA"] in (2, 13):
                base = R2_BASE if lf["rA"] == 2 else 0x804141C0
                verdict = classify_const(dol.read_f32((base + lf["d"]) & 0xFFFFFFFF))
                if verdict:
                    return verdict[0], verdict[1] + f"  [{src}]"
            # object/param-relative (runtime value) -> the dangerous Petey-class raw param
            return "SUSPECT", f"raw rate <- lfs {src} (4x fast at 120fps)"
        fa = is_farith(w)
        if fa and fa["frD"] == fpr:
            # computed. is either operand the AnmFrameRate result (f1) or is this a rate²?
            note = f"{fa['op']} f{fa['frA']},f{fa['frB']}"
            if saw_anm or fa["frA"] == 1 or fa["frB"] == 1:
                return "REVIEW", f"computed rate ({note}); AnmFrameRate in block — verify scaling/rate²"
            return "SUSPECT", f"computed raw rate ({note}); no AnmFrameRate feed"
        tgt = bl_target(w, a)
        if tgt is not None:            # a CALL (LK=1)
            if tgt == ANM_FRAME_RATE and fpr == 1:
                return "CLEAN", "rate = SMSGetAnmFrameRate() (compensated)"
            if fpr <= 13:              # volatile FPR is clobbered by the call
                return "REVIEW", f"f{fpr} clobbered by bl 0x{tgt:08x}; source unresolved"
            # non-volatile FPR (f14-f31) survives the call -> keep tracing past it
            a -= 4; steps += 1; continue
        op = w >> 26                   # non-call: stop only at a hard CFG boundary
        if op == 18 or (op == 19 and ((w >> 1) & 0x3FF) in (16, 528)):  # b / blr / bctr
            break
        a -= 4; steps += 1
    if saw_anm:
        return "CLEAN", "AnmFrameRate in block, no raw override found"
    return "REVIEW", f"rate f{rate_fpr} source not resolved in block"


def sweep(dol):
    rows = []
    # (1) MActor::setFrameRate callers — rate is f1
    for site in find_bl_sites(dol, SET_FRAME_RATE):
        fs = dol.fstart(site)
        klass, note = trace_rate(dol, site, 1, fs)
        rows.append(dict(kind="setFrameRate", addr=site, func=fs, klass=klass, note=note))
    # (2) getFrameCtrl callers followed by an inline stfs fN,0xc/0x10(r3) — rate is fN
    for site in find_bl_sites(dol, GET_FRAME_CTRL):
        # find the inline store of the returned ctrl within the next few instrs
        store = None; rate_fpr = None
        for k in range(1, 7):
            w = dol.u32(site + 4 * k)
            st = is_stfs(w) if w else None
            if st and st["rA"] == 3 and st["d"] in (0x0c, 0x10):  # ctrl+rate field
                store = site + 4 * k; rate_fpr = st["frS"]; break
            if w and (is_branch(w) or bl_target(w, site + 4 * k)):  # r3 likely clobbered
                break
        if store is None:
            continue
        fs = dol.fstart(site)
        klass, note = trace_rate(dol, store, rate_fpr, fs)
        rows.append(dict(kind="getFrameCtrl+stfs", addr=store, func=fs,
                         klass=klass, note=note))
    # dedupe by store address
    seen = {}
    for r in rows:
        seen[r["addr"]] = r
    return list(seen.values())


def load_usa_map(path):
    """optional: name__mangled = .text:0xADDR;  ->  {func_start_addr: name}."""
    m = {}
    if not path or not os.path.exists(path):
        return m
    rx = re.compile(r'^(\S+?)\s*=\s*\.text:(0x[0-9A-Fa-f]+)')
    for line in open(path, encoding="utf-8", errors="replace"):
        g = rx.match(line)
        if g:
            m[int(g.group(2), 16)] = g.group(1)
    return m


RANK = {"SUSPECT": 0, "REVIEW": 1, "CLEAN": 2}


def main():
    global SET_FRAME_RATE, GET_FRAME_CTRL, ANM_FRAME_RATE
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dol", default=os.environ.get("SMS_DOL", "main.dol"))
    ap.add_argument("--usa-map", default=None, help="optional USA symbol map for names")
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", choices=["suspect", "review", "actionable", "all"],
                    default="all")
    ap.add_argument("--set-frame-rate", type=lambda x: int(x, 16), default=SET_FRAME_RATE)
    ap.add_argument("--get-frame-ctrl", type=lambda x: int(x, 16), default=GET_FRAME_CTRL)
    ap.add_argument("--anm-rate", type=lambda x: int(x, 16), default=ANM_FRAME_RATE)
    a = ap.parse_args()

    SET_FRAME_RATE, GET_FRAME_CTRL, ANM_FRAME_RATE = a.set_frame_rate, a.get_frame_ctrl, a.anm_rate

    if not os.path.exists(a.dol):
        sys.exit(f"no DOL at {a.dol} (set SMS_DOL or --dol)")
    dol = Dol(a.dol)
    names = load_usa_map(a.usa_map)
    rows = sweep(dol)
    for r in rows:
        r["name"] = names.get(r["func"], "")
        # sub-priority within SUSPECT: runtime object-param (Petey-class) first,
        # then computed rates, then baked constants.
        if r["klass"] == "SUSPECT":
            if re.search(r"\(r\d+\)", r["note"]):
                r["prio"] = 0          # raw param from an object field — most dangerous
            elif "computed" in r["note"]:
                r["prio"] = 1
            else:
                r["prio"] = 2          # baked literal constant
        else:
            r["prio"] = 5
    rows.sort(key=lambda r: (RANK.get(r["klass"], 3), r["prio"], r["addr"]))

    from collections import Counter
    c = Counter(r["klass"] for r in rows)

    base = a.out or os.path.join(os.getcwd(), "sunshine", "research", "animrate-disasm")
    if a.out is None and not os.path.isdir(os.path.dirname(base)):
        base = os.path.join(os.path.dirname(os.path.abspath(a.dol)), "animrate-disasm")

    with open(base + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class", "kind", "usa_addr", "enclosing_func", "func_name", "note"])
        for r in rows:
            w.writerow([r["klass"], r["kind"], f'{r["addr"]:#x}', f'{r["func"]:#x}',
                        r["name"], r["note"]])

    def table(rs):
        out = ["| class | USA addr | enclosing func | kind | note |",
               "|---|---|---|---|---|"]
        for r in rs:
            nm = f' `{r["name"]}`' if r["name"] else ""
            out.append(f'| **{r["klass"]}** | `{r["addr"]:#x}` | `{r["func"]:#x}`{nm} '
                       f'| {r["kind"]} | {r["note"]} |')
        return "\n".join(out)

    with open(base + ".md", "w") as f:
        f.write("# SMS high-fps family-B — binary disasm sweep (stub-TU coverage)\n\n")
        f.write(f"DOL: `{os.path.abspath(a.dol)}`  ·  anchors: setFrameRate "
                f"`{SET_FRAME_RATE:#x}`, getFrameCtrl `{GET_FRAME_CTRL:#x}`, "
                f"AnmFrameRate `{ANM_FRAME_RATE:#x}`\n\n")
        f.write("Counts: " + ", ".join(f"**{k}** {c[k]}" for k in
                ["SUSPECT", "REVIEW", "CLEAN"] if c[k]) + "\n\n")
        f.write("Heuristic classifier — confirm each SUSPECT/REVIEW at its USA address. "
                "Sites here that also appear in `animrate-audit` are cross-validation; "
                "sites in **stub TUs** (popo, bosspakkun, …) appear ONLY here.\n\n")
        top = [r for r in rows if r["klass"] == "SUSPECT" and r["prio"] == 0]
        f.write(f"## ★ Highest priority — runtime object-param rates (Petey-class), {len(top)}\n\n")
        f.write("A rate loaded from an object/param field (e.g. `mSLVomitAnmRate` at "
                "+0x16c) and set raw — tuned for 30Hz, so 4x fast at 120fps. Petey v16 "
                "(`0x800955cc`) is in this list. Fix shape: gate on the framerate global "
                "and scale, exactly like v16.\n\n")
        f.write(table(top) + "\n\n")
        f.write("## SUSPECT — computed & baked-constant raw rates (4x fast)\n\n")
        f.write(table([r for r in rows if r["klass"] == "SUSPECT" and r["prio"] != 0]) + "\n\n")
        f.write("## REVIEW — computed / unresolved\n\n")
        f.write(table([r for r in rows if r["klass"] == "REVIEW"]) + "\n\n")
        f.write(f"## CLEAN — {c['CLEAN']} sites (see CSV)\n")

    print(f"swept {a.dol}: {len(rows)} rate-set sites")
    print("  " + "  ".join(f"{k}={c[k]}" for k in ["SUSPECT", "REVIEW", "CLEAN"]))
    print(f"  actionable (SUSPECT+REVIEW): {sum(1 for r in rows if r['klass'] in ('SUSPECT','REVIEW'))}")
    print(f"  wrote {base}.md and {base}.csv")

    show = {"suspect": ["SUSPECT"], "review": ["REVIEW"],
            "actionable": ["SUSPECT", "REVIEW"], "all": []}[a.only]
    if show:
        print()
        for r in [r for r in rows if r["klass"] in show]:
            print(f'  [{r["klass"]}] {r["addr"]:#x} func={r["func"]:#x} {r["kind"]}  {r["note"]}')


if __name__ == "__main__":
    main()
