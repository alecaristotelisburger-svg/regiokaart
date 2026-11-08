"""Locaties bij de afstandsthema's ('Toon ... op de kaart').

Bron: OpenStreetMap via Overpass, in delen gedownload (de server gaf bij één grote vraag een 504):
  bron-downloads/osm-locaties-1.json  supermarkten, ziekenhuizen, snelwegaansluitingen, stations
  bron-downloads/osm-locaties-2.json  huisartsen/artsen, scholen
  bron-downloads/osm-locaties-3.json  apotheken, kinderopvang, brandweer, bibliotheken, zwembaden
  bron-downloads/osm-locaties-4.json  sportaccommodaties, buurthuizen, gemeentehuizen, klinieken
Bbox van alle vragen: (51.81,4.44,52.20,4.98). Zie CLAUDE.md voor de queries.

Gehouden: alles binnen de regio + BUFFER meter, want de CBS-afstand rekent ook met
voorzieningen net buiten de regio (bijv. IJsselland Ziekenhuis in Capelle).
Uitvoer: data/locaties.json (properties: k = soort, n = naam, a = adres/plaats, r = in regio 0/1)

Gebruik (vanuit de projectmap): .venv/bin/python scripts/locaties.py
"""
import json, os, re, collections
from shapely.geometry import shape, Point
from shapely.ops import unary_union, transform
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
BUFFER = 5000  # meter rond de regio

to_rd = Transformer.from_crs(4326, 28992, always_xy=True).transform
regio = transform(to_rd, unary_union([shape(f['geometry']) for f in json.load(open(P('data', 'gemeenten.json')))['features']]))
zone = regio.buffer(BUFFER)

VO_JA = re.compile(r'\bcsg\b|college|lyceum|gymnasium|mavo|havo|vwo|vmbo|atheneum|praktijkonderwijs|scholengemeenschap|'
                   r'voortgezet|middelbare', re.I)
GEEN_BO_VO = re.compile(r'\broc\b|mbo|hogeschool|universiteit|kinderopvang|peuter|muziekschool|rijschool|dansschool|zwemschool', re.I)
VO = re.compile(VO_JA.pattern + '|' + GEEN_BO_VO.pattern, re.I)  # alles wat geen basisschool is
GEEN_ZWEMBAD = re.compile(r'speeltuin|spettertuin', re.I)
BO = re.compile(r'basisschool|\b(o|c|pc|rk|r\.k\.|k|chr\.?)\s?bs\b|\bobs\b|\bcbs\b|\bkbs\b|\bsbo\b|daltonschool|montessori|jenaplan|vrije school|kindcentrum|\bikc\b|\bikc\b|\bkc\b', re.I)
NIET_ZH = re.compile(r'ggz|revalidatie|gezichtskliniek|ooghuis|hospice|lupine', re.I)
HA = re.compile(r'huisarts|gezondheidscentrum|medisch centrum|dokter|praktijk', re.I)
SPECIALIST = re.compile(r'tandarts|orthodont|fysio|dermat|plastisch|oog|kaak|dier|psych|cosmet|kliniek', re.I)


