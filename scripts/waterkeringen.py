"""Dijken en waterkeringen (waterschappen, PDOK 'Waterschappen Keringen IMWA', collectie waterkering).

Bron: https://api.pdok.nl/hwh/waterschappen-keringen-imwa/ogc/v1/collections/waterkering (OGC API Features, per 1000)
Ruwe download: bron-downloads/waterschappen-keringen-regio.json.gz (bbox rond de regio). Met --opnieuw opnieuw ophalen.
Uitvoer data/keringen.json: lijnen geknipt op de regio + 60 m (niet de dijken aan de overkant van de rivier), vereenvoudigd (3 m), met categorie (primair/regionaal/overig),
naam, type (dijk/kunstwerk) en beheerder.

Gebruik (vanuit de projectmap): .venv/bin/python scripts/waterkeringen.py [--opnieuw]
"""
import json, os, sys, gzip, time, collections, urllib.request
import shapely
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
BRON = P('bron-downloads', 'waterschappen-keringen-regio.json.gz')
URL = 'https://api.pdok.nl/hwh/waterschappen-keringen-imwa/ogc/v1/collections/waterkering/items?f=json&bbox=4.50,51.86,4.92,52.15&limit=1000'

if '--opnieuw' in sys.argv or not os.path.exists(BRON):
    feats, url = [], URL
    while url:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'regiokaart-midden-holland/1.0'}), timeout=180))
        feats += d['features']; url = next((l['href'] for l in d.get('links', []) if l['rel'] == 'next'), None)
    json.dump({'opgehaald': time.strftime('%Y-%m-%d'), 'features': feats}, gzip.open(BRON, 'wt'))
d = json.load(gzip.open(BRON, 'rt'))

rd = Transformer.from_crs(4326, 28992, always_xy=True).transform
wgs = Transformer.from_crs(28992, 4326, always_xy=True).transform
regio = transform(rd, unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(P('data', 'gemeenten.json')))['features']])).buffer(60)
uit, lengte = [], collections.Counter()
for f in d['features']:
    p = f['properties']
    if not f.get('geometry'):
        continue
    g = transform(rd, shape(f['geometry'])).intersection(regio)
    if g.is_empty or g.length < 20:
        continue
    g = g.simplify(3)
    cat = (p.get('categoriewaterkering') or 'overig').lower()
    lengte[cat] += g.length
    g = shapely.set_precision(transform(wgs, g), 0.00001)
    uit.append({'type': 'Feature', 'geometry': mapping(g),
                'properties': {'c': cat, 'n': (p.get('naam') or '').strip(), 't': p.get('typewaterkering') or 'Dijk', 'b': p.get('waterbeheerder') or ''}})
json.dump({'opgehaald': d['opgehaald'], 'type': 'FeatureCollection', 'features': uit}, open(P('data', 'keringen.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(uit), 'keringen;', {k: f'{v/1000:.0f} km' for k, v in lengte.items()}, '|', round(os.path.getsize(P('data', 'keringen.json')) / 1e3), 'kB')
print(collections.Counter(f['properties']['b'] for f in uit))
