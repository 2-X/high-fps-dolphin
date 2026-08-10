"""Locate and dump the Zelda-ucode VPB array from live SMS memory (music bug).

The DSP-HLE renderer reads one 0x180-byte VPB per voice (64 voices) from MRAM.
We find the array by scanning MEM1 for the distinctive DSP mixing-buffer IDs in
channels[] (0x0D00 front-L at +0x10, 0x0D60 front-R at +0x18), then cluster
candidates on a 0x180 stride to find the base.

For every enabled voice, prints: src type, looping, end_requested, ARAM
base/current address, remaining length, resampling ratio, and all channel
(dest-id, target-vol, current-vol) triples.

Usage: SMS_DOL=research/main.dol python3 vpbdump.py [pid] [--all]
"""
import os, struct, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcmem import Dolphin, find_dolphin_pid, MEM1_SIZE

VPB_BYTES = 0x180
NUM_VOICES = 64

SRC_NAMES = {0: "SQUARE", 1: "SAW", 3: "SQUARE25", 7: "PAT0", 10: "PAT0V", 4: "PAT1",
             11: "PAT2", 12: "PAT3", 5: "AFC_LQ", 8: "PCM8", 9: "AFC_HQ",
             16: "PCM16_ARAM", 33: "PCM16_MRAM"}
BUF_NAMES = {0x0D00: "frontL", 0x0D60: "frontR", 0x0F40: "backL", 0x0CA0: "backR",
             0x0E80: "revFL", 0x0EE0: "revFR", 0x0C00: "revBL", 0x0C50: "revBR",
             0x0DC0: "revU0", 0x0E20: "revU1", 0x09A0: "unk0", 0x0FA0: "unk1",
             0x0B00: "unk2"}


def u16(b, w):  # word index -> BE u16
    return struct.unpack_from(">H", b, w * 2)[0]


def s16(b, w):
    return struct.unpack_from(">h", b, w * 2)[0]


def u32w(b, w):  # (h,l) word pair
    return (u16(b, w) << 16) | u16(b, w + 1)


def find_vpb_base(mem1):
    hits = []
    pos = 0
    while True:
        pos = mem1.find(b"\x0d\x00", pos)
        if pos == -1:
            break
        if pos % 2 == 0 and mem1[pos + 8: pos + 10] == b"\x0d\x60":
            start = pos - 0x10
            if start >= 0:
                hits.append(start)
        pos += 2
    if not hits:
        return None
    # cluster on 0x180 stride: most enabled voices share (addr % 0x180) with the base
    by_mod = Counter(h % VPB_BYTES for h in hits)
    mod, _ = by_mod.most_common(1)[0]
    aligned = sorted(h for h in hits if h % VPB_BYTES == mod)
    # base = smallest hit such that a healthy number of hits fall within the array span
    best, best_n = None, -1
    for cand in aligned:
        n = sum(1 for h in aligned if cand <= h < cand + NUM_VOICES * VPB_BYTES)
        if n > best_n:
            best, best_n = cand, n
    # walk back while preceding slots still look like VPBs (enabled/done in {0,1})
    while best - VPB_BYTES >= 0:
        prev = best - VPB_BYTES
        en, dn = struct.unpack_from(">HH", mem1, prev)
        if en > 1 or dn > 1:
            break
        best = prev
    return best


def dump_voice(vid, b, show_all=False):
    enabled, done = u16(b, 0), u16(b, 1)
    if not enabled and not show_all:
        return None
    src = u16(b, 0x80)
    chans = []
    for c in range(6):
        cid = u16(b, 8 + 4 * c)
        tgt = s16(b, 8 + 4 * c + 1)
        cur = s16(b, 8 + 4 * c + 2)
        if cid:
            chans.append(f"{BUF_NAMES.get(cid, hex(cid))}:t={tgt:#x},c={cur:#x}")
    return (f"v{vid:02d} en={enabled} done={done} src={SRC_NAMES.get(src, src)} "
            f"loop={u16(b, 0x81)} endreq={u16(b, 0x85)} dolby={u16(b, 0x2C)} "
            f"ratio={u16(b, 2):#06x} base={u32w(b, 0x8C):#x} cur_aram={u32w(b, 0x38):#x} "
            f"remain={u32w(b, 0x3A):#x} | {' '.join(chans) if chans else 'NO-CHANNELS'}")


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else find_dolphin_pid()
    show_all = "--all" in sys.argv
    if not pid:
        raise SystemExit("no Dolphin process found")
    dol = os.environ.get("SMS_DOL")
    if not dol:
        raise SystemExit("set SMS_DOL")
    d = Dolphin(pid, dol)
    mem1 = d._raw(d.base, MEM1_SIZE)
    if mem1 is None:
        raise SystemExit("failed to read MEM1")
    base = find_vpb_base(mem1)
    if base is None:
        raise SystemExit("VPB array not found (no 0x0D00/0x0D60 channel pattern in MEM1)")
    print(f"VPB array @ GC 0x{0x80000000 + base:08x} (MEM1+0x{base:x})")
    n_enabled = 0
    for vid in range(NUM_VOICES):
        blk = mem1[base + vid * VPB_BYTES: base + (vid + 1) * VPB_BYTES]
        if len(blk) < VPB_BYTES:
            break
        line = dump_voice(vid, blk, show_all)
        if line:
            print(line)
            if u16(blk, 0):
                n_enabled += 1
    print(f"[{n_enabled} enabled voices]")


if __name__ == "__main__":
    main()
