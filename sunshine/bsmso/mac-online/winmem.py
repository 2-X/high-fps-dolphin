"""Windows Dolphin memory access via Win32 ReadProcessMemory/WriteProcessMemory.

The Windows counterpart to macmem.py.  On macOS, AMFI refuses task_for_pid to
un-entitled callers, which forced the signed `memhelper` subprocess.  Windows
has no such gate: a same-user process may OpenProcess with VM_READ/VM_WRITE
directly, so this backend talks to the kernel via ctypes and needs no helper.

PROTOCOL.md §D.2 documents the original Windows launcher's API surface, which
this restores 1:1:
    OpenProcess + PID        <- task_for_pid
    VirtualQueryEx walk      <- mach_vm_region
    ReadProcessMemory        <- mach_vm_read_overwrite
    WriteProcessMemory       <- mach_vm_write

Only the platform primitives are reimplemented here.  Everything above them --
locate_comm_buffer()'s anchor logic, _try_parse_anchor(), _looks_like_comm_buffer(),
read(), write(), read_comm(), write_comm_subregion() -- is INHERITED from
macmem.DolphinMem unchanged, so the two backends cannot drift apart.

Public API is identical to macmem.py; bridge.py / set_bse_fps.py depend on it:
  DolphinMem(pid)
  .locate_comm_buffer() -> Optional[int]
  .read(guest_va, n) -> Optional[bytes]
  .write(guest_va, data) -> bool
  .read_comm() -> Optional[bytes]
  .write_comm_subregion(offset, data) -> bool
  find_dolphin_pid() -> Optional[int]
"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import threading
from typing import Optional

from macmem import DolphinMem as _BaseDolphinMem, _ANCHOR_GUEST
from protocol import MEM1_GUEST_BASE

# --- Win32 constants -------------------------------------------------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
_ACCESS = (PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION
           | PROCESS_VM_READ | PROCESS_VM_WRITE)

MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
_READABLE = (0x02 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80)  # R, RW, WC, XR, XRW, XWC

# Highest user-mode address on x64 Windows.
_MAX_USER_ADDR = 0x7FFFFFFF0000

# MEM1 is >= 24 MB, and the GameCube disc header ("GMSE01") sits at guest
# 0x80000000 -- i.e. exactly at the MEM1 host base.  Same trick set_bse_fps.py
# uses to find MEM1 without scanning.
_MEM1_MIN_SIZE = 0x1800000
_DISC_ID = b"GMSE01"

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class _MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    """x64 layout -- field order and padding must be exact or the walk breaks."""
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wt.DWORD),
        ("__alignment1", wt.DWORD),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("__alignment2", wt.DWORD),
    ]


_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.OpenProcess.restype = wt.HANDLE
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.CloseHandle.restype = wt.BOOL
_k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_size_t)]
_k32.ReadProcessMemory.restype = wt.BOOL
_k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_size_t)]
_k32.WriteProcessMemory.restype = wt.BOOL
_k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                ctypes.POINTER(_MEMORY_BASIC_INFORMATION64),
                                ctypes.c_size_t]
_k32.VirtualQueryEx.restype = ctypes.c_size_t


def find_dolphin_pid() -> Optional[int]:
    """Return the newest running Dolphin PID, or None."""
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
        ).stdout
    except OSError:
        return None
    pids = []
    for line in out.splitlines():
        parts = [p.strip().strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        if parts[0].lower() == "dolphin.exe":
            try:
                pids.append(int(parts[1]))
            except ValueError:
                pass
    return max(pids) if pids else None


class DolphinMem(_BaseDolphinMem):
    """Windows Dolphin memory interface.  Overrides only the platform seam."""

    def __init__(self, pid: int):
        # Deliberately does NOT call super().__init__() -- that spawns the Mach
        # memhelper subprocess.  Set every attribute the inherited methods use.
        self.pid = pid
        self._comm_host_addr: Optional[int] = None
        self._mem1_host_base: Optional[int] = None
        self._lock = threading.Lock()
        self._proc = None          # keeps the inherited close()/__del__ harmless
        self._handle = _k32.OpenProcess(_ACCESS, False, pid)
        if not self._handle:
            err = ctypes.get_last_error()
            raise PermissionError(
                f"OpenProcess failed for pid {pid} (error {err}). "
                f"Run this terminal as the same user that launched Dolphin; "
                f"if Dolphin is elevated, run this as Administrator too."
            )

    # ------------------------------------------------------------------
    # Low-level read / write -- same signatures as the Mac backend
    # ------------------------------------------------------------------

    def _raw_read(self, host_addr: int, n: int) -> Optional[bytes]:
        """Read n bytes from Dolphin's virtual address space (host addr)."""
        buf = (ctypes.c_char * n)()
        got = ctypes.c_size_t(0)
        ok = _k32.ReadProcessMemory(self._handle, ctypes.c_void_p(host_addr),
                                    ctypes.byref(buf), n, ctypes.byref(got))
        if not ok or got.value != n:
            return None
        return bytes(buf)

    def _raw_write(self, host_addr: int, data: bytes) -> bool:
        """Write data into Dolphin's address space.  PROTOCOL.md §D.2."""
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
        put = ctypes.c_size_t(0)
        ok = _k32.WriteProcessMemory(self._handle, ctypes.c_void_p(host_addr),
                                     ctypes.byref(buf), len(data),
                                     ctypes.byref(put))
        return bool(ok) and put.value == len(data)

    # ------------------------------------------------------------------
    # Region enumeration -- VirtualQueryEx walk (PROTOCOL.md §D.2)
    # ------------------------------------------------------------------

    def _regions(self):
        """Yield (base, size) for committed, readable, non-guard regions."""
        addr = 0
        mbi = _MEMORY_BASIC_INFORMATION64()
        size = ctypes.sizeof(mbi)
        while addr < _MAX_USER_ADDR:
            if _k32.VirtualQueryEx(self._handle, ctypes.c_void_p(addr),
                                   ctypes.byref(mbi), size) != size:
                break
            region_size = int(mbi.RegionSize)
            if region_size <= 0:
                break                       # guard against an infinite loop
            if (mbi.State == MEM_COMMIT
                    and (mbi.Protect & _READABLE)
                    and not (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))):
                yield int(mbi.BaseAddress), region_size
            addr = int(mbi.BaseAddress) + region_size

    def _scan_region(self, base: int, size: int, magic_hex: str):
        """Host addresses in [base, base+size) whose 4 bytes == magic.

        Chunked 1 MB reads with an overlap so a match straddling a chunk
        boundary is still found.  1 GB cap per region, as on the Mac.

        NOTE: byte granularity, NOT the Mac helper's 4-byte stride.  bridge.py
        reuses this to find Setting *name strings* (_scan_settings_by_name),
        which are not word-aligned -- e.g. "Frame Rate" lands at guest
        0x805291bb.  A 4-byte stride silently misses those.  Every caller
        re-validates its hits, so over-reporting is safe; under-reporting is not.
        """
        magic = bytes.fromhex(magic_hex)
        hits = []
        chunk = 1 << 20
        overlap = len(magic) - 1
        size = min(size, 0x40000000)
        off = 0
        while off < size:
            n = min(chunk, size - off)
            data = self._raw_read(base + off, n)
            if data is None:
                off += n                    # unreadable page: skip, don't abort
                continue
            i = data.find(magic)
            while i != -1:
                hits.append(base + off + i)
                i = data.find(magic, i + 1)
            off += (n - overlap) if n > overlap else n
        return hits

    # ------------------------------------------------------------------
    # Comm-buffer location -- fast path, then the inherited full scan
    # ------------------------------------------------------------------

    def locate_comm_buffer(self) -> Optional[int]:
        """Find the BSMSO comm buffer.  PROTOCOL.md §A.1.

        Dolphin reserves a multi-GB fastmem arena, so the Mac backend's
        scan-every-readable-region approach is far too slow here.  Fast path:
        find MEM1 by its "GMSE01" disc header at the region base, then read the
        anchor directly at its known guest offset.  Falls back to the inherited
        full scan if that finds nothing.
        """
        for base, size in self._regions():
            if size < _MEM1_MIN_SIZE:
                continue
            if self._raw_read(base, len(_DISC_ID)) != _DISC_ID:
                continue
            host_anchor = base + (_ANCHOR_GUEST - MEM1_GUEST_BASE)
            twelve = self._raw_read(host_anchor, 12)
            if twelve is None:
                continue
            parsed = self._try_parse_anchor(host_anchor, twelve, 0)
            if parsed is None:
                continue
            host_comm, buffer_guest = parsed
            if self._looks_like_comm_buffer(host_comm):
                self._comm_host_addr = host_comm
                self._mem1_host_base = base
                return int(buffer_guest)
        return super().locate_comm_buffer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        """Close the process handle.  Idempotent."""
        h = getattr(self, "_handle", None)
        if h:
            _k32.CloseHandle(h)
            self._handle = None


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    verify_write = "--verify-write" in sys.argv

    pid = find_dolphin_pid()
    if pid is None:
        print("Dolphin is not running.")
        sys.exit(1)
    print(f"Dolphin pid      : {pid}")

    try:
        mem = DolphinMem(pid)
    except PermissionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    guest = mem.locate_comm_buffer()
    if guest is None:
        print("Comm buffer NOT FOUND -- you are probably not in a stage "
              "(title screen / paused). Load a level and retry.")
        sys.exit(1)

    print(f"MEM1 host base   : 0x{mem._mem1_host_base:x}")
    print(f"comm buffer guest: 0x{guest:08x}")
    print(f"comm buffer host : 0x{mem._comm_host_addr:x}")

    if verify_write:
        # No-op round trip: read 8 bytes and write the SAME bytes back, proving
        # the write path works without changing any game state.
        before = mem._raw_read(mem._comm_host_addr, 8)
        if before is None:
            print("FAIL: could not read the comm buffer")
            sys.exit(1)
        if not mem._raw_write(mem._comm_host_addr, before):
            print("FAIL: WriteProcessMemory rejected the no-op write")
            sys.exit(1)
        after = mem._raw_read(mem._comm_host_addr, 8)
        if after != before:
            print(f"FAIL: readback mismatch {before.hex()} -> {after.hex()}")
            sys.exit(1)
        print(f"write verified   : no-op round trip OK ({before.hex()})")

    mem.close()
    print("OK")
