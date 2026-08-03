import struct,bisect
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
DOL="/Users/kbrethower/code/high-fps-dolphin/work/main.dol"
data=open(DOL,"rb").read()
th_off=struct.unpack(">7I",data[0x00:0x1C]);th_a=struct.unpack(">7I",data[0x48:0x64]);th_s=struct.unpack(">7I",data[0x90:0xAC])
TXT=[(a,a+s,o) for o,a,s in zip(th_off,th_a,th_s) if s]
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
def u32(va):
    for a0,a1,o in TXT:
        if a0<=va<a1: return struct.unpack(">I",data[o+va-a0:o+va-a0+4])[0]
    return None
READER2=0x802A7BD8
# find bl reader2 followed within 4 instrs by fctiwz (0xFC00081E | D<<21, i.e. opcode 63 XO 0x0F<<1 with rc0 on f1 source)
sites=[]
for a0,a1,o in TXT:
    n=(a1-a0)//4; ws=struct.unpack(">%dI"%n,data[o:o+n*4])
    for i,w in enumerate(ws):
        if (w>>26)==18 and (w&1)==1 and not(w&2):
            off=w&0x03FFFFFC
            if off&0x02000000: off-=0x04000000
            if ((a0+i*4+off)&0xFFFFFFFF)==READER2:
                for k in range(1,5):
                    if i+k>=n: break
                    w2=ws[i+k]
                    # fctiwz fD,f1 : 111111 DDDDD 00000 00001 0000011110 0 -> 0xFC00081E | D<<21
                    if (w2 & 0xFC1FFFFF) == 0xFC00081E|0x0800:
                        sites.append((a0+i*4, a0+(i+k)*4, w2)); break
print(f"{len(sites)} 'bl AnmFrameRate -> fctiwz' truncation sites:")
for bl,fc,w2 in sites:
    ins=next(md.disasm(struct.pack(">I",w2),fc),None)
    print(f"  bl@{bl:08X}  fctiwz@{fc:08X}  {w2:08X} {ins.mnemonic if ins else '?'} {ins.op_str if ins else ''}")
    # context
    for a in range(bl-4, fc+20, 4):
        w=u32(a); ii=next(md.disasm(struct.pack(">I",w),a),None)
        print(f"      {a:08x}: {w:08x}  {ii.mnemonic+' '+ii.op_str if ii else '.word'}")
