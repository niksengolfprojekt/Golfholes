# Kamerapunkter för ögonhöjdsvyerna (Glasriket hål 3, 5, 14, 17 + allmänna vyer). Flyttad från tmp-ai/.
# Kör från repots rot: python verktyg/ogonhojd_vyer.py (kräver data/glasriket/ med ortofoto och höjdmodell).
import sys
from pathlib import Path
from golfholes.hole import Hole
from golfholes.render.perspektiv import perspektiv
O=Path('data/glasriket/orto/o63050_4900_25_mr25.tif'); D=Path('data/glasriket/hojd/m630_49.tif')
fria=[]; linjer=[]
for h in ("03","05","14","17"):
    hole=Hole.from_yaml(f"klubbar/glasriket/hal-{h}.yaml")
    fria += hole.fairways + [hole.green] + [z.polygon for z in hole.hazards]
    linjer.append(hole.centerline)
vyer={
 "h14-tee":   ((492314.0,6305866.0),(492300.0,6305760.0),1.6),
 "h14-inspel":((492272.0,6305702.0),(492172.0,6305630.0),4.0),
 "h05-tee":   ((491797.0,6305418.0),(491960.0,6305460.0),1.6),
 "h05-inspel":((491945.0,6305452.0),(492055.0,6305487.0),3.0),
 "h03-tee":   ((491546.8,6305902.0),(491653.5,6305800.7),1.6),
 "h03-inspel":((491698.0,6305783.0),(491715.1,6305712.0),3.0),
 "h17-tee":   ((491725.5,6305958.0),(491645.3,6306054.6),1.6),
 "allm-park": ((491830.0,6305730.0),(491960.0,6305780.0),5.0),
 "allm-lang": ((492060.0,6305630.0),(492040.0,6305860.0),5.0),
 "allm-damm": ((491850.0,6305440.0),(491805.0,6305490.0),5.0),
 "allm-h14green":((492260.0,6305715.0),(492190.0,6305655.0),5.0),
}
for n in (sys.argv[1:] or vyer):
    k,m,h=vyer[n]
    perspektiv(O,D,k,m,hojd_m=h,fov_grader=70 if n.startswith(('allm','h03-inspel')) else 60,ut=Path(f'tmp-ai/{n}-3d.jpg'),fria=fria,linjer=linjer,laz=Path('data/glasriket/laser/y26a023-63050_4900_25.copc.laz')); print(n)
