"""BSMSO network client — TCP handshake/join + UDP snapshot relay.

Handles the complete join flow, background threads, and clean shutdown.
PROTOCOL.md §B, §C.2.
"""
import os
import socket
import struct
import threading
import time
from typing import Callable, List, Optional, Tuple

import protocol
from protocol import (
    PlayerSnapshot,
    build_handshake,
    build_join_request,
    build_udp_register,
    build_heartbeat,
    build_disconnect,
    build_player_snapshot,
    parse_snapshot_batch,
    parse_handshake_ack,
    parse_join_accepted,
    parse_join_rejected,
    parse_roster_snapshot,
    parse_player_left,
    try_unwrap_tcp,
    wrap_tcp,
    TCP_HANDSHAKE_ACK,
    TCP_JOIN_ACCEPTED,
    TCP_JOIN_REJECTED,
    TCP_ROSTER_SNAPSHOT,
    TCP_PLAYER_LEFT,
    TCP_HEARTBEAT,
    TCP_DISCONNECT,
    DEFAULT_PORT,
    HEARTBEAT_INTERVAL_MS,
    MOD_BUILD_ID,
)


class JoinError(Exception):
    """Raised when the server rejects a join attempt."""
    def __init__(self, reason: int, reason_name: str):
        self.reason = reason
        self.reason_name = reason_name
        super().__init__(f"Join rejected: {reason_name} ({reason})")


