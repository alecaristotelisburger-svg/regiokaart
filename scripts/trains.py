import json, math, collections
d=json.load(open('../bron-downloads/osm-treinroutes.json'))
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
TYPE={'long_distance':'Intercity','regional':'Sprinter','night':'Nachtnet','international':'Internationaal'}
services={}; way_serv=collections.defaultdict(set); way_geom={}; stops=[]
for e in d['elements']:
    t=e['tags']; ref=t.get('ref',''); name=t.get('name','')
    route=name.split(':',1)[1].strip() if ':' in name else name
    ends=[s.strip() for s in route.replace('→','-').replace('=>','-').split(' - ')]
    key=(t.get('operator',''),ref,tuple(sorted([ends[0],ends[-1]])))
    typ=TYPE.get(t.get('service'),'Trein')
    if key not in services:
        services[key]={'label':(f"Nachtnet: {ends[0].replace('Nachtnet ','').replace('(Gouda -) ','')} – {ends[-1]}" if typ=='Nachtnet' else f"{typ} {ref}: {ends[0]} – {ends[-1]}"),'typ':typ,'op':t.get('operator',''),'stops':set()}
    for m in e['members']:
        if m['type']=='way' and m.get('role','')=='' and m.get('geometry'):
            way_serv[m['ref']].add(key); way_geom[m['ref']]=[[p['lon'],p['lat']] for p in m['geometry'] if p]
        if m['type']=='node' and m.get('role','').startswith('stop') and 'lat' in m:
            g=gm_of(m['lon'],m['lat'])
            if g: stops.append((m['lon'],m['lat'],key,g))
# alleen diensten die in de regio stoppen tonen we als 'stopt hier'
stopping={k for *_,k,_ in stops}
# stations clusteren (300 m)
clusters=[]
for x,y,k,g in stops:
    for c in clusters:
        if math.hypot((c['x']-x)*68000,(c['y']-y)*111000)<400: c['keys'].add(k); break
    else: clusters.append({'x':x,'y':y,'keys':{k},'g':g})
KNOWN={'Gouda':(4.7061,52.0174),'Gouda Goverwelle':(4.7421,52.0150),'Waddinxveen Triangel':(4.6491,52.0273),'Waddinxveen':(4.6498,52.0441),'Waddinxveen Noord':(4.6484,52.0552),'Bodegraven':(4.7462,52.0814),'Nieuwerkerk a/d IJssel':(4.6169,51.9653)}
feats=[]
for c in clusters:
    best=min(KNOWN.items(), key=lambda kv: math.hypot((kv[1][0]-c['x'])*68000,(kv[1][1]-c['y'])*111000))
    dist=math.hypot((best[1][0]-c['x'])*68000,(best[1][1]-c['y'])*111000)
    naam=best[0] if dist<700 else None
    labs=sorted({services[k]['label'] for k in c['keys']}, key=lambda s:(not s.startswith('Intercity'),s))
    feats.append({'type':'Feature','properties':{'naam':naam,'gm':c['g'],'diensten':labs},'geometry':{'type':'Point','coordinates':[round(c['x'],5),round(c['y'],5)]}})
    print(naam, round(dist), c['g'], len(labs))
json.dump({'type':'FeatureCollection','features':feats},open('stations.json','w'),ensure_ascii=False)
# trajecten: groepeer ways per set diensten
F=[]
for wid,ks in way_serv.items():
    st=sorted({services[k]['label'] for k in ks if k in stopping}, key=lambda s:(not s.startswith('Intercity'),s))
    door=sorted({services[k]['label'] for k in ks if k not in stopping})
    F.append({'type':'Feature','properties':{'stop':' | '.join(st),'door':' | '.join(door),'n':len(st)},'geometry':{'type':'LineString','coordinates':way_geom[wid]}})
json.dump({'type':'FeatureCollection','features':F},open('rail_in.json','w'),ensure_ascii=False)
print(len(F),'ways;', len(stopping),'diensten stoppen in regio;', len(services),'totaal')
for k in services: print(('STOP ' if k in stopping else 'door ')+services[k]['label'])
