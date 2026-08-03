import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
# C2 @ 0x801EB034 (orig: lbz r0,0x70(r3)); free regs: r0,r4,r5,r11,r12,f0,f1,f13
words=[
 0x816D9F4C, # lwz r11,-0x60b4(r13)      ; pos vec (mario/cam)
 0xC00B0000, # lfs f0,0(r11)             ; pos.x
 0xC0230010, # lfs f1,0x10(r3)           ; gate.x
 0xEC000828, # fsubs f0,f0,f1
 0xEDA00032, # fmuls f13,f0,f0
 0xC00B0008, # lfs f0,8(r11)             ; pos.z
 0xC0230018, # lfs f1,0x18(r3)           ; gate.z
 0xEC000828, # fsubs f0,f0,f1
 0xEDA0683A, # fmadds f13,f0,f0,f13      ; dist2 (xz)
 0xC022DD90, # lfs f1,-0x2270(r2)        ; 40000 (=200^2, stock glow radius)
 0xFC0D0800, # fcmpu cr0,f13,f1
 0x40800014, # bge +0x14 -> skip (leave 2.0)
 0x3D808041, # lis r12,0x8041
 0x618C67B8, # ori r12,r12,0x67B8
 0x3D603F00, # lis r11,0x3F00
 0x916C0000, # stw r11,0(r12)            ; framerate=0.5 while near
 0x88030070, # skip: lbz r0,0x70(r3)     ; re-exec original
 0x60000000, # nop
 0x60000000, # nop
 0x00000000, # pad (branch-back slot)
]
print(f"{len(words)} words = {len(words)//2} lines")
for i,w in enumerate(words):
    ins=next(md.disasm(struct.pack('>I',w),0x80001800+i*4),None)
    print(f"+{i*4:02x} {w:08X}  {ins.mnemonic+' '+ins.op_str if ins else '(pad)'}")
lines=["044167B8 40000000","042FCB24 60000000","C20066EC 00000002","C2C28028 EC2105B2","FEC00890 00000000",
       f"C21EB034 {len(words)//2:08X}"]
for j in range(0,len(words),2): lines.append(f"{words[j]:08X} {words[j+1]:08X}")
open("/tmp/prox.txt","w").write("\n".join(lines)+"\n")
print("\n".join(lines))