class NetClient:
    """BSMSO network client.

    Usage:
        client = NetClient("hostname", on_snapshot_batch=my_callback)
        client.join("MyName")
        # now send snapshots:
        client.send_snapshot(snap)
        # on shutdown:
        client.close()

    on_snapshot_batch: callable(list[(slot, seq, PlayerSnapshot)]) — called from
    the UDP receive thread when a SnapshotBatch arrives.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        on_snapshot_batch: Optional[Callable] = None,
        on_player_left: Optional[Callable] = None,
        model_id: bytes = None,
    ):
        self.host = host
        self.port = port
        self.on_snapshot_batch = on_snapshot_batch
        self.on_player_left = on_player_left
        self.model_id = model_id or b'\x00' * 8  # retail/empty model id

        self.assigned_slot: Optional[int] = None
        self.roster: List[dict] = []

        self._tcp: Optional[socket.socket] = None
        self._udp: Optional[socket.socket] = None
        self._udp_port: Optional[int] = None

        self._seq = 0
        self._seq_lock = threading.Lock()
        self._recv_buf = bytearray()
        self._closed = False
        self._close_event = threading.Event()

        self._tcp_lock = threading.Lock()
        self._threads: List[threading.Thread] = []

        # Dispatch table for inbound TCP packets after join
        self._tcp_handlers = {
            TCP_ROSTER_SNAPSHOT: self._on_roster_snapshot,
            TCP_PLAYER_LEFT:     self._on_player_left,
            TCP_HEARTBEAT:       self._on_heartbeat,
            TCP_DISCONNECT:      self._on_disconnect,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def join(self, username: str) -> int:
        """Connect, handshake, join.  Returns the assigned slot.

        Raises JoinError on rejection.  PROTOCOL.md §C.2 steps 1–4.
        """
        # Step 1: TCP connect
        self._tcp = socket.create_connection((self.host, self.port), timeout=10)
        self._tcp.settimeout(None)

        # Step 2: Handshake  (PROTOCOL.md §C.2 step 2)
        guid = os.urandom(16)
        self._tcp_send_raw(build_handshake(guid))
        ack = self._wait_tcp(TCP_HANDSHAKE_ACK, timeout=10)
        parsed_ack = parse_handshake_ack(ack)
        self.assigned_slot = parsed_ack["slot"]

        # Step 3: JoinRequest  (PROTOCOL.md §C.2 step 3)
        self._tcp_send_raw(build_join_request(username, self.model_id))
        pkt_id, join_payload = self._wait_tcp_multi(
            (TCP_JOIN_ACCEPTED, TCP_JOIN_REJECTED), timeout=10
        )
        if pkt_id == TCP_JOIN_REJECTED:
            info = parse_join_rejected(join_payload)
            raise JoinError(info["reason"], info["reason_name"])
        joined = parse_join_accepted(join_payload)
        # Confirm slot (server may reassign; trust JoinAccepted)
        self.assigned_slot = joined["assigned_slot"]
        self.roster = joined["roster"]

        # Step 4: Bind UDP, send UdpRegister  (PROTOCOL.md §C.2 step 4)
        self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp.bind(("", 0))
        self._udp_port = self._udp.getsockname()[1]
        self._tcp_send_raw(build_udp_register(self._udp_port))

        # Start background threads
        self._start_threads()

        return self.assigned_slot

    def send_snapshot(self, snapshot: PlayerSnapshot) -> None:
        """Send a UDP PlayerSnapshot (id 20).  PROTOCOL.md §C.2 step 5."""
        if self._udp is None or self._closed:
            return
        with self._seq_lock:
            seq = self._seq
            self._seq = (self._seq + 1) & 0xFFFFFFFF
        pkt = build_player_snapshot(self.assigned_slot, seq, snapshot)
        try:
            self._udp.sendto(pkt, (self.host, self.port))
        except OSError:
            pass

    def close(self) -> None:
        """Send Disconnect and cleanly shut down.  PROTOCOL.md §C.2."""
        if self._closed:
            return
        self._closed = True
        self._close_event.set()
        # Send Disconnect over TCP
        try:
            if self._tcp:
                self._tcp_send_raw(build_disconnect())
        except OSError:
            pass
        # Close sockets (unblocks recv threads)
        for sock in (self._tcp, self._udp):
            try:
                if sock:
                    sock.close()
            except OSError:
                pass
        # Join threads
        for t in self._threads:
            t.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Private: TCP send
    # ------------------------------------------------------------------

    def _tcp_send_raw(self, data: bytes) -> None:
        """Send bytes over TCP with lock."""
        with self._tcp_lock:
            if self._tcp and not self._closed:
                self._tcp.sendall(data)

    # ------------------------------------------------------------------
    # Private: synchronous TCP read (used during join handshake only)
    # ------------------------------------------------------------------

    def _recv_tcp_frame(self, timeout: float) -> Tuple[int, bytes]:
        """Block until one TCP frame arrives. Returns (pkt_id, payload)."""
        self._tcp.settimeout(timeout)
        try:
            while True:
                chunk = self._tcp.recv(4096)
                if not chunk:
                    raise ConnectionError("Server closed connection")
                self._recv_buf.extend(chunk)
                result = try_unwrap_tcp(bytes(self._recv_buf))
                if result is not None:
                    pkt_id, payload, consumed = result
                    self._recv_buf = self._recv_buf[consumed:]
                    return pkt_id, payload
        finally:
            self._tcp.settimeout(None)

    def _wait_tcp(self, expected_id: int, timeout: float = 10) -> bytes:
        """Wait for a specific TCP packet id; discard others."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for TCP packet id {expected_id}")
            pkt_id, payload = self._recv_tcp_frame(min(remaining, 1.0))
            if pkt_id == expected_id:
                return payload
            # Discard unexpected packets during handshake

    def _wait_tcp_multi(self, expected_ids: tuple, timeout: float = 10) -> Tuple[int, bytes]:
        """Wait for one of several TCP packet ids."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for TCP packets {expected_ids}")
            pkt_id, payload = self._recv_tcp_frame(min(remaining, 1.0))
            if pkt_id in expected_ids:
                return pkt_id, payload

    # ------------------------------------------------------------------
    # Private: background threads
    # ------------------------------------------------------------------

    def _start_threads(self):
        for target in (self._tcp_recv_loop, self._udp_recv_loop, self._heartbeat_loop):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self._threads.append(t)

    def _tcp_recv_loop(self):
        """Receive and dispatch inbound TCP frames after join."""
        self._tcp.settimeout(1.0)
        buf = bytearray(self._recv_buf)  # carry over any leftover from handshake
        self._recv_buf.clear()
        while not self._closed:
            try:
                chunk = self._tcp.recv(4096)
                if not chunk:
                    break
                buf.extend(chunk)
                while True:
                    result = try_unwrap_tcp(bytes(buf))
                    if result is None:
                        break
                    pkt_id, payload, consumed = result
                    buf = buf[consumed:]
                    handler = self._tcp_handlers.get(pkt_id)
                    if handler:
                        try:
                            handler(payload)
                        except Exception:
                            pass
            except socket.timeout:
                continue
            except OSError:
                break

    def _udp_recv_loop(self):
        """Receive UDP SnapshotBatch datagrams and dispatch to callback."""
        if self._udp is None:
            return
        self._udp.settimeout(1.0)
        while not self._closed:
            try:
                data, _ = self._udp.recvfrom(4096)
                entries = parse_snapshot_batch(data)
                if entries and self.on_snapshot_batch:
                    try:
                        self.on_snapshot_batch(entries)
                    except Exception:
                        pass
            except socket.timeout:
                continue
            except OSError:
                break

    def _heartbeat_loop(self):
        """Send Heartbeat every 2 s.  PROTOCOL.md §B.5 / §C.2 step 6."""
        interval = HEARTBEAT_INTERVAL_MS / 1000.0
        while not self._close_event.wait(timeout=interval):
            try:
                self._tcp_send_raw(build_heartbeat())
            except OSError:
                break

    # ------------------------------------------------------------------
    # Private: inbound TCP handlers (post-join)
    # ------------------------------------------------------------------

    def _on_roster_snapshot(self, payload: bytes):
        # Compute the set of slots that have departed BEFORE replacing self.roster,
        # then fire on_player_left for each.  The server sends id-6 on any roster
        # change (join or leave), so a diff gives us the departed set.
        old_slots = {r.get("slot") for r in self.roster}
        self.roster = parse_roster_snapshot(payload)
        new_slots = {r.get("slot") for r in self.roster}
        departed = old_slots - new_slots
        for slot in departed:
            if self.on_player_left:
                try:
                    self.on_player_left(slot)
                except Exception:
                    pass

    def _on_player_left(self, payload: bytes):
        # id-13 payload is a roster blob (same format as id-6), NOT a bare slot byte.
        # Parse it as a roster snapshot to get the current member set, then diff
        # against self.roster to find who actually left.  This is the same logic as
        # _on_roster_snapshot, so both paths (id-6 and id-13) stay consistent.
        old_slots = {r.get("slot") for r in self.roster}
        new_roster = parse_roster_snapshot(payload)
        self.roster = new_roster
        new_slots = {r.get("slot") for r in self.roster}
        departed = old_slots - new_slots
        for slot in departed:
            if self.on_player_left:
                try:
                    self.on_player_left(slot)
                except Exception:
                    pass

    def _on_heartbeat(self, payload: bytes):
        # Server echoes our heartbeat payload back; nothing to do.
        pass

    def _on_disconnect(self, payload: bytes):
        self._closed = True
        self._close_event.set()
