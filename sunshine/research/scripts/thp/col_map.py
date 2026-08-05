"""Render a top-down height-colored map from an SMS collision file (map/map.col).

Usage: python col_map.py <map.col> <out.png> [width]

.col format (reversed 2026-08-04):
  0x00 u32 vertexCount
  0x04 u32 vertexOffset        -> f32 x,y,z * count
  0x08 u32 groupCount
  0x0C u32 groupOffset         -> groupCount * 24-byte entries:
       u16 surfaceType, u16 triCount, u16 ?, u16 0xFFFF,
       u32 indexOffset (3*u16 per tri), u32 terrainOff, u32 terrainOff2, u32 opt
Triangles with any edge > 6000u are skipped (water/death planes).
"""
import struct, sys, math
from PIL import Image, ImageDraw

src, dst = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 1400

d = open(src, "rb").read()
vc, vo, gc, go = struct.unpack(">IIII", d[:16])
verts = [struct.unpack(">3f", d[vo+i*12:vo+i*12+12]) for i in range(vc)]
tris = []
for g in range(gc):
    e = struct.unpack(">6I", d[go+g*24:go+(g+1)*24])
    for t in range(e[0] & 0xFFFF):
        a, b, c = struct.unpack(">3H", d[e[2]+t*6:e[2]+t*6+6])
        tris.append((verts[a], verts[b], verts[c]))
tris = [t for t in tris if max(math.dist(t[0], t[1]), math.dist(t[1], t[2]),
                               math.dist(t[0], t[2])) < 6000]

pts = [p for t in tris for p in t]
xs = [p[0] for p in pts]; ys = sorted(p[1] for p in pts); zs = [p[2] for p in pts]
x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
y0, y1 = ys[int(len(ys)*0.02)], ys[int(len(ys)*0.98)]
H = max(300, int(W*(z1-z0)/(x1-x0)))
im = Image.new("RGB", (W, H+1), (8, 8, 12)); dr = ImageDraw.Draw(im)
uv = lambda p: ((p[0]-x0)/(x1-x0)*(W-1), (p[2]-z0)/(z1-z0)*(H-1))
for a, b, c in sorted(tris, key=lambda t: (t[0][1]+t[1][1]+t[2][1])):
    t = max(0, min(1, ((a[1]+b[1]+c[1])/3 - y0)/(y1-y0+1)))
    dr.polygon([uv(a), uv(b), uv(c)],
               fill=(int(25+230*t), int(60+90*(1-t)+60*t), int(200-160*t)),
               outline=(0, 0, 0))
for gx in range(int(x0)//5000*5000, int(x1)+1, 5000):
    u, _ = uv((gx, 0, z0)); dr.line([(u, 0), (u, H)], fill=(90, 90, 90))
    dr.text((u+2, 2), str(gx), fill=(200, 200, 200))
for gz in range(int(z0)//5000*5000, int(z1)+1, 5000):
    _, v = uv((x0, 0, gz)); dr.line([(0, v), (W, v)], fill=(90, 90, 90))
    dr.text((2, v+2), str(gz), fill=(200, 200, 200))
im.save(dst)
print(dst, f"{len(tris)} tris, x [{int(x0)},{int(x1)}] z [{int(z0)},{int(z1)}]")
