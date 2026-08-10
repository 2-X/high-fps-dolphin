"""Read GameCube emulated memory out of a live Dolphin process.

Locates MEM1 by matching a known code signature from main.dol, then translates
GC virtual addresses (0x80xxxxxx) to host pointers.

Cross-platform: Windows (kernel32 OpenProcess/VirtualQueryEx/ReadProcessMemory)
and macOS (Mach task_for_pid/mach_vm_region/mach_vm_read_overwrite). The MEM1
signature scan is identical on both — GC RAM at 0x00000000 and 0x80000000 alias
the same physical MEM1, so a region whose (base + SIG_VA-0x80000000) matches the
prologue always yields correct reads regardless of which mirror was found.

macOS note: task_for_pid needs privilege. Run these scripts under `sudo` (simplest)
against a user-built, non-hardened Dolphin.app. SIP need not be disabled.
"""
import struct, sys, os, time

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


# ============================ Windows backend ==============================
if sys.platform == "win32":
    import ctypes, ctypes.wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ           = 0x0010
    MEM_COMMIT                = 0x1000
    READABLE = {0x02, 0x04, 0x20, 0x40}   # RO, RW, EXEC_R, EXEC_RW

    class MBI(ctypes.Structure):
        _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wt.DWORD), ("__align1", wt.DWORD),
                    ("RegionSize", ctypes.c_size_t), ("State", wt.DWORD),
                    ("Protect", wt.DWORD), ("Type", wt.DWORD), ("__align2", wt.DWORD)]

    k32.OpenProcess.restype = wt.HANDLE
    k32.VirtualQueryEx.restype = ctypes.c_size_t

    class _Backend:
        def __init__(self, pid):
            self.h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if not self.h:
                raise SystemExit(f"OpenProcess failed on pid {pid}: {ctypes.get_last_error()}")

        def raw(self, addr, n):
            buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t(0)
            if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
                return None
            return buf.raw[:got.value] if got.value == n else None

        def regions(self):
            mbi = MBI(); addr = 0
            while k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                size = mbi.RegionSize
                if mbi.State == MEM_COMMIT and mbi.Protect in READABLE:
                    yield int(mbi.BaseAddress), size
                addr = int(mbi.BaseAddress or 0) + size
                if addr > 0x7FFFFFFFFFFF: break

