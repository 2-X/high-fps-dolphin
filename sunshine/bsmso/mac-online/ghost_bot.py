"""BSMSO ghost bot — sends a moving circular puppet to the relay server.

CLI:
    python3 ghost_bot.py --server HOST --name NAME [--stage N --episode N
                          --radius R --hz 60]

PROTOCOL.md §C.2.
"""
import argparse
import math
import sys
import time
import threading

from netclient import NetClient, JoinError
from protocol import PlayerSnapshot, DEFAULT_PORT

# ---------------------------------------------------------------------------
# Animation id constants (comm buffer / TMario::mAnimationID).
# Source: bse-fork/lib/sms_interface/include/SMS/Player/Mario.hxx
# ---------------------------------------------------------------------------
ANIM_IDLE     = 0xC3   # 195 — standing idle
ANIM_FALL     = 0x4C   # 76  — airborne/falling
ANIM_SPINJUMP = 0xF4   # 244 — spin jump

# UNVERIFIED — capture live by reading TMario::mAnimationID while walking/running;
# no walk/run ids are documented anywhere in this repo.
# Bot falls back to ANIM_IDLE until these are set.
ANIM_WALK = None
ANIM_RUN  = None


def _select_anim(speed: float) -> int:
    """Choose an animation id from the bot's horizontal speed (units/s).

    Walk/run ids are not yet verified (see ANIM_WALK/ANIM_RUN above).
    Falls back to ANIM_IDLE when the ids are unknown or speed is negligible.
    """
    if ANIM_WALK is None or ANIM_RUN is None or speed < 5.0:
        return ANIM_IDLE
    if speed < 20.0:
        return ANIM_WALK
    return ANIM_RUN


