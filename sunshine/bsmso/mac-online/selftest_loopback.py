"""BSMSO loopback self-test.

Assumes a BSMSO server is ALREADY running on 127.0.0.1:27015.
Spawns two ghost bots in-process, runs ~5 s, and asserts:
  - Bot A receives SnapshotBatch entries for bot B's slot (and vice versa)
  - The received positions change over time (the puppet moves)

Prints PASS/FAIL with observed slots and sample positions.
Exits nonzero on failure.
"""
import math
import sys
import time
import threading
from collections import defaultdict
from typing import List, Tuple

from netclient import NetClient, JoinError
from protocol import PlayerSnapshot, DEFAULT_PORT


SERVER_HOST = "127.0.0.1"
SERVER_PORT = DEFAULT_PORT
TEST_STAGE   = 1
TEST_EPISODE = 0
RUN_SECONDS  = 5.0
HZ           = 60.0
RADIUS       = 200.0


class BotRunner:
    """Runs a single ghost-bot in a background thread."""

    def __init__(self, name: str):
        self.name = name
        self.assigned_slot: int = -1
        self.received: defaultdict[int, List[Tuple[float, float, float]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._client: NetClient = None
        self._thread: threading.Thread = None
        self._stop_event = threading.Event()

    def _on_batch(self, entries):
        with self._lock:
            for slot, seq, snap in entries:
                if slot != self.assigned_slot:
                    self.received[slot].append((snap.pos_x, snap.pos_y, snap.pos_z))

    def start(self):
        """Connect, join, start sending loop in background thread."""
        self._client = NetClient(
            SERVER_HOST,
            port=SERVER_PORT,
            on_snapshot_batch=self._on_batch,
        )
        self.assigned_slot = self._client.join(self.name)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        interval = 1.0 / HZ
        angle = 0.0
        anim_id = 0
        anim_tick = 0
        while not self._stop_event.is_set():
            t0 = time.monotonic()
            px = RADIUS * math.cos(angle)
            pz = RADIUS * math.sin(angle)
            rot_y = math.degrees(angle + math.pi / 2) % 360.0
            anim_tick += 1
            if anim_tick >= int(HZ * 2):
                anim_tick = 0
                anim_id = (anim_id + 1) & 0xFFFF

            snap = PlayerSnapshot(
                pos_x=px,
                pos_y=500.0,
                pos_z=pz,
                rotation_y=rot_y,
                anim_id=anim_id,
                health=8,
                stage_id=TEST_STAGE,
                episode_id=TEST_EPISODE,
                connected=1,
                slot=self.assigned_slot,
                name=self.name.encode("utf-8")[:16].ljust(16, b'\x00'),
                anim_frame=anim_tick & 0xFFFF,
            )
            self._client.send_snapshot(snap)
            angle = (angle + (2 * math.pi) / (HZ * 5)) % (2 * math.pi)

            elapsed = time.monotonic() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._client:
            self._client.close()

    def received_positions_for(self, slot: int) -> List[Tuple[float, float, float]]:
        with self._lock:
            return list(self.received.get(slot, []))


def positions_are_changing(positions: List[Tuple[float, float, float]], min_delta: float = 0.01) -> bool:
    """Return True if position list contains at least 2 distinct positions."""
    if len(positions) < 2:
        return False
    first = positions[0]
    for p in positions[1:]:
        dx = p[0] - first[0]
        dy = p[1] - first[1]
        dz = p[2] - first[2]
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist > min_delta:
            return True
    return False


def main():
    print(f"[selftest] Connecting two bots to {SERVER_HOST}:{SERVER_PORT}…")

    bot_a = BotRunner("BotAlpha")
    bot_b = BotRunner("BotBeta")

    try:
        bot_a.start()
        print(f"[selftest] BotAlpha joined as slot {bot_a.assigned_slot}")
        bot_b.start()
        print(f"[selftest] BotBeta  joined as slot {bot_b.assigned_slot}")
    except JoinError as e:
        print(f"[selftest] FAIL — could not join: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[selftest] FAIL — unexpected error during join: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[selftest] Running for {RUN_SECONDS:.0f}s…")
    time.sleep(RUN_SECONDS)

    bot_a.stop()
    bot_b.stop()

    slot_a = bot_a.assigned_slot
    slot_b = bot_b.assigned_slot

    # Check A saw B's slot
    a_saw_b = bot_a.received_positions_for(slot_b)
    # Check B saw A's slot
    b_saw_a = bot_b.received_positions_for(slot_a)

    print()
    print(f"  BotAlpha (slot {slot_a}) saw slot {slot_b} (BotBeta):  {len(a_saw_b)} entries")
    print(f"  BotBeta  (slot {slot_b}) saw slot {slot_a} (BotAlpha): {len(b_saw_a)} entries")

    if a_saw_b:
        sample_a = a_saw_b[:3]
        print(f"  Sample positions A received for B: {sample_a}")
    if b_saw_a:
        sample_b = b_saw_a[:3]
        print(f"  Sample positions B received for A: {sample_b}")

    # Assertions
    failures = []

    if len(a_saw_b) == 0:
        failures.append(f"BotAlpha received 0 snapshots for BotBeta (slot {slot_b})")
    if len(b_saw_a) == 0:
        failures.append(f"BotBeta received 0 snapshots for BotAlpha (slot {slot_a})")
    if a_saw_b and not positions_are_changing(a_saw_b):
        failures.append("BotAlpha sees BotBeta's position but it is NOT changing")
    if b_saw_a and not positions_are_changing(b_saw_a):
        failures.append("BotBeta sees BotAlpha's position but it is NOT changing")

    print()
    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("PASS")
        print(f"  Observed slots: A={slot_a}, B={slot_b}")
        if a_saw_b:
            print(f"  A received {len(a_saw_b)} snapshots from B; "
                  f"first={a_saw_b[0]}, last={a_saw_b[-1]}")
        if b_saw_a:
            print(f"  B received {len(b_saw_a)} snapshots from A; "
                  f"first={b_saw_a[0]}, last={b_saw_a[-1]}")
        sys.exit(0)


if __name__ == "__main__":
    main()
