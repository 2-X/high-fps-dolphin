"""macOS Dolphin memory access via a signed native helper (memhelper).

Routes all Mach calls (task_for_pid, mach_vm_read_overwrite, mach_vm_write,
mach_vm_region) through sunshine/bsmso/mac-online/memhelper/memhelper — a
tiny C binary signed with the com.apple.security.cs.debugger entitlement.
This sidesteps AMFI's refusal to grant task_for_pid to un-entitled Python
interpreters on Apple Silicon.

No sudo needed.  If the memhelper binary is absent, it is auto-built once
via memhelper/build.sh (requires Xcode Command Line Tools).

Public API of DolphinMem is unchanged — bridge.py depends on it:
  DolphinMem(pid)
  .locate_comm_buffer() -> Optional[int]
  .read(guest_va, n) -> Optional[bytes]
  .write(guest_va, data) -> bool
  .read_comm() -> Optional[bytes]
  .write_comm_subregion(offset, data) -> bool
  find_dolphin_pid() -> Optional[int]
"""
import struct
import subprocess
import sys
import os
import threading
from typing import Optional, Tuple

import protocol
from protocol import (
    MAGIC,
    COMM_VERSION,
    COMM_BUFFER_SIZE,
    DEFAULT_MAILBOX_ADDR,
    MEM1_GUEST_BASE,
)

# ---------------------------------------------------------------------------
# find_dolphin_pid  (unchanged from the ctypes version)
# ---------------------------------------------------------------------------

def find_dolphin_pid() -> Optional[int]:
    """Return the newest running Dolphin PID, or None.  Reused from gcmem.py."""
    out = subprocess.run(
        ["pgrep", "-x", "Dolphin"], capture_output=True, text=True
    ).stdout.strip()
    if not out:
        out = subprocess.run(
            ["pgrep", "-if", "Dolphin.app"], capture_output=True, text=True
        ).stdout.strip()
    return int(out.splitlines()[-1]) if out else None


# ---------------------------------------------------------------------------
# Internal helpers  (same constants as before)
# ---------------------------------------------------------------------------

_MAGIC_BYTES  = struct.pack(">I", MAGIC)  # b'\x53\x4d\x53\x4f'  (BE "SMSO")
_ANCHOR_GUEST = DEFAULT_MAILBOX_ADDR      # 0x817FC000

# Path to the helper binary and its build script, both relative to this file.
_HERE        = os.path.dirname(os.path.abspath(__file__))
_HELPER_DIR  = os.path.join(_HERE, "memhelper")
_HELPER_BIN  = os.path.join(_HELPER_DIR, "memhelper")
_BUILD_SH    = os.path.join(_HELPER_DIR, "build.sh")


# ---------------------------------------------------------------------------
# DolphinMem
# ---------------------------------------------------------------------------

