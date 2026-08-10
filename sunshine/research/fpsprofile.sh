#!/usr/bin/env bash
# fpsprofile.sh — find WHAT is eating the frame in a running Dolphin (macOS).
#
# This is the "browser profiler for Dolphin" workflow that found the Noki Bay
# Ep.1 pollution-readback stall (105->119). Use it whenever ONE area/level runs
# slower than the rest and you don't know why. Measure BEFORE hypothesizing.
#
#   ./fpsprofile.sh            # sample 5s, summarize hot functions + stalls
#   ./fpsprofile.sh 8          # sample 8s
#   ./fpsprofile.sh 5 /tmp/x   # keep the raw sample at /tmp/x.sample
#
# HOW TO USE: boot SMS, get INTO the slow spot, let it settle ~10s, hold a
# representative view, THEN run this. Compare against a fast area (run it twice).
#
# WHAT TO LOOK FOR in the output:
#   * "CPU-GPU thread" is the emulation thread — its hot leaves are the budget.
#   * Any of these = a synchronous GPU->CPU readback STALL (the usual high-fps
#     killer on Metal; each one blocks in -[MTLCommandBuffer waitUntilCompleted]):
#       AbstractStagingTexture::ReadTexels   (EFB->RAM copy readback)
#       Metal::StagingTexture::Flush         (the blocking wait itself)
#       PerfQuery::FlushResults              (GXReadPixMetric / pixel-metric readback)
#       FramebufferManager::PeekEFBColor     (GXPeekARGB EFB peek)
#   * If those dominate -> the game is reading the framebuffer back every frame.
#     At 120fps (4x native 30) that fires 4x too often. FIX = gate the game code
#     that triggers it back to native 30Hz (see PERF-PLAYBOOK.md).
#   * If instead VertexManager/DrawIndexed/BPFunctions dominate with NO readback,
#     it's genuine draw/geometry cost — a different problem (see playbook).
set -euo pipefail
DUR="${1:-5}"
OUT="${2:-/tmp/dolphin_fpsprofile}"
PID=$(pgrep -f 'Dolphin.app/Contents/MacOS/Dolphin' | head -1 || true)
[ -z "${PID:-}" ] && { echo "Dolphin not running."; exit 1; }
echo "Dolphin PID $PID — sampling ${DUR}s (hold a steady view)..."
sample "$PID" "$DUR" -file "${OUT}.sample" >/dev/null 2>&1
S="${OUT}.sample"

echo
echo "===== hot leaves on the emulation thread (self-heavy, >=40 samples) ====="
# isolate the CPU-GPU thread subtree, strip tree glyphs, aggregate by symbol
awk '/^ *[0-9]+ Thread_.*CPU-GPU thread/{f=1;next} /^ *[0-9]+ Thread_/{f=0} f' "$S" \
 | grep -E 'in Dolphin|in Metal|in AGX|in IOGPU' \
 | grep -vE 'thread_start|_pthread|mach_msg|__psynch|wait\b' \
 | sed -E 's/^[[:space:]!:|+-]*//; s/\[0x[0-9a-f]+\].*//' \
 | awk '{c=$1; $1=""; if(c+0>=40) print c"\t"$0}' | sort -rn | head -30

echo
echo "===== READBACK-STALL total (the high-fps killer) ====="
awk '/^ *[0-9]+ Thread_.*CPU-GPU thread/{f=1;next} /^ *[0-9]+ Thread_/{f=0} f' "$S" \
 | grep -E 'ReadTexels|StagingTexture::Flush|PerfQuery::FlushResults|PeekEFB|waitUntilCompleted' \
 | sed -E 's/^[[:space:]!:|+-]*//' \
 | awk '{c=$1; for(i=2;i<=NF;i++){if($i~/\(in/){NF=i-1;break}} name=""; for(i=2;i<=NF;i++)name=name" "$i;
         if(name!=last){print c"\t"name; last=name}}' | sort -rn -u | head -15
echo
echo "raw sample kept at: $S   (open in a viewer or grep for callers)"