# ============================= macOS backend ===============================
else:
    import ctypes, ctypes.util

    _libc = ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)
    _mach_port_t = ctypes.c_uint
    VM_REGION_BASIC_INFO_64 = 9
    VM_PROT_READ = 0x1

    class _vm_region_basic_info_64(ctypes.Structure):
        _fields_ = [("protection", ctypes.c_int), ("max_protection", ctypes.c_int),
                    ("inheritance", ctypes.c_uint), ("shared", ctypes.c_uint),
                    ("reserved", ctypes.c_uint), ("offset", ctypes.c_ulonglong),
                    ("behavior", ctypes.c_int), ("user_wired_count", ctypes.c_ushort)]

    _libc.task_for_pid.argtypes = [_mach_port_t, ctypes.c_int, ctypes.POINTER(_mach_port_t)]
    _libc.task_for_pid.restype = ctypes.c_int
    _libc.mach_vm_region.argtypes = [_mach_port_t, ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64), ctypes.c_int, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(_mach_port_t)]
    _libc.mach_vm_region.restype = ctypes.c_int
    _libc.mach_vm_read_overwrite.argtypes = [_mach_port_t, ctypes.c_uint64, ctypes.c_uint64,
        ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64)]
    _libc.mach_vm_read_overwrite.restype = ctypes.c_int

    class _Backend:
        def __init__(self, pid):
            self.task = _mach_port_t(0)
            self_tport = _mach_port_t.in_dll(_libc, "mach_task_self_")
            kr = _libc.task_for_pid(self_tport, pid, ctypes.byref(self.task))
            if kr != 0:
                raise SystemExit(
                    f"task_for_pid failed on pid {pid} (kr={kr}). "
                    f"Run under sudo, e.g.  sudo -E python3 {os.path.basename(sys.argv[0] or 'script.py')}")

        def raw(self, addr, n):
            buf = ctypes.create_string_buffer(n); out = ctypes.c_uint64(0)
            kr = _libc.mach_vm_read_overwrite(self.task, addr, n, ctypes.addressof(buf), ctypes.byref(out))
            if kr != 0 or out.value != n:
                return None
            return buf.raw[:n]

        def regions(self):
            addr = ctypes.c_uint64(0)
            while True:
                size = ctypes.c_uint64(0)
                info = _vm_region_basic_info_64()
                cnt = ctypes.c_uint(ctypes.sizeof(info) // 4)
                obj = _mach_port_t(0)
                kr = _libc.mach_vm_region(self.task, ctypes.byref(addr), ctypes.byref(size),
                    VM_REGION_BASIC_INFO_64, ctypes.byref(info), ctypes.byref(cnt), ctypes.byref(obj))
                if kr != 0 or size.value == 0:
                    break
                if info.protection & VM_PROT_READ:
                    yield addr.value, size.value
                addr = ctypes.c_uint64(addr.value + size.value)


def find_dolphin_pid():
    """Return the newest running Dolphin PID, or None."""
    import subprocess
    if sys.platform == "win32":
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-Process Dolphin -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
            capture_output=True, text=True).stdout.strip()
    else:
        out = subprocess.run(["pgrep", "-x", "Dolphin"], capture_output=True, text=True).stdout.strip()
        if not out:
            out = subprocess.run(["pgrep", "-if", "Dolphin.app"], capture_output=True, text=True).stdout.strip()
    return int(out.splitlines()[-1]) if out else None


class Dolphin:
    def __init__(self, pid, dol):
        self._be = _Backend(pid)
        self.sig = dol_bytes(dol, SIG_VA, 32)
        self.base = self._find_mem1()

    def _raw(self, addr, n):
        return self._be.raw(addr, n)

    def _find_mem1(self):
        cands = [(b, size) for b, size in self._be.regions() if size >= MEM1_SIZE]
        # fast path: signature exactly at the MEM1 offset (base == GC 0x80000000 view)
        for b, size in cands:
            if self._raw(b + (SIG_VA - 0x80000000), 32) == self.sig:
                return b
        # robust path: search inside each candidate (handles arenas where MEM1
        # doesn't start at the region base). base = hit - (SIG_VA-0x80000000).
        off = SIG_VA - 0x80000000
        CH = 0x100000
        for b, size in cands:
            limit = min(size, 0x8000000)          # scan first 128 MB of the region
            for c in range(0, limit, CH):
                blob = self._raw(b + c, min(CH + 32, size - c))
                if not blob:
                    continue
                i = blob.find(self.sig)
                if i != -1 and (c + i - off) % 4 == 0:
                    return b + c + i - off
        sizes = ", ".join(f"{s:#x}" for _, s in cands[:8])
        raise SystemExit(f"MEM1 not found ({len(cands)} readable regions >=24MB; sizes: {sizes})")

    def read(self, va, n=4):
        return self._raw(self.base + (va - 0x80000000), n)

    def f32(self, va):
        b = self.read(va, 4)
        return struct.unpack(">f", b)[0] if b else None

    def u32(self, va):
        b = self.read(va, 4)
        return struct.unpack(">I", b)[0] if b else None


if __name__ == "__main__":
    pid = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else find_dolphin_pid()
    if not pid:
        raise SystemExit("no Dolphin process found")
    dol = os.environ["SMS_DOL"]
    d = Dolphin(pid, dol)
    print(f"pid {pid}: MEM1 host base = {d.base:#x}  (GC 0x80000000)")
    for spec in sys.argv[2:]:
        if spec.isdigit():
            continue
        va = int(spec, 16)
        print(f"  {va:#010x}  u32={d.u32(va):08x}  f32={d.f32(va)!r}")
