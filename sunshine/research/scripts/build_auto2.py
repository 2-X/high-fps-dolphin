import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
words=[
 0x816D9F4C, # 0  lwz r11,-0x60b4(r13)
 0xC00B0000, # 1  lfs f0,0(r11)
 0xC0230010, # 2  lfs f1,0x10(r3)
 0xEC000828, # 3  fsubs f0,f0,f1
 0xEDA00032, # 4  fmuls f13,f0,f0
 0xC00B0008, # 5  lfs f0,8(r11)
 0xC0230018, # 6  lfs f1,0x18(r3)
 0xEC000828, # 7  fsubs f0,f0,f1
 0xEDA0683A, # 8  fmadds f13,f0,f0,f13
 0xC0228028, # 9  lfs f1,-0x7fd8(r2)  ; 0.5
 0xEDAD0072, # 10 fmuls f13,f13,f1
 0xEDAD0072, # 11 fmuls f13,f13,f1    ; dist2*0.25 -> radius 400
 0xC022DD90, # 12 lfs f1,-0x2270(r2)  ; 40000
 0xFC0D0800, # 13 fcmpu cr0,f13,f1
 0x41800010, # 14 blt +0x10 -> write (idx 18)
 0x888300C4, # 15 lbz r4,0xc4(r3)
 0x28040002, # 16 cmplwi r4,2
 0x41800014, # 17 blt +0x14 -> skip (idx 22)
 0x3D808041, # 18 lis r12,0x8041
 0x618C67B8, # 19 ori r12,r12,0x67B8
 0x3D603F00, # 20 lis r11,0x3F00
 0x916C0000, # 21 stw r11,0(r12)
 0x88030070, # 22 skip: lbz r0,0x70(r3) (re-exec orig)
 0x00000000, # 23 pad (branch-back slot)
]
assert len(words)%2==0
for i,w in enumerate(words):
    ins=next(md.disasm(struct.pack(">I",w),0x80001800+i*4),None)
    t=ins.mnemonic+' '+ins.op_str if ins else ('fcmpu cr0,f13,f1' if w==0xFC0D0800 else '(pad)' if w==0 else '???')
    print(f"+{i*4:02x} {w:08X}  {t}")
BASE=["044167B8 40000000","042FCB24 60000000","C20066EC 00000002","C2C28028 EC2105B2","FEC00890 00000000"]
FX=["C22887A8 00000002","C0028028 EC21002A","FC00081E 00000000",
    "C2288D30 00000002","C0028028 EC21002A","FC00081E 00000000",
    "C2288DEC 00000002","C0028028 EC21002A","FC00081E 00000000"]
L=BASE+FX+[f"C21EB034 {len(words)//2:08X}"]
for j in range(0,len(words),2): L.append(f"{words[j]:08X} {words[j+1]:08X}")
open("/tmp/auto2.txt","w").write("\n".join(L)+"\n")
print(f"\ntotal lines: {len(L)}")
