# The cheat codes

**You probably don't need to touch anything in here.** The config file in
[`../dolphin-config/`](../dolphin-config/) already contains all of these, ready to
go. Just follow the [setup guide](../docs/SETUP-WINDOWS.md).

This folder is here for reference and for people who want a different frame rate.

---

## What's what

| File | What it is |
|---|---|
| `120fps.txt` | The full 120 FPS code (speed fix + audio fix + ~30 bug fixes) |
| `180fps.txt` | Same, for 180 FPS |
| `240fps.txt` | Same, for 240 FPS |
| `widescreen-16-9.txt` | Optional 16:9 widescreen (includes the 2D-screen fix) |
| `fpspatch.py` | The generator that made the above — for other frame rates |

Each `*fps.txt` is a complete, self-contained Gecko code. It isn't just "run
faster" — most of it is the ~30 fixes that keep animations, timers, particles,
sound effects, and physics correct once the game is running several times faster
than Nintendo intended.

---

## Making a different frame rate

Want 300 FPS, or 360? Generate it with the included script (needs Python 3):

```bash
python3 fpspatch.py 300 > 300fps.txt
```

The number must be a multiple of 60. Then paste the result into your
`GMSE01.ini` and set `EmulationSpeed = <fps> / 60` to match. Run
`python3 fpspatch.py --help` to see the options.

> Higher frame rates need a faster CPU. If the game runs slow instead of smooth,
> your PC can't sustain that rate.
