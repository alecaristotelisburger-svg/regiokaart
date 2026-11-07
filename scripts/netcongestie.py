"""Netcongestie: capaciteitskaart elektriciteitsnet van Netbeheer Nederland, voor de regio.

Bron: ArcGIS Feature Service (Esri Nederland voor Netbeheer Nederland), laag 'afname'.
Die laag bevat per voedingsgebied zowel de code voor afname (verbruik) als opwek (teruglevering).
Codes: 0 = capaciteit beschikbaar, 1 = beperkte capaciteit, 2 = geen capaciteit (onderzoek naar
oplossing), 3 = geen capaciteit (wachtrij). Indicatief; ververst ca. elk kwartaal.

Stappen:
  1. ophalen (alleen als bron-downloads/netcongestie-regio.json.gz ontbreekt, of met --opnieuw):
     id's van gebieden die de regio-bbox raken, daarna per 20 id's met geometrie (WGS84).
  2. verwerken: geometrie naar RD, vereenvoudigen (15 m), knippen op de regiogrens -> data/net.json

Gebruik (vanuit de projectmap): .venv/bin/python scripts/netcongestie.py [--opnieuw]
"""
import json, os, sys, time, gzip, shapely, urllib.request, urllib.parse, collections
from shapely.geometry import Polygon, MultiPolygon, shape, mapping
from shapely.ops import unary_union, transform
from shapely.validation import make_valid
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
URL = ('https://services.arcgis.com/nSZVuSZjHpEZZbRo/arcgis/rest/services/'
       'Capaciteitskaart_elektriciteitsnet_v2_afname/FeatureServer/0/query')
BRON = P('bron-downloads', 'netcongestie-regio.json.gz')
FIELDS = 'OBJECTID,afname,opwek,voedingsgebied_id,voedingsgebied_naam,RNB,wachtrij_afname,wachtrij_invoeding,unieke_verzoeken_afname,unieke_verzoeken_invoeding'


def get(params):
    q = URL + '?' + urllib.parse.urlencode(params)
    for poging in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers={'User-Agent': 'regiokaart-midden-holland/1.0'}), timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print('  opnieuw na fout:', e); time.sleep(5 * (poging + 1))
    raise SystemExit('Ophalen mislukt: ' + q[:120])


def ophalen():
    env = {'geometry': '4.47,51.84,4.95,52.17', 'geometryType': 'esriGeometryEnvelope', 'inSR': 4326,
           'spatialRel': 'esriSpatialRelIntersects', 'where': '1=1', 'f': 'json'}
    ids = sorted(get({**env, 'returnIdsOnly': 'true'})['objectIds'])
    print('voedingsgebieden rond de regio:', len(ids))
    feats = []
    for i in range(0, len(ids), 20):
        d = get({'objectIds': ','.join(map(str, ids[i:i + 20])), 'outFields': FIELDS, 'outSR': 4326, 'f': 'json'})
        feats += d['features']
        print(f'  {len(feats)}/{len(ids)}')
    json.dump({'opgehaald': time.strftime('%Y-%m-%d'), 'bron': URL, 'features': feats}, gzip.open(BRON, 'wt'))


def esri_naar_shapely(rings):
    """ArcGIS-ringen: met de klok mee = buitenrand, tegen de klok in = gat."""
    buiten, gaten = [], []
    for r in rings:
        if len(r) < 4:
            continue
        a = sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(r, r[1:]))
        (buiten if a > 0 else gaten).append(Polygon(r))
    polys = []
    for b in buiten:
        hs = [h for h in gaten if b.contains(h.representative_point())]
        polys.append(Polygon(b.exterior.coords, [h.exterior.coords for h in hs]))
    return make_valid(MultiPolygon(polys) if len(polys) > 1 else polys[0])


if '--opnieuw' in sys.argv or not os.path.exists(BRON):
    ophalen()
d = json.load(gzip.open(BRON, 'rt'))
to_rd = Transformer.from_crs(4326, 28992, always_xy=True).transform
to_wgs = Transformer.from_crs(28992, 4326, always_xy=True).transform
regio = unary_union([shape(f['geometry']) for f in json.load(open(P('data', 'gemeenten.json')))['features']])
regio_rd = transform(to_rd, regio)
out = []
for f in d['features']:
    g = transform(to_rd, esri_naar_shapely(f['geometry']['rings'])).simplify(15)
    g = make_valid(g).intersection(regio_rd)
    if g.is_empty or g.area < 5000:  # snippers langs de rand (< 0,5 ha) weglaten
        continue
    g = transform(to_wgs, g)
    g = g if g.geom_type in ('Polygon', 'MultiPolygon') else unary_union([x for x in getattr(g, 'geoms', []) if x.geom_type in ('Polygon', 'MultiPolygon')])
    g = shapely.set_precision(g, 0.00001)  # afronden op ~1 m zonder ongeldige vlakken
    a = f['attributes']
    naam = (a['voedingsgebied_naam'] or '').strip()
    if not a['RNB'] and naam in ('', '0'):  # gebied zonder netbeheerder en naam: geen bruikbare gegevens
        a = {**a, 'afname': None, 'opwek': None}
        naam = 'Onbekend voedingsgebied'
    pr = {'naam': naam, 'rnb': a['RNB'], 'af': a['afname'], 'op': a['opwek'],
          'wa': a['wachtrij_afname'], 'wi': a['wachtrij_invoeding'],
          'va': a['unieke_verzoeken_afname'], 'vi': a['unieke_verzoeken_invoeding']}
    geom = mapping(g)
    out.append({'type': 'Feature', 'properties': pr, 'geometry': geom})
json.dump({'type': 'FeatureCollection', 'opgehaald': d['opgehaald'], 'features': out},
          open(P('data', 'net.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('in de regio:', len(out), 'gebieden | opgehaald', d['opgehaald'], '|',
      round(os.path.getsize(P('data', 'net.json')) / 1e3), 'kB')
print('afname:', collections.Counter(f['properties']['af'] for f in out), '| opwek:', collections.Counter(f['properties']['op'] for f in out))
print('netbeheerders:', collections.Counter(f['properties']['rnb'] for f in out))
