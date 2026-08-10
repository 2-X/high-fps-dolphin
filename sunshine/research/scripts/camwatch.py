#!/usr/bin/env python3
"""Live camera-state watcher for the look-up extension bug (SMS USA).

Finds the CPolarSubCamera instance by MEM1 scan (unk268==0.0f && unk26C==1.0f
&& small mMode @+0x50 && ratio @+0xA8 in [0,1]), then samples ~20Hz:

    t  mode  ratio  E  deficit  lastmode  pitchT(deg)  pitchCur(deg)  posTy

Repro while it runs: extend camera fully up -> dive -> try stick-up.
The stuck state shows up as exactly one of:
  - mode changed & E stayed big        -> mode-zeroing (v4) missed/mismatched
  - E big, pitchT NOT lowered          -> hook A not applying (mode/branch)
  - pitchT lowered, posTy at ground,
    deficit == 0                       -> ground/water clamp outside hook D
  - deficit > 0 but view flat          -> hook C lookat raise not landing

Usage:  sudo SMS_DOL=main.dol venv/bin/python scripts/camwatch.py [seconds]
Writes scripts/camlog.txt
"""
import os, struct, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcmem import Dolphin, find_dolphin_pid

SCRATCH = 0x800016F0
GP_CAMERA = 0x8040D0A8   # CPolarSubCamera* (found by candidate-xref scan)

def find_camera(d):
    p = d.u32(GP_CAMERA)
    if p and 0x80000000 <= p < 0x81800000 and d.u32(p + 0x68):
        return [p]
    return []

def deg(s16v):
    if s16v >= 0x8000:
        s16v -= 0x10000
    return s16v * 180.0 / 32768.0

def main():
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    pid = find_dolphin_pid()
    if not pid:
        raise SystemExit("no Dolphin process")
    dol = os.environ.get("SMS_DOL", os.path.join(os.path.dirname(__file__), "..", "main.dol"))
    d = Dolphin(pid, dol)
    cams = find_camera(d)
    print(f"camera candidates: {[hex(c) for c in cams]}")
    if not cams:
        raise SystemExit("camera object not found")
    cam = cams[0]
    log = open(os.path.join(os.path.dirname(__file__), "camlog.txt"), "w")
    hdr = "t\tmode\tratio\tE\taCnt\teCnt\tdCnt\tdLast\tcCnt\tcLast\tposTy\tu18y\teyeY\tatY"
    print(hdr); log.write(f"# cam @ {cam:#x}\n" + hdr + "\n")
    t0 = time.time()
    last = None
    while time.time() - t0 < dur:
        u16 = lambda a: struct.unpack(">H", d.read(a, 2))[0]
        row = (
            d.u32(cam + 0x50),               # mode
            d.f32(cam + 0xA8),               # ratio
            d.f32(SCRATCH),                  # E (angle units)
            d.u32(SCRATCH + 0x38),           # hookA apply count
            d.u32(SCRATCH + 0x3C),           # hookE force count
            d.u32(SCRATCH + 0x28),           # hookD fire count
            d.f32(SCRATCH + 0x2C),           # hookD last deficit
            d.u32(SCRATCH + 0x30),           # hookC consume count
            d.f32(SCRATCH + 0x34),           # hookC last consumed
            d.f32(cam + 0x84),               # target camera y
            d.f32(cam + 0x9C),               # unk18.y (unrevised pos)
            d.f32(cam + 0x128),              # render eye y
            d.f32(cam + 0x14C),              # render at y
        )
        line = f"{time.time()-t0:7.2f}\t{row[0]}\t{row[1]:.3f}\t{row[2]:.0f}\t{row[3]}\t{row[4]}\t{row[5]}\t{row[6]:.0f}\t{row[7]}\t{row[8]:.0f}\t{row[9]:.0f}\t{row[10]:.0f}\t{row[11]:.0f}\t{row[12]:.0f}"
        if row != last:
            print(line)
        log.write(line + "\n")
        last = row
        time.sleep(0.05)
    log.close()

if __name__ == "__main__":
    main()
