"""Extra gegevens (8-11-2026): bevolkingsprognose, klimaat, sociaal domein, Leefbaarometer, reistijden, verkeersongevallen.

Elke bron wordt één keer opgehaald en als ruwe download bewaard in bron-downloads/ (gzip).
Met --opnieuw wordt alles opnieuw opgehaald; met een naam (bijv. `prognose`) alleen dat onderdeel.

Uitvoer (data/):
  prognose.json      CBS/PBL Regionale prognose 2023-2050 (85173NED): inwoners per gemeente, ZH en NL, met 67%-interval
  klimaat.json       lagen uit de Klimaateffectatlas (WMS) met legenda als data-URI
  sociaal.json       CBS sociaal domein per buurt (2024, inkomen 2023) + Zuid-Holland en Nederland
  leefbaarometer.json  Leefbaarometer 2024 per buurt (Provincie Zuid-Holland, WFS)
  reistijd.json      reistijd per buurt naar station, ziekenhuis, middelbare school (OSRM, OpenStreetMap)
  ongevallen.json    verkeersongevallen met letsel of doden 2022-2024 (BRON, Rijkswaterstaat WFS)

Gebruik (vanuit de projectmap): .venv/bin/python scripts/extra_data.py [--opnieuw] [onderdeel ...]
"""
import json, os, sys, gzip, time, base64, subprocess, urllib.request, urllib.parse
from shapely.geometry import shape, Point
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
UA = {'User-Agent': 'regiokaart-midden-holland/1.0'}
GMS = ['1901', '0513', '1931', '0627', '1892']
OPNIEUW = '--opnieuw' in sys.argv
WEL = [a for a in sys.argv[1:] if not a.startswith('--')]


def haal(url, timeout=180):
    for poging in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if 'SSL' in str(e):   # oude SSL in de Python van macOS: via curl
                r = subprocess.run(['curl', '-s', '-f', '--max-time', str(timeout), '-A', UA['User-Agent'], url], capture_output=True)
                if r.returncode == 0: return r.stdout
            print('   opnieuw proberen:', str(e)[:80]); time.sleep(3 + 5 * poging)
    raise RuntimeError('ophalen mislukt: ' + url[:120])


def bron(naam, maak):
    """ruwe download in bron-downloads/<naam>.json.gz (alleen ophalen als die er nog niet is)"""
    pad = P('bron-downloads', naam + '.json.gz')
    if OPNIEUW or not os.path.exists(pad):
        d = maak(); d['opgehaald'] = time.strftime('%Y-%m-%d')
        json.dump(d, gzip.open(pad, 'wt'), ensure_ascii=False)
    return json.load(gzip.open(pad, 'rt'))


