# Troubleshooting

Almost every problem is one of these. Check them in order.

---

### The game runs too FAST (chipmunk audio, Mario sprints)

Your emulation speed and your enabled cheat don't match, **or** you're not using
our special Dolphin.

- Make sure `EmulationSpeed` (top of `GMSE01.ini`) matches the bundle you turned
  on: `2.0` with 120, `3.0` with 180, `4.0` with 240.
- Make sure you launched **our** Dolphin (from Releases or your own build), not a
  normal copy. Normal Dolphin can't fix the audio speed.

---

### The game runs too SLOW (drags, choppy, laggy)

Your PC can't keep up with that frame rate. This isn't a bug — it's horsepower.

- Drop down a level: 240 → 180, or 180 → 120.
- Close other programs. Plug in a laptop. Set Windows to a high-performance power
  plan.
- Remember: **frame rate costs CPU, not GPU.** Lowering the resolution won't help.

---

### The cheats don't seem to work at all

Two usual causes:

1. **Cheats are off.** In Dolphin: **Config → General → Enable Cheats** must be
   ticked. (Our `Dolphin.ini` sets this, so this only happens if you skipped
   copying it.)
2. **The memory-size override is off.** This one is easy to miss and it silently
   breaks some codes. In Dolphin: **Config → Advanced → Enable Emulated Memory
   Size Override**, and set **MEM1** above 24 MiB (32 is fine). Our `GMSE01.ini`
   turns this on for you, so again — make sure you copied that file in.

---

### I edited GMSE01.ini but nothing changed

You almost certainly edited it **while Dolphin was open.** Dolphin overwrites
that file every time it closes, wiping your change.

**Fix:** fully quit Dolphin, edit the file, save, *then* reopen Dolphin.

---

### The FPS counter isn't showing

It's turned on in our `GFX.ini`. If you don't see it, you didn't copy that file
in — redo [Step 3](SETUP-WINDOWS.md#step-3--copy-in-the-config-files). (Or turn
it on manually: **Graphics → General → Show FPS**.)

---

### I loaded a save state and the speed went weird

Save states remember the settings that were active when you made them. If you
made one at a different FPS, loading it brings that speed back.

**Fix:** don't rely on old save states after changing FPS. Boot the game fresh
(don't load a state), or make a new state after switching.

---

### It still won't launch / crashes on boot

- Double-check your game is the **USA** version. These codes are USA-only.
- Make sure you're opening the game through **our** Dolphin build.
- Try booting with cheats temporarily off (untick Enable Cheats) to confirm the
  game itself runs; then turn them back on.

---

Still stuck? The [main README](../README.md) links to the projects this is built
on — their communities can help with general Dolphin questions.
