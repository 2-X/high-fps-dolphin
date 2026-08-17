# BSMSO v1.1 Protocol Spec (implementation-grade)

Reverse-engineered from the decompiled managed C# of the Windows launcher:
`SMSO.Net` (comm buffer + wire protocol + NetClient), `SMSO.Bridge` (Dolphin RAM
attach/read/write loop), `SMSO.Server` (relay server). All line references are into
the three `*.decompiled.cs` files under `sunshine/bsmso/decompiled/`.

BSMSO is **position-sync, server-relay** (not lockstep). The game module `_BSMSO.kxe`
maintains a fixed-layout *comm buffer* in GameCube MEM1. The bridge attaches to the
Dolphin process, reads the local player's outbound region, ships it over the network,
and writes remote players' inbound regions back into the buffer.

---

## Master constants (`ProtocolConstants`, SMSO.Net L9265)

| Name | Value | Notes |
|---|---|---|
| `Magic` | `0x534D534F` = `1397576527u` | ASCII "SMSO" (big-endian in RAM / anchor; little-endian on the TCP wire header) |
| `ProtocolVersion` | `2` | on-wire TCP header version |
| `CommVersion` | `15` | comm-buffer `Version` field + anchor version |
| `ModBuildId` | `118` | handshake/join version gate; **mismatch ⇒ JoinRejected(VersionMismatch=4)** |
| `DefaultPort` | `27015` | TCP **and** UDP |
| `MaxPlayers` / `MaxRemoteSlots` | `10` | 10 total slots (index 0..9). Server clamps configurable max to [2,10] |
| `CommBufferSize` | `5494` | exact struct size |
| `DefaultMailboxAddress` | `0x817FC000` = `2172633088u` | **guest address of the ANCHOR** (matches boot log `anchor @ 0x817FC000`) |
| `SnapshotRateHz` | `60` | UDP snapshot send rate |
| `BridgePollMs` / `UdpSnapshotIntervalMs` | `16` | poll + UDP cadence (~60 Hz) |
| `HeartbeatIntervalMs` | `2000` | client heartbeat |
| `StaleTimeoutMs` | `10000` | (client-side UDP-health) |
| `DisconnectTimeoutMs` | `15000` | **server drops a session with no activity for 15 s** |
| `Mem1GuestBase` | `0x80000000` | MEM1 start |
| `Mem1GuestSize` | `25165824` = `0x1800000` (24 MB) | MEM1 logical size |
| `Mem1MappedSize` | `0x2000000` (32 MB) | mapped span |
| `CommMailboxAnchorSize` | `12` | anchor record length |
| `WarpNoTarget` | `252` | |
| `WarpAllSlots` | `255` | |

CRC32 is the standard reflected CRC-32 (poly `0xEDB88320`, init `0xFFFFFFFF`,
xor-out `0xFFFFFFFF`): `Crc32.Compute`, SMSO.Net L1469.

---

# A. Comm buffer (Dolphin-RAM shared region)

## A.1 How the bridge LOCATES the comm buffer: the ANCHOR mechanism

The address is **dynamic** and found via a fixed **anchor pointer**, not by scanning
for the comm buffer directly. There are two things in guest RAM:

1. **The anchor** at guest `0x817FC000` (`DefaultMailboxAddress`). A 12-byte record:
   ```
   off 0  : magic[4]      = "SMSO" (0x53 0x4D 0x53 0x4F), byte order = big-endian
   off 4  : version u16   = 15  (big-endian)   // CommVersion
   off 6  : reserved u16  = 0   (big-endian)
   off 8  : bufferGuest u32 (big-endian)       // guest address of the comm buffer
   ```
   Confirmed by `TryParseAnchor` (SMSO.Bridge L5858): checks `magic == "SMSO"`,
   `ReadUInt16BigEndian(off 4) == 15`, `ReadUInt16BigEndian(off 6) == 0`, then reads
   `bufferGuest = ReadUInt32BigEndian(off 8)` and validates
   `0x80000000 <= bufferGuest < 0x82000000` (`2147483648 .. 2181038080`).
2. **The comm buffer** itself, whose guest address the anchor points to
   (at runtime `0x80567C10`; must not be assumed: always read it from the anchor).

Note `_guestMailboxAddress` is misleadingly named "mailbox" throughout the bridge; it
is the **anchor guest address** `0x817FC000`, and the resolved `MailboxHost` is the
**host address of the comm buffer** (i.e. after following the anchor).

