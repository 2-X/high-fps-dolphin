"""Passive watcher for the Dune Bud (SandBombBase) JPA-0x55 registration bug.

Read-only. Polls the live BSMSO game ~1 Hz and logs, per scene:
  - gpResourceManager pointer (changes = scene reload)
  - registry count/capacity (silent-drop overflow check)
  - once-flag[0x55] (0x803FD0BD) vs "id 0x55 present in registry"

The moment a SandBombBase initializes (flag flips to 1), we learn which
failure mode is real:
  flag=1, 0x55 registered     -> registration fine; NULL emit = emitter-pool/other
  flag=1, 0x55 NOT registered -> load() failed/dropped (overflow if count>=cap)
  flag=1 BEFORE scene had any SandBomb -> stale-flag/stomp path

Log: /tmp/dunebud-watch.log
"""
import struct
import sys
import time

import macmem
from set_bse_fps import find_mem1_base

R13 = 0x804141C0
GP_RESOURCE_MANAGER = R13 - 0x5FE0   # 0x8040E1E0
FLAG_ARRAY = 0x803FD068              # u8[0x201], flag[id]
LOG = "/tmp/dunebud-watch.log"


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def main():
    m = None
    while m is None:
        pid = macmem.find_dolphin_pid()
        if pid:
            cand = macmem.DolphinMem(pid)
            if find_mem1_base(cand, timeout_s=10):
                m = cand
                log(f"watching pid {pid}")
                break
        log("waiting for a booted game (MEM1 not present)...")
        time.sleep(10)

    def r32(a):
        b = m.read(a, 4)
        return struct.unpack(">I", b)[0] if b else None

    def registry_ids():
        rm = r32(GP_RESOURCE_MANAGER)
        if not rm or not (0x80000000 <= rm < 0x83000000):
            return rm, None, None, None
        reg = r32(rm + 4)
        if not reg:
            return rm, None, None, None
        cnt, cap, arr = r32(reg), r32(reg + 4), r32(reg + 8)
        ids = set()
        if arr and cnt is not None:
            n = min(cnt, cap)
            raw = m.read(arr, 4 * n)
            if raw:
                for p in struct.unpack(f">{n}I", raw):
                    if p:
                        b = m.read(p + 6, 2)
                        if b:
                            ids.add(struct.unpack(">H", b)[0])
        return rm, cnt, cap, ids

    last_rm = None
    last_flag55 = None
    reported_this_scene = False
    while True:
        try:
            rm, cnt, cap, ids = registry_ids()
            fb = m.read(FLAG_ARRAY + 0x55, 1)
            flag55 = fb[0] if fb else None

            if rm != last_rm:
                log(f"scene change: mgr={hex(rm) if rm else rm} count={cnt}/{cap} "
                    f"flag55={flag55} has55={ids is not None and 0x55 in ids}")
                last_rm = rm
                reported_this_scene = False

            if flag55 != last_flag55:
                log(f"flag55 {last_flag55} -> {flag55} | count={cnt}/{cap} "
                    f"has55={ids is not None and 0x55 in ids}")
                last_flag55 = flag55

            if flag55 == 1 and not reported_this_scene and ids is not None:
                has55 = 0x55 in ids
                verdict = ("REGISTERED-OK (NULL must be emit-time)" if has55 else
                           ("DROPPED-BY-OVERFLOW" if cnt is not None and cap is not None and cnt >= cap
                            else "LOAD-FAILED-OR-STALE-FLAG"))
                log(f"*** SANDBOMB SCENE: flag55=1 has55={has55} count={cnt}/{cap} -> {verdict}")
                allflags = m.read(FLAG_ARRAY, 0x201)
                if allflags:
                    setf = {i for i, b in enumerate(allflags) if b}
                    stale = sorted(setf - ids)
                    log(f"*** stale flagged-but-unregistered ids: {[hex(x) for x in stale]}")
                reported_this_scene = True
        except Exception as e:
            log(f"error: {e}")
            time.sleep(3)
            try:
                if not find_mem1_base(m, timeout_s=5):
                    time.sleep(5)
            except Exception:
                time.sleep(5)
        time.sleep(1)


if __name__ == "__main__":
    main()
