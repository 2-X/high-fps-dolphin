#!/usr/bin/env python3
"""animrate_merge.py — unify the source + binary family-B audits into one ranked
master worklist for the fps-fix / boss-audit handoff.

INPUTS (produced by the sibling scripts)
  animrate-audit.csv    (animrate_audit.py, SOURCE)  — JP addresses, function names,
                        file:line; covers decompiled TUs; also has the MISUSE class
                        (arithmetic on SMSGetAnmFrameRate) the binary tool can't see.
  animrate-disasm.csv   (animrate_disasm.py, BINARY)  — USA addresses; covers the whole
                        ROM incl. stub TUs (popo, bosspakkun); no names.

WHY NOT A PER-ROW JOIN
  The two live in different address spaces (source=JP via GMSJ01 symbols, binary=USA),
  and there is no JP DOL / USA symbol map here to bridge them by fingerprint. So this
  does NOT invent a fragile cross-space row join. Instead it dedupes on the unit you
  actually fix — the ENCLOSING FUNCTION (one C2 hook per function, like v16) — grouping
  each tool's sites by function and ranking all groups on one severity scale.

SEVERITY (worst site in a function wins)
  0 PARAM     rate from an object/param field (mSL*, +0x16c(r3)) — Petey-class, tuned
              for 30Hz -> 4x fast. Highest value. From BOTH tools (named / USA-addr).
  1 MISUSE    SMSGetAnmFrameRate() read as a timing quantity (source-only class).
  2 COMPUTED  rate = arithmetic with no AnmFrameRate feed (may be a rate²).
  3 CONSTANT  rate = baked non-zero literal (1.0f/0.5f/…) — often cosmetic, still 4x.
  4 REVIEW    unresolved; needs eyes.

OVERLAP CAVEAT (printed in the output)
  A DECOMPILED-TU function is seen by BOTH tools: once as a SOURCE group (with a name)
  and once as a BINARY group (with a USA address) — they can't be auto-joined, so both
  appear. When you open the USA address in the disassembler you'll confirm it's the same
  function; fix it once. STUB-TU functions appear only as BINARY groups (that's the whole
  point of the sweep). Use SOURCE groups for names, BINARY groups for addresses.

USAGE
  animrate_merge.py                       # reads ../animrate-{audit,disasm}.csv, writes master
  animrate_merge.py --source A.csv --binary B.csv --out master
"""
import argparse, csv, os, re
from collections import defaultdict

SEV_LABEL = {0: "PARAM", 1: "MISUSE", 2: "COMPUTED", 3: "CONSTANT", 4: "REVIEW"}


def sev_source(row):
    cls, reason = row["class"], row["reason"].lower()
    if cls == "MISUSE":
        return 1
    if cls == "REVIEW":
        return 4
    # SUSPECT (raw setter): sub-type by the reason text
    if "param" in reason or "msl" in reason or ".get()" in reason:
        return 0
    if "literal" in reason:
        return 3
    return 2


def sev_binary(row):
    cls, note = row["class"], row["note"].lower()
    if cls == "REVIEW":
        return 4
    if re.search(r"\(r\d+\)", note):        # raw rate <- lfs +0xNN(rX)  = object param
        return 0
    if "computed" in note:
        return 2
    if "constant" in note:
        return 3
    return 2


def load_source(path):
    groups = defaultdict(lambda: dict(sites=[], sev=9, prov="SOURCE"))
    if not os.path.exists(path):
        return groups
    for r in csv.DictReader(open(path)):
        if r["class"] not in ("SUSPECT", "MISUSE", "REVIEW"):
            continue
        key = r["enclosing"] or f'{r["file"]}?'
        s = sev_source(r)
        g = groups[("SOURCE", key)]
        g["name"] = r["enclosing"]
        g["addr"] = r["jp_addr"]           # JP hint
        g["space"] = "JP"
        g["sev"] = min(g["sev"], s)
        g["sites"].append(dict(sev=s, where=f'{r["file"]}:{r["line"]}',
                               detail=r["reason"], code=r["code"]))
    return groups