### Guest→host translation (Dolphin fastmem arena)
`TryResolveMailboxFast` (SMSO.Bridge L5672):
- `anchorGuestOffset = guestMailbox - 0x80000000` (offset of the anchor within MEM1).
- Enumerate readable committed regions ≥ `MinFastmemArenaSize` (`8623489024` bytes ≈ 8 GB,
  Dolphin's fastmem arena). For each candidate arena base, and for each of
  `DolphinMemLayout.Mem1ViewBaseOffsets` (6 candidate view offsets; RVA-init array, the
  standard set being `0`, `PhysicalBaseOffset=0x80000000`, `LogicalBaseOffset=0x200000000`,
  etc.; see note below), compute
  `anchorHost = arenaBase + viewBaseOffset + anchorGuestOffset`, read 12 bytes there,
  `TryParseAnchor`. If it parses, compute the comm-buffer host address:
  ```
  commHost = anchorHost - anchorGuestOffset + (bufferGuest - 0x80000000)
  ```
  (SMSO.Bridge L5849; arithmetic written as `anchorHost - anchorGuestOffset + (uint)((int)bufferGuest - -2147483648)`),
  then confirm via `LooksLikeCommBuffer` (magic "SMSO" + version 15 at that host addr,
  and the first 12 bytes must **not** themselves parse as an anchor).
- The resolved `(arenaBase, viewBaseOffset)` is cached (`_cachedArenaBase`,
  `_cachedViewBaseOffset`) so subsequent resolves are one read.

### Fallback: `TryResolveMailboxScan` (SMSO.Bridge L5729)
Chunked scan (256 KB chunks, **16-byte stride**) of each readable region for the 4-byte
magic (`MatchesMagic`); at each hit it tries **both** interpretations: `LooksLikeCommBuffer`
(the hit IS the comm buffer) and `TryResolveFromAnchor` (the hit is an anchor pointing
elsewhere). Capped at `MaxBackgroundScanBytes = 1 GB` per region.

### Mac (Mach) equivalent
- Enumerate regions with `mach_vm_region` / `vm_region_recurse_64` (replaces
  `VirtualQueryEx`); keep committed, readable regions ≥ 5494 bytes.
- Read with `mach_vm_read_overwrite` (replaces `ReadProcessMemory`); write with
  `mach_vm_write` (replaces `WriteProcessMemory`).
- **Simplest robust approach:** don't replicate the fastmem-view math. Scan readable
  regions for the 4-byte magic `53 4D 53 4F` on a 4-byte stride. At each hit, first test
  the 12-byte anchor shape (`"SMSO"` + `be16==15` + `be16==0` + `be32 in [0x80000000,0x82000000)`).
  If it's an anchor, you have `bufferGuest`; then find the host address of `bufferGuest`
  by scanning again for a magic hit whose following bytes satisfy `LooksLikeCommBuffer`
  (magic + version 15) and whose first 12 bytes do **not** parse as an anchor. In practice
  the comm buffer sits at a fixed guest-offset delta from MEM1 base, so once you know the
  host address of the anchor (`hostAnchor`) you can compute
  `hostComm = hostAnchor + (bufferGuest - 0x817FC000)` because both live in the same MEM1
  view. This is the load-bearing invariant to replicate.

> Ambiguity: `Mem1ViewBaseOffsets` and `MagicBytes`/`CommMagicBytes` are populated by
> `RuntimeHelpers.InitializeArray` from RVA field data not present in the decompiled text.
> `MagicBytes` is provably `53 4D 53 4F` ("SMSO") from every consumer (`TryParseAnchor`,
> `LooksLikeCommBuffer`, `MatchesMagic`) and from `Magic=0x534D534F`. The exact six view
> offsets aren't recoverable from source, but the scan-based locate above does not need
> them.

## A.2 Full byte-level CommBuffer layout (`CommBuffer`, SMSO.Net L456; serialized by `CommBufferEndian`, L758)

`[StructLayout Pack=1, Size=5494]`. **Everything multi-byte in the comm buffer is
BIG-ENDIAN** (GameCube). `CommBufferEndian.FromDolphinBytes` / `ToDolphinBytes` do the
byte-swap; the managed struct is host-endian in memory but the RAM image is always BE.
There is **no CRC and no separate version/dirty counter inside the buffer** beyond
`Magic`+`Version`; producer/consumer is handled by region ownership (see D.1), not a
sequence flag.

| Off (dec / hex) | Field | Size | Type / endianness |
|---|---|---|---|
| 0 / 0x0000 | `Magic` | 4 | u32 BE = `0x534D534F` |
| 4 / 0x0004 | `Version` | 2 | u16 BE = 15 |
| 6 / 0x0006 | `BridgeFlags` | 4 | u32 BE (bitfield, see below) - **CommBridgeControlOffset=6** |
| 10 / 0x000A | `LocalSlot` | 1 | u8 |
| 11 / 0x000B | `DolphinState` | 1 | u8 enum |
| 12 / 0x000C | `PlayerCount` | 1 | u8 |
| 13 / 0x000D | `WarpTargetSlot` | 1 | u8 (default 252) |
| 14 / 0x000E | `WarpCourseId` | 1 | u8 |
| 15 / 0x000F | `WarpEpisodeId` | 1 | u8 |
| 16 / 0x0010 | `WarpPosX` | 4 | f32 BE |
| 20 / 0x0014 | `WarpPosY` | 4 | f32 BE |
| 24 / 0x0018 | `WarpPosZ` | 4 | f32 BE |
| 28 / 0x001C | `WarpFacingY` | 4 | f32 BE |
| 32 / 0x0020 | `LocalPlayerName[16]` | 16 | UTF-8, NUL-padded |
| 48 / 0x0030 | `LocalSnapshot` | 64 | PlayerSnapshot (A.3) |
| 112 / 0x0070 | `RemoteSnapshots[10]` | 640 | 10 × PlayerSnapshot - **CommRemoteSnapshotsOffset=112** |
| 752 / 0x02F0 | `LocalNameTagAppearance` | 10 | NameTagAppearance |
| 762 / 0x02FA | `RemoteNameTagAppearances[10]` | 100 | 10 × 10B - **CommNameTagAppearancesOffset=752, size 110** |
| 862 / 0x035E | `LocalMarioVoiceEvent` | 12 | MarioVoiceEvent |
| 874 / 0x036A | `RemoteMarioVoiceEvents[10]` | 120 | 10 × 12B - **CommMarioVoiceEventsOffset=862, size 132** |
| 994 / 0x03E2 | `GameModeState` | 21 | CommGameModeState (A.5) - **CommGameModeStateOffset=994** |
| 1015 / 0x03F7 | `WorldSync` | 80 | CommWorldSyncState - **CommWorldSyncOffset=1015** |
| 1095 / 0x0447 | `RosterHud` | 202 | CommRosterHudSync (A.5) - **CommRosterHudOffset=1095** |
| 1297 / 0x0511 | `LocalMarioModelId[8]` | 8 | CharacterPack model id - **CommMarioModelIdsOffset=1297, size 88** |
| 1305 / 0x0519 | `RemoteMarioModelIds[80]` | 80 | 10 × 8B |
| 1385 / 0x0569 | `ProgressSnapshotHostSeq` | 4 | u32 BE - **CommProgressSnapshotOffset=1385** |
| 1389 / 0x056D | `ProgressSnapshotModuleAppliedSeq` | 4 | u32 BE |
| 1393 / 0x0571 | `ProgressSnapshotPayloadLen` | 2 | u16 BE (≤4096) |
| 1395 / 0x0573 | `ProgressSnapshotFlags` | 1 | u8 |
| 1396 / 0x0574 | `ProgressSnapshotReserved` | 1 | u8 |
| 1397 / 0x0575 | `ProgressSnapshotPayload[4096]` | 4096 | opaque |
| 5493 / 0x1575 | `MusicVolume` | 1 | u8 (0..100, default 100) - **CommMusicVolumeOffset=5493** |
| **5494** | **TOTAL** | | matches `CommBufferSize` |

`BridgeFlags` (u32 BE @6, `BridgeFlags` enum SMSO.Net L9466):
`Connected=1, Host=2, WarpPending=4, Loading=8, SyncShine=0x10, SyncBlueCoin=0x20,
SyncEvent=0x40, SyncStory=0x80, SyncMission=0x100, SyncSecret=0x200, SyncObjects=0x400,
SyncProgress=0x800, RequestProgress=0x1000, WarpToPoint=0x2000, WarpAll=0x4000`.

`DolphinState` (u8 @11): `None=0, Booting=1, Loading=2, Active=3, Warping=4`.

The 26-byte block at offset 6 (`CommBridgeControlOffset=6, CommBridgeControlSize=26`)
= `BridgeFlags`+`LocalSlot`+`DolphinState`+`PlayerCount`+`Warp*` fields is the
**bridge→game control region** (the bridge writes it via `ApplyWarpIntentToControlSpan`,
SMSO.Net L872).

## A.3 Local-player OUTBOUND slot: `PlayerSnapshot` (64 B, SMSO.Net L8951; BE reader `ReadSnapshotInto` L1360)

`LocalSnapshot` @ comm offset 48. The game writes it; the bridge reads it each poll and
publishes it to the network. **Field byte layout within the 64-byte snapshot (BE in RAM):**

| Off | Field | Size | Type |
|---|---|---|---|
| 0 | `Position.X` | 4 | f32 BE |
| 4 | `Position.Y` | 4 | f32 BE |
| 8 | `Position.Z` | 4 | f32 BE |
| 12 | `Velocity.X` | 4 | f32 BE |
| 16 | `Velocity.Y` | 4 | f32 BE |
| 20 | `Velocity.Z` | 4 | f32 BE |
| 24 | `RotationY` | 4 | f32 BE (facing / yaw) |
| 28 | `AnimId` | 2 | u16 BE (animation id) |
| 30 | `NozzleId` | 1 | u8 (FLUDD nozzle) |
| 31 | `Water` | 1 | u8 (FLUDD water level) |
| 32 | `Health` | 1 | u8 |
| 33 | `StageId` | 1 | u8 (course/area) |
| 34 | `EpisodeId` | 1 | u8 |
| 35 | `MovementState` | 1 | u8 (nerve/action bucket) |
| 36 | `ActionId` | 2 | u16 BE (low 16 of nerve/action) |
| 38 | `VfxFlags` | 2 | u16 BE (see `VfxFlags` enum) |
| 40 | `Connected` | 1 | u8 (nonzero = live) |
| 41 | `Slot` | 1 | u8 |
| 42 | `PingMs` | 2 | u16 BE |
| 44 | `Name[16]` | 16 | UTF-8 + name-tag appearance marker in byte 15 |
| 60 | `AnimFrame` | 2 | u16 BE (animation frame cursor) |
| 62 | `ActionIdHi` | 2 | u16 BE (high 16 of action id) |

`VfxFlags` (u16, SMSO.Net L9493): `WaterSpray=1, Hover=2, Rocket=4, Turbo=8, Dead=0x10,
FluddEmpty=0x20, YCam=0x40, NozzleSwitching=0x80, WetSlide=0x100, NoFludd=0x200,
YoshiFruitMouth=0x400`. Held-object / Yoshi-fruit state is carried via `VfxFlags` +
world events (there is no dedicated held-object field in the snapshot).

> **Important on-wire endianness split:** the SAME 64-byte snapshot is BIG-endian inside
> the comm buffer (`CommBufferEndian.WriteSnapshot`) but LITTLE-endian on the UDP wire
> (`PacketSerializer.SnapshotToBytes`, L8695). The field offsets are identical; only the
> byte order of each scalar differs. The bridge translates between them.

## A.4 Remote-player INBOUND slots

`RemoteSnapshots[10]` @ comm offset **112**, stride **64**, 10 slots
(`slot k` at `112 + 64*k`). The bridge writes remote puppets here. Occupancy is the
per-snapshot `Connected` byte (@ +40 within the slot; nonzero = puppet active). `Slot`
(@ +41) echoes the index. Name-tag string is `Name[16]` (@ +44).

Parallel remote arrays keyed by the same slot index:
- `RemoteNameTagAppearances[10]` @ **762**, stride 10 (colors/outline/gradient).
- `RemoteMarioVoiceEvents[10]` @ **874**, stride 12.
- `RemoteMarioModelIds[80]` @ **1305**, stride 8 (CharacterPack model id per slot).

The bridge writes remotes as a fused block via `TryWriteRemoteSyncPayload`
(SMSO.Bridge L5163): a 750-byte scratch = `RemoteSnapshots(640)` + `NameTagAppearances(110)`
written at host `+112`, and a 141-byte scratch = `RemoteMarioVoiceEvents(120)` +
`GameModeState(21)` written at host `+874` (`862+12`). It skips the write when the bytes
are unchanged from last frame (dirty-diff, not a buffer sequence counter).

**Max slots = 10 (index 0..9). The local player also occupies one of these 10.**

## A.5 Roster / HUD / game-mode sub-structs

**`CommGameModeState`** (21 B @994, SMSO.Net L2148; BE reader `ReadGameModeStateInto` L1319):
```
+0  Mode           u8
+1  Flags          u8
+2  LocalRole      u8
+3  LastTaggedSlot u8   (default 255)
+4  TagEventId     u8
+5  RoundStartMs   u32 BE
+9  RoleBySlot[10] 10 bytes
+19 GraceRemainingMs u16 BE
```
**`CommRosterHudSync`** (202 B @1095, L644; reader `ReadRosterHudSyncInto` L1236):
```
+0  LatestSequence u16 BE
+2  Events[10], each CommRosterHudEvent (20 B):
      +0 Sequence u16 BE
      +2 Kind     u8   (RosterHudEventKind: None=0, Connected=1, Disconnected=2)
      +3 Slot     u8
      +4 Name[16]
```
These are **bridge→game** (the bridge writes them so the game HUD/roster reflects the
network state). `RosterHud` is written independently via `TryWriteRosterHudOnly`
(host `+1095`, SMSO.Bridge L5251).

**`CommWorldSyncState`** (80 B @1015): four `CommWorldEvent` (19 B each):
`LocalPendingOwnership`, `LocalPendingMission` (game→bridge outbound world events),
`IncomingOwnership`, `Incoming` (bridge→game), plus `LastAppliedEventId` u32 BE at +76.
`CommWorldEvent` (19 B): `EventId u32 BE`, `Sequence u16 BE`, `Type u8`, `CourseId u8`,
`EpisodeId u8`, `Payload0 u8`, `Reserved u8`, `Payload1 u32 BE`, `Payload2 u32 BE`.

---

# B. Wire protocol (port 27015, TCP + UDP)

## B.0 TCP framing (`PacketSerializer.WrapTcp` / `TryUnwrapTcp`, SMSO.Net L7826)

Every TCP message is length-prefixed, magic-tagged, and CRC-checked. **All wire scalars
are LITTLE-endian** (opposite of the comm buffer).

```
Frame = header(9) + payload(N) + crc(4)     total = 13 + N
 off 0 : magic   u32 LE = 0x534D534F ("SMSO")   // note: LE on the wire ⇒ bytes 4F 53 4D 53
 off 4 : version u16 LE = 2   (ProtocolVersion)
 off 6 : id      u8         (TcpPacketId)
 off 7 : length  u16 LE = N  (payload length, ≤ 60000 = MaxTcpPayloadSize)
 off 9 : payload[N]
 off 9+N : crc   u32 LE = Crc32.Compute(bytes[0 .. 9+N))   // CRC over header+payload, NOT incl crc
```
Reader validates magic==0x534D534F, version==2, N≤60000, total length exact, and CRC.
Framing helper `TryGetTcpFrameLength` reads the first 13 bytes to learn full length.

## B.1 UDP framing (`PacketSerializer.WriteUdpSnapshotInto` etc., L8604)

UDP datagrams: `magic u32 LE (0x534D534F)` + `id u8 (UdpPacketId)` + type-specific body.
**No length prefix, no CRC** (unreliable). Server drops datagrams < 7 bytes or with wrong
magic (SMSO.Server L1350).

## B.2 Message catalog

### `TcpPacketId` (u8, SMSO.Net L9419) - reliable
```
1  Handshake              9  WorldEvent           17 GameModeState
2  HandshakeAck          10  Disconnect           18 WorldStateReplay
3  JoinRequest           11  Heartbeat            19 WorldProgressRequest
4  JoinAccepted          12  PlayerLeft           20 MarioModelIntent
5  JoinRejected          13  UdpRegister          21 WorldProgressSnapshot
6  RosterSnapshot        14  MarioVoiceEvent
7  WarpRequest           15  ... (note enum starts at 1; MarioVoiceEvent=15)
8  WarpCommand           16  ClientTeleportSettings
```
(Enum order, ids 1..21: Handshake=1, HandshakeAck=2, JoinRequest=3, JoinAccepted=4,
JoinRejected=5, RosterSnapshot=6, WarpRequest=7, WarpCommand=8, SyncSettings=9,
WorldEvent=10, Disconnect=11, Heartbeat=12, PlayerLeft=13, UdpRegister=14,
MarioVoiceEvent=15, ClientTeleportSettings=16, GameModeState=17, WorldStateReplay=18,
WorldProgressRequest=19, MarioModelIntent=20, WorldProgressSnapshot=21.)

### `UdpPacketId` (u8, SMSO.Net L9443) - unreliable
`PlayerSnapshot=20, SnapshotBatch=21, Ping=22, Pong=23`.

### Payload layouts (all payload-internal scalars LITTLE-endian)

**Handshake (id 1)** - 18-byte payload (`BuildHandshake` L7915):
`clientGuid[16]` (`Guid.ToByteArray()` layout) + `modBuildId u16 LE` (=118).

**HandshakeAck (id 2)** - 19-byte payload (`BuildHandshakeAck` L7934):
16 zero bytes + `slot u8` (@16) + `serverModBuildId u16 LE` (@17). (Client reads slot@16.)

**JoinRequest (id 3)** - 26-byte payload (`BuildJoinRequest` L7961):
`username[16]` UTF-8 NUL-pad (≤15 bytes) + `marioModelId[8]` (CharacterPack.EncodeModelId,
@16) + `modBuildId u16 LE` (@24, =118).

**JoinAccepted (id 4)** - payload = `assignedSlot u8` (@0) + **roster blob** (rest).
Client: `_assignedSlot = payload[0]; ParseRoster(payload[1..])` (SMSO.Net L7430).

**JoinRejected (id 5)** - 1-byte payload = `JoinRejectReason`:
`None=0, NameTaken=1, Full=2, InvalidName=3, VersionMismatch=4`.

**RosterSnapshot (id 6)** / roster blob (`BuildRoster`, SMSO.Server L3396):
`count u8`, then `count` entries of **30 bytes** each (`RosterEntrySize=30`):
`slot u8` + `name[16]` + `stageId u8` + `episodeId u8` + `state u8 (DolphinState)`
+ `pingMs` (`BitConverter.GetBytes(ushort)` = 2 bytes LE) + `modelId[8]`.
(30 = 1+16+1+1+1+2+8.)

**WarpRequest (id 7)** - 3 bytes: `targetSlot, courseId, episodeId`.
**WarpCommand (id 8)** - 4 bytes: `targetSlot, courseId, episodeId, requesterSlot`.
**SyncSettings (id 9)** - 3 bytes: `syncFlags, syncObjects, syncProgress` (each 0/1).
**ClientTeleportSettings (id 16)** - 1 byte: `allowClientTeleport` (0/1).

**WorldEvent (id 10)** - polymorphic by direction:
- client→server request (`BuildWorldEventRequest` L8494), **15 bytes**:
  `sequence u16 LE`, `type u8`, `courseId u8`, `episodeId u8`, `payload0 u8`,
  `reserved u8`, `payload1 u32 LE`, `payload2 u32 LE`.
- server→client broadcast (`BuildWorldEventBroadcast` L8525), **17 bytes**:
  `eventId u32 LE`, `type u8`, `courseId u8`, `episodeId u8`, `payload0 u8`,
  `reserved u8`, `payload1 u32 LE`, `payload2 u32 LE`.
`WorldEventType` (u8, L9514): ShineCollected=1, BlueCoinCollected=2, EpisodeComplete=3,
StoryFlag=4, TriggerFlag=5, SecretComplete=6, GoldCoinCollected=7, HipDropObject=8,
RedCoinCollected=9, YoshiFruitTaken=10, MarioFruit{Kicked=11,Picked=12,Thrown=13,
Dropped=14,Sync=15}, NpcReact=16, NpcCleaned=17, GraffitiCleaned=18,
SessionProgressReset=19.

**WorldStateReplay (id 18)** - `count u16 LE` then `count` × 17-byte broadcast records
(`TryReadWorldStateReplay` L8558). Sent to a joiner to replay authoritative world state.

**Disconnect (id 11)** - 1 byte `DisconnectReason`
(`UserRequest=0, Timeout=1, Kicked=2, ServerShutdown=3, DolphinClosed=4`).
**Heartbeat (id 12)** - 8-byte payload `timestamp i64 LE` (`BuildHeartbeat` L8088);
server echoes the same payload back.
**PlayerLeft (id 13)** - broadcast when a slot frees.
**UdpRegister (id 14)** - 2-byte payload `udpPort u16 LE` (`BuildUdpRegister` L8590).
The server binds the client's UDP endpoint = `(TCP-source-IP, announced udpPort)`
(SMSO.Server L746).
**MarioVoiceEvent (id 15)** - 11-byte payload (`BuildMarioVoiceEvent` L8132):
`slot u8`, `soundId u32 LE`, `sequence u16 LE`, `flags u8`, `health u8`, `stageId u8`,
`episodeId u8`.
**GameModeState (id 17)** - 22-byte payload (`BuildGameModeState` L8020):
`gameMode u8`, `flags u8`, `seq u16 LE`, `roundStartMs u32 LE`, `tagEventId u8` (@8),
`roleBySlot[10]` (@9..18), `lastTaggedSlot u8` (@19), `graceRemainingMs u16 LE` (@20).
**WorldProgressRequest (id 19)** - 4-byte payload `clientProgressSeq u32 LE`.
**MarioModelIntent (id 20)** - 12-byte payload (`BuildMarioModelIntent` L8100):
`sequence u32 LE` + `marioModelId[8]`.
**WorldProgressSnapshot (id 21)** - variable TLV blob (`BuildWorldProgressSnapshotPayload`
L8197): header `formatByte=2`, `unchanged u8`, `progressSeq u32 LE`; if changed:
`shineBits[32]`, then count-prefixed lists (blue courses u8-count of {courseId u8,
mask u64 LE}; story/secret u16-count of {id u32 LE, val u8}; trigger u16-count of
{courseId,episodeId,id u32 LE,val u8}; redStages u16-count of {courseId,episodeId,mask,
packedPos[8] u32 LE}; npcCleanStages u16-count of {courseId,episodeId,val u16 LE}).

### The high-frequency position update

**UDP PlayerSnapshot (id 20)** - client→server, **74 bytes** (`WriteUdpSnapshotInto` L8604):
```
off 0 : magic u32 LE = 0x534D534F
off 4 : id    u8     = 20
off 5 : slot  u8
off 6 : seq   u32 LE
off 10: snapshot[64]   (PlayerSnapshot, LITTLE-endian per SnapshotToBytes)
```
**UDP SnapshotBatch (id 21)** - server→clients, up to 696 bytes
(`WriteUdpSnapshotBatchHeader`/`Entry` L8618):
```
off 0 : magic u32 LE
off 4 : id    u8 = 21
off 5 : count u8 (≤10)
then count entries of 69 bytes: slot u8, seq u32 LE, snapshot[64]
```
(`UdpSnapshotBatchHeaderSize=6, EntrySize=69, MaxSize=696`.)
**UDP Ping (id 22)** - 18 bytes: magic + id + `slot u8` + `u32 LE (0)` + `timestampMs i64 LE`
(`WriteUdpPingInto` L8674). **Pong (id 23)** - server reply for RTT.

## B.3 TCP vs UDP split
- **Reliable (TCP):** all join/handshake, roster, warp, sync-settings, world events,
  world-progress, mario-model-intent, mario-voice, game-mode-state, heartbeat, disconnect.
- **Unreliable (UDP):** the high-frequency **PlayerSnapshot** (client→server, id 20) and
  server→client **SnapshotBatch** (id 21), plus **Ping/Pong** (22/23) for RTT.
- Ordering: UDP carries a per-sender **`seq u32`** (monotonic; the server keeps the latest
  and drops stale via `LastSnapshotSeq`). TCP is inherently ordered by the stream.

## B.4 CRC32
Applied **only** to TCP frames: `crc = Crc32.Compute(header + payload)` appended as the
last 4 bytes (LE). Standard reflected CRC-32 (poly `0xEDB88320`, init `0xFFFFFFFF`,
final xor `0xFFFFFFFF`). No CRC on UDP and no CRC inside the comm buffer.

## B.5 Tick / rate / keepalive
- Bridge poll + UDP snapshot: every **16 ms** (~60 Hz) when Dolphin is running; 250 ms
  when idle (SMSO.Bridge L354). `SnapshotRateHz=60`.
- Client **Heartbeat every 2000 ms** (id 12); server echoes it and updates `LastSeen`.
- **Server drops any session idle > 15000 ms** (`DisconnectTimeoutMs`, reclaim logic
  `IsSessionReclaimable`, SMSO.Server L3057). A *nameless* (pre-JoinRequest) session is
  reclaimable after **5000 ms**. ⇒ **A bot must send a heartbeat (or any packet that
  touches `LastSeen`: Heartbeat, UDP snapshot, world event, etc.) at least every ~15 s;
  send every 2 s to match the reference client.**

---

# C. Server behavior

## C.1 On join / event / disconnect (SMSO.Server L576+)
- **Handshake (id 1):** `AssignSlot` (L2907) picks the lowest free slot 0..9 (host-claim
  logic may reserve slot 0 for a same-process/loopback host). If full it tries to reclaim
  stale sessions, else replies `JoinRejected(Full=2)`. On success replies **HandshakeAck**
  with the assigned slot. Version gate: if the handshake's modBuildId ≠ 118 ⇒
  `JoinRejected(VersionMismatch=4)`.
- **JoinRequest (id 3):** re-checks modBuildId==118, validates the username
  (`PlayerNameValidator`) and uniqueness (`TryRegisterName`, L3100; duplicate live name ⇒
  `JoinRejected(NameTaken=1)`; invalid ⇒ `InvalidName=3`). On success it sets the model id,
  then sends, in order: **JoinAccepted** (`[slot][roster]`), **SyncSettings**,
  **ClientTeleportSettings**, **GameModeState**, optionally a progress snapshot, and
  broadcasts an updated roster to everyone.
- **World event (id 10):** authority-checked and de-duplicated per type (shine/blue/red/
  story/secret/trigger/npc), then rebroadcast to all as a 17-byte broadcast with a
  server-assigned `eventId`. World events use the "snapshot-only"/fanout policy in
  `WorldEventTcpPolicy`.
- **UDP snapshot (id 20):** `TryApplySnapshotFromUdp` validates the datagram's `slot`
  matches the session and updates `LatestUdpSnapshotPacket` + `LastSnapshotSeq` + `LastSeen`.
  A separate **UdpSnapshotBroadcastLoop** (L1493) runs continuously: it packs the latest
  snapshot of **every** session with a bound UDP endpoint into one `SnapshotBatch` and
  sends it to **every** session with a UDP endpoint.
  ⇒ **The server DOES echo the sender's own snapshot back** (the batch includes all
  slots). The *client* filters its own slot on receive (`b != _assignedSlot`, SMSO.Net UDP
  read loop): a bot can simply ignore its own slot too.
