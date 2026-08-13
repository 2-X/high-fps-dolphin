"""BSMSO v1.1 protocol constants, CRC32, framing, packet builders/parsers.

Wire endianness: LITTLE-endian (TCP/UDP).
Comm buffer endianness: BIG-endian (GameCube / PROTOCOL.md §A.2).

References: PROTOCOL.md §Master constants, §A.3, §B.0-B.2, §D.3.
"""
import struct
import dataclasses
from typing import Optional, List, Tuple

# ---------------------------------------------------------------------------
# Master constants  (PROTOCOL.md §"Master constants")
# ---------------------------------------------------------------------------
MAGIC               = 0x534D534F       # "SMSO" BE in RAM / anchor
PROTOCOL_VERSION    = 2                # TCP header version
COMM_VERSION        = 15              # comm-buffer Version field + anchor version
MOD_BUILD_ID        = 118             # join gate; mismatch → JoinRejected(VersionMismatch=4)
DEFAULT_PORT        = 27015           # TCP + UDP
MAX_PLAYERS         = 10
COMM_BUFFER_SIZE    = 5494
DEFAULT_MAILBOX_ADDR = 0x817FC000    # anchor guest address
SNAPSHOT_RATE_HZ    = 60
BRIDGE_POLL_MS      = 16
HEARTBEAT_INTERVAL_MS = 2000
STALE_TIMEOUT_MS    = 10000
DISCONNECT_TIMEOUT_MS = 15000
MEM1_GUEST_BASE     = 0x80000000
MEM1_GUEST_SIZE     = 0x1800000       # 24 MB
MEM1_MAPPED_SIZE    = 0x2000000       # 32 MB
COMM_MAILBOX_ANCHOR_SIZE = 12
WARP_NO_TARGET      = 252
WARP_ALL_SLOTS      = 255

# Comm buffer sub-region offsets (PROTOCOL.md §A.2)
COMM_BRIDGE_CONTROL_OFFSET    = 6
COMM_BRIDGE_CONTROL_SIZE      = 26
COMM_LOCAL_SNAPSHOT_OFFSET    = 48
COMM_REMOTE_SNAPSHOTS_OFFSET  = 112   # 10 × 64B
COMM_NAME_TAG_APPEARANCES_OFFSET = 752
COMM_NAME_TAG_APPEARANCES_SIZE   = 110
COMM_MARIO_VOICE_EVENTS_OFFSET = 862
COMM_MARIO_VOICE_EVENTS_SIZE   = 132
COMM_GAME_MODE_STATE_OFFSET   = 994
COMM_WORLD_SYNC_OFFSET        = 1015
COMM_ROSTER_HUD_OFFSET        = 1095
COMM_MARIO_MODEL_IDS_OFFSET   = 1297
COMM_MARIO_MODEL_IDS_SIZE     = 88
COMM_PROGRESS_SNAPSHOT_OFFSET = 1385
COMM_MUSIC_VOLUME_OFFSET      = 5493
SNAPSHOT_SIZE                 = 64
ROSTER_ENTRY_SIZE             = 30

# BridgeFlags (u32 BE @6; PROTOCOL.md §A.2)
BRIDGE_FLAG_CONNECTED       = 1
BRIDGE_FLAG_HOST            = 2
BRIDGE_FLAG_WARP_PENDING    = 4
BRIDGE_FLAG_LOADING         = 8
BRIDGE_FLAG_SYNC_SHINE      = 0x10
BRIDGE_FLAG_SYNC_BLUE_COIN  = 0x20
BRIDGE_FLAG_SYNC_EVENT      = 0x40
BRIDGE_FLAG_SYNC_STORY      = 0x80
BRIDGE_FLAG_SYNC_MISSION    = 0x100
BRIDGE_FLAG_SYNC_SECRET     = 0x200
BRIDGE_FLAG_SYNC_OBJECTS    = 0x400
BRIDGE_FLAG_SYNC_PROGRESS   = 0x800
BRIDGE_FLAG_REQUEST_PROGRESS = 0x1000
BRIDGE_FLAG_WARP_TO_POINT   = 0x2000
BRIDGE_FLAG_WARP_ALL        = 0x4000