def schrijf(naam, d):
    json.dump(d, open(P('data', naam + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'  data/{naam}.json', round(os.path.getsize(P('data', naam + '.json')) / 1e3), 'kB')


def odata(tabel, velden, flt):
    q = urllib.parse.urlencode({'$format': 'json', '$select': ','.join(velden), '$filter': flt})
    rows, url = [], f'https://opendata.cbs.nl/ODataApi/odata/{tabel}/TypedDataSet?{q}'
    while url:
        d = json.loads(haal(url)); rows += d['value']; url = d.get('odata.nextLink')
    return rows


buurten = json.load(open(P('data', 'buurten.json')))['features']
BP = {f['properties']['buurtcode']: f['properties'] for f in buurten}
cl = lambda v: v if isinstance(v, (int, float)) and v >= 0 else None


# ---------- 4. Bevolkingsprognose ----------
def prognose():
    def maak():
        regs = [f'GM{g}' for g in GMS] + ['PV28', 'NL01']
        flt = '(' + ' or '.join(f"startswith(RegioIndeling2021,'{r}')" for r in regs) + ')'   # codes zijn opgevuld met spaties
        return {'rijen': odata('85173NED', ['RegioIndeling2021', 'PrognoseInterval', 'Perioden', 'TotaleBevolking_1'], flt)}
    d = bron('cbs-prognose-2023-2050', maak)
    out = {}
    for r in d['rijen']:
        reg = r['RegioIndeling2021'].strip(); jaar = int(r['Perioden'][:4]); v = r['TotaleBevolking_1']
        if v is None: continue
        soort = {'MW00000': 'p', 'MOG0067': 'laag', 'MBG0067': 'hoog'}[r['PrognoseInterval'].strip()]
        out.setdefault(reg, {}).setdefault(soort, {})[jaar] = round(v * 1000)   # CBS geeft x 1.000 inwoners (1 decimaal)
    regio = {s: {j: sum(out[f'GM{g}'][s][j] for g in GMS) for j in out['GM0513'][s]} for s in ['p', 'laag', 'hoog']}
    schrijf('prognose', {'bron': 'CBS/PBL Regionale prognose 2023-2050 (tabel 85173NED), prognose met 67%-interval', 'opgehaald': d['opgehaald'],
                         'gm': {k: v for k, v in out.items() if k.startswith('GM')}, 'regio': regio, 'zh': out['PV28'], 'nl': out['NL01']})
    print('   regio 2024 → 2030 → 2040:', regio['p'][2024], regio['p'][2030], regio['p'][2040])


# ---------- 5. Klimaat (Klimaateffectatlas, WMS) ----------
KEA = 'https://cas.cloud.sogelink.com/public/data/org/gws/YWFMLMWERURF/kea_public'
KLIMAAT = [
    ('hitte', 'gevoelstemperatuur_2022', 'Hitte: gevoelstemperatuur', 'Gevoelstemperatuur op een hete zomerdag (ca. 30 °C luchttemperatuur), op basis van 2022. Hoe donkerder, hoe meer hittestress.', .6),
    ('water', 'nl_fcab_omgevingsscore_wateroverlast_v20260806', 'Wateroverlast bij hevige regen', 'Hoe groot de kans is op hinderlijk water rond gebouwen bij een flinke wolkbreuk. Zoom in om de gebouwen te zien.', .8),
    ('overstroming', 'maximale_waterdiepte_nederland_kleine_kans_20260128', 'Overstromingsdiepte', 'Maximale waterdiepte als een dijk doorbreekt, bij een kleine kans (ca. 1 op 1.000 per jaar). Laat zien hoe diep het kan worden, niet hoe waarschijnlijk.', .55),
    ('bodemdaling', 'bodemdaling_2020_2050hoog', 'Bodemdaling 2020–2050', 'Verwachte bodemdaling tussen 2020 en 2050 bij een hoog klimaatscenario. Belangrijk voor de veenweide in het Groene Hart.', .6),
]
def klimaat():
    def maak():
        leg = {}
        for k, laag, *_ in KLIMAAT:
            png = haal(f'{KEA}/ows?service=WMS&version=1.3.0&request=GetLegendGraphic&format=image/png&width=16&height=16&layer={laag}')
            leg[k] = 'data:image/png;base64,' + base64.b64encode(png).decode()
        return {'legenda': leg}
    d = bron('klimaateffectatlas-legenda', maak)
    schrijf('klimaat', {'wms': KEA + '/wms', 'bron': 'Klimaateffectatlas (Climate Adaptation Services)', 'opgehaald': d['opgehaald'],
                        'lagen': [{'k': k, 'laag': l, 'naam': n, 'uitleg': u, 'op': o, 'legenda': d['legenda'][k]} for k, l, n, u, o in KLIMAAT]})


# ---------- 6. Sociaal domein (CBS) ----------
SOC24, SOC23 = '85984NED', '85618NED'
def sociaal():
    v24 = ['WijkenEnBuurten', 'AantalInwoners_5', 'k_0Tot15Jaar_8', 'WmoClienten_93', 'WmoClientenRelatief_94', 'JongerenMetJeugdzorgInNatura_91',
           'PercentageJongerenJeugdzorgInNatura_92', 'PersonenInArmoede_81']
    v23 = ['WijkenEnBuurten', 'AantalInwoners_5', 'HuishoudensTotaal_29', 'HuishoudensMetEenLaagInkomen_87', 'GemiddeldInkomenPerInwoner_81']
    def maak():
        fb = ' or '.join(f"startswith(WijkenEnBuurten,'BU{g}')" for g in GMS)
        fg = "startswith(WijkenEnBuurten,'GM') or WijkenEnBuurten eq 'NL01'"
        return {'b24': odata(SOC24, v24, fb), 'b23': odata(SOC23, v23, fb), 'g24': odata(SOC24, v24, fg), 'g23': odata(SOC23, v23, fg)}
    d = bron('cbs-sociaal-2023-2024', maak)
    def per_code(rows):
        return {r['WijkenEnBuurten'].strip(): {k: (None if isinstance(v, (int, float)) and v < 0 else v) for k, v in r.items()} for r in rows}
    b24, b23, g24, g23 = map(per_code, (d['b24'], d['b23'], d['g24'], d['g23']))
    def rij(a, b):
        """eigen sleutels; aantallen meegenomen zodat gemeente-, regio-, ZH- en NL-waarden op dezelfde manier worden berekend"""
        a = a or {}; b = b or {}; inw = a.get('AantalInwoners_5'); k15 = a.get('k_0Tot15Jaar_8')
        return {'soc_wmo_per_1000': a.get('WmoClientenRelatief_94'), 'soc_wmo_n': a.get('WmoClienten_93'),
                'soc_jeugdzorg_pct': a.get('PercentageJongerenJeugdzorgInNatura_92'), 'soc_jeugd_w': k15,
                'soc_armoede_pct': a.get('PersonenInArmoede_81'),
                'soc_laag_inkomen_pct': b.get('HuishoudensMetEenLaagInkomen_87'), 'soc_hh23': b.get('HuishoudensTotaal_29'),
                'soc_inkomen_inw': b.get('GemiddeldInkomenPerInwoner_81'), 'soc_inw23': b.get('AantalInwoners_5'), 'soc_inw24': inw}
    buurt = {c: {k: v for k, v in rij(b24.get(c), b23.get(c)).items() if v is not None} for c in BP}
    # Zuid-Holland: gemeenten waarvan het middelpunt in de provincie ligt (zoals ref.py)
    prov = [f for f in json.load(open(P('data', 'provincie_2024.geojson')))['features'] if f['properties']['statnaam'] == 'Zuid-Holland'][0]
    ZH = shape(prov['geometry']).buffer(0)
    gem = json.load(open(P('bron-downloads', 'cbs-gemeenten-2024-nederland.geojson')))['features']
    zh = {f['properties']['gemeentecode'] for f in gem if f['properties'].get('water') == 'NEE' and ZH.contains(shape(f['geometry']).representative_point())}
    def agg(rijen):
        r = [x for x in rijen]
        def ratio(n, dn, m=1): a = sum(x[n] for x in r if x.get(n) is not None and x.get(dn)); b = sum(x[dn] for x in r if x.get(n) is not None and x.get(dn)); return a / b * m if b else None
        def w(k, wk): a = sum(x[k] * x[wk] for x in r if x.get(k) is not None and x.get(wk)); b = sum(x[wk] for x in r if x.get(k) is not None and x.get(wk)); return a / b if b else None
        return {'soc_wmo_per_1000': ratio('soc_wmo_n', 'soc_inw24', 1000), 'soc_jeugdzorg_pct': w('soc_jeugdzorg_pct', 'soc_jeugd_w'),
                'soc_armoede_pct': w('soc_armoede_pct', 'soc_inw24'), 'soc_laag_inkomen_pct': w('soc_laag_inkomen_pct', 'soc_hh23'),
                'soc_inkomen_inw': w('soc_inkomen_inw', 'soc_inw23')}
    gm_rij = {c: rij(g24.get(c), g23.get(c)) for c in g24 if c.startswith('GM')}
    ref = {'zh': agg([v for c, v in gm_rij.items() if c in zh]), 'nl': agg(gm_rij.values())}
    schrijf('sociaal', {'bron': f'CBS Kerncijfers wijken en buurten 2024 ({SOC24}); inkomen 2023 ({SOC23})', 'opgehaald': d['opgehaald'], 'buurt': buurt, 'ref': ref,
                        'aantal_zh_gemeenten': len(zh)})
    print('   buurten met Wmo:', sum('soc_wmo_per_1000' in b for b in buurt.values()), '| ZH-gemeenten', len(zh), '| ref', {k: round(v, 1) for k, v in ref['nl'].items() if v})


# ---------- 6. Leefbaarometer 2024 (Provincie Zuid-Holland) ----------
def leefbaarometer():
    def maak():
        u = ('https://geodata.zuid-holland.nl/geoserver/samenleving/wfs?service=WFS&version=2.0.0&request=GetFeature'
             '&typeNames=samenleving:GEZONDZH_LEEFBAARHEID_BUURT&outputFormat=application/json&srsName=EPSG:4326'
             '&propertyName=buurtcode,buurt_naam,jaar,afwijking_gem_NL,fysieke_omgeving,overlast_onveiligheid,sociale_samenhang,voorzieningen,woningvoorraad'
             '&bbox=51.84,4.47,52.17,4.95,urn:ogc:def:crs:EPSG::4326')
        return {'rijen': [f['properties'] for f in json.loads(haal(u))['features']]}
    d = bron('leefbaarometer-2024-zh', maak)
    K = {'afwijking_gem_NL': 'lbm_totaal', 'fysieke_omgeving': 'lbm_fysiek', 'overlast_onveiligheid': 'lbm_overlast',
         'sociale_samenhang': 'lbm_sociaal', 'voorzieningen': 'lbm_voorz', 'woningvoorraad': 'lbm_woning'}
    buurt = {}
    for r in d['rijen']:
        if r['buurtcode'] in BP:
            buurt[r['buurtcode']] = {K[k]: round(r[k], 4) for k in K if isinstance(r.get(k), (int, float))}
    jaar = sorted({r.get('jaar') for r in d['rijen']})
    schrijf('leefbaarometer', {'bron': 'Leefbaarometer (Rijksoverheid), via Provincie Zuid-Holland', 'jaar': jaar[-1], 'opgehaald': d['opgehaald'], 'buurt': buurt})
    print('   buurten:', len(buurt), 'van', len(BP), '| jaar', jaar)


# ---------- 7. Reistijden (OSRM, OpenStreetMap) ----------
def reistijd():
    loc = json.load(open(P('data', 'locaties.json')))['features']
    doelen = {'station': ('bike', 'station', 'Fietstijd naar treinstation'), 'ziekenhuis': ('car', 'ziekenhuis', 'Autotijd naar ziekenhuis'),
              'vo': ('bike', 'middelbaar', 'Fietstijd naar middelbare school')}
    herkomst = [(c, shape(f['geometry']).representative_point()) for c, f in ((f['properties']['buurtcode'], f) for f in buurten)]
    def maak():
        uit = {}
        for k, (profiel, soort, _) in doelen.items():
            dst = [f['geometry']['coordinates'] for f in loc if f['properties']['k'] == soort]
            # de openbare server rekent hooguit 100 punten per keer: herkomsten in stukjes
            stuk = max(10, 95 - len(dst)); mins = []
            for i in range(0, len(herkomst), stuk):
                pts = [(p.x, p.y) for _, p in herkomst[i:i + stuk]] + [tuple(x) for x in dst]; n = len(pts) - len(dst)
                coords = ';'.join(f'{x:.5f},{y:.5f}' for x, y in pts)
                u = (f'https://routing.openstreetmap.de/routed-{profiel}/table/v1/driving/{coords}?sources=' + ';'.join(map(str, range(n)))
                     + '&destinations=' + ';'.join(map(str, range(n, len(pts)))) + '&annotations=duration')
                r = json.loads(haal(u, 300)); assert r['code'] == 'Ok', r.get('message')
                mins += [min([t for t in rij if t is not None], default=None) for rij in r['durations']]
                time.sleep(1.5)
            uit[k] = {'n_doelen': len(dst), 'min': mins}
            print(f'   {k}: {len(dst)} bestemmingen, {len(mins)} buurten')
        return uit
    d = bron('osrm-reistijden', maak)
    buurt = {}
    for i, (c, _) in enumerate(herkomst):
        for k in doelen:
            s = d[k]['min'][i]
            if s is not None: buurt.setdefault(c, {})['rt_' + k] = round(s / 60, 1)
    schrijf('reistijd', {'bron': 'Routes over OpenStreetMap (OSRM, routing.openstreetmap.de); bestemmingen uit OpenStreetMap, ook tot 5 km buiten de regio',
                         'opgehaald': d['opgehaald'], 'buurt': buurt, 'doelen': {k: d[k]['n_doelen'] for k in doelen}})


# ---------- 7. Verkeersongevallen (BRON, Rijkswaterstaat) ----------
def ongevallen():
    namen = ['Bodegraven-Reeuwijk', 'Gouda', 'Krimpenerwaard', 'Waddinxveen', 'Zuidplas']
    def maak():
        flt = "verkeersongeval_afloop<>'Uitsluitend materiele schade' AND gemeente IN (" + ','.join(f"'{n}'" for n in namen) + ')'
        rows, start = [], 0
        while True:
            u = ('https://geo.rijkswaterstaat.nl/services/ogc/gdr/verkeersongevallen_nederland/ows?service=WFS&version=2.0.0&request=GetFeature'
                 '&typeNames=verkeersongevallen_nederland:ongevallen_2022_2024&outputFormat=application/json&srsName=EPSG:4326'
                 '&propertyName=shape,jaar_ongeval,verkeersongeval_afloop,aard_ongeval,partij_1_objecttype,partij_2_objecttype,straatnaam,woonplaats,gemeente,maximum_snelheid'
                 f'&count=1000&startIndex={start}&CQL_FILTER=' + urllib.parse.quote(flt))
            page = json.loads(haal(u))['features']; rows += page; start += len(page)
            print('   ongevallen opgehaald:', len(rows))
            if len(page) < 1000: return {'features': rows}
    d = bron('bron-ongevallen-2022-2024-regio', maak)
    regio = unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(P('data', 'gemeenten.json')))['features']])
    bshape = [(f['properties']['buurtcode'], shape(f['geometry']).buffer(0)) for f in buurten]
    pts, per_buurt = [], {}
    for f in d['features']:
        if not f.get('geometry'): continue
        x, y = f['geometry']['coordinates'][:2]; p = f['properties']; pt = Point(x, y)
        if not regio.contains(pt): continue
        dood = p['verkeersongeval_afloop'] == 'Dodelijk'
        pts.append([round(x, 5), round(y, 5), p['jaar_ongeval'], 1 if dood else 0, (p.get('aard_ongeval') or '').capitalize(),
                    ' / '.join(t for t in [p.get('partij_1_objecttype'), p.get('partij_2_objecttype')] if t), (p.get('straatnaam') or '').title(), p.get('maximum_snelheid')])
        c = next((c for c, g in bshape if g.contains(pt)), None)
        if c: per_buurt[c] = per_buurt.get(c, 0) + 1
    schrijf('ongevallen', {'bron': 'BRON, Rijkswaterstaat (ongevallen met letsel of doden, 2022–2024)', 'opgehaald': d['opgehaald'],
                           'punten': pts, 'buurt': per_buurt})
    print('   in de regio:', len(pts), '| dodelijk:', sum(p[3] for p in pts))


ONDERDELEN = {'prognose': prognose, 'klimaat': klimaat, 'sociaal': sociaal, 'leefbaarometer': leefbaarometer, 'reistijd': reistijd, 'ongevallen': ongevallen}
for naam, fn in ONDERDELEN.items():
    if not WEL or naam in WEL:
        print('==', naam); fn()
