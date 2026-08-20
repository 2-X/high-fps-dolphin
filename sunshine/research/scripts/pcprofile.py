"""PC-side fps profiler: 20s of (a) emulated-PC sampling via thread-context
SRR0 (interrupts keep it fresh while the thread runs), (b) host thread CPU%
by thread name (CPU vs Video utilization — the class C lock-step signature).
"""
import sys, time, struct, collections, ctypes
from ctypes import wintypes
sys.path.insert(0, r"C:\code\high-fps-dolphin\sunshine\research\scripts")
from gcmem import Dolphin, find_dolphin_pid

DOL = r"C:\code\high-fps-dolphin\sunshine\research\main.dol"
pid = find_dolphin_pid()
d = Dolphin(pid, DOL)
MAIN_THREAD = 0x80402AA8
CUR = 0x800000E4
DUR = 20.0

# ---- host thread times (before) ----
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
THREAD_QUERY = 0x0040 | 0x0800  # QUERY_INFORMATION | QUERY_LIMITED
class FT(ctypes.Structure):
    _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]
def ft2s(ft):
    return ((ft.hi << 32) | ft.lo) / 1e7
k32.GetThreadDescription = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p))(
    ("GetThreadDescription", k32))

def thread_times():
    import subprocess
    out = {}
    # enumerate thread ids via toolhelp
    TH32CS_SNAPTHREAD = 0x4
    class THREADENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                    ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD)]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32(); te.dwSize = ctypes.sizeof(THREADENTRY32)
    ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            h = k32.OpenThread(THREAD_QUERY, False, te.th32ThreadID)
            if h:
                c, e, kt, ut = FT(), FT(), FT(), FT()
                if k32.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e),
                                      ctypes.byref(kt), ctypes.byref(ut)):
                    name = ctypes.c_wchar_p()
                    k32.GetThreadDescription(h, ctypes.byref(name))
                    out[te.th32ThreadID] = (name.value or f"tid{te.th32ThreadID}",
                                            ft2s(kt) + ft2s(ut))
                k32.CloseHandle(h)
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    k32.CloseHandle(snap)
    return out

t0 = thread_times()

# ---- emulated PC sampling ----
pcs, lrs = collections.Counter(), collections.Counter()
n = 0
end = time.time() + DUR
while time.time() < end:
    thr = d.u32(CUR)
    if not (thr and 0x80000000 <= thr < 0x81800000):
        thr = MAIN_THREAD
    blob = d.read(thr + 0x84, 4)
    blob2 = d.read(thr + 0x198, 4)
    if blob2:
        pc = struct.unpack(">I", blob2)[0]
        if pc:
            pcs[pc] += 1
    if blob:
        lr = struct.unpack(">I", blob)[0]
        if lr:
            lrs[lr] += 1
    n += 1

t1 = thread_times()

print(f"samples: {n} over {DUR:.0f}s")
print("\n===== host thread CPU (core-seconds in window; >90% of a core = hot) =====")
rows = []
for tid, (name, tt1) in t1.items():
    tt0 = t0.get(tid, (name, 0))[1]
    dt = tt1 - tt0
    if dt > 0.5:
        rows.append((dt, name))
for dt, name in sorted(rows, reverse=True):
    print(f"  {dt/DUR*100:5.1f}%  {name}")

print("\n===== emulated PC histogram (top 25 exact) =====")
tot = sum(pcs.values())
for pc, c in pcs.most_common(25):
    print(f"  {pc:#010x}  {c:6d}  {c/tot*100:5.1f}%")

print("\n===== by 4KB region (top 15) =====")
reg = collections.Counter()
for pc, c in pcs.items():
    reg[pc & 0xFFFFF000] += c
for r, c in reg.most_common(15):
    print(f"  {r:#010x}  {c/tot*100:5.1f}%")

print("\n===== LR histogram (top 15) =====")
ltot = sum(lrs.values())
for lr, c in lrs.most_common(15):
    print(f"  {lr:#010x}  {c:6d}  {c/ltot*100:5.1f}%")
