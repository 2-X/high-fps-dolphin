"""Locate TSunModel::getZBufValue (the 17x GXPeekZ sun lens-flare occlusion sampler)
and its caller TSunMgr::drawSyncCallback in the USA GMSE01 DOL.

Why it matters: getZBufValue does 17 synchronous EFB depth peeks per frame for the
sun lens-flare. On Dolphin/Metal each GXPeekZ is a full GPU pipeline stall
(waitUntilCompleted), which is ~36% of the CPU-GPU thread in Noki Bay (where the
flare is large and constantly on-screen over water). This is the root cause of
Noki Bay's 105fps-only drop at 120fps.

Signature (from decomp src/Camera/sunmodel.cpp::getZBufValue):
  for (int i = 0; i < 17; ++i, ++it, ++it2) {
      *it2 = 0;
      if (!indoor && it->x != -1 && it->y != -1) {
          u32 depth;
          GXPeekZ(it->x, it->y, &depth);   // <- bl
          if (depth == 0xffffff) *it2 = 1;
      }
  }

We fingerprint on: a function body containing BOTH a `cmpwi r?,17` (loop bound)
AND a `cmplwi r?,0xffffff` (depth test) within ~40 instructions, plus at least
one `bl` (the GXPeekZ call). That combination is essentially unique.
"""
import os, struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32

DOL = os.environ["SMS_DOL"]
data = open(DOL, "rb").read()

# DOL header: 7 text sections (offset@0x00, addr@0x48, size@0x90)
th_off = struct.unpack(">7I", data[0x00:0x1C])
th_a   = struct.unpack(">7I", data[0x48:0x64])
th_s   = struct.unpack(">7I", data[0x90:0xAC])
TEXT = [(a, a + s, o) for o, a, s in zip(th_off, th_a, th_s) if s]

md = Cs(CS_ARCH_PPC, CS_MODE_32)
md.detail = False

def fn_starts():
    """Yield plausible function entry points (mflr r0; stw r0,... or stwu r1,...)."""
    for a0, a1, off in TEXT:
        words = [struct.unpack(">I", data[off+i:off+i+4])[0] for i in range(0, a1-a0, 4)]
        for i, w in enumerate(words):
            # stwu r1,-IMM(r1)  OR  mflr r0 immediately followed by stw r0
            is_stwu = (w >> 26) == 37 and ((w >> 21) & 0x1F) == 1 and (w & 0x8000)
            is_mflr_stw = False
            if i+1 < len(words):
                nxt = words[i+1]
                # mflr r0 = 0x7C0802A6 ; stw r0, x(r1) = (37<<26)|(0<<21)|(1<<16)|imm
                is_mflr_stw = (w == 0x7C0802A6) and ((nxt >> 26) == 37) and (((nxt >> 16) & 0x1F) == 0) and ((nxt >> 21) & 0x1F) == 1
            if is_stwu or is_mflr_stw:
                yield a0 + i*4, off + i*4, a1

candidates = []
for fn_addr, fn_off, seg_end in fn_starts():
    # Slurp up to 60 instructions as the function body (getZBufValue is ~40 insns)
    end = min(fn_off + 60*4, seg_end)
    body = data[fn_off:end]
    has_17 = has_ffffff = bl_count = False
    for ins in md.disasm(body, fn_addr):
        if ins.mnemonic == "cmpwi" and "17" in ins.op_str and ", 17" in ins.op_str.replace(" ", ""):
            has_17 = True
        if ins.mnemonic == "cmplwi" and "0xffffff" in ins.op_str:
            has_ffffff = True
        if ins.mnemonic == "bl":
            bl_count += 1
        if ins.mnemonic == "blr":  # end of function
            break
    if has_17 and has_ffffff and bl_count >= 1:
        candidates.append((fn_addr, bl_count))

print("=== getZBufValue candidates (cmpwi 17 AND cmplwi 0xffffff AND >=1 bl) ===")
for addr, bls in candidates:
    print(f"  0x{addr:08x}  (bl count in body: {bls})")

if not candidates:
    print("  (none — loosen signature)")