# TcpPacketId (PROTOCOL.md §B.2)
TCP_HANDSHAKE               = 1
TCP_HANDSHAKE_ACK           = 2
TCP_JOIN_REQUEST            = 3
TCP_JOIN_ACCEPTED           = 4
TCP_JOIN_REJECTED           = 5
TCP_ROSTER_SNAPSHOT         = 6
TCP_WARP_REQUEST            = 7
TCP_WARP_COMMAND            = 8
TCP_SYNC_SETTINGS           = 9
TCP_WORLD_EVENT             = 10
TCP_DISCONNECT              = 11
TCP_HEARTBEAT               = 12
TCP_PLAYER_LEFT             = 13
TCP_UDP_REGISTER            = 14
TCP_MARIO_VOICE_EVENT       = 15
TCP_CLIENT_TELEPORT_SETTINGS = 16
TCP_GAME_MODE_STATE         = 17
TCP_WORLD_STATE_REPLAY      = 18
TCP_WORLD_PROGRESS_REQUEST  = 19
TCP_MARIO_MODEL_INTENT      = 20
TCP_WORLD_PROGRESS_SNAPSHOT = 21

# UdpPacketId (PROTOCOL.md §B.2)
UDP_PLAYER_SNAPSHOT         = 20
UDP_SNAPSHOT_BATCH          = 21
UDP_PING                    = 22
UDP_PONG                    = 23

# JoinRejectReason (PROTOCOL.md §B.2)
REJECT_NONE                 = 0
REJECT_NAME_TAKEN           = 1
REJECT_FULL                 = 2
REJECT_INVALID_NAME         = 3
REJECT_VERSION_MISMATCH     = 4

REJECT_NAMES = {
    0: "None",
    1: "NameTaken",
    2: "Full",
    3: "InvalidName",
    4: "VersionMismatch",
}

# DisconnectReason (PROTOCOL.md §B.2)
DISCONNECT_USER_REQUEST     = 0
DISCONNECT_TIMEOUT          = 1
DISCONNECT_KICKED           = 2
DISCONNECT_SERVER_SHUTDOWN  = 3
DISCONNECT_DOLPHIN_CLOSED   = 4

# UDP framing sizes (PROTOCOL.md §B.2)
UDP_SNAPSHOT_BATCH_HEADER_SIZE = 6   # magic(4)+id(1)+count(1)
UDP_BATCH_ENTRY_SIZE           = 69  # slot(1)+seq(4)+snapshot(64)
UDP_PLAYER_SNAPSHOT_SIZE       = 74  # magic(4)+id(1)+slot(1)+seq(4)+snapshot(64)

# TCP wire magic (LE bytes on wire = 4F 53 4D 53)
WIRE_MAGIC_LE = struct.pack("<I", MAGIC)  # b'\x4f\x53\x4d\x53'

# ---------------------------------------------------------------------------
# CRC32  (PROTOCOL.md §B.4 — reflected poly 0xEDB88320, init/xor 0xFFFFFFFF)
# ---------------------------------------------------------------------------
_CRC_TABLE = None

def _build_crc_table():
    global _CRC_TABLE
    tbl = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
        tbl.append(crc)
    _CRC_TABLE = tbl

def crc32(data: bytes) -> int:
    """Standard reflected CRC-32 (poly 0xEDB88320, init/xor 0xFFFFFFFF).

    Applied only to TCP frames (header + payload).  PROTOCOL.md §B.4.
    """
    if _CRC_TABLE is None:
        _build_crc_table()
    crc = 0xFFFFFFFF
    for b in data:
        crc = (crc >> 8) ^ _CRC_TABLE[(crc ^ b) & 0xFF]
    return crc ^ 0xFFFFFFFF

