"""Lagen voor de regio als samenwerkingsverband (9-11-2026): regionale indelingen, bedrijventerreinen, energie, veenweide en bodem.

  indelingen   CBS-gebiedsindelingen via PDOK (api.pdok.nl/cbs/gebiedsindelingen/ogc/v1), nieuwste jaar per indeling
  bedrijven    IBIS-bedrijventerreinen via Provincie Zuid-Holland (WFS economie:BEDRIJVEN_TERREINEN), terreinen in de 5 gemeenten
  energie      hoogspanning (≥ 50 kV), stations, windturbines en zonneparken uit OpenStreetMap
               (bron-downloads/osm-energie-net.json en osm-energie-opwek.json, opgehaald via Overpass)
  bodem        legenda's van de provinciale bodemkaarten (WMS geodata.zuid-holland.nl), als data-URI

Uitvoer: data/indelingen.json, data/bedrijventerreinen.json, data/energie.json, data/bodem.json
Gebruik (vanuit de projectmap): .venv/bin/python scripts/regio_lagen.py [--opnieuw] [onderdeel ...]
"""
import json, os, sys, gzip, time, base64, subprocess, urllib.request, urllib.parse, collections
import shapely
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union, transform
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
UA = {'User-Agent': 'regiokaart-midden-holland/1.0'}
OPNIEUW = '--opnieuw' in sys.argv
WEL = [a for a in sys.argv[1:] if not a.startswith('--')]
rd = Transformer.from_crs(4326, 28992, always_xy=True).transform
wgs = Transformer.from_crs(28992, 4326, always_xy=True).transform
GEM = json.load(open(P('data', 'gemeenten.json')))['features']
REGIO = unary_union([shape(f['geometry']).buffer(0) for f in GEM])
REGIO_RD = transform(rd, REGIO)


def haal(url, timeout=180):
    for poging in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if 'SSL' in str(e):
                r = subprocess.run(['curl', '-s', '-f', '--max-time', str(timeout), '-A', UA['User-Agent'], url], capture_output=True)
                if r.returncode == 0: return r.stdout
            print('   opnieuw proberen:', str(e)[:80]); time.sleep(3 + 5 * poging)
    raise RuntimeError('ophalen mislukt: ' + url[:120])


def bron(naam, maak):
    pad = P('bron-downloads', naam + '.json.gz')
    if OPNIEUW or not os.path.exists(pad):
        d = maak(); d['opgehaald'] = time.strftime('%Y-%m-%d')
        json.dump(d, gzip.open(pad, 'wt'), ensure_ascii=False)
    return json.load(gzip.open(pad, 'rt'))


