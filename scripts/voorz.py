"""Voorzieningen per categorie (laag 'Voorzieningen', tabel per gemeente en gemeenteprofiel).

Sinds 7-11-2026 afgeleid uit data/locaties.json (scripts/locaties.py), zodat de laag, de tabel,
het profiel en de vinkjes 'Toon ... op de kaart' dezelfde, opgeschoonde OpenStreetMap-gegevens
gebruiken. Alleen locaties binnen de regio (r = 1).

Uitvoer data/voorz.json: properties c (categorie), t (soort), n (naam), a (adres), gm (gemeente).
Gebruik (vanuit de projectmap): .venv/bin/python scripts/voorz.py
"""
import json, os, collections
from shapely.geometry import shape, Point

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
CAT = {'basisschool': ('onderwijs', 'Basisschool'), 'middelbaar': ('onderwijs', 'Middelbare school'),
       'huisarts': ('zorg', 'Huisarts'), 'huisartsenpost': ('zorg', 'Huisartsenpost'), 'apotheek': ('zorg', 'Apotheek'),
       'ziekenhuis': ('zorg', 'Ziekenhuis'), 'kliniek': ('zorg', 'Kliniek / polikliniek'),
       'sport': ('sport', 'Sportaccommodatie'),
       'buurthuis': ('maatsch', 'Buurt- of dorpshuis'), 'bibliotheek': ('maatsch', 'Bibliotheek'),
       'gemeentehuis': ('maatsch', 'Gemeentehuis')}

gms = [(f['properties']['gemeentenaam'], shape(f['geometry']).buffer(0))
       for f in json.load(open(P('data', 'gemeenten.json')))['features']]
gm_of = lambda x, y: next((n for n, g in gms if g.contains(Point(x, y))), None)

out, idx = [], {}
for f in json.load(open(P('data', 'locaties.json')))['features']:
    p = f['properties']
    if not p['r'] or p['k'] not in CAT:
        continue
    c, t = CAT[p['k']]
    x, y = f['geometry']['coordinates']
    key = (c, p['n'].lower(), round(x, 3), round(y, 3))
    if key in idx:  # school met basis- én middelbaar onderwijs: één punt
        idx[key]['properties']['t'] = 'Basis- en middelbare school'
        continue
    g = gm_of(x, y)
    if not g:
        continue
    q = {'c': c, 't': t, 'n': p['n'], 'gm': g}
    if p.get('a'):
        q['a'] = p['a']
    idx[key] = {'type': 'Feature', 'properties': q, 'geometry': f['geometry']}
    out.append(idx[key])

json.dump({'type': 'FeatureCollection', 'features': out}, open(P('data', 'voorz.json'), 'w'),
          ensure_ascii=False, separators=(',', ':'))
print(len(out), collections.Counter(f['properties']['c'] for f in out))
tab = collections.defaultdict(collections.Counter)
for f in out:
    tab[f['properties']['gm']][f['properties']['c']] += 1
for g in sorted(tab):
    print(' ', g, dict(tab[g]))