def run_bot(
    host: str,
    name: str,
    port: int = DEFAULT_PORT,
    stage: int = 1,
    episode: int = 0,
    radius: float = 200.0,
    hz: float = 60.0,
    follow: bool = True,
):
    """Connect and loop, sending a circling puppet.  Blocks until Ctrl-C.

    follow=True (default): adopt the stage/episode/position of the most recent
    peer snapshot relayed by the server, so the puppet circles right next to the
    live player (puppets only render for peers on the same stage — PROTOCOL.md
    §C.2).  Falls back to the --stage/--episode args until a peer is seen.
    """
    peers_seen: dict[int, list] = {}   # slot → list of recent positions
    peers_lock = threading.Lock()
    # Latest full state of any peer (for follow mode): (stage, episode, x, y, z)
    latest_peer = {"seen": False, "stage": stage, "episode": episode,
                   "x": 0.0, "y": 500.0, "z": 0.0}

    def on_batch(entries):
        with peers_lock:
            for slot, seq, snap in entries:
                if peers_seen.get(slot) is None:
                    peers_seen[slot] = []
                peers_seen[slot].append((snap.pos_x, snap.pos_y, snap.pos_z))
                if len(peers_seen[slot]) > 10:
                    peers_seen[slot].pop(0)
                if slot != client.assigned_slot and snap.connected:
                    latest_peer.update(seen=True, stage=snap.stage_id,
                                       episode=snap.episode_id,
                                       x=snap.pos_x, y=snap.pos_y, z=snap.pos_z)

    client = NetClient(host, port=port, on_snapshot_batch=on_batch)
    try:
        assigned_slot = client.join(name)
        print(f"[ghost_bot] joined as slot {assigned_slot} (name={name})")
    except JoinError as e:
        print(f"[ghost_bot] join failed: {e}", file=sys.stderr)
        client.close()
        return

    interval = 1.0 / hz
    angle = 0.0
    # angle_delta is constant for a fixed radius/hz: one full circle every 5 s.
    angle_delta = (2 * math.pi) / (hz * 5)
    # Horizontal speed in world units/s: arc length per radian × angular speed.
    speed = radius * abs(angle_delta) * hz
    status_tick = 0
    center_x, center_y, center_z = 0.0, 500.0, 0.0

    try:
        while True:
            t0 = time.monotonic()

            # Follow mode: center the circle on the live player and match their
            # stage/episode so the puppet renders right next to them.
            if follow and latest_peer["seen"]:
                with peers_lock:
                    center_x = latest_peer["x"]
                    center_y = latest_peer["y"]
                    center_z = latest_peer["z"]
                    cur_stage = latest_peer["stage"]
                    cur_episode = latest_peer["episode"]
            else:
                cur_stage, cur_episode = stage, episode

            # Compute circle position
            px = center_x + radius * math.cos(angle)
            pz = center_z + radius * math.sin(angle)
            # RotationY faces travel direction (tangent to circle)
            rot_y = math.degrees(angle + math.pi / 2) % 360.0

            # Select animation from actual travel speed.  anim_frame advances at
            # ~30 fps so the receiver-side interpolation doesn't hold frame 0.
            # bridge.py sanitizes any anim_id >=411 to 0, so ANIM_IDLE (0xC3=195)
            # is safe.  MUST stay within gMarioAnimeData (411 entries, ids 0..410).
            anim_id = _select_anim(speed)
            anim_frame = int(time.monotonic() * 30) & 0xFFFF

            # Velocity: derivative of circle position × angular rate.
            #   d/dt(center_x + r*cos(θ)) = -r*sin(θ)*ω  (ω = angle_delta * hz)
            omega = angle_delta * hz
            vel_x = -radius * math.sin(angle) * omega
            vel_z =  radius * math.cos(angle) * omega

            snap = PlayerSnapshot(
                pos_x=px,
                pos_y=center_y,
                pos_z=pz,
                vel_x=vel_x,
                vel_y=0.0,
                vel_z=vel_z,
                rotation_y=rot_y,
                anim_id=anim_id,
                nozzle_id=0,
                water=0,
                health=8,
                stage_id=cur_stage,
                episode_id=cur_episode,
                movement_state=0,
                action_id=0,
                vfx_flags=0,
                connected=1,
                slot=assigned_slot,
                ping_ms=0,
                name=name.encode("utf-8")[:16].ljust(16, b'\x00'),
                anim_frame=anim_frame,
                action_id_hi=0,
            )

            client.send_snapshot(snap)

            # Advance angle for next frame
            angle = (angle + angle_delta) % (2 * math.pi)

            # Periodic status
            status_tick += 1
            if status_tick >= int(hz * 5):
                status_tick = 0
                with peers_lock:
                    peer_slots = [s for s in peers_seen if s != assigned_slot]
                    fseen = latest_peer["seen"]
                    fstage = latest_peer["stage"]
                loc = (f"following stage={fstage} @({center_x:.0f},{center_y:.0f},"
                       f"{center_z:.0f})" if (follow and fseen)
                       else f"static stage={stage}")
                print(f"[ghost_bot] slot={assigned_slot} {loc} peers={peer_slots}")

            elapsed = time.monotonic() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        print(f"\n[ghost_bot] shutting down slot {assigned_slot}")
    finally:
        client.close()


def main():
    p = argparse.ArgumentParser(description="BSMSO ghost bot — circling puppet")
    p.add_argument("--server", required=True, help="Server hostname/IP")
    p.add_argument("--name",   required=True, help="Player name (unique, ≤15 chars)")
    p.add_argument("--port",   type=int, default=DEFAULT_PORT)
    p.add_argument("--stage",  type=int, default=1, help="StageId / course (default 1)")
    p.add_argument("--episode",type=int, default=0, help="EpisodeId (default 0)")
    p.add_argument("--radius", type=float, default=200.0, help="Circle radius in units")
    p.add_argument("--hz",     type=float, default=60.0,  help="Send rate in Hz")
    p.add_argument("--no-follow", dest="follow", action="store_false",
                   help="Disable auto-follow; stay at the fixed --stage/--episode/origin")
    args = p.parse_args()

    run_bot(
        host=args.server,
        name=args.name,
        port=args.port,
        stage=args.stage,
        episode=args.episode,
        radius=args.radius,
        hz=args.hz,
        follow=args.follow,
    )


if __name__ == "__main__":
    main()
