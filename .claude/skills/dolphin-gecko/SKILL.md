---
name: dolphin-gecko
description: Add, replace, list, or remove Gecko codes in the Dolphin per-game INI for Super Mario Sunshine high-fps / M-portal testing. Use whenever asked to add/enable/test a Gecko code, or when codes "don't show up" in Dolphin. Handles Dolphin's on-close INI rewrite that silently clobbers external edits.
---

# Dolphin Gecko code management (GMSE01 / Super Mario Sunshine USA)

## The one gotcha that matters

Dolphin loads the **user** per-game INI at
`~/Library/Application Support/Dolphin/GameSettings/GMSE01.ini`
and **rewrites it from memory when it closes** (after any per-game setting was
touched — e.g. ticking a Gecko code). So **any edit made while Dolphin is
running is reverted on quit.** That is the "I added a code but it doesn't show
up" symptom.

**Golden rule: Dolphin must be fully quit before editing the INI, then relaunched.**

Do NOT edit the Sys/GameSettings INI in the app bundle to work around this — it
is the shipped default set, gets overwritten on rebuild, and merge semantics
cause duplicate/confusing entries. Always target the user INI above.

## Workflow

1. **Confirm Dolphin is quit.**
   `pgrep -if dolphin` → if it prints a PID, Dolphin is running. Ask the user to
   quit it, or quit it gracefully: `osascript -e 'quit app "Dolphin"'` then wait
   for the process to disappear (poll `pgrep`). Never edit until it is gone.
2. **Use the helper script** (it backs up to `<ini>.bak`, sanitizes lines, and is
   idempotent — re-adding a title replaces the old block):
   ```bash
   PY=python3
   S=.claude/skills/dolphin-gecko/scripts/gecko.py
   $PY $S list
   $PY $S add --title "120fps + My Fix" --code-file /tmp/mycode.txt
   $PY $S add --title "Quick" --code $'044167B8 40000000\n042FCB24 60000000'
   $PY $S remove --title "Diag-S"
   $PY $S enable --title "120fps + My Fix"   # tick its checkbox for next launch
   ```
   The script **refuses** to write while Dolphin is running (override: `--force`).
3. **Verify** the code is present and well-formed: `$PY $S list`.
4. **Tell the user to relaunch Dolphin** and open Properties → Gecko Codes; the
   new code will be at the bottom of the list.

## Code format (Dolphin INI)

Under the `[Gecko]` section, each code is a `$Title` line followed by one or more
`XXXXXXXX YYYYYYYY` lines (two 8-hex-digit words, space-separated). Enabled codes
are listed by `$Title` under `[Gecko_Enabled]`. Example:

```
[Gecko]
$120fps + M-fix A (gate anim x0.5)
044167B8 40000000
042FCB24 60000000
C20066EC 00000002
C2C28028 EC2105B2
FEC00890 00000000
C21EBA74 00000002
EFE20032 C0028028
EFFF0032 60000000
```

Each self-contained SMS high-fps code = the **noB 120fps base**
```
044167B8 40000000
042FCB24 60000000
C20066EC 00000002
C2C28028 EC2105B2
FEC00890 00000000
```
plus whatever patch/hook is appended. Only ONE 120fps variant should be enabled
at a time — they all write `0x804167B8` and will fight otherwise.

## Building C2 (insert-assembly) hooks

- First word `C2AAAAAA` where `AAAAAA = address & 0x01FFFFFF` (for `0x80xxxxxx`,
  that's the low 6 hex digits). Second word = number of 8-byte lines that follow.
- Those lines are the PPC instructions to run; the code handler branches back to
  `address + 4` afterward, so **re-execute the original instruction** at the top
  of your block (the C2 replaces it with a branch).
- **CRITICAL GOTCHA — the block MUST end with a `00000000` padding word.** The
  code handler **overwrites the LAST word of the block with its branch-back**. If
  your last word is a real instruction it gets clobbered → `f`-reg/`r`-reg left
  garbage → typically an "Invalid write to 0x00000000" crash or silent no-op.
  Always pad so the final word is `00000000` (add a `60000000 00000000` line if
  needed to make the instruction count land right). This single mistake silently
  breaks every multi-instruction C2 — verify the last word is `00000000`.
- Relative branches inside the block (`b`, `bge`, …) are self-relative and stay
  correct because the handler copies the block verbatim to its cave.
- Dolphin's C2 cave is SMALL. Stacking many/large C2 codes overflows it and they
  silently don't run (looks like "the code does nothing"). Prefer ONE compact C2
  over many. To test many call sites, use a single C2 at a shared choke point
  that branches on a discriminator (e.g. the caller return address at `0x14(r1)`
  inside a leaf function) rather than one C2 per site.
- Handy constant: `0.5` lives at `0x8040EBC8` = `lfs f0,-0x7fd8(r2)` = `C0028028`
  (r2 = 0x80416BA0). Two `fmuls f,f,f0` = ×0.25.
- Reader-friendly disassembly + robust function boundaries: `/tmp/sms_starts.py`
  and friends; assemble/verify words with capstone in `/tmp/smsvenv`.

## Project context

The live investigation (finding `TModelGate::perform = 0x801EB014`, the reader3
timing dependency, and which Gecko fixes work) is tracked in
`~/.claude/.../memory/sunshine-portal-glow-bug.md`. Read it before designing a
new M-portal fix code.
