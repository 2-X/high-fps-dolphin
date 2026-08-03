#!/usr/bin/env python3
import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

DOL = "/Users/kbrethower/code/high-fps-dolphin/work/excitetruck/DATA/sys/main.dol"
data = open(DOL, "rb").read()

def load():
    text_off = struct.unpack(">7I", data[0x00:0x1C]); data_off = struct.unpack(">11I", data[0x1C:0x48])
    text_addr= struct.unpack(">7I", data[0x48:0x64]); data_addr= struct.unpack(">11I", data[0x64:0x90])
    text_sz  = struct.unpack(">7I", data[0x90:0xAC]); data_sz  = struct.unpack(">11I", data[0xAC:0xD8])
    segs=[]
    for o,a,s in zip(text_off,text_addr,text_sz):
        if s: segs.append((a,a+s,o,"text"))
    for o,a,s in zip(data_off,data_addr,data_sz):
        if s: segs.append((a,a+s,o,"data"))
    return segs
segs=load()
print("Segments:")
for a0,a1,o,k in segs: print(f"  {k}: 0x{a0:08X}-0x{a1:08X} (off 0x{o:X})")

def a2o(addr):
    for a0,a1,o,k in segs:
        if a0<=addr<a1: return o+(addr-a0),k
    return None,None

# 1) Are the PAL addresses even inside the USA image? (expect roughly, layout shifted)
print("\nPAL addrs mapped into USA image (content differs, just checking range):")
for a in (0x80177E90, 0x80577DF8, 0x8057F6A8):
    o,k=a2o(a); print(f"  0x{a:08X}: {'in '+k+' seg' if o else 'NOT in any seg'}")

# 2) Count 3.0f (0x40400000) constants in data segments -> how big is the haystack?
needle=struct.pack(">I",0x40400000)
count=0; hits=[]
for a0,a1,o,k in segs:
    if k!="data": continue
    seg=data[o:o+(a1-a0)]
    i=0
    while True:
        j=seg.find(needle,i)
        if j<0: break
        if j%4==0: count+=1; hits.append(a0+j)
        i=j+1
print(f"\n3.0f (0x40400000) word-aligned occurrences in DATA: {count}")
print("  first few addrs:", [f"0x{h:08X}" for h in hits[:8]])

# 3) The PAL patch injects instruction D00D9A9C = stfs f0, -0x6564(r13). Search USA text for stfs f0,x(r13) (D00Dxxxx)
md=Cs(CS_ARCH_PPC, CS_MODE_32|CS_MODE_BIG_ENDIAN)
stfs_r13=[]
for a0,a1,o,k in segs:
    if k!="text": continue
    seg=data[o:o+(a1-a0)]
    for i in range(0,len(seg)-3,4):
        w=struct.unpack(">I",seg[i:i+4])[0]
        if (w>>16)==0xD00D:  # stfs f0, disp(r13)
            stfs_r13.append((a0+i,w))
print(f"\n'stfs f0, x(r13)' (D00Dxxxx) occurrences in TEXT: {len(stfs_r13)}")
print("  samples:", [f"0x{a:08X}:{w:08X}" for a,w in stfs_r13[:8]])