- **Disconnect / timeout:** `RemoveSession` frees the slot, records a `_recentReleases`
  entry (30 s reconnect window to preserve slot/name), and broadcasts roster + PlayerLeft.

## C.2 Absolute-minimum ghost-bot checklist (moving puppet in another player's game)

Ordered exact packets (magic `0x534D534F` LE, version 2, CRC32 appended on all TCP):

1. **TCP connect** to `server:27015`.
2. **Send Handshake (id 1):** payload `guid[16]` + `modBuildId=118` (u16 LE). Wait for
   **HandshakeAck (id 2)**; read your `slot` from payload byte 16.
3. **Send JoinRequest (id 3):** `username[16]` (unique, valid) + `modelId[8]` +
   `modBuildId=118`. Wait for **JoinAccepted (id 4)**; confirm `slot = payload[0]`.
   (If you get JoinRejected, stop and read the reason byte.)
4. **Bind a local UDP socket**; **Send UdpRegister (id 14)** over TCP with your local
   UDP port (u16 LE). The server now knows where to send you the batch and will accept
   your snapshots.
5. **Loop at ~60 Hz (16 ms):** send **UDP PlayerSnapshot (id 20):** 74 bytes:
   magic + `id=20` + `slot=yourSlot` + `seq++` (u32 LE) + 64-byte PlayerSnapshot
   (**little-endian**). Vary `Position`/`RotationY`/`AnimId` frame-to-frame so the puppet
   visibly moves. Set `Connected=1`, `Slot=yourSlot`, a valid `StageId`/`EpisodeId`
   matching where the other player is (puppets only render for peers on the same stage).