# ---------------------------------------------------------------------------
# TCP framing  (PROTOCOL.md §B.0 — WrapTcp / TryUnwrapTcp)
# ---------------------------------------------------------------------------
# Frame = header(9) + payload(N) + crc(4)   total = 13 + N
#   off 0: magic   u32 LE = 0x534D534F
#   off 4: version u16 LE = 2
#   off 6: id      u8
#   off 7: length  u16 LE = N
#   off 9: payload[N]
#   off 9+N: crc u32 LE
MAX_TCP_PAYLOAD = 60000
TCP_HEADER_SIZE = 9
TCP_FRAME_OVERHEAD = 13   # header(9) + crc(4)

def wrap_tcp(pkt_id: int, payload: bytes) -> bytes:
    """Build a complete TCP frame.  PROTOCOL.md §B.0."""
    n = len(payload)
    if n > MAX_TCP_PAYLOAD:
        raise ValueError(f"Payload too large: {n} > {MAX_TCP_PAYLOAD}")
    # 9-byte header, no alignment padding: magic u32 LE, version u16 LE, id u8, len u16 LE.
    header = struct.pack("<IHBH", MAGIC, PROTOCOL_VERSION, pkt_id, n)
    body = header + payload
    crc = crc32(body)
    return body + struct.pack("<I", crc)


def try_unwrap_tcp(buf: bytes) -> Optional[Tuple[int, bytes, int]]:
    """Try to parse one TCP frame from the start of buf.

    Returns (pkt_id, payload, consumed_bytes) or None if buf is too short.
    Raises ValueError on framing errors (bad magic/version/CRC).
    PROTOCOL.md §B.0.
    """
    if len(buf) < TCP_FRAME_OVERHEAD:
        return None
    magic, version, pkt_id, n = struct.unpack_from("<IHBH", buf, 0)
    total = TCP_FRAME_OVERHEAD + n
    if len(buf) < total:
        return None
    # Validate header
    if magic != MAGIC:
        raise ValueError(f"Bad TCP magic: {magic:#010x}")
    if version != PROTOCOL_VERSION:
        raise ValueError(f"Bad TCP version: {version} (expected {PROTOCOL_VERSION})")
    if n > MAX_TCP_PAYLOAD:
        raise ValueError(f"TCP payload length too large: {n}")
    # CRC covers header + payload
    body = buf[:TCP_HEADER_SIZE + n]
    expected_crc = crc32(body)
    got_crc = struct.unpack_from("<I", buf, TCP_HEADER_SIZE + n)[0]
    if got_crc != expected_crc:
        raise ValueError(f"TCP CRC mismatch: got {got_crc:#010x} expected {expected_crc:#010x}")
    payload = bytes(buf[TCP_HEADER_SIZE:TCP_HEADER_SIZE + n])
    return pkt_id, payload, total

# ---------------------------------------------------------------------------
# PlayerSnapshot dataclass  (PROTOCOL.md §A.3)
# ---------------------------------------------------------------------------
# Both comm-buffer (BE) and wire (LE) have identical field layout;
# only per-scalar byte order differs.

@dataclasses.dataclass
class PlayerSnapshot:
    """64-byte player snapshot.  PROTOCOL.md §A.3."""
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    vel_x: float = 0.0
    vel_y: float = 0.0
    vel_z: float = 0.0
    rotation_y: float = 0.0
    anim_id: int = 0        # u16
    nozzle_id: int = 0      # u8
    water: int = 0          # u8
    health: int = 0         # u8
    stage_id: int = 0       # u8
    episode_id: int = 0     # u8
    movement_state: int = 0 # u8
    action_id: int = 0      # u16
    vfx_flags: int = 0      # u16
    connected: int = 0      # u8
    slot: int = 0           # u8
    ping_ms: int = 0        # u16
    name: bytes = b'\x00' * 16   # 16 bytes
    anim_frame: int = 0     # u16
    action_id_hi: int = 0   # u16

    def pack_wire(self) -> bytes:
        """Pack snapshot LITTLE-endian (UDP wire).  PROTOCOL.md §A.3."""
        return _pack_snapshot(self, '<')

    def pack_comm(self) -> bytes:
        """Pack snapshot BIG-endian (comm buffer).  PROTOCOL.md §A.3."""
        return _pack_snapshot(self, '>')

    @classmethod
    def unpack_wire(cls, data: bytes) -> 'PlayerSnapshot':
        """Unpack from 64-byte little-endian wire data."""
        return _unpack_snapshot(data, '<')

    @classmethod
    def unpack_comm(cls, data: bytes) -> 'PlayerSnapshot':
        """Unpack from 64-byte big-endian comm buffer data."""
        return _unpack_snapshot(data, '>')


