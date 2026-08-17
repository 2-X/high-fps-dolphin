# Setup guide (Windows)

Follow these in order. It takes about 15 minutes. You only do steps 1–4 once.

> **Before you start** you need two things:
> - Your own **Super Mario Sunshine (USA)** game file (`.iso` or `.rvz`). See the
>   [main README](../README.md#what-you-need-first) for how to get one legally.
> - This repo, downloaded to your PC (green **Code → Download ZIP** button on
>   GitHub, then unzip it).

---

## Step 1 — Get the special Dolphin

Regular Dolphin will **not** work (the audio would play too fast). You need our
build.

**Easiest way:** go to the **[Releases page](../../releases)** and download the
Windows build. Unzip it anywhere you like, e.g. `C:\SMS-Dolphin\`.

**Or build it yourself** if you prefer — see
[dolphin-patch/README.md](../dolphin-patch/README.md).

---

## Step 2 — Find Dolphin's user folder

Dolphin keeps its settings in one folder. You need to find it, because in the
next step you'll copy our files into it.

- Open Dolphin once, then close it. This makes the folder appear.
- It's usually here:
  ```
  C:\Users\<your name>\Documents\Dolphin Emulator\
  ```
- **If that folder doesn't exist**, look for a folder called `User` sitting right
  next to `Dolphin.exe`. (Some downloads are "portable" and keep settings there.)

Inside it you'll see folders named `Config`, `GameSettings`, and others. Good —
that's the right place.

---

## Step 3 — Copy in the config files

From this repo's [`dolphin-config/`](../dolphin-config/) folder, copy the files
into Dolphin's user folder like this:

| Copy this file | Into this folder |
|---|---|
| `dolphin-config/Dolphin.ini` | `<user folder>\Config\` |
| `dolphin-config/GFX.ini` | `<user folder>\Config\` |
| `dolphin-config/GameSettings/GMSE01.ini` | `<user folder>\GameSettings\` |

Say **yes** if Windows asks to replace existing files. (If you'd already set
things up in Dolphin and want to keep it, back those three up first.)

That's it — this turns on the cheat codes, the correct speed, and the right
audio and graphics settings all at once.

---

## Step 4 — Add your game and controller

1. Open our Dolphin.
2. Click the folder icon / **Config → Paths** and add the folder where your
   Super Mario Sunshine file lives. It should appear in the game list.
3. Set up your controller: **Controllers → Port 1 → Configure**. Map your gamepad
   or keyboard however you like.

---

## Step 5 — Play

**Double-click the game.** It boots at **120 FPS** at correct speed.

You should see the FPS counter in the top-left. If it reads around **120** and
the game feels normal-speed (not fast, not slow), you're done. 🎉

---

## Changing to 180 or 240 FPS

Everything is already prepared — you just flip which one is on. Two small edits,
**with Dolphin closed**:

Open `<user folder>\GameSettings\GMSE01.ini` in Notepad.

1. Near the **top**, find this line and change the number:
   ```
   EmulationSpeed = 2.0
   ```
   - `2.0` = 120 FPS
   - `3.0` = 180 FPS
   - `4.0` = 240 FPS

2. Near the **bottom**, under `[Gecko_Enabled]`, there's a short list. Put a `#`
   in front of the line that's currently on, and remove the `#` from the one you
   want. For example, for 180 FPS:
   ```
   #$SMS 120fps bundle (fpspatch)
   $SMS 180fps bundle (fpspatch)
   #$SMS 240fps bundle (fpspatch)
   ```

Save the file, reopen Dolphin, play. **The speed number and the enabled bundle
must match** (3.0 ↔ 180, etc.) or the game runs at the wrong speed.

> ⚠️ **Always edit this file while Dolphin is fully closed.** Dolphin rewrites it
> when it quits and will undo your changes if it's open.

---

## Optional: 16:9 widescreen

Want the game to fill a widescreen monitor instead of having black bars? In the
same `GMSE01.ini`, under `[Gecko_Enabled]`, remove the `#` from:
```
$Widescreen
```
Leave your FPS bundle enabled too. Save, reopen, play.

---

Stuck? See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.
