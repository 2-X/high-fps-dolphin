# Super Mario Sunshine at 120 / 180 / 240 FPS

Play Super Mario Sunshine on PC at double, triple, or quadruple the original
frame rate — with **correct game speed, correct audio, correct timers, and ~30
bug fixes** so the game still plays exactly like it should, just smoother.

This works with a lightly-modified version of the **Dolphin** emulator plus a
set of cheat codes. Everything you need is in this repo. **You provide your own
game** — see below.

---

## What you need first

1. **A Windows PC.** (A reasonably fast one — see [How fast can I go?](#how-fast-can-i-go) below.)
2. **Your own copy of Super Mario Sunshine**, dumped from your own disc to an
   `.iso` or `.rvz` file. We do **not** provide the game — that would be illegal.
   Dolphin's official guide walks you through dumping a disc:
   <https://dolphin-emu.org/docs/guides/ripping-games/>
   (It must be the **USA / North American** version.)

---

## Setup in 5 steps

Full click-by-click instructions are in **[docs/SETUP-WINDOWS.md](docs/SETUP-WINDOWS.md)**.
The short version:

1. **Get the special Dolphin.** Download the ready-made build from the
   [Releases page](../../releases), or build it yourself
   ([dolphin-patch/README.md](dolphin-patch/README.md)).
2. **Copy the config files** from [`dolphin-config/`](dolphin-config/) into
   Dolphin's user folder (this turns on the cheats and the correct settings).
3. **Open your game** in Dolphin and set up your controller.
4. **Press Play.** You're now at 120 FPS.
5. **Want 180 or 240?** Change two lines in one file — see the setup guide.

If something doesn't look right, check
**[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — it lists the handful of
things that commonly trip people up (and their one-line fixes).

---

## How fast can I go?

| Target | You need | Rough guide |
|---|---|---|
| **120 FPS** | An okay gaming PC | Almost anything modern handles this |
| **180 FPS** | A fast PC | Needs a strong CPU |
| **240 FPS** | A very fast PC | High-end CPU, tested working |

Higher frame rates cost **CPU**, not graphics power — a monster GPU won't help if
the processor can't keep up. If the game runs *slow* instead of smooth, your PC
can't sustain that rate; drop down one level.

---

## What's in this folder

| Folder | What it is |
|---|---|
| [`dolphin-patch/`](dolphin-patch/) | The modification to Dolphin + how to build it |
| [`gecko-codes/`](gecko-codes/) | The cheat codes for 120 / 180 / 240 FPS (already made for you) |
| [`dolphin-config/`](dolphin-config/) | Ready-to-use Dolphin settings — just copy them in |
| [`docs/`](docs/) | The step-by-step setup guide and troubleshooting |
| [`CREDITS.md`](CREDITS.md) | Who made what, and the licenses |

---

## The one rule

**Never share the game files.** Not the ISO, not save states, not ripped
textures. Share this repo (it has no Nintendo files in it) and tell people to
dump their own disc. That's the line that keeps this project alive.