def schrijf(naam, d):
    json.dump(d, open(P('data', naam + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'  data/{naam}.json', round(os.path.getsize(P('data', naam + '.json')) / 1e3), 'kB')


def wgs_geom(g_rd, tol):
    return mapping(shapely.set_precision(transform(wgs, g_rd.simplify(tol)), 0.00001))


# ---------- 1. Regionale indelingen ----------
INDELINGEN = [  # (collectie, naam in de kaart)
    ('veiligheidsregio', 'Veiligheidsregio'), ('ggdregio', 'GGD-regio'), ('regionale_energiestrategie', 'RES-regio (energie)'),
    ('arbeidsmarktregio', 'Arbeidsmarktregio'), ('jeugdregio', 'Jeugdzorgregio'), ('veiligthuisregio', 'Veilig Thuis-regio'),
    ('zorgkantoorregio', 'Zorgkantoorregio'), ('regionale_eenheid', 'Politie-eenheid'), ('arrondissementsgebied', 'Arrondissement (rechtspraak)'),
    ('coropgebied', 'COROP-gebied (statistiek)'),
]
def indelingen():
    bbox = '4.40,51.80,5.05,52.25'
    def maak():
        uit = {}
        for col, _ in INDELINGEN:
            feats, url = [], f'https://api.pdok.nl/cbs/gebiedsindelingen/ogc/v1/collections/{col}_gegeneraliseerd/items?f=json&limit=1000&bbox={bbox}'
            while url:
                d = json.loads(haal(url)); feats += d['features']; url = next((l['href'] for l in d.get('links', []) if l['rel'] == 'next'), None)
            uit[col] = feats; print(f'   {col}: {len(feats)}')
        return uit
    d = bron('cbs-gebiedsindelingen-regio', maak)
    gm_punt = {f['properties']['gemeentenaam']: shape(f['geometry']).representative_point() for f in GEM}
    out = []
    for col, naam in INDELINGEN:
        fs = d[col]; jaar = max(f['properties']['jaarcode'] for f in fs)
        lagen, leden = [], {}
        for f in fs:
            p = f['properties']
            if p['jaarcode'] != jaar: continue
            g = shape(f['geometry']).buffer(0)
            if not g.intersects(REGIO) or g.intersection(REGIO).area < 0.002 * REGIO.area: continue
            wie = [gn for gn, pt in gm_punt.items() if g.contains(pt)]
            lagen.append({'type': 'Feature', 'properties': {'n': p['statnaam'], 'c': p['statcode'], 'gm': wie},
                          'geometry': wgs_geom(transform(rd, g), 120)})
            for gn in wie: leden[gn] = p['statnaam']
        out.append({'k': col, 'naam': naam, 'jaar': jaar, 'gebieden': {'type': 'FeatureCollection', 'features': lagen}, 'per_gemeente': leden})
        print(f'   {naam} {jaar}: ' + ' / '.join(f"{x['properties']['n']} ({', '.join(x['properties']['gm']) or '—'})" for x in lagen))
    schrijf('indelingen', {'bron': 'CBS-gebiedsindelingen, via PDOK', 'opgehaald': d['opgehaald'], 'indelingen': out})


# ---------- 3. Bedrijventerreinen (IBIS, Provincie Zuid-Holland) ----------
def bedrijven():
    def maak():
        flt = 'gemeente_code IN (513,1892,1901,1931,627)'
        u = ('https://geodata.zuid-holland.nl/geoserver/economie/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=economie:BEDRIJVEN_TERREINEN'
             '&outputFormat=application/json&srsName=EPSG:4326&cql_filter=' + urllib.parse.quote(flt))
        return {'features': json.loads(haal(u))['features']}
    d = bron('ibis-bedrijventerreinen-regio', maak)
    out = []
    for f in d['features']:
        p = f['properties']
        if not f.get('geometry'): continue
        g = transform(rd, shape(f['geometry'])).buffer(0)
        if not REGIO_RD.buffer(200).contains(g.representative_point()): continue   # alleen terreinen in de regio
        num = lambda k: round(p.get(k) or 0, 1)
        out.append({'type': 'Feature', 'geometry': wgs_geom(g, 2),
                    'properties': {'n': p.get('plan_naam'), 'kern': (p.get('kern_naam') or '').title(), 'gm': next((gf['properties']['gemeentenaam'] for gf in GEM if shape(gf['geometry']).buffer(0).contains(transform(wgs, g.representative_point()))), (p.get('gemeente_naam') or '').title()),   # gemeente op de kaart (IBIS heeft soms een verkeerde naam)
                                   'bruto': num('bruto_oppervlakte'), 'netto': num('netto_oppervlakte'), 'uitg': num('oppervlakte_totaal_uitgeefbaar'),
                                   'direct': num('oppervlakte_totaal_terstond_uit'), 'vol': p.get('vol') == 'JA', 'status': (p.get('status_2') or '').lower(),
                                   'milieu': p.get('maximale_milieucategorie'), 'start': p.get('start_jaar'), 'verouderd': p.get('verouderd') == 'JA',
                                   'transf': num('oppervlakte_transformatie'), 'pm': p.get('park_management') == 'JA', 'jaar': p.get('jaar')}})
    out.sort(key=lambda f: -f['properties']['bruto'])
    tot = collections.Counter()
    for f in out:
        tot['bruto'] += f['properties']['bruto']; tot['uitg'] += f['properties']['uitg']; tot['n'] += 1
    schrijf('bedrijventerreinen', {'bron': 'IBIS-bedrijventerreinen, Provincie Zuid-Holland', 'opgehaald': d['opgehaald'], 'type': 'FeatureCollection', 'features': out})
    print('   terreinen:', tot['n'], '| bruto', round(tot['bruto']), 'ha | uitgeefbaar', round(tot['uitg'], 1), 'ha |', collections.Counter(f['properties']['gm'] for f in out))


# ---------- 2. Energie (OpenStreetMap) ----------
def kv(s):
    try: return max(int(x) for x in str(s).replace(',', ';').split(';') if x.strip().isdigit()) // 1000
    except Exception: return 0
def energie():
    net = json.load(open(P('bron-downloads', 'osm-energie-net.json')))['elements']
    opw = json.load(open(P('bron-downloads', 'osm-energie-opwek.json')))['elements']
    zone = REGIO_RD.buffer(3000)
    lijnen, stations, wind, zon = [], [], [], []
    for e in net:
        t = e.get('tags', {}); v = kv(t.get('voltage'))
        if t.get('power') in ('line', 'minor_line') and v >= 110 and e.get('geometry'):   # 50 kV ligt meestal ondergronds en staat maar deels in OSM
            from shapely.geometry import LineString
            g = transform(rd, LineString([(q['lon'], q['lat']) for q in e['geometry']])).intersection(zone)
            if g.is_empty: continue
            lijnen.append({'type': 'Feature', 'geometry': wgs_geom(g, 5), 'properties': {'kv': v, 'n': t.get('name') or '', 'o': t.get('operator') or ''}})
        elif t.get('power') == 'substation' and v >= 50:
            if e['type'] == 'node': x, y = e['lon'], e['lat']
            elif e.get('geometry'): xs = [q['lon'] for q in e['geometry']]; ys = [q['lat'] for q in e['geometry']]; x, y = sum(xs) / len(xs), sum(ys) / len(ys)
            else: continue
            if not zone.contains(Point(rd(x, y))): continue
            if not t.get('name') or t.get('name','').startswith('MVK'): continue   # naamloze of klantstations overslaan
            stations.append([round(x, 5), round(y, 5), v, t.get('name') or '', t.get('operator') or ''])
    for e in opw:
        t = e.get('tags', {})
        c = (e['lon'], e['lat']) if e['type'] == 'node' else ((e.get('center') or {}).get('lon'), (e.get('center') or {}).get('lat'))
        if c[0] is None or not zone.contains(Point(rd(*c))): continue
        if (t.get('generator:source') or t.get('plant:source')) == 'wind':
            wind.append([round(c[0], 5), round(c[1], 5), t.get('name') or '', t.get('operator') or '', t.get('generator:output:electricity') or t.get('plant:output:electricity') or ''])
        else:
            zon.append([round(c[0], 5), round(c[1], 5), t.get('name') or '', t.get('operator') or '', t.get('plant:output:electricity') or t.get('generator:output:electricity') or ''])
    schrijf('energie', {'bron': 'OpenStreetMap-bijdragers (hoogspanning ≥ 50 kV, stations, windturbines, zonneparken)', 'opgehaald': time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(P('bron-downloads', 'osm-energie-net.json')))),
                        'lijnen': {'type': 'FeatureCollection', 'features': lijnen}, 'stations': stations, 'wind': wind, 'zon': zon})
    print('   lijnen', len(lijnen), collections.Counter(f['properties']['kv'] for f in lijnen), '| stations', len(stations), '| wind', len(wind), '| zon', len(zon))
    print('   ', [s[3] + f' ({s[2]} kV)' for s in stations])