def _pack_snapshot(s: PlayerSnapshot, e: str) -> bytes:
    """Pack PlayerSnapshot into 64 bytes with endian e ('>'=>BE, '<'=>LE).

    Exact offsets per PROTOCOL.md §A.3:
      0   pos_x       f32
      4   pos_y       f32
      8   pos_z       f32
     12   vel_x       f32
     16   vel_y       f32
     20   vel_z       f32
     24   rotation_y  f32
     28   anim_id     u16
     30   nozzle_id   u8
     31   water       u8
     32   health      u8
     33   stage_id    u8
     34   episode_id  u8
     35   movement_state u8
     36   action_id   u16
     38   vfx_flags   u16
     40   connected   u8
     41   slot        u8
     42   ping_ms     u16
     44   name[16]    bytes
     60   anim_frame  u16
     62   action_id_hi u16
    """
    name16 = (s.name + b'\x00' * 16)[:16]
    buf = bytearray(64)
    struct.pack_into(f"{e}f", buf, 0,  s.pos_x)
    struct.pack_into(f"{e}f", buf, 4,  s.pos_y)
    struct.pack_into(f"{e}f", buf, 8,  s.pos_z)
    struct.pack_into(f"{e}f", buf, 12, s.vel_x)
    struct.pack_into(f"{e}f", buf, 16, s.vel_y)
    struct.pack_into(f"{e}f", buf, 20, s.vel_z)
    struct.pack_into(f"{e}f", buf, 24, s.rotation_y)
    struct.pack_into(f"{e}H", buf, 28, s.anim_id)
    struct.pack_into("B",     buf, 30, s.nozzle_id)
    struct.pack_into("B",     buf, 31, s.water)
    struct.pack_into("B",     buf, 32, s.health)
    struct.pack_into("B",     buf, 33, s.stage_id)
    struct.pack_into("B",     buf, 34, s.episode_id)
    struct.pack_into("B",     buf, 35, s.movement_state)
    struct.pack_into(f"{e}H", buf, 36, s.action_id)
    struct.pack_into(f"{e}H", buf, 38, s.vfx_flags)
    struct.pack_into("B",     buf, 40, s.connected)
    struct.pack_into("B",     buf, 41, s.slot)
    struct.pack_into(f"{e}H", buf, 42, s.ping_ms)
    buf[44:60] = name16
    struct.pack_into(f"{e}H", buf, 60, s.anim_frame)
    struct.pack_into(f"{e}H", buf, 62, s.action_id_hi)
    return bytes(buf)


def _unpack_snapshot(data: bytes, e: str) -> PlayerSnapshot:
    """Unpack 64-byte snapshot with endian e.  PROTOCOL.md §A.3."""
    if len(data) < 64:
        data = data + b'\x00' * (64 - len(data))
    s = PlayerSnapshot()
    s.pos_x          = struct.unpack_from(f"{e}f", data,  0)[0]
    s.pos_y          = struct.unpack_from(f"{e}f", data,  4)[0]
    s.pos_z          = struct.unpack_from(f"{e}f", data,  8)[0]
    s.vel_x          = struct.unpack_from(f"{e}f", data, 12)[0]
    s.vel_y          = struct.unpack_from(f"{e}f", data, 16)[0]
    s.vel_z          = struct.unpack_from(f"{e}f", data, 20)[0]
    s.rotation_y     = struct.unpack_from(f"{e}f", data, 24)[0]
    s.anim_id        = struct.unpack_from(f"{e}H", data, 28)[0]
    s.nozzle_id      = data[30]
    s.water          = data[31]
    s.health         = data[32]
    s.stage_id       = data[33]
    s.episode_id     = data[34]
    s.movement_state = data[35]
    s.action_id      = struct.unpack_from(f"{e}H", data, 36)[0]
    s.vfx_flags      = struct.unpack_from(f"{e}H", data, 38)[0]
    s.connected      = data[40]
    s.slot           = data[41]
    s.ping_ms        = struct.unpack_from(f"{e}H", data, 42)[0]
    s.name           = bytes(data[44:60])
    s.anim_frame     = struct.unpack_from(f"{e}H", data, 60)[0]
    s.action_id_hi   = struct.unpack_from(f"{e}H", data, 62)[0]
    return s

