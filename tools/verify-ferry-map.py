"""Check departure against Erudin base collision triangles, not client hulls.

Usage: python3 tools/verify-ferry-map.py erudnext.map
Input: EQEmu/Maps base/erudnext.map, SHA256 pinned below. Only base collision
faces are inspected; placed objects and the moving RoF2 hull need device QA.
"""
import hashlib
import math
from pathlib import Path
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import ferry_route

DIGEST='eb27dd8a37679f424d0e1ac2076fc4068914993147c37bd8c4f892a0856f0188'


def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def point_segment(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def segments(a,b,c,d):
    if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0
    return min(point_segment(a,c,d),point_segment(b,c,d),point_segment(c,a,b),point_segment(d,a,b))


def inside(p,poly):
    signs=[cross(a,b,p) for a,b in zip(poly,poly[1:]+poly[:1])]
    return all(x>=0 for x in signs) or all(x<=0 for x in signs)


def distance(path,polys):
    best=float('inf')
    for poly in polys:
        if any(inside(p,poly) for p in path):return 0
        for a,b in zip(path,path[1:]):
            for c,d in zip(poly,poly[1:]+poly[:1]):best=min(best,segments(a,b,c,d))
    return best


def verify(path):
    raw=Path(path).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==DIGEST,'Unreviewed collision map'
    version,compressed,expanded=struct.unpack_from('<III',raw)
    assert version==0x02000000 and len(raw)==12+compressed
    data=zlib.decompress(raw[12:]);assert len(data)==expanded
    nv,ni=struct.unpack_from('<II',data)
    verts=list(struct.iter_unpack('<fff',data[40:40+nv*12]))
    ids=list(struct.iter_unpack('<III',data[40+nv*12:40+nv*12+ni*4]))
    polys=[]
    for indices in ids:
        tri=[verts[i] for i in indices]
        if max(p[0] for p in tri)<-1600 or min(p[0] for p in tri)>-200 or max(p[1] for p in tri)<-700 or min(p[1] for p in tri)>650:continue
        # Clip each triangle to the near-deck-height portion of terrain.
        poly=[]
        for a,b in zip(tri,tri[1:]+tri[:1]):
            if a[2]>=10:poly.append(a[:2])
            if (a[2]>=10)!=(b[2]>=10):
                t=(10-a[2])/(b[2]-a[2]);poly.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
        if len(poly)>=3 and abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))>1e-6:polys.append(poly)
    old=[(-443,95.96875),(-443,-220),(-675.106,-248),(-1055.88,-248),(-1219.9,-247.846),(-1354.36,178.488)]
    new=[(p['x'],p['y']) for p in ferry_route.phases()[2]['points'][6:]]
    assert distance(old,polys)==0,'Old failing route should intersect shoreline'
    assert distance([(-424.711,-214.898)]*2,polys)==0,'Observed detachment should touch rock'
    clearance=distance(new,polys)
    assert clearance>=75,clearance
    assert distance(new[1:],polys)>150,'Departure must increase shoreline clearance'
    print(f'PASS: old route and observed detachment intersect terrain; new centerline clearance {clearance:.3f} units including berth, >150 after first departure waypoint. Base terrain only; no client hull/placed-object acceptance claimed.')


if __name__=='__main__':verify(sys.argv[1])