class DolphinMem:
    """macOS Dolphin memory interface via the signed memhelper subprocess.

    Spawns memhelper/memhelper as a persistent child process with stdin/stdout
    pipes.  The child holds the Mach task port for the Dolphin process.
    A threading.Lock serialises request/response pairs so the class is
    safe to call from multiple threads.

    Call locate_comm_buffer() after construction to find the BSMSO comm buffer.
    """

    def __init__(self, pid: int):
        self.pid = pid
        self._comm_host_addr: Optional[int] = None
        self._mem1_host_base: Optional[int] = None
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None

        # Build the helper if the binary is missing.
        if not os.path.isfile(_HELPER_BIN):
            try:
                subprocess.run(["/bin/sh", _BUILD_SH], check=True)
            except subprocess.CalledProcessError as exc:
                raise PermissionError(
                    f"memhelper build failed (see output above). "
                    f"Make sure Xcode Command Line Tools are installed. ({exc})"
                ) from exc

        # Spawn the helper.  text=True + bufsize=1 gives line-buffered I/O.
        self._proc = subprocess.Popen(
            [_HELPER_BIN, str(pid)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,   # inherit — error messages from helper go to our stderr
            text=True,
            bufsize=1,
        )

        # First line from the helper: "OK" or "ERR attach kr=<n>"
        banner = self._proc.stdout.readline().rstrip("\n")
        if not banner.startswith("OK"):
            self._proc.terminate()
            self._proc = None
            raise PermissionError(
                f"memhelper could not attach to pid {pid}: {banner}\n"
                f"Ensure the binary is signed: cd {_HELPER_DIR} && ./build.sh"
            )

    # ------------------------------------------------------------------
    # Subprocess I/O  (all access serialised by _lock)
    # ------------------------------------------------------------------

    def _send_recv(self, line: str) -> str:
        """Send one command line, return the response line (stripped)."""
        assert self._proc is not None
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()
        return self._proc.stdout.readline().rstrip("\n")

    # ------------------------------------------------------------------
    # Low-level read / write — same signature as the ctypes version
    # ------------------------------------------------------------------

    def _raw_read(self, host_addr: int, n: int) -> Optional[bytes]:
        """Read n bytes from Dolphin's virtual address space (host addr)."""
        with self._lock:
            resp = self._send_recv(f"READ {host_addr:x} {n:x}")
        if not resp.startswith("OK "):
            return None
        data = bytes.fromhex(resp[3:])
        return data if len(data) == n else None

    def _raw_write(self, host_addr: int, data: bytes) -> bool:
        """Write data to Dolphin's virtual address space (host addr).

        Uses mach_vm_write.  PROTOCOL.md §D.2.
        """
        hex_payload = data.hex()
        with self._lock:
            resp = self._send_recv(f"WRITE {host_addr:x} {hex_payload}")
        return resp == "OK"

    # ------------------------------------------------------------------
    # Region enumeration — same yield signature as before
    # ------------------------------------------------------------------

    def _regions(self):
        """Yield (base_addr, size) for readable committed regions.

        Collects all REGION lines under the lock, then yields after releasing
        it.  This lets locate_comm_buffer() call _raw_read() (which also
        acquires the lock) while iterating without deadlock.
        """
        with self._lock:
            self._proc.stdin.write("REGIONS\n")
            self._proc.stdin.flush()
            lines = []
            while True:
                line = self._proc.stdout.readline().rstrip("\n")
                if line.startswith("REGION "):
                    lines.append(line)
                elif line == "OK":
                    break
                else:
                    # Unexpected output (ERR or empty) — stop enumerating
                    break
        for line in lines:
            parts = line.split()
            yield int(parts[1], 16), int(parts[2], 16)

    def _scan_region(self, base: int, size: int, magic_hex: str):
        """Return host addresses in [base, base+size) whose 4 bytes == magic.

        The native helper scans region memory in C on a 4-byte stride, so only
        match addresses cross the pipe (not the region contents as hex).
        """
        with self._lock:
            self._proc.stdin.write(f"SCAN {base:x} {size:x} {magic_hex}\n")
            self._proc.stdin.flush()
            hits = []
            while True:
                line = self._proc.stdout.readline().rstrip("\n")
                if line.startswith("HIT "):
                    hits.append(int(line[4:], 16))
                elif line == "OK":
                    break
                else:
                    # Unexpected output (ERR or empty) — stop scanning.
                    break
        return hits

    # ------------------------------------------------------------------
    # Comm-buffer location  (PROTOCOL.md §A.1 Mac approach)
    # Algorithm is byte-for-byte identical to the ctypes version.
    # ------------------------------------------------------------------

    def locate_comm_buffer(self) -> Optional[int]:
        """Scan readable regions for the BSMSO comm buffer.  PROTOCOL.md §A.1.

        Algorithm (Mac fallback-scan approach):
          1. Scan every readable region for magic bytes 53 4D 53 4F
             on a 4-byte stride (PROTOCOL.md §A.1 TryResolveMailboxScan).
          2. At each hit, test the 12-byte anchor shape:
               magic(4) + be16==15 + be16==0 + be32 bufferGuest ∈ [0x80000000,0x82000000)
          3. If anchor is valid, compute:
               hostComm = hostAnchor + (bufferGuest - 0x817FC000)
             Both anchor and comm buffer live in the same MEM1 host view.
             Invariant from PROTOCOL.md §A.1.
          4. Verify via _looks_like_comm_buffer(hostComm).

        Returns the guest address of the comm buffer (for reference/debugging),
        and caches the host address for subsequent read/write calls.
        """
        MAX_SCAN  = 0x40000000               # 1 GB max per region (PROTOCOL.md §A.1)
        magic_hex = _MAGIC_BYTES.hex()       # "534d534f"

        for region_base, region_size in self._regions():
            scan_size = min(region_size, MAX_SCAN)
            for host_hit in self._scan_region(region_base, scan_size, magic_hex):
                twelve = self._raw_read(host_hit, 12)
                if twelve is None:
                    continue
                result = self._try_parse_anchor(host_hit, twelve, 0)
                if result is not None:
                    host_comm, buffer_guest = result
                    if self._looks_like_comm_buffer(host_comm):
                        # Success — cache both addresses
                        self._comm_host_addr = host_comm
                        # MEM1 host base: anchor is at guest 0x817FC000,
                        # host = host_hit; MEM1 base is guest 0x80000000
                        self._mem1_host_base = host_hit - (_ANCHOR_GUEST - MEM1_GUEST_BASE)
                        return int(buffer_guest)
        return None

    def _try_parse_anchor(
        self, host_hit: int, chunk: bytes, chunk_off: int
    ) -> Optional[Tuple[int, int]]:
        """Try to parse a 12-byte anchor at host_hit.  PROTOCOL.md §A.1.

        Returns (host_comm, buffer_guest) if valid, else None.
        """
        if chunk_off + 12 <= len(chunk):
            anchor_bytes = chunk[chunk_off:chunk_off + 12]
        else:
            anchor_bytes = self._raw_read(host_hit, 12)
        if anchor_bytes is None or len(anchor_bytes) < 12:
            return None
        if anchor_bytes[0:4] != _MAGIC_BYTES:
            return None
        version   = struct.unpack_from(">H", anchor_bytes, 4)[0]
        reserved  = struct.unpack_from(">H", anchor_bytes, 6)[0]
        buf_guest = struct.unpack_from(">I", anchor_bytes, 8)[0]
        if version != COMM_VERSION:
            return None
        if reserved != 0:
            return None
        if not (0x80000000 <= buf_guest < 0x82000000):
            return None
        # Both anchor (guest 0x817FC000) and comm buffer (guest bufferGuest) live in
        # the same MEM1 host-memory view.  PROTOCOL.md §A.1.
        host_comm = host_hit + (buf_guest - _ANCHOR_GUEST)
        return host_comm, buf_guest

    def _looks_like_comm_buffer(self, host_addr: int) -> bool:
        """Validate magic+version at host_addr and confirm it is NOT an anchor.

        PROTOCOL.md §A.1 LooksLikeCommBuffer: magic=="SMSO" + version==15,
        and the first 12 bytes must NOT parse as a valid anchor.
        """
        hdr = self._raw_read(host_addr, 12)
        if hdr is None or len(hdr) < 12:
            return False
        if hdr[0:4] != _MAGIC_BYTES:
            return False
        version = struct.unpack_from(">H", hdr, 4)[0]
        if version != COMM_VERSION:
            return False
        # Reject if the 12 bytes look like an anchor
        # (anchor: version==15, reserved==0, bufferGuest ∈ [0x80000000,0x82000000))
        reserved  = struct.unpack_from(">H", hdr, 6)[0]
        buf_guest = struct.unpack_from(">I", hdr, 8)[0]
        is_anchor = (reserved == 0 and 0x80000000 <= buf_guest < 0x82000000)
        return not is_anchor

    # ------------------------------------------------------------------
    # High-level guest-VA read/write
    # ------------------------------------------------------------------

    def read(self, guest_va: int, n: int) -> Optional[bytes]:
        """Read n bytes at a GameCube guest virtual address.

        Translates via MEM1 host base (cached by locate_comm_buffer).
        """
        if self._mem1_host_base is None:
            raise RuntimeError("locate_comm_buffer() must be called first")
        host_addr = self._mem1_host_base + (guest_va - MEM1_GUEST_BASE)
        return self._raw_read(host_addr, n)

    def write(self, guest_va: int, data: bytes) -> bool:
        """Write data at a GameCube guest virtual address.

        PROTOCOL.md §D.1/D.2 — targeted sub-region writes only.
        """
        if self._mem1_host_base is None:
            raise RuntimeError("locate_comm_buffer() must be called first")
        host_addr = self._mem1_host_base + (guest_va - MEM1_GUEST_BASE)
        return self._raw_write(host_addr, data)

    # ------------------------------------------------------------------
    # Comm-buffer targeted accessors
    # ------------------------------------------------------------------

    def read_comm(self) -> Optional[bytes]:
        """Read the full 5494-byte comm buffer."""
        if self._comm_host_addr is None:
            return None
        return self._raw_read(self._comm_host_addr, COMM_BUFFER_SIZE)

    def write_comm_subregion(self, offset: int, data: bytes) -> bool:
        """Write data into the comm buffer at the given byte offset.

        Uses a targeted sub-region write — never rewrites the whole buffer.
        PROTOCOL.md §D.1.
        """
        if self._comm_host_addr is None:
            return False
        return self._raw_write(self._comm_host_addr + offset, data)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        """Terminate the memhelper subprocess."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# __main__ — print comm buffer address and optionally verify a no-op write
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Locate BSMSO comm buffer in a running Dolphin process."
    )
    parser.add_argument(
        "--verify-write", action="store_true",
        help="After locating the comm buffer, read 8 bytes and write them "
             "back unchanged to verify write access (no-op write proof)."
    )
    args = parser.parse_args()

    pid = find_dolphin_pid()
    if pid is None:
        print("No Dolphin process found.", file=sys.stderr)
        sys.exit(1)
    print(f"Found Dolphin pid={pid}")

    try:
        mem = DolphinMem(pid)
    except PermissionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print("Scanning for comm buffer…")
    guest_comm = mem.locate_comm_buffer()
    if guest_comm is None:
        print("Comm buffer NOT FOUND. Is the game running with _BSMSO.kxe loaded?")
        sys.exit(1)

    print(f"Comm buffer guest address: {guest_comm:#010x}")
    hdr = mem.read_comm()
    if hdr:
        print(f"First 16 bytes: {hdr[:16].hex(' ')}")
    else:
        print("Failed to read comm buffer.")

    if args.verify_write:
        print("\n-- verify-write --")
        original = mem.read_comm()
        if original is None:
            print("Could not read comm buffer for verify-write.")
        else:
            probe = original[:8]
            print(f"Read 8 bytes:  {probe.hex(' ')}")
            ok = mem.write_comm_subregion(0, probe)
            print(f"Write returned: {ok}")
            after = mem.read_comm()
            if after is None:
                print("Re-read failed.")
            else:
                match = (after[:8] == probe)
                print(f"Re-read 8 bytes: {after[:8].hex(' ')}")
                print(f"Bytes unchanged: {match}")
