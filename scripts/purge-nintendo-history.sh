#!/usr/bin/env bash
# purge-nintendo-history.sh
#
# Rewrites git history to permanently remove Nintendo-copyrighted and
# license-unverified files that were accidentally committed.
#
# PREREQUISITES:
#   brew install git-filter-repo
#
# IMMEDIATE STOPGAP (run this NOW while you plan the full purge):
#   gh repo edit 2-X/high-fps-dolphin --visibility private
#   This makes the repo private so the objects are no longer publicly reachable
#   while the history rewrite is being prepared.
#
# HOW TO RUN:
#   1. Read PURGE-PLAN.md fully.
#   2. Make sure no collaborators are actively working — they will need to re-clone.
#   3. Run this script from the repo root.
#   4. After verifying, uncomment and run the force-push block at the bottom.
#
# DO NOT RUN THIS ON A WORKING REPO WITHOUT THE BACKUP STEP.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
BACKUP_DIR="$(dirname "$REPO_ROOT")/high-fps-dolphin-backup.git"
REMOTE="origin"
BRANCH="main"   # adjust if your default branch differs

# ── Size before ────────────────────────────────────────────────────────────────
echo "=== Repository size BEFORE purge ==="
git -C "$REPO_ROOT" count-objects -vH
du -sh "$REPO_ROOT/.git"

# ── Hard-stop confirmation ──────────────────────────────────────────────────────
echo ""
echo "WARNING: This rewrites ALL git history and is destructive and irreversible."
echo "All collaborators/clones will need to re-clone after a force-push."
echo "GitHub may retain unreachable objects in its own cache; contact GitHub"
echo "Support to request expungement if needed."
echo ""
read -rp "Type YES (all-caps) to continue, or anything else to abort: " CONFIRM
if [[ "$CONFIRM" != "YES" ]]; then
    echo "Aborted."
    exit 1
fi

# ── Mirror backup ──────────────────────────────────────────────────────────────
echo ""
echo "=== Cloning mirror backup to $BACKUP_DIR ==="
if [[ -d "$BACKUP_DIR" ]]; then
    echo "Backup dir already exists: $BACKUP_DIR — remove it first if you want a fresh backup."
    exit 1
fi
git clone --mirror "$REPO_ROOT" "$BACKUP_DIR"
echo "Backup created at: $BACKUP_DIR"

# ── Run git-filter-repo ────────────────────────────────────────────────────────
echo ""
echo "=== Rewriting history with git-filter-repo ==="
cd "$REPO_ROOT"

git filter-repo --force \
    --invert-paths \
    --path "sunshine/saves/savestates/GMSE01.s01" \
    --path "sunshine/saves/savestates/GMSE01.s02" \
    --path "sunshine/saves/savestates/GMSE01.s03" \
    --path "sunshine/saves/savestates/GMSE01.s05" \
    --path "sunshine/saves/savestates/GMSE01.s06" \
    --path "sunshine/saves/01-GMSE-super_mario_sunshine.gci" \
    --path "sunshine/saves/SRAM.raw" \
    --path "sunshine/research/main.dol" \
    --path "sunshine/research/main-hd.dol" \
    --path "sunshine/research/thp-assets/EX128x144_ai3x.thp" \
    --path "sunshine/textures/GMSE01-pruned" \
    --path "sunshine/bsmso/bse-release" \
    --path "sunshine/bsmso/BetterSunshineEngine-highfps-v400.kxe" \
    --path "work/disc" \
    --path "work/main.dol"

echo ""
echo "=== Repository size AFTER purge ==="
git count-objects -vH
du -sh .git

# ── Verify ─────────────────────────────────────────────────────────────────────
echo ""
echo "=== Verifying offenders are gone from all history ==="
OFFENDERS=(
    "sunshine/saves/savestates/GMSE01.s01"
    "sunshine/saves/savestates/GMSE01.s02"
    "sunshine/saves/savestates/GMSE01.s03"
    "sunshine/saves/savestates/GMSE01.s05"
    "sunshine/saves/savestates/GMSE01.s06"
    "sunshine/saves/01-GMSE-super_mario_sunshine.gci"
    "sunshine/saves/SRAM.raw"
    "sunshine/research/main.dol"
    "sunshine/research/main-hd.dol"
    "sunshine/research/thp-assets/EX128x144_ai3x.thp"
    "sunshine/textures/GMSE01-pruned"
    "sunshine/bsmso/bse-release"
    "sunshine/bsmso/BetterSunshineEngine-highfps-v400.kxe"
    "work/disc"
    "work/main.dol"
)
ALL_CLEAN=true
for path in "${OFFENDERS[@]}"; do
    HITS=$(git log --all --oneline -- "$path" | wc -l | tr -d ' ')
    if [[ "$HITS" -gt 0 ]]; then
        echo "  STILL PRESENT ($HITS commits): $path"
        ALL_CLEAN=false
    else
        echo "  clean: $path"
    fi
done

if [[ "$ALL_CLEAN" != "true" ]]; then
    echo ""
    echo "ERROR: Some paths still appear in history. Do NOT force-push. Investigate."
    exit 1
fi

echo ""
echo "All offenders confirmed removed from history."

# ── Force-push (UNCOMMENT ONLY AFTER VERIFYING ABOVE) ─────────────────────────
#
# WARNING: Force-pushing rewrites the public remote. All open clones and forks
# will have diverged history. Collaborators MUST re-clone — they cannot simply
# pull. GitHub may retain the old objects in its internal cache for some time;
# contact GitHub Support (privacy@github.com or the DMCA/legal form) to request
# that the unreachable objects be garbage-collected immediately.
#
# Also re-add the remote (git-filter-repo removes it as a safety measure):
#   git remote add origin https://github.com/2-X/high-fps-dolphin.git
#
# Then force-push ALL refs:
#   git push origin --force --all
#   git push origin --force --tags
#
# After pushing:
#   - Re-invite collaborators and ask them to re-clone.
#   - Verify on GitHub that the files no longer appear in any commit.
#   - If making the repo public again: gh repo edit 2-X/high-fps-dolphin --visibility public

echo ""
echo "=== Done ==="
echo "Review the output above, then uncomment the force-push block and re-run,"
echo "or run the push commands manually."