6. **Every ~2 s:** send **Heartbeat (id 12)** (8-byte i64 LE timestamp) so the server
   doesn't reclaim you at the 15 s timeout. (Sending snapshots also refreshes `LastSeen`,
   but the heartbeat is the safe, model-faithful keepalive.)

That is sufficient: the server relays your snapshots inside its SnapshotBatch to every
peer; each peer's bridge writes your snapshot into `RemoteSnapshots[yourSlot]` and the
game renders a moving puppet. GameModeState / world events / model-intent are **not**
required for a visible moving puppet.

---

# D. Implementation notes for the Mac rebuild

## D.1 Producer/consumer handshake with the comm buffer
There is **no dirty/ready flag or sequence counter** guarding the buffer. Coherency is by
**region ownership**, which the Mac bridge must honor to avoid torn reads / clobbering:
- **Game → bridge (read-only for the bridge):** the header/control validated fields
  (`Magic`,`Version`), `LocalSnapshot` (@48), `LocalMarioVoiceEvent` (@862),
  `WorldSync.LocalPending*` (@1015/@1034), and `BridgeFlags.RequestProgress`. The bridge
  reads the whole 5494 bytes each poll, checks `Magic==0x534D534F` (and expects
  `Version==15`), and only *consumes* these (e.g. clears `RequestProgress` in its working
  copy, does not necessarily write it back unless it owns the control region).