# ---------------------------------------------------------------------------
# TCP packet builders (client → server)
# ---------------------------------------------------------------------------

def build_handshake(guid: bytes = None) -> bytes:
    """Handshake (id 1) — 18-byte payload.  PROTOCOL.md §B.2.

    guid: 16 bytes (any; server ignores content). If None, uses os.urandom(16).
    """
    import os
    if guid is None:
        guid = os.urandom(16)
    payload = guid[:16].ljust(16, b'\x00') + struct.pack("<H", MOD_BUILD_ID)
    return wrap_tcp(TCP_HANDSHAKE, payload)


def build_join_request(username: str, model_id: bytes = None) -> bytes:
    """JoinRequest (id 3) — 26-byte payload.  PROTOCOL.md §B.2."""
    name_bytes = username.encode("utf-8")[:15].ljust(16, b'\x00')
    if model_id is None:
        model_id = b'\x00' * 8  # retail / empty model id
    payload = name_bytes + model_id[:8].ljust(8, b'\x00') + struct.pack("<H", MOD_BUILD_ID)
    return wrap_tcp(TCP_JOIN_REQUEST, payload)


def build_udp_register(udp_port: int) -> bytes:
    """UdpRegister (id 14) — 2-byte payload.  PROTOCOL.md §B.2."""
    return wrap_tcp(TCP_UDP_REGISTER, struct.pack("<H", udp_port))


def build_heartbeat() -> bytes:
    """Heartbeat (id 12) — 8-byte i64 LE timestamp.  PROTOCOL.md §B.2."""
    import time
    ts = int(time.monotonic() * 1000) & 0x7FFFFFFFFFFFFFFF
    return wrap_tcp(TCP_HEARTBEAT, struct.pack("<q", ts))


def build_disconnect(reason: int = DISCONNECT_USER_REQUEST) -> bytes:
    """Disconnect (id 11) — 1-byte reason.  PROTOCOL.md §B.2."""
    return wrap_tcp(TCP_DISCONNECT, struct.pack("B", reason))

# ---------------------------------------------------------------------------
# TCP packet parsers (server → client)
# ---------------------------------------------------------------------------

def parse_handshake_ack(payload: bytes) -> dict:
    """HandshakeAck (id 2) — 19-byte payload.  PROTOCOL.md §B.2.

    Returns {'slot': int, 'server_mod_build_id': int}.
    """
    if len(payload) < 19:
        raise ValueError(f"HandshakeAck payload too short: {len(payload)}")
    slot = payload[16]
    server_mod_build_id = struct.unpack_from("<H", payload, 17)[0]
    return {"slot": slot, "server_mod_build_id": server_mod_build_id}


def parse_join_accepted(payload: bytes) -> dict:
    """JoinAccepted (id 4).  PROTOCOL.md §B.2.

    Returns {'assigned_slot': int, 'roster': list[dict]}.
    """
    if len(payload) < 1:
        raise ValueError("JoinAccepted payload empty")
    assigned_slot = payload[0]
    roster = _parse_roster(payload[1:])
    return {"assigned_slot": assigned_slot, "roster": roster}


