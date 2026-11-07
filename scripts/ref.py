import json, sys
from shapely.geometry import shape
src=sys.argv[1]
spec=json.load(open('spec.json'))
prov=[f for f in json.load(open('provincie_2024.geojson'))['features'] if f['properties']['statnaam']=='Zuid-Holland'][0]
ZH=shape(prov['geometry']).buffer(0)
d=json.load(open(src)); F=[f for f in d['features'] if f['properties'].get('water')=='NEE']
def zh(f):
    try: return ZH.contains(shape(f['geometry']).representative_point())
    except Exception: return False
clean=lambda v: v if isinstance(v,(int,float)) and v>=0 else None
def agg(fs,sp,key):
    t=sp['type']
    if t=='sum':
        vs=[clean(f['properties'].get(key)) for f in fs]; vs=[v for v in vs if v is not None]; return sum(vs) if vs else None
    if t=='w':
        s=w=0
        for f in fs:
            v=clean(f['properties'].get(key)); ww=clean(f['properties'].get(sp['w']))
            if v is not None and ww: s+=v*ww; w+=ww
        return s/w if w else None
    if t=='ratio':
        a=b=0
        for f in fs:
            x=clean(f['properties'].get(sp['num'])); y=clean(f['properties'].get(sp['den']))
            if x is not None and y: a+=x; b+=y
        return a/b*sp['mult'] if b else None
out={}
zhF=[f for f in F if zh(f)]
for lvl,fs in [('nl',F),('zh',zhF)]:
    r={}
    for k,s in spec.items():
        r[k]=agg(fs,s['agg'],k)
        if s.get('cmp'): r[k+'__cmp']=agg(fs,s['cmp'],k)
    out[lvl]=r
out['n']={'nl':len(F),'zh':len(zhF)}
json.dump(out,open('ref.json','w'),indent=1)
print(out['n']); print({k:round(v,1) if v else v for k,v in out['zh'].items()})
