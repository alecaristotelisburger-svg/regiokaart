import json, math, collections
gm=json.load(open('gemeenten.json'))
def inring(x,y,r):
    ins=False; j=len(r)-1
    for i in range(len(r)):
        xi,yi=r[i]; xj,yj=r[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi: ins=not ins
        j=i
    return ins
def gm_of(x,y):
    for f in gm['features']:
        g=f['geometry']; polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
        for p in polys:
            if inring(x,y,p[0]) and not any(inring(x,y,h) for h in p[1:]): return f['properties']['gemeentenaam']
    return None
rels={}; stops={}
for i in '123':
    for f in json.load(open(f'../bron-downloads/osm-busroutes/{i}.geojson'))['features']:
        p=f['properties']; g=f['geometry']
        if g['type']=='Point':
            sid=p['@id']; x,y=g['coordinates']
            s=stops.setdefault(sid,{'x':x,'y':y,'rels':{}})
            for r in p.get('@relations',[]):
                rt=r.get('reltags',{})
                if rt.get('route')=='bus': s['rels'][r['rel']]=rt
        else:
            rid=p['@id']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
            e=rels.setdefault(rid,{'tags':p,'lines':[]}); e['lines']+=lines
# lijnen
def key(t): return (t.get('operator',''), t.get('ref',''))
L={}
for rid,e in rels.items():
    t=e['tags']; k=key(t)
    l=L.setdefault(k,{'ref':t.get('ref',''),'op':t.get('operator',''),'brand':t.get('brand',''),'ends':set(),'lines':[],'gms':set()})
    for a in ('from','to'):
        if t.get(a): l['ends'].add(t[a].split(',')[0].strip())
    l['lines']+=e['lines']
# haltes in regio
S=[]
for sid,s in stops.items():
    g=gm_of(s['x'],s['y'])
    if not g: continue
    ks={key(t) for t in s['rels'].values()}
    for k in ks:
        if k in L: L[k]['gms'].add(g)
    S.append({'x':s['x'],'y':s['y'],'g':g,'ks':ks})
# clusteren 80 m (haltes aan twee kanten van de weg)
C=[]
for s in S:
    for c in C:
        if math.hypot((c['x']-s['x'])*68000,(c['y']-s['y'])*111000)<80: c['ks']|=s['ks']; break
    else: C.append(dict(s))
def lab(k): return L[k]['ref'] if k in L else k[1]
stf=[{'type':'Feature','properties':{'gm':c['g'],'lijnen':sorted({lab(k) for k in c['ks']}, key=lambda r:(len(r),r))},'geometry':{'type':'Point','coordinates':[round(c['x'],5),round(c['y'],5)]}} for c in C]
json.dump({'type':'FeatureCollection','features':stf},open('busstops.json','w'),ensure_ascii=False,separators=(',',':'))
lf=[]
for k,l in L.items():
    if not l['gms']: continue
    lf.append({'type':'Feature','properties':{'ref':l['ref'],'op':l['op'],'brand':l['brand'],'route':' – '.join(sorted(l['ends'])),'gms':', '.join(sorted(l['gms']))},'geometry':{'type':'MultiLineString','coordinates':l['lines']}})
json.dump({'type':'FeatureCollection','features':lf},open('buslines_in.json','w'),ensure_ascii=False)
print(len(rels),'relaties;',len(L),'lijnen;',len(lf),'stoppen in regio;',len(S),'haltes ->',len(C),'clusters')
print(collections.Counter(l['op'] for l in L.values() if l['gms']))
for f in sorted(lf,key=lambda f:(len(f['properties']['ref']),f['properties']['ref']))[:60]: print(f['properties']['ref'],f['properties']['op'],'|',f['properties']['route'][:70],'|',f['properties']['gms'])
