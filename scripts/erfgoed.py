"""Erfgoed: rijksmonumenten en beschermde stads- en dorpsgezichten (RCE, via PDOK), voor de regio.

Bron: WFS https://service.pdok.nl/rce/beschermde-gebieden-cultuurhistorie/wfs/v1_0
  ps-ch:rce_inspire_points    punten (rijksmonumenten; ook middelpunten van gezichten, die laten we weg)
  ps-ch:rce_inspire_polygons  vlakken (stads- en dorpsgezichten, monumentcomplexen, werelderfgoed)
Max. 1000 objecten per verzoek, dus gepagineerd met startIndex.

Uitvoer data/erfgoed.json:
  mon:  [[lon, lat, monumentnummer, jaar van aanwijzing], ...]  (alleen binnen de regio)
  vlak: FeatureCollection met soort, naam, jaar en link, geknipt op de regiogrens

Gebruik (vanuit de projectmap): .venv/bin/python scripts/erfgoed.py [--opnieuw]
"""
import json, os, sys, time, gzip, re, collections, urllib.request, urllib.parse
import shapely
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union, transform
from shapely.validation import make_valid
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
WFS = 'https://service.pdok.nl/rce/beschermde-gebieden-cultuurhistorie/wfs/v1_0'
BRON = P('bron-downloads', 'rce-erfgoed-regio.json.gz')
BBOX = '51.84,4.47,52.17,4.95,urn:ogc:def:crs:EPSG::4326'
SOORT = {'nlps-rijksmonumenten': 'Rijksmonument', 'nlps-stadsendorpsgezichten': 'Beschermd stads- of dorpsgezicht',
         'nlps-werelderfgoed': 'Werelderfgoed'}


def laag(typename):
    feats, start = [], 0
    while True:
        q = WFS + '?' + urllib.parse.urlencode({'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature',
             'typeNames': typename, 'outputFormat': 'application/json', 'srsName': 'EPSG:4326',
             'count': 1000, 'startIndex': start, 'bbox': BBOX})
        with urllib.request.urlopen(urllib.request.Request(q, headers={'User-Agent': 'regiokaart-midden-holland/1.0'}), timeout=120) as r:
            page = json.load(r)['features']
        feats += page
        print(f'  {typename}: {len(feats)}')
        if len(page) < 900:
            return feats
        start += len(page)


if '--opnieuw' in sys.argv or not os.path.exists(BRON):
    json.dump({'opgehaald': time.strftime('%Y-%m-%d'), 'punten': laag('ps-ch:rce_inspire_points'),
               'vlakken': laag('ps-ch:rce_inspire_polygons')}, gzip.open(BRON, 'wt'))
d = json.load(gzip.open(BRON, 'rt'))

regio = make_valid(unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(P('data', 'gemeenten.json')))['features']]))
jaar = lambda p: int(p['legalfoundationdate'][:4]) if p.get('legalfoundationdate') else None
nummer = lambda p: (re.search(r'/(\d+)$', p.get('ciCitation') or '') or [None, None])[1]

mon, seen = [], set()
for f in d['punten']:
    p = f['properties']
    if p['namespace'] != 'nlps-rijksmonumenten':
        continue
    x, y = f['geometry']['coordinates'][:2]
    nr = nummer(p)
    if not nr or nr in seen or not regio.contains(Point(x, y)):
        continue
    seen.add(nr)
    mon.append([round(x, 5), round(y, 5), int(nr), jaar(p)])

to_rd = Transformer.from_crs(4326, 28992, always_xy=True).transform
to_wgs = Transformer.from_crs(28992, 4326, always_xy=True).transform
regio_rd = transform(to_rd, regio)
vlak = []
for f in d['vlakken']:
    p = f['properties']
    g = make_valid(transform(to_rd, shape(f['geometry']))).simplify(3).intersection(regio_rd)
    if g.is_empty or g.area < 100:
        continue
    g = shapely.set_precision(transform(to_wgs, g), 0.00001)
    vlak.append({'type': 'Feature', 'geometry': mapping(g),
                 'properties': {'s': SOORT.get(p['namespace'], p['namespace']), 'n': (p.get('text') or '').strip(),
                                'j': jaar(p), 'u': p.get('ciCitation')}})

json.dump({'opgehaald': d['opgehaald'], 'mon': mon, 'vlak': {'type': 'FeatureCollection', 'features': vlak}},
          open(P('data', 'erfgoed.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('rijksmonumenten in de regio:', len(mon), '| vlakken:', collections.Counter(v['properties']['s'] for v in vlak),
      '|', round(os.path.getsize(P('data', 'erfgoed.json')) / 1e3), 'kB')
print([(v['properties']['s'], v['properties']['n']) for v in vlak])