def load_binary(path):
    groups = defaultdict(lambda: dict(sites=[], sev=9, prov="BINARY"))
    if not os.path.exists(path):
        return groups
    for r in csv.DictReader(open(path)):
        if r["class"] not in ("SUSPECT", "REVIEW"):
            continue
        key = r["enclosing_func"]
        s = sev_binary(r)
        g = groups[("BINARY", key)]
        g["name"] = r["func_name"]
        g["addr"] = r["enclosing_func"]    # USA func start
        g["space"] = "USA"
        g["sev"] = min(g["sev"], s)
        g["sites"].append(dict(sev=s, where=r["usa_addr"],
                               detail=r["note"], code=""))
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    here = os.path.join(os.getcwd(), "sunshine", "research")
    if not os.path.isdir(here):
        here = os.getcwd()
    ap.add_argument("--source", default=os.path.join(here, "animrate-audit.csv"))
    ap.add_argument("--binary", default=os.path.join(here, "animrate-disasm.csv"))
    ap.add_argument("--out", default=os.path.join(here, "animrate-master"))
    a = ap.parse_args()

    groups = {}
    groups.update(load_source(a.source))
    groups.update(load_binary(a.binary))

    rows = []
    for (prov, key), g in groups.items():
        g["sites"].sort(key=lambda s: s["sev"])
        rows.append(dict(prov=prov, key=key, name=g.get("name", ""),
                         addr=g.get("addr", ""), space=g.get("space", ""),
                         sev=g["sev"], n=len(g["sites"]), sites=g["sites"]))
    # one ranked master: severity, then USA before JP (fix-ready first), then size
    rows.sort(key=lambda r: (r["sev"], 0 if r["space"] == "USA" else 1, -r["n"]))

    from collections import Counter
    bysev = Counter(SEV_LABEL[r["sev"]] for r in rows)
    src_n = sum(1 for r in rows if r["prov"] == "SOURCE")
    bin_n = sum(1 for r in rows if r["prov"] == "BINARY")

    # ---- machine CSV: one row per SITE, with group id + rank ----
    with open(a.out + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["severity", "provenance", "func_addr", "space", "func_name",
                    "site_addr_or_loc", "detail"])
        for r in rows:
            for s in r["sites"]:
                w.writerow([SEV_LABEL[s["sev"]], r["prov"], r["addr"], r["space"],
                            r["name"] or r["key"], s["where"], s["detail"]])

    # ---- human MD: one row per FUNCTION work-item, globally ranked ----
    def fmt(r):
        nm = r["name"] or (r["key"] if r["prov"] == "SOURCE" else "—")
        addr = f'`{r["addr"]}`' if r["addr"] else "—"
        rep = r["sites"][0]["detail"].replace("|", "\\|")[:80]
        tag = "USA fix-ready" if r["space"] == "USA" else "JP hint"
        return (f'| {SEV_LABEL[r["sev"]]} | {r["prov"]} | {addr} ({tag}) '
                f'| `{nm}` | {r["n"]} | {rep} |')

    with open(a.out + ".md", "w") as f:
        f.write("# SMS high-fps family-B — MASTER worklist (source ∪ binary)\n\n")
        f.write(f"Function work-items: **{len(rows)}** "
                f"({bin_n} BINARY/USA-addr, {src_n} SOURCE/named).  "
                f"By severity: " + ", ".join(f"{k}={bysev[k]}" for k in
                ["PARAM","MISUSE","COMPUTED","CONSTANT","REVIEW"] if bysev[k]) + ".\n\n")
        f.write("**One row = one function to fix** (a single C2 hook usually covers all "
                "its sites, like v16). Ranked worst-severity first; within a severity, "
                "USA (fix-ready) before JP (named hint).\n\n")
        f.write("> **Overlap:** a decompiled-TU function appears twice — once BINARY "
                "(USA addr, no name) and once SOURCE (named, JP hint) — because the two "
                "address spaces can't be auto-joined. Confirm they're the same function "
                "when you open the USA address; fix once. Stub-TU functions (popo, "
                "bosspakkun, …) appear ONLY as BINARY rows.\n\n")
        f.write("| sev | from | func addr | name / key | sites | representative detail |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(fmt(r) + "\n")
        f.write("\n## Per-site detail (top PARAM + MISUSE work-items)\n\n")
        for r in [r for r in rows if r["sev"] <= 1][:40]:
            nm = r["name"] or r["key"]
            f.write(f'\n### {SEV_LABEL[r["sev"]]} · {r["prov"]} · `{r["addr"]}` `{nm}`\n')
            for s in r["sites"]:
                loc = s["where"]
                f.write(f'- `{loc}` — {s["detail"]}'
                        + (f'  `{s["code"]}`' if s["code"] else "") + "\n")

    print(f"merged: {len(rows)} function work-items "
          f"({bin_n} binary, {src_n} source)")
    print("  by severity: " + "  ".join(f"{k}={bysev[k]}" for k in
          ["PARAM","MISUSE","COMPUTED","CONSTANT","REVIEW"] if bysev[k]))
    print(f"  PARAM (Petey-class, do first): {bysev['PARAM']} functions")
    print(f"  wrote {a.out}.md and {a.out}.csv")


if __name__ == "__main__":
    main()
