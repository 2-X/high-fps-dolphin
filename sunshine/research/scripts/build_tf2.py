import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
data=open('/Users/kbrethower/code/high-fps-dolphin/work/main.dol','rb').read()
th_off=struct.unpack('>7I',data[0x00:0x1C]);th_a=struct.unpack('>7I',data[0x48:0x64]);th_s=struct.unpack('>7I',data[0x90:0xAC])
def u32(va):
    for o,a,s in zip(th_off,th_a,th_s):
        if s and a<=va<a+s: return struct.unpack('>I',data[o+va-a:o+va-a+4])[0]
assert u32(0x801EBA60)==0xC05F00D0, "hook orig mismatch"
# C2 @ 0x801EBA60. LIVE regs: r0(0x4330 magic), f1(176.0 dbl). Free: r3,r4,r11,r12,f0,f2,f13
words=[
 0x816D9F4C, # 0  lwz r11,-0x60b4(r13)   ; player/cam pos vec
 0xC04B0000, # 1  lfs f2,0(r11)
 0xC01F0010, # 2  lfs f0,0x10(r31)       ; gate.x
 0xEC420028, # 3  fsubs f2,f2,f0
 0xEDA200B2, # 4  fmuls f13,f2,f2
 0xC04B0008, # 5  lfs f2,8(r11)
 0xC01F0018, # 6  lfs f0,0x18(r31)       ; gate.z
 0xEC420028, # 7  fsubs f2,f2,f0
 0xEDA268BA, # 8  fmadds f13,f2,f2,f13   ; xz dist^2
 0xC002DD90, # 9  lfs f0,-0x2270(r2)     ; 40000 = 200^2 stock radius
 0xFC0D0000, # 10 fcmpu cr0,f13,f0
 0x40800018, # 11 bge +0x18 -> far (idx17)
 0xC042DD68, # 12 lfs f2,-0x2298(r2)     ; 1.0
 0xD05F00D0, # 13 stfs f2,0xd0(r31)      ; glow = 1.0
 0xA97F00C8, # 14 lha r11,0xc8(r31)
 0xB17F00CA, # 15 sth r11,0xca(r31)      ; pin lit-timer
 0x48000008, # 16 b +8 -> done (idx18)
 0xC05F00D0, # 17 far: lfs f2,0xd0(r31)  ; original (natural decay)
 0x60000000, # 18 done: nop
 0x00000000, # 19 pad
]
assert len(words)%2==0
for i,w in enumerate(words):
    ins=next(md.disasm(struct.pack(">I",w),0x80001800+i*4),None)
    t=ins.mnemonic+' '+ins.op_str if ins else ('fcmpu cr0,f13,f0' if w==0xFC0D0000 else '(pad)' if w==0 else 'CHECK:'+hex(w))
    print(f"+{i*4:02x} {w:08X}  {t}")
BASE=["044167B8 40000000","042FCB24 60000000","C20066EC 00000002","C2C28028 EC2105B2","FEC00890 00000000"]
FX=["C22887A8 00000002","C0028028 EC21002A","FC00081E 00000000",
    "C2288D30 00000002","C0028028 EC21002A","FC00081E 00000000",
    "C2288DEC 00000002","C0028028 EC21002A","FC00081E 00000000"]
FO=["C21EB034 00000007","88030070 700B0001","40820020 7D6802A6","3D80801E 618CBFD4",
    "7D8903A6 4E800421","7D6803A6 7FE3FB78","88030070 60000000","60000000 00000000"]
L=BASE+FX+FO+[f"C21EBA60 {len(words)//2:08X}"]
for j in range(0,len(words),2): L.append(f"{words[j]:08X} {words[j+1]:08X}")
open("/tmp/tf2.txt","w").write("\n".join(L)+"\n")
print(f"\ntotal {len(L)} lines")
