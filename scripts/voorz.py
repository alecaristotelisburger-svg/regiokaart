import json, collections
exec(open('../scripts/bus.py').read().split('rels={}')[0])  # hergebruik gm_of
d=json.load(open('../bron-downloads/osm-voorzieningen.geojson'))
CAT={'school':('onderwijs','School'),'hospital':('zorg','Ziekenhuis'),'clinic':('zorg','Kliniek / polikliniek'),'doctors':('zorg','Huisarts / arts'),'pharmacy':('zorg','Apotheek'),
     'sports_centre':('sport','Sportaccommodatie'),'community_centre':('maatsch','Buurt- of dorpshuis'),'library':('maatsch','Bibliotheek'),'townhall':('maatsch','Gemeentehuis')}
out=[]; seen=set()
for f in d['features']:
    p=f['properties']; t=p.get('amenity') or p.get('leisure'); x,y=f['geometry']['coordinates']
    g=gm_of(x,y)
    if not g or t not in CAT: continue
    c,l=CAT[t]
    adr=' '.join(filter(None,[p.get('addr:street'),p.get('addr:housenumber')]))
    if p.get('addr:city'): adr=(adr+', ' if adr else '')+p['addr:city']
    k=(p.get('name'),t,round(x,3),round(y,3))
    if k in seen: continue
    seen.add(k)
    pr={'c':c,'t':l,'n':p.get('name','')}
    if adr: pr['a']=adr
    if p.get('operator'): pr['o']=p['operator']
    if t=='school' and p.get('isced:level'): pr['lvl']=p['isced:level']
    pr['gm']=g
    out.append({'type':'Feature','properties':pr,'geometry':{'type':'Point','coordinates':[round(x,5),round(y,5)]}})
json.dump({'type':'FeatureCollection','features':out},open('voorz.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(out), collections.Counter(f['properties']['t'] for f in out))
tab=collections.defaultdict(collections.Counter)
for f in out: tab[f['properties']['gm']][f['properties']['c']]+=1
for g in sorted(tab): print(g, dict(tab[g]))