def soort(t):
    """Welke afstandscategorieën horen bij deze OSM-tags (lijst, kan leeg zijn)."""
    a, n = t.get('amenity'), t.get('name', '')
    if t.get('shop') == 'supermarket':
        return ['supermarkt']
    if a == 'hospital':
        return [] if NIET_ZH.search(n) else ['ziekenhuis']
    if t.get('highway') == 'motorway_junction':
        return ['oprit']
    if t.get('railway') == 'station':
        st = t.get('station', '')
        if t.get('usage') == 'tourism' or (st in ('subway', 'light_rail') and t.get('train') != 'yes'):
            return []
        return ['station']
    if a == 'doctors' or t.get('healthcare') == 'general_practitioner':
        if re.search(r'huisartsenpost', n, re.I):
            return ['huisartsenpost']
        gp = t.get('healthcare') == 'general_practitioner' or 'general' in t.get('healthcare:speciality', '')
        return ['huisarts'] if gp or (HA.search(n) and not SPECIALIST.search(n)) else []
    if a == 'school':
        lvl = t.get('isced:level', '')
        if lvl:
            parts = re.split(r'[;,\-]', lvl)
            k = []
            if '1' in parts or lvl in ('0-2', '0-1'):
                k.append('basisschool')
            if ('2' in parts or '3' in parts) and not GEEN_BO_VO.search(n):
                k.append('middelbaar')
            return k
        if not n:
            return []
        if VO_JA.search(n) and not GEEN_BO_VO.search(n):
            return ['middelbaar']
        return ['basisschool'] if (BO.search(n) or not VO.search(n)) else []
    if a == 'pharmacy':
        return ['apotheek']
    if a in ('childcare', 'kindergarten'):
        return ['kinderopvang']
    if a == 'fire_station':
        return ['brandweer']
    if a == 'library':
        return ['bibliotheek']
    k = []
    if t.get('leisure') == 'sports_centre':
        k.append('sport')
    zwem = t.get('leisure') in ('water_park', 'swimming_pool') or 'swimming' in t.get('sport', '')
    if zwem and t.get('leisure') in ('sports_centre', 'water_park', 'swimming_pool') and not GEEN_ZWEMBAD.search(n):
        k.append('zwembad')
    if a == 'community_centre':
        k.append('buurthuis')
    if a == 'townhall':
        k.append('gemeentehuis')
    if a == 'clinic':
        k.append('kliniek')
    return k


out, seen, dichtbij = [], set(), {}
for fn in ['osm-locaties-1.json', 'osm-locaties-2.json', 'osm-locaties-3.json', 'osm-locaties-4.json']:
    for e in json.load(open(P('bron-downloads', fn)))['elements']:
        t = e.get('tags', {})
        lon, lat = (e['lon'], e['lat']) if 'lon' in e else (e['center']['lon'], e['center']['lat'])
        pt = Point(to_rd(lon, lat))
        if not zone.contains(pt):
            continue
        for k in soort(t):
            n = t.get('name', '')
            if k == 'oprit':
                n = ' '.join(filter(None, [('afrit ' + t['ref']) if t.get('ref') else '', t.get('name', '')])) or 'aansluiting'
            if k in ('ziekenhuis', 'station'):
                # zelfde naam binnen 1 km = zelfde object (punt + gebouw); verder weg = andere locatie
                # (bijv. Groene Hart Ziekenhuis in Gouda én in Bodegraven)
                key = (k, n.lower())
                if any(pt.distance(q) < 1000 for q in dichtbij.get(key, [])):
                    continue
                dichtbij.setdefault(key, []).append(pt)
            else:
                key = (k, n.lower(), round(lon, 3), round(lat, 3))
                if key in seen:
                    continue
                seen.add(key)
            adr = ' '.join(filter(None, [t.get('addr:street'), t.get('addr:housenumber')]))
            if t.get('addr:city'):
                adr = (adr + ', ' if adr else '') + t['addr:city']
            pr = {'k': k, 'n': n, 'r': 1 if regio.contains(pt) else 0}
            if adr:
                pr['a'] = adr
            out.append({'type': 'Feature', 'properties': pr,
                        'geometry': {'type': 'Point', 'coordinates': [round(lon, 5), round(lat, 5)]}})

json.dump({'type': 'FeatureCollection', 'features': out}, open(P('data', 'locaties.json'), 'w'),
          ensure_ascii=False, separators=(',', ':'))
c = collections.Counter((f['properties']['k'], f['properties']['r']) for f in out)
for k in ['huisarts', 'huisartsenpost', 'apotheek', 'basisschool', 'middelbaar', 'kinderopvang', 'supermarkt',
          'ziekenhuis', 'kliniek', 'station', 'oprit', 'brandweer', 'bibliotheek', 'zwembad', 'sport', 'buurthuis',
          'gemeentehuis']:
    print(f'{k:14s} in regio {c[(k, 1)]:4d}   tot {BUFFER // 1000} km erbuiten {c[(k, 0)]:4d}')
