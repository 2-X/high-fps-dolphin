#!/usr/bin/env python3
"""
input_sync.py — translate Dolphin input INIs between PC and Mac dialects.

The SAME bindings enumerate under different device + token names on each OS:

  keyboard  PC: DInput/0/Keyboard Mouse            Mac: Quartz/0/Keyboard & Mouse
  Xbox pad  PC: WGInput/0/Xbox One Game Controller Mac: SDL/0/Xbox One Wireless Controller
  key names PC: SPACE LSHIFT RETURN UP APOSTROPHE  Mac: Space "Left Shift" Return "Up Arrow" '
  pad faces PC: Button A/B/X/Y                      Mac: Button S/E/W/N  (South/East/West/North)

Copying a PC config onto the Mac verbatim leaves the keyboard bound to a device
that does not exist there, so nothing binds. This translates the device strings
and control tokens so the ported bindings actually work.

RELIABLE: the keyboard half is a deterministic 1:1 map.
BEST-EFFORT: the controller half depends on how the pad enumerates. After
translating, open Dolphin once and re-pick the device if it differs; the
per-button bindings carry. See sunshine/HANDOFF-MAC.md "Input configs".

Usage:
  input_sync.py --to mac  GCPadNew.ini            > GCPadNew.mac.ini
  input_sync.py --to pc   GCPadNew.ini -o out.ini
  input_sync.py --selftest                        # verify against mac-originals/
"""
import argparse, os, re, sys, difflib

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DCFG = os.path.join(REPO, "dolphin-config")

# --- device names -----------------------------------------------------------
DEVICE_PC2MAC = {
    "DInput/0/Keyboard Mouse":            "Quartz/0/Keyboard & Mouse",
    "WGInput/0/Xbox One Game Controller": "SDL/0/Xbox One Wireless Controller",
}
# --- keyboard control tokens (PC -> Mac) ------------------------------------
KEY_PC2MAC = {
    "SPACE": "Space", "LSHIFT": "Left Shift", "RSHIFT": "Right Shift",
    "LCONTROL": "Left Control", "RCONTROL": "Right Control",
    "RMENU": "Right Alt", "LMENU": "Left Alt",
    "LWIN": "Left Command", "RWIN": "Right Command",
    "RETURN": "Return", "BACK": "Backspace", "TAB": "Tab", "ESCAPE": "Escape",
    "CAPITAL": "Caps Lock", "DELETE": "Delete", "INSERT": "Insert",
    "HOME": "Home", "END": "End", "PRIOR": "Page Up", "NEXT": "Page Down",
    "UP": "Up Arrow", "DOWN": "Down Arrow", "LEFT": "Left Arrow", "RIGHT": "Right Arrow",
    "SEMICOLON": ";", "APOSTROPHE": "'", "MINUS": "-", "EQUALS": "=",
    "LBRACKET": "[", "RBRACKET": "]", "COMMA": ",", "PERIOD": ".",
    "SLASH": "/", "BACKSLASH": "\\", "GRAVE": "Paragraph", "MULTIPLY": "Keypad *",
}
# --- Xbox pad control tokens (PC/WGInput -> Mac/SDL) -------------------------
PAD_PC2MAC = {
    "Button A": "Button S", "Button B": "Button E",
    "Button X": "Button W", "Button Y": "Button N",
    "Bumper L": "Shoulder L", "Bumper R": "Shoulder R",
    "Menu": "Start",                       # WGInput "Menu" collapses onto SDL "Start"
    "Switch 0 N": "Pad N", "Switch 0 S": "Pad S",
    "Switch 0 W": "Pad W", "Switch 0 E": "Pad E",
}

def _invert(d):
    out = {}
    for k, v in d.items():
        out.setdefault(v, k)   # first wins -> lossy collapses map back to canonical
    return out

DEVICE_MAC2PC = _invert(DEVICE_PC2MAC)
KEY_MAC2PC = _invert(KEY_PC2MAC)
PAD_MAC2PC = _invert(PAD_PC2MAC)

def _maps(direction):
    if direction == "mac":
        return DEVICE_PC2MAC, {**KEY_PC2MAC, **PAD_PC2MAC}
    return DEVICE_MAC2PC, {**KEY_MAC2PC, **PAD_MAC2PC}

def _map_seg(seg, devmap, ctrlmap):
    """A backtick binding segment: 'device:control' OR a bare 'control'
    (profiles omit the device, taking it from the Device= line)."""
    if ":" in seg:                           # device names never contain ':'
        dev, ctrl = seg.split(":", 1)
        return f"{devmap.get(dev, dev)}:{ctrlmap.get(ctrl, ctrl)}"
    return ctrlmap.get(seg, seg)             # bare control