# ---------- 4. Veenweide en bodem (provinciale WMS) ----------
ZH = 'https://geodata.zuid-holland.nl/geoserver'
BODEM = [  # (sleutel, werkruimte, laag, naam, uitleg, dekking)
    ('grondsoort', 'bodem', 'BODEMKUNDIGE_GRONDSOORTEN', 'Grondsoort', 'Welke grond er in de bovenste meter zit: veen, klei op veen, klei of zand (Bodemkundige grondsoortenkaart Zuid-Holland, 2025).', .6),
    ('veenoxidatie', 'bodem', 'SK_BODEMDALING_VEENOXIDATIE', 'Gevoelig voor veenoxidatie', 'Waar veen in contact met lucht komt en verdwijnt, met bodemdaling en CO₂-uitstoot als gevolg (signaleringskaart van de provincie).', .6),
    ('kleidek', 'bodem', 'BB_DEKLAAG_DIKTE', 'Dikte kleidek op veen', 'Hoe dik de kleilaag boven het veen is. Een dun kleidek betekent meer kans op veenoxidatie en bodemdaling.', .6),
    ('veenweide', 'omgevingsbeleid', 'VEENWEIDEN', 'Veenweidegebied (provinciaal beleid)', 'Het veenweidegebied waarvoor de provincie in het omgevingsbeleid een aanpak tegen bodemdaling heeft.', .45),
]
def bodem():
    def maak():
        leg = {}
        for k, ws, laag, *_ in BODEM:
            png = haal(f'{ZH}/{ws}/wms?service=WMS&version=1.3.0&request=GetLegendGraphic&format=image/png&width=16&height=16&layer={ws}:{laag}&LEGEND_OPTIONS=fontAntiAliasing:true;fontName:Arial')
            leg[k] = 'data:image/png;base64,' + base64.b64encode(png).decode()
        # grondsoort: 23 klassen, in de kaart samengevat in hoofdgroepen
        js = json.loads(haal(f'{ZH}/bodem/wms?service=WMS&version=1.3.0&request=GetLegendGraphic&format=application/json&layer=bodem:BODEMKUNDIGE_GRONDSOORTEN'))
        leg['grondsoort_klassen'] = [[r.get('title') or r.get('name'), r['symbolizers'][0]['Polygon']['fill']] for r in js['Legend'][0]['rules']]
        return {'legenda': leg}
    d = bron('zh-bodemkaarten-legenda-v2', maak)
    def groep(n):
        n = n.lower()
        if any(w in n for w in ['veen', 'riet', 'zegge', 'broek', 'gyttja']): return 'Veen'
        if 'zand' in n: return 'Zand'
        if 'klei' in n or 'zavel' in n: return 'Klei en zavel'
        return 'Overig'
    groepen = {}
    for n, c in d['legenda']['grondsoort_klassen']:
        groepen.setdefault(groep(n), []).append([n, c])
    schrijf('bodem', {'bron': 'Provincie Zuid-Holland (geodata.zuid-holland.nl)', 'opgehaald': d['opgehaald'],
                      'lagen': [{'k': k, 'wms': f'{ZH}/{ws}/wms', 'laag': f'{ws}:{laag}', 'naam': n, 'uitleg': u, 'op': o, 'legenda': d['legenda'][k], **({'groepen': [[g, groepen[g]] for g in ['Veen', 'Klei en zavel', 'Zand', 'Overig'] if g in groepen]} if k == 'grondsoort' else {})} for k, ws, laag, n, u, o in BODEM]})


ONDERDELEN = {'indelingen': indelingen, 'bedrijven': bedrijven, 'energie': energie, 'bodem': bodem}
for naam, fn in ONDERDELEN.items():
    if not WEL or naam in WEL:
        print('==', naam); fn()
