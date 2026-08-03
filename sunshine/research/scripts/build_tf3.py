import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
data=open('/Users/kbrethower/code/high-fps-dolphin/work/main.dol','rb').read()
d_off=struct.unpack('>11I',data[0x1C:0x48]);d_a=struct.unpack('>11I',data[0x64:0x90]);d_s=struct.unpack('>11I',data[0xAC:0xD8])
def rdf(va):
    for o,a,s in zip(d_off,d_a,d_s):
        if s and a<=va<a+s: return struct.unpack('>f',data[o+va-a:o+va-a+4])[0]
assert rdf(0x8041496C)==500.0, rdf(0x8041496C)
print("pool [0x8041496C] =",rdf(0x8041496C),"-> threshold 500*500*0.5 = 125000 -> radius", (125000**0.5))
words=[
 0x816D9F4C, # lwz r11,-0x60b4(r13)
 0xC04B0000, # lfs f2,0(r11)
 0xC01F0010, # lfs f0,0x10(r31)
 0xEC420028, # fsubs f2,f2,f0
 0xEDA200B2, # fmuls f13,f2,f2
 0xC04B0008, # lfs f2,8(r11)
 0xC01F0018, # lfs f0,0x18(r31)
 0xEC420028, # fsubs f2,f2,f0
 0xEDA268BA, # fmadds f13,f2,f2,f13
 0xC002DDCC, # lfs f0,-0x2234(r2)   ; 500.0
 0xEC000032, # fmuls f0,f0,f0       ; 250000
 0xC0428028, # lfs f2,-0x7fd8(r2)   ; 0.5
 0xEC0000B2, # fmuls f0,f0,f2       ; 125000 (~353.6u)
 0xFC0D0000, # fcmpu cr0,f13,f0
 0x40800018, # bge +0x18 -> far
 0xC042DD68, # lfs f2,-0x2298(r2)   ; 1.0
 0xD05F00D0, # stfs f2,0xd0(r31)
 0xA97F00C8, # lha r11,0xc8(r31)
 0xB17F00CA, # sth r11,0xca(r31)
 0x48000008, # b +8 -> done
 0xC05F00D0, # far: lfs f2,0xd0(r31)
 0x60000000, # done: nop
 0x60000000, # nop
 0x00000000, # pad
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
open("/tmp/tf3.txt","w").write("\n".join(L)+"\n")
print(f"\ntotal {len(L)} lines")