- **Bridge → game (bridge writes, game reads):** `RemoteSnapshots` (@112),
  `NameTagAppearances` (@752), `MarioVoiceEvents remote` (@874), `GameModeState` (@994),
  `WorldSync.Incoming*` (@1053/@1072), `RosterHud` (@1095), `MarioModelIds` (@1297),
  `MusicVolume` (@5493), and the 26-byte control block (@6, warp intent).
- **Never write the whole 5494-byte buffer in one shot in steady state:** that would
  clobber the game's live `LocalSnapshot`. Mirror the reference bridge: do **targeted
  sub-region writes** at the exact host offsets above (it uses `TryWriteRemoteSyncPayload`
  @+112 and @+874, `TryWriteRosterHudOnly` @+1095, `TryWriteMarioModelIdsOnly` @+1297,
  `TryWriteMusicVolumeOnly` @+5493, `ApplyWarpIntentToControlSpan` @+6). It also skips a
  write when the new bytes equal the last-written bytes (dirty-diff) to minimize traffic.
- Each write is a single `mach_vm_write`; the reference relies on OS write atomicity of
  the contiguous block (no fences). Torn reads are tolerated because remote snapshots are
  re-sent at 60 Hz and interpolated (`RemoteInterpolation`).

## D.2 Windows-specific bridge logic → Mach equivalents
| Windows | Mach / macOS |
|---|---|
| `OpenProcess` + PID | `task_for_pid` (needs entitlement / sudo) |
| `VirtualQueryEx` region walk | `mach_vm_region` / `vm_region_recurse_64` loop (State==committed, readable prot) |
| `ReadProcessMemory` | `mach_vm_read_overwrite` |
| `WriteProcessMemory` | `mach_vm_write` |
| fastmem arena ≥ 8 GB heuristic | same idea, or just magic-scan MEM1-sized readable regions |
| region cache (1 s TTL) | keep it; region layout is stable while Dolphin runs |
| `PeriodicTimer(16ms)` poll | any 16 ms tick; re-resolve anchor on read failure / magic mismatch |
No memory barriers are used on Windows beyond the syscall boundary; none are needed on
Mach. **Re-resolution:** if a read returns the wrong magic, invalidate the cached address
and re-run the anchor resolve (the game can relocate the buffer across boots).

