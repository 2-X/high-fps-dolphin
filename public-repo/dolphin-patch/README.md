# The special Dolphin build

The high-FPS codes need a slightly modified version of Dolphin. Two of the
changes are what make everything work:

- **Correct audio at high speed** — without this, the music and sound effects
  play too fast.
- **Room for all the cheat codes** — stock Dolphin silently drops codes past a
  certain number; this lifts that limit.

(It also adds an optional frame-interpolation feature and a couple of quality-of-
life tweaks.)

---

## Just want to play? Don't build anything.

Grab the ready-made Windows build from the **[Releases page](../../releases)** and
skip the rest of this file. Building is only for people who want to compile it
themselves.

---

## Building it yourself

You need [Git](https://git-scm.com/) and, on Windows,
[Visual Studio 2022](https://visualstudio.microsoft.com/) with the "Desktop
development with C++" workload.

```bash
# 1. Get Dolphin's source at the exact version this patch was made for
git clone https://github.com/dolphin-emu/dolphin
cd dolphin
git checkout <the commit in UPSTREAM_COMMIT.txt>

# 2. Apply our modification
git apply /path/to/dolphin-patch/high-fps-dolphin.patch
```

Then build normally:

- **Windows:** open `Source/dolphin-emu.sln` in Visual Studio, pick `Release | x64`,
  and Build. The result is `Binaries\x64\Dolphin.exe`.
- **Linux / macOS:** `mkdir build && cd build && cmake .. && make -j`

The exact base version is pinned in
[`UPSTREAM_COMMIT.txt`](UPSTREAM_COMMIT.txt).

---

## Important runtime setting

After building, make sure the **memory-size override** is on, or some codes won't
run:

- In Dolphin: **Config → Advanced → Enable Emulated Memory Size Override**, set
  **MEM1** to 32 MiB.
- Our supplied `GMSE01.ini` already turns this on, so if you use our config files
  you don't have to touch this.

---

## License

Dolphin is licensed under the **GPLv2+**. This patch is our modification to it;
the full corresponding source is Dolphin's source plus
[`high-fps-dolphin.patch`](high-fps-dolphin.patch) in this folder. See
[../CREDITS.md](../CREDITS.md).
