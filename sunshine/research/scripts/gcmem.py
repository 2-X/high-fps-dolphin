"""Read GameCube emulated memory out of a live Dolphin process.

Locates MEM1 by matching a known code signature from main.dol, then translates
GC virtual addresses (0x80xxxxxx) to host pointers.
"""
import ctypes, ctypes.wintypes as wt, struct, sys, os, time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ           = 0x0010
MEM_COMMIT                = 0x1000
READABLE = {0x02, 0x04, 0x20, 0x40}   # READONLY, READWRITE, EXECUTE_READ, EXECUTE_READWRITE

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD),
                ("__align1", wt.DWORD),
                ("RegionSize", ctypes.c_size_t),
                ("State", wt.DWORD),
                ("Protect", wt.DWORD),
                ("Type", wt.DWORD),
                ("__align2", wt.DWORD)]

k32.OpenProcess.restype = wt.HANDLE
k32.VirtualQueryEx.restype = ctypes.c_size_t

MEM1_SIZE = 0x1800000        # 24 MB
SIG_VA    = 0x8034F684       # VIWaitForRetrace - stable, distinctive prologue

def dol_bytes(dol_path, va, n):
    d = open(dol_path, "rb").read()
    th_off = struct.unpack(">7I", d[0x00:0x1C]); th_a = struct.unpack(">7I", d[0x48:0x64]); th_s = struct.unpack(">7I", d[0x90:0xAC])
    dt_off = struct.unpack(">11I", d[0x1C:0x48]); dt_a = struct.unpack(">11I", d[0x64:0x90]); dt_s = struct.unpack(">11I", d[0xAC:0xD8])
    for o, a, s in list(zip(th_off, th_a, th_s)) + list(zip(dt_off, dt_a, dt_s)):
        if s and a <= va < a + s:
            k = o + va - a
            return d[k:k + n]
    raise SystemExit(f"{va:#x} not in DOL")

class Dolphin:
    def __init__(self, pid, dol):
        self.h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.h:
            raise SystemExit(f"OpenProcess failed on pid {pid}: {ctypes.get_last_error()}")
        self.sig = dol_bytes(dol, SIG_VA, 32)
        self.base = self._find_mem1()

    def _raw(self, addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
            return None
        return buf.raw[:got.value] if got.value == n else None

    def _find_mem1(self):
        mbi = MBI(); addr = 0; cands = []
        while k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            size = mbi.RegionSize
            if mbi.State == MEM_COMMIT and mbi.Protect in READABLE and size >= MEM1_SIZE:
                cands.append(int(mbi.BaseAddress))
            addr = int(mbi.BaseAddress or 0) + size
            if addr > 0x7FFFFFFFFFFF: break
        for b in cands:
            if self._raw(b + (SIG_VA - 0x80000000), 32) == self.sig:
                return b
        raise SystemExit(f"MEM1 not found ({len(cands)} candidate regions scanned)")

    def read(self, va, n=4):
        return self._raw(self.base + (va - 0x80000000), n)

    def f32(self, va):
        b = self.read(va, 4)
        return struct.unpack(">f", b)[0] if b else None

    def u32(self, va):
        b = self.read(va, 4)
        return struct.unpack(">I", b)[0] if b else None

if __name__ == "__main__":
    pid = int(sys.argv[1])
    dol = os.environ["SMS_DOL"]
    d = Dolphin(pid, dol)
    print(f"MEM1 host base = {d.base:#x}  (GC 0x80000000)")
    for spec in sys.argv[2:]:
        va = int(spec, 16)
        print(f"  {va:#010x}  u32={d.u32(va):08x}  f32={d.f32(va)!r}")
