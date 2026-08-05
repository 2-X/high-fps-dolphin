import struct,re
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
import os; DOL=os.environ["SMS_DOL"]
data=open(DOL,"rb").read()
th_off=struct.unpack(">7I",data[0x00:0x1C]);th_a=struct.unpack(">7I",data[0x48:0x64]);th_s=struct.unpack(">7I",data[0x90:0xAC])
d_off=struct.unpack(">11I",data[0x1C:0x48]);d_a=struct.unpack(">11I",data[0x64:0x90]);d_s=struct.unpack(">11I",data[0xAC:0xD8])
ALL=[(a,a+s,o) for o,a,s in zip(th_off,th_a,th_s) if s]+[(a,a+s,o) for o,a,s in zip(d_off,d_a,d_s) if s]
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
R2=0x80416ba0;R13=0x804141c0
def u32(va):
    for a0,a1,o in ALL:
        if a0<=va<a1: return struct.unpack(">I",data[o+va-a0:o+va-a0+4])[0]
    return None
def f32(va):
    v=u32(va); return struct.unpack(">f",struct.pack(">I",v))[0] if v is not None else None
def dec(w,a):
    ins=next(md.disasm(struct.pack(">I",w),a),None)
    if not ins: 
        # decode fcmpo/fcmpu manually
        if (w&0xFC0007FF)==0xFC000040: return f"fcmpo cr{(w>>23)&7},f{(w>>16)&31},f{(w>>11)&31}"
        if (w&0xFC0007FF)==0xFC000000: return f"fcmpu cr{(w>>23)&7},f{(w>>16)&31},f{(w>>11)&31}"
        return f".word {w:08x}"
    t=f"{ins.mnemonic} {ins.op_str}"
    for reg,base in (("r2",R2),("r13",R13)):
        m=re.search(r'(-?0x[0-9a-f]+)\('+reg+r'\)',t)
        if m:
            tg=(base+int(m.group(1),16))&0xFFFFFFFF; fv=f32(tg)
            if fv is not None and abs(fv)<1e9: t+=f"  ;[{tg:#x}]={fv:g}"
    if (w>>26)==18 and (w&1) and not(w&2):
        off=w&0x03FFFFFC
        if off&0x02000000: off-=0x04000000
        t=f"bl {((a+off)&0xFFFFFFFF):#x}"
    return t
import sys
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
a=lo
while a<hi:
    w=u32(a); print(f"{a:08x}: {w:08x}  {dec(w,a)}"); a+=4