def translate(text, direction):
    devmap, ctrlmap = _maps(direction)
    out = []
    for line in text.splitlines():
        if "=" not in line or line.lstrip().startswith("["):
            out.append(line); continue
        key, _, val = line.partition("=")
        # backtick-quoted `device:control` segments joined by |
        if "`" in val:
            def repl(m): return "`" + _map_seg(m.group(1), devmap, ctrlmap) + "`"
            newval = re.sub(r"`([^`]*)`", repl, val)
            # drop duplicate tokens a lossy map can produce (Switch0|Pad, Menu|Start)
            toks = [t for t in newval.strip().split("|")]
            seen, dedup = set(), []
            for t in toks:
                if t not in seen:
                    seen.add(t); dedup.append(t)
            out.append(f"{key}= " + "|".join(dedup))
        elif key.strip() == "Device":
            out.append(f"{key}= " + devmap.get(val.strip(), val.strip()))
        else:
            out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")

def selftest():
    """Translate every PC pad/profile config to Mac and diff against the hand-made
    mac-originals. GCKeyNew.ini (the GC *Keyboard* controller — unused by Sunshine,
    and a different `Keys/X = token` line shape) is intentionally out of scope."""
    pairs = [("GCPadNew.ini", "GCPadNew.ini")]
    prof = os.path.join("Profiles", "GCPad")
    src_prof = os.path.join(DCFG, prof)
    if os.path.isdir(src_prof):
        for fn in sorted(os.listdir(src_prof)):
            if fn.endswith(".ini"):
                pairs.append((os.path.join(prof, fn), os.path.join(prof, fn)))
    ok = True
    for pc_rel, mac_rel in pairs:
        pc = os.path.join(DCFG, pc_rel)
        mac = os.path.join(DCFG, "mac-originals", mac_rel)
        if not (os.path.exists(pc) and os.path.exists(mac)):
            continue
        got = translate(open(pc, encoding="utf-8").read(), "mac")
        want = open(mac, encoding="utf-8").read()
        # compare binding VALUES only; ignore Mac-only lines PC never had
        # (e.g. mouse Button 6/7 stick modifiers) and key-name-only rows.
        gset = {l.split("=")[0].strip(): l for l in got.splitlines() if "`" in l or l.startswith("Device")}
        wset = {l.split("=")[0].strip(): l for l in want.splitlines() if "`" in l or l.startswith("Device")}
        diffs = []
        for k in sorted(set(gset) & set(wset)):
            g, w = gset[k].replace(" ", ""), wset[k].replace(" ", "")
            if g == w:
                continue
            # Two documented, intentional deltas between PC (source) and the
            # older mac-originals (HANDOFF-MAC.md "Input configs"):
            #   * Buttons/Z keyboard: PC=C, mac-original=Tab  (carry C forward)
            #   * Mac-only mouse Button 6/7 as stick modifiers (PC dropped them)
            if k == "Buttons/Z" and g.endswith("Mouse:C`") and w.endswith("Mouse:Tab`"):
                continue
            if k.endswith("/Modifier") and w.replace(g, "") in (
                "|`Quartz/0/Keyboard&Mouse:Button6`", "|`Quartz/0/Keyboard&Mouse:Button7`"):
                continue
            diffs.append((k, gset[k], wset[k]))
        tag = "ok " if not diffs else "DIFF"
        print(f"[{tag}] {pc_rel}")
        for k, g, w in diffs:
            print(f"        {k}\n     got:  {g}\n     want: {w}")
        ok = ok and not diffs
    print("\nSELFTEST", "PASSED" if ok else "FAILED (diffs above; may be intentional Mac-only binds)")
    return 0 if ok else 1

def main():
    ap = argparse.ArgumentParser(description="Translate Dolphin input INIs between PC and Mac dialects.")
    ap.add_argument("infile", nargs="?")
    ap.add_argument("--to", choices=["mac", "pc"], help="target dialect")
    ap.add_argument("-o", "--out", help="output file (default: stdout)")
    ap.add_argument("--selftest", action="store_true", help="verify translation vs mac-originals/")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not (a.infile and a.to):
        ap.error("need INFILE and --to (or --selftest)")
    res = translate(open(a.infile, encoding="utf-8").read(), a.to)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(res)
        print(f"wrote {a.out}", file=sys.stderr)
    else:
        sys.stdout.write(res)

if __name__ == "__main__":
    main()