def parse_join_rejected(payload: bytes) -> dict:
    """JoinRejected (id 5) — 1-byte reason.  PROTOCOL.md §B.2."""
    reason = payload[0] if payload else 0
    return {"reason": reason, "reason_name": REJECT_NAMES.get(reason, str(reason))}


def _parse_roster(blob: bytes) -> List[dict]:
    """Parse a roster blob.  PROTOCOL.md §B.2 — RosterSnapshot.

    Each entry is 30 bytes: slot(1)+name(16)+stageId(1)+episodeId(1)+state(1)+pingMs(2)+modelId(8).
    """
    if not blob:
        return []
    count = blob[0]
    entries = []
    off = 1
    for _ in range(count):
        if off + ROSTER_ENTRY_SIZE > len(blob):
            break
        entry_slot   = blob[off]
        name         = blob[off+1:off+17]
        stage_id     = blob[off+17]
        episode_id   = blob[off+18]
        state        = blob[off+19]
        ping_ms      = struct.unpack_from("<H", blob, off+20)[0]
        model_id     = blob[off+22:off+30]
        entries.append({
            "slot": entry_slot,
            "name": name.rstrip(b'\x00').decode("utf-8", errors="replace"),
            "stage_id": stage_id,
            "episode_id": episode_id,
            "state": state,
            "ping_ms": ping_ms,
            "model_id": model_id,
        })
        off += ROSTER_ENTRY_SIZE
    return entries


def parse_roster_snapshot(payload: bytes) -> List[dict]:
    """RosterSnapshot (id 6) — same blob format as the roster in JoinAccepted.  PROTOCOL.md §B.2."""
    return _parse_roster(payload)


def parse_player_left(payload: bytes) -> dict:
    """PlayerLeft (id 13).  PROTOCOL.md §B.2."""
    slot = payload[0] if payload else 255
    return {"slot": slot}

# ---------------------------------------------------------------------------
# UDP packet builders / parsers
# ---------------------------------------------------------------------------

def build_player_snapshot(slot: int, seq: int, snapshot: PlayerSnapshot) -> bytes:
    """Build 74-byte UDP PlayerSnapshot (id 20).  PROTOCOL.md §B.2.

    Wire layout:
      off 0: magic u32 LE
      off 4: id    u8 = 20
      off 5: slot  u8
      off 6: seq   u32 LE
      off 10: snapshot[64] LE
    """
    hdr = (struct.pack("<I", MAGIC) +
           struct.pack("<B", UDP_PLAYER_SNAPSHOT) +
           struct.pack("<B", slot) +
           struct.pack("<I", seq))
    return hdr + snapshot.pack_wire()


def parse_snapshot_batch(datagram: bytes) -> List[Tuple[int, int, PlayerSnapshot]]:
    """Parse UDP SnapshotBatch (id 21) → list of (slot, seq, PlayerSnapshot).

    Wire layout (PROTOCOL.md §B.2):
      off 0: magic u32 LE
      off 4: id    u8 = 21
      off 5: count u8
      then count × 69 bytes: slot(1)+seq(4)+snapshot(64) LE
    """
    if len(datagram) < UDP_SNAPSHOT_BATCH_HEADER_SIZE:
        return []
    magic = struct.unpack_from("<I", datagram, 0)[0]
    if magic != MAGIC:
        return []
    pkt_id = datagram[4]
    if pkt_id != UDP_SNAPSHOT_BATCH:
        return []
    count = datagram[5]
    results = []
    off = UDP_SNAPSHOT_BATCH_HEADER_SIZE
    for _ in range(count):
        if off + UDP_BATCH_ENTRY_SIZE > len(datagram):
            break
        slot = datagram[off]
        seq  = struct.unpack_from("<I", datagram, off + 1)[0]
        snap_data = datagram[off + 5: off + 5 + SNAPSHOT_SIZE]
        snap = PlayerSnapshot.unpack_wire(snap_data)
        results.append((slot, seq, snap))
        off += UDP_BATCH_ENTRY_SIZE
    return results