## D.3 Embedded constants quick table
| Constant | Value |
|---|---|
| Magic (comm BE / anchor) | `53 4D 53 4F` = "SMSO" = `0x534D534F` |
| Magic on TCP/UDP wire | same u32 written **little-endian** ⇒ bytes `4F 53 4D 53` |
| TCP header version | `2` |
| Comm `Version` / anchor version | `15` |
| ModBuildId (join gate) | `118` |
| Port (TCP+UDP) | `27015` |
| Anchor guest addr | `0x817FC000` |
| Anchor record | 12 B: `"SMSO"` + `be16=15` + `be16=0` + `be32 bufferGuest` |
| bufferGuest valid range | `0x80000000 .. 0x82000000` |
| Comm buffer size | `5494` |
| Max slots | `10` |
| PlayerSnapshot size | `64` |
| UDP snapshot / batch-entry | `74` / `69` (+6 header) |
| Poll / snapshot cadence | `16 ms` (~60 Hz) |
| Heartbeat | `2000 ms` |
| Server idle timeout | `15000 ms` (nameless `5000 ms`) |
| Reconnect window | `30000 ms` |
| CRC32 | reflected, poly `0xEDB88320`, init/xor `0xFFFFFFFF`, TCP frame header+payload only |

---

## Verifiability / open ambiguities
- **Byte-verified** against `CommBufferEndian` (comm offsets), `PacketSerializer` (wire
  layouts), `ProtocolConstants` (constants), and the server's join/relay code. Computed
  comm offsets match every `ProtocolConstants.Comm*Offset` exactly (total 5494).
- **`Mem1ViewBaseOffsets` and the magic byte arrays** are RVA-initialized (not in the
  decompiled text). `MagicBytes = "SMSO"` is provable from all consumers; the six fastmem
  view offsets are not, but the magic-scan locate in A.1 does not require them.
- **`Guid.ToByteArray()`** in the Handshake uses .NET's mixed-endian GUID layout; for a
  bot the 16 bytes are opaque (the server does not parse them), so any 16 bytes work.
- **CharacterPack model-id encode/decode** (8-byte field) is a separate codec
  (`CharacterPack.EncodeModelId`/`DecodeModelId`); an empty/"retail" id is the safe
  default for a ghost bot.
