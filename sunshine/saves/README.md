# sunshine/saves/: Bring Your Own Saves

This directory previously contained Dolphin savestates, a memory card image (.gci),
and an SRAM file for Super Mario Sunshine (GMSE01). Those files have been removed
from the repository because they contain Nintendo-copyrighted game data and cannot be
legally redistributed.

## What belonged here

| File / Directory | Description |
|-----------------|-------------|
| `savestates/GMSE01.s01` – `.s03`, `.s05`, `.s06` | Dolphin savestates (full RAM snapshots) |
| `01-GMSE-super_mario_sunshine.gci` | GameCube memory card image |
| `SRAM.raw` | GameCube SRAM (system settings / slot data) |

## Supplying your own saves

Dolphin stores saves in its user data directory by default. You can also configure
Dolphin to use a custom path:

- **Savestates:** `Emulation > Save State` in-game, or copy your `.s0*` files into
  this directory and configure Dolphin's savestate path accordingly.
- **Memory card (.gci):** Use `Options > Configuration > GameCube > Slot A/B` and
  point it at a `.gci` or raw memory card file you own.
- **SRAM:** Generated automatically by Dolphin on first run; no action needed.

The `.gitignore` at the repo root excludes all of these file types from being
re-added to version control.
