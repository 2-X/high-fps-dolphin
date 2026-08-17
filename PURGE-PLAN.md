# Nintendo-Copyright Purge Plan

> **Immediate action while you decide on a full strategy:**  
> `gh repo edit 2-X/high-fps-dolphin --visibility private`  
> This removes public access to the objects without touching history.

---

## 1. Offenders

| Path | Why problematic | Approx. size |
|------|-----------------|-------------|
| `sunshine/saves/savestates/GMSE01.s01` – `.s03`, `.s05`, `.s06` | Dolphin savestates = full RAM snapshots (contain Nintendo executable code and game data) | 183 MB total |
| `sunshine/saves/01-GMSE-super_mario_sunshine.gci` | Memory card image, Nintendo game save data | 60 KB |
| `sunshine/saves/SRAM.raw` | GC SRAM, Nintendo system data | 4 KB |
| `sunshine/research/main.dol` | Nintendo DOL executable extracted from disc | 3.9 MB |
| `sunshine/research/main-hd.dol` | Nintendo DOL executable (HD variant) | 3.9 MB |
| `sunshine/research/thp-assets/EX128x144_ai3x.thp` | Derivative of Nintendo THP video (upscaled from disc) | 11 MB |
| `sunshine/textures/GMSE01-pruned/` | 1,155 `.dds` files ripped directly from the game disc | 226 MB |
| `sunshine/bsmso/bse-release/BetterSunshineEngine_RELEASE/boot.bin` | Nintendo disc boot metadata | ~1 KB |
| `sunshine/bsmso/bse-release/BetterSunshineEngine_RELEASE/main.dol` | Nintendo DOL in BSE release bundle | ~3.9 MB |
| `sunshine/bsmso/bse-release/BetterSunshineEngine_RELEASE/Kuribo!/System/KuriboKernel.bin` | KuriboKernel, license unverified | ~300 KB |
| `sunshine/bsmso/bse-release/` (entire dir) | BSE upstream release, includes the two Nintendo files above; full dir untracked together | 6.3 MB |
| `sunshine/bsmso/BetterSunshineEngine-highfps-v400.kxe` | Our GPL-3.0 BSE fork build: distributing without publishing fork source violates GPL-3.0 §6 | 572 KB |
| `work/disc/sys/` (apploader.img, bi2.bin, boot.bin, fst.bin, main.dol) | Nintendo disc system files extracted from GMSE01 disc | 4.1 MB |
| `work/main.dol` | Nintendo DOL executable (duplicate of research/main.dol, same disc) | 3.9 MB |

**Total tracked data to remove from history: ~444 MB.**

---

## 2. Current state

`git rm -r --cached` has already been run on all paths above (index cleaned, working tree intact).
`.gitignore` has been updated to prevent re-tracking.
No commit has been made yet. The index changes are staged but uncommitted.

---

## 3. Remediation options

### Option A: git-filter-repo rewrite + force-push (recommended)
Permanently rewrites every commit in history to remove the blobs.
Keeps the repo URL, stars, and issue history.

**Script:** `scripts/purge-nintendo-history.sh` (do not run without reading it fully).

Steps:
1. `gh repo edit 2-X/high-fps-dolphin --visibility private` (immediate stopgap).
2. Run `scripts/purge-nintendo-history.sh` (it backs up, rewrites, verifies, and prints force-push instructions).
3. Force-push all refs.
4. Notify collaborators to re-clone.
5. Contact GitHub Support to request expungement of unreachable objects.
6. Re-publish when clean: `gh repo edit 2-X/high-fps-dolphin --visibility public`.

**Consequences:**
- All open clones and forks retain the old objects until they re-clone or GC.
- GitHub's own object store may cache unreachable objects; GitHub Support can flush this on request.
- All collaborator local clones will have diverged history; they must `git clone` fresh, not `git pull`.
- Force-push invalidates any open PRs against this repo.

### Option B: Make private + create a fresh public repo from a clean tree
Does not rewrite history. Leaves the old repo private (containing the offending history) and creates a new clean repo.

Steps:
1. `gh repo edit 2-X/high-fps-dolphin --visibility private` (immediately).
2. Create a new repo: `gh repo create 2-X/high-fps-dolphin-clean --public`.
3. From a clean checkout (with `.gitignore` already updated and offenders not present), push to the new remote.
4. Optionally archive or delete the private old repo after confirming the new one is complete.

**Consequences:**
- Old repo URL/stars/issues are lost (or stay on the now-private repo).
- Simpler: no force-push, no filter-repo, no collaborator re-clone required for the *new* repo.
- History on the old repo still exists (private); Nintendo can still request deletion if they discover it.
- The old objects are still on GitHub's servers until GitHub GC's them or the repo is deleted.

---

## 4. Post-purge checklist

- [ ] Verify each offender is gone from all history:
  ```bash
  git log --all --oneline -- sunshine/saves/savestates/
  git log --all --oneline -- sunshine/saves/01-GMSE-super_mario_sunshine.gci
  git log --all --oneline -- sunshine/saves/SRAM.raw
  git log --all --oneline -- sunshine/research/main.dol
  git log --all --oneline -- sunshine/research/main-hd.dol
  git log --all --oneline -- sunshine/research/thp-assets/EX128x144_ai3x.thp
  git log --all --oneline -- sunshine/textures/GMSE01-pruned/
  git log --all --oneline -- sunshine/bsmso/bse-release/
  git log --all --oneline -- sunshine/bsmso/BetterSunshineEngine-highfps-v400.kxe
  git log --all --oneline -- work/disc/
  git log --all --oneline -- work/main.dol
  ```
  All should return empty.
- [ ] Force-push all branches and tags (Option A only).
- [ ] Contact GitHub Support to request expungement of the unreachable objects.
- [ ] Re-invite / notify all collaborators to re-clone.
- [ ] Add a tombstone README in `sunshine/saves/` explaining that users must supply their own saves (already written at `sunshine/saves/README.md`).
- [ ] Re-add `sunshine/saves/` directory to the repo (it is now empty of tracked files; add the README).
- [ ] Before redistributing `BetterSunshineEngine-highfps-v400.kxe`: push the BSE fork source publicly (satisfies GPL-3.0 §6 corresponding-source requirement). Then re-add the kxe under a clear license header.
- [ ] Verify `git ls-files | grep -iE '\.(dds|dol|gci|raw|s0[0-9]|thp|kxe|bin)$'` shows only expected remaining tracked binaries (see section 5 below).
- [ ] Re-make the repo public after all of the above are confirmed.

---

## 5. Remaining tracked binaries after purge (justified)

After the purge, the following binary-extension files will remain tracked, each justified:

| Path | Extension | Justification |
|------|-----------|---------------|
| `sunshine/dolphin-patches/*.patch` | `.patch` | Our own diff output; contains no copyrighted blobs |
| `sunshine/bsmso/mac-online/memhelper/memhelper` | (no ext, ELF/Mach-O) | Our own build of our own C source (`memhelper.c`) in the same dir |

The `.bin` and `.kxe` files under `sunshine/bsmso/bse-release/` and the standalone `.kxe` are now untracked. The only remaining `.bin`-adjacent concern is if any other `.bin` files are present; run `git ls-files '*.bin'` to confirm.
