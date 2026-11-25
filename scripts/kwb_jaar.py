"""Buurtcijfers naar het nieuwste CBS-jaar (sinds 17-11-2026: 2025, met 2024 waar 2025 nog leeg is).

Het CBS vult de Kerncijfers Wijken en Buurten per jaargang in stappen (eerst bevolking, later inkomen en zorg).
Dit script kiest daarom per kenmerk het nieuwste jaar dat in de regio gevuld is, en valt anders terug op het jaar ervoor.

Bronnen (eenmalig opgehaald, bewaard in bron-downloads/):
  - CBS OData Kerncijfers wijken en buurten NIEUW (86165NED = 2025) en VORIG (85984NED = 2024): buurten van de regio,
    alle gemeenten (voor Zuid-Holland en Nederland)
  - PDOK wijken-en-buurten-NIEUW: buurtgrenzen en namen (de buurtindeling van het nieuwe jaar)
De veldnamen in de kaart zijn die van de PDOK-bestanden 2024 (bijv. 'percentage_koopwoningen'). De koppeling naar de
CBS-tabellen wordt automatisch gelegd door de waarden van 2024 in beide bronnen te vergelijken.

Uitvoer: data/buurten.json (nieuwe indeling), data/kwb_jaar.json (jaar per kenmerk), en via ref.py data/ref.json.
Grenzen: buurten die niet veranderd zijn houden hun bestaande vereenvoudigde grens; nieuwe of gewijzigde buurten
krijgen de grens uit PDOK, licht vereenvoudigd.

Gebruik (vanuit de projectmap): .venv/bin/python scripts/kwb_jaar.py [--opnieuw]
"""
import json, os, sys, gzip, time, subprocess, urllib.request, urllib.parse, collections
import shapely
from shapely.geometry import shape, mapping
from shapely.ops import transform
from pyproj import Transformer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maak_data import BRON, DATA, REGIO, keep_list, buurt_props

NIEUW, VORIG = (2025, '86165NED'), (2024, '85984NED')
GMS = ['0513', '1892', '1901', '1931', '0627']
OPNIEUW = '--opnieuw' in sys.argv
UA = {'User-Agent': 'regiokaart-midden-holland/1.0'}
rd = Transformer.from_crs(4326, 28992, always_xy=True).transform
wgs = Transformer.from_crs(28992, 4326, always_xy=True).transform


def haal(url, timeout=180):
    for poging in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            r = subprocess.run(['curl', '-s', '-f', '--max-time', str(timeout), '-A', UA['User-Agent'], url], capture_output=True)
            if r.returncode == 0: return r.stdout
            print('   opnieuw proberen:', str(e)[:80]); time.sleep(3 + 5 * poging)
    raise RuntimeError('ophalen mislukt: ' + url[:120])


def bron(naam, maak):
    pad = os.path.join(BRON, naam + '.json.gz')
    if OPNIEUW or not os.path.exists(pad):
        d = maak(); d['opgehaald'] = time.strftime('%Y-%m-%d')
        json.dump(d, gzip.open(pad, 'wt'), ensure_ascii=False)
    return json.load(gzip.open(pad, 'rt'))


def odata(tabel):
    """buurten van de regio + alle gemeenten + Nederland, plus de onderwerpen (sleutel -> titel)"""
    def maak():
        props = json.loads(haal(f'https://opendata.cbs.nl/ODataApi/odata/{tabel}/DataProperties?$format=json'))['value']
        rijen = []
        for flt in [' or '.join(f"startswith(WijkenEnBuurten,'BU{g}')" for g in GMS), "startswith(WijkenEnBuurten,'GM') or startswith(WijkenEnBuurten,'NL')"]:
            url = f'https://opendata.cbs.nl/ODataApi/odata/{tabel}/TypedDataSet?' + urllib.parse.urlencode({'$format': 'json', '$filter': flt})
            while url:
                d = json.loads(haal(url)); rijen += d['value']; url = d.get('odata.nextLink')
        return {'props': [{'Key': p['Key'], 'Title': (p.get('Title') or '').strip(), 'Type': p.get('Type')} for p in props], 'rijen': rijen}
    d = bron(f'cbs-kwb-{tabel}-regio-en-gemeenten', maak)
    titels = {p['Key']: p['Title'] for p in d['props'] if p['Type'] == 'Topic'}
    rijen = {r['WijkenEnBuurten'].strip(): r for r in d['rijen']}
    return titels, rijen, d['opgehaald']


def pdok_gemeenten(jaar):
    def maak():
        feats, url = [], f'https://api.pdok.nl/cbs/wijken-en-buurten-{jaar}/ogc/v1/collections/gemeenten/items?f=json&limit=1000'
        while url:
            d = json.loads(haal(url)); feats += d['features']; url = next((l['href'] for l in d.get('links', []) if l['rel'] == 'next'), None)
        return {'props': [f['properties'] for f in feats]}
    return bron(f'pdok-gemeenten-{jaar}-nederland', maak)


def pdok_buurten(jaar):
    def maak():
        feats, url = [], f'https://api.pdok.nl/cbs/wijken-en-buurten-{jaar}/ogc/v1/collections/buurten/items?f=json&limit=1000&bbox=4.45,51.84,4.95,52.17'
        while url:
            d = json.loads(haal(url)); feats += d['features']; url = next((l['href'] for l in d.get('links', []) if l['rel'] == 'next'), None)
        return {'features': [f for f in feats if f['properties'].get('gemeentenaam') in REGIO]}
    return bron(f'pdok-buurten-{jaar}-regio', maak)


getal = lambda v: v if isinstance(v, (int, float)) and v > -99990 else None

# ---------- 1. gegevens ----------
t_nieuw, r_nieuw, opg_nieuw = odata(NIEUW[1])
t_vorig, r_vorig, opg_vorig = odata(VORIG[1])
pdok_vorig = json.load(open(os.path.join(BRON, 'cbs-buurten-2024-regio.geojson')))['features']
pdok_vorig = [f for f in pdok_vorig if f['properties']['gemeentenaam'] in REGIO]
pdok_nieuw = pdok_buurten(NIEUW[0])['features']
keep = keep_list(pdok_vorig[0]['properties'])
NAAM = {'buurtcode', 'buurtnaam', 'wijknaam', 'gemeentecode', 'gemeentenaam'}
cijfers = [k for k in keep if k not in NAAM]

# ---------- 2. koppeling PDOK-veld -> CBS-onderwerp (via de waarden van 2024) ----------
codes_v = [f['properties']['buurtcode'] for f in pdok_vorig]
koppel, niet = {}, []
for k in cijfers:
    best, score = None, 0
    pv = {c: getal(f['properties'].get(k)) for c, f in zip(codes_v, pdok_vorig)}
    n = sum(v is not None for v in pv.values())
    for key, titel in t_vorig.items():
        gelijk = sum(1 for c, v in pv.items() if v is not None and c in r_vorig and getal(r_vorig[c].get(key)) is not None and abs(getal(r_vorig[c][key]) - v) <= max(0.051, 0.006 * abs(v)))   # WOZ e.d. soms 1 verschil door afronding
        if gelijk > score: best, score = titel, gelijk
    if n and score >= 0.8 * n: koppel[k] = best   # 0,8: WOZ is bij ~1 op 5 buurten later door het CBS herzien
    else: niet.append((k, best, score, n))

# percentages die het CBS als aantallen publiceert: zelf uitrekenen (teller / noemer x 100, afgerond)
PCT = {'percentage_personen_0_tot_15_jaar': ('0 tot 15 jaar', 'Aantal inwoners'), 'percentage_personen_15_tot_25_jaar': ('15 tot 25 jaar', 'Aantal inwoners'),
       'percentage_personen_25_tot_45_jaar': ('25 tot 45 jaar', 'Aantal inwoners'), 'percentage_personen_45_tot_65_jaar': ('45 tot 65 jaar', 'Aantal inwoners'),
       'percentage_personen_65_jaar_en_ouder': ('65 jaar of ouder', 'Aantal inwoners'),
       'percentage_met_herkomstland_nederland': ('Nederland', 'Aantal inwoners'), 'percentage_met_herkomstland_uit_europa_excl_nl': ('Europa (exclusief Nederland)', 'Aantal inwoners'),
       'percentage_met_herkomstland_buiten_europa': ('Buiten Europa', 'Aantal inwoners'),
       'percentage_eenpersoonshuishoudens': ('Eenpersoonshuishoudens', 'Huishoudens totaal'), 'percentage_huishoudens_met_kinderen': ('Huishoudens met kinderen', 'Huishoudens totaal')}
def pct(rij, titels_sleutel, k, afronden=True):
    a, b = (getal(rij.get(titels_sleutel.get(x))) for x in PCT[k])
    return (round(a / b * 100) if afronden else a / b * 100) if a is not None and b else None
pct_ok = {}
for k in PCT:
    pv = {c: getal(f['properties'].get(k)) for c, f in zip(codes_v, pdok_vorig)}
    sv = {v: kk for kk, v in t_vorig.items()}
    paren = [(v, pct(r_vorig[c], sv, k)) for c, v in pv.items() if v is not None and c in r_vorig]
    goed = sum(1 for v, w in paren if w is not None and abs(v - w) <= 1.5)
    if paren and goed >= 0.97 * len(paren): pct_ok[k] = True   # CBS rondt aantallen af op 5: in kleine buurten wijkt het percentage dan af
niet = [x for x in niet if x[0] not in pct_ok]
print('zelf berekende percentages:', sorted(pct_ok))
if niet: print('BLIJFT 2024 (geen koppeling, bijv. afstanden uit de nabijheidsstatistiek):', [x[0] for x in niet])

sleutel_nieuw = {v: k for k, v in t_nieuw.items()}
sleutel_vorig = {v: k for k, v in t_vorig.items()}

# ---------- 3. per kenmerk het jaar kiezen ----------
# Eerste keus: PDOK nieuw jaar (exacte percentages, zelfde veldnamen); dan CBS-tabel nieuw jaar; anders het vorige jaar.
pn_rij = {f['properties']['buurtcode']: f['properties'] for f in pdok_nieuw}
pdok_ok = set()
for k in cijfers:
    nn = sum(getal(p.get(k)) is not None for p in pn_rij.values())
    nv = sum(getal(f['properties'].get(k)) is not None for f in pdok_vorig)
    if nv and nn >= 0.8 * nv: pdok_ok.add(k)
print('uit PDOK', NIEUW[0], ':', sorted(pdok_ok))
regio_b = lambda rijen: [r for c, r in rijen.items() if c.startswith('BU')]
jaar, bronkey = {}, {}
for k, titel in koppel.items():
    kn, kv = sleutel_nieuw.get(titel), sleutel_vorig[titel]
    nn = sum(getal(r.get(kn)) is not None for r in regio_b(r_nieuw)) if kn else 0
    nv = sum(getal(r.get(kv)) is not None for r in regio_b(r_vorig))
    if kn and nn >= 0.8 * nv: jaar[k], bronkey[k] = NIEUW[0], (r_nieuw, kn)
    else: jaar[k], bronkey[k] = VORIG[0], (r_vorig, kv)
for k in pct_ok:
    kn = PCT[k][0] in sleutel_nieuw and PCT[k][1] in sleutel_nieuw
    nn = sum(pct(r, sleutel_nieuw, k) is not None for r in regio_b(r_nieuw)) if kn else 0
    nv = sum(pct(r, sleutel_vorig, k) is not None for r in regio_b(r_vorig))
    jaar[k], bronkey[k] = (NIEUW[0], (r_nieuw, ('pct', sleutel_nieuw))) if nn >= 0.8 * nv else (VORIG[0], (r_vorig, ('pct', sleutel_vorig)))
for k in niet: jaar[k[0]] = VORIG[0]   # niet te koppelen: blijft de waarde uit PDOK 2024 (komt hieronder)
for k in pdok_ok: jaar[k] = NIEUW[0]
print('jaar per kenmerk:', collections.Counter(jaar.values()))
print('   nog', VORIG[0], ':', sorted(k for k, j in jaar.items() if j == VORIG[0]))

def waarde(rij, k):
    if not rij: return None
    b = bronkey[k][1]
    return pct(rij, b[1], k) if isinstance(b, tuple) else getal(rij.get(b))

# ---------- 4. buurten (nieuwe indeling) ----------
oud = {f['properties']['buurtcode']: f for f in json.load(open(os.path.join(DATA, 'buurten.json')))['features']}
ruw_v = {f['properties']['buurtcode']: f for f in pdok_vorig}
wijk_v = {c: f['properties'].get('wijknaam') for c, f in ruw_v.items()}
uit, veranderd = [], []
for f in sorted(pdok_nieuw, key=lambda f: f['properties']['buurtcode']):
    pn = f['properties']; c = pn['buurtcode']
    p = {'buurtcode': c, 'buurtnaam': pn.get('buurtnaam'), 'gemeentecode': pn.get('gemeentecode'), 'gemeentenaam': pn.get('gemeentenaam'),
         'wijknaam': pn.get('wijknaam') or wijk_v.get(c)}
    for k in cijfers:
        if k in pdok_ok:
            p[k] = getal(pn.get(k))
        elif k in bronkey:
            rij = bronkey[k][0].get(c); p[k] = waarde(rij, k)
        else:
            p[k] = getal((ruw_v.get(c) or {'properties': {}})['properties'].get(k))
    g_n = transform(rd, shape(f['geometry']).buffer(0))
    if c in oud and c in ruw_v and abs(transform(rd, shape(ruw_v[c]['geometry']).buffer(0)).area - g_n.area) <= 0.005 * g_n.area:
        geom = oud[c]['geometry']   # ongewijzigde buurt: bestaande vereenvoudigde grens houden
    else:
        veranderd.append(c); geom = mapping(shapely.set_precision(transform(wgs, g_n.simplify(4)), 0.00001))
    uit.append({'type': 'Feature', 'properties': buurt_props(p, keep), 'geometry': geom})
json.dump({'type': 'FeatureCollection', 'features': uit}, open(os.path.join(DATA, 'buurten.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
# nieuw of gewijzigd ten opzichte van het vorige CBS-jaar (niet ten opzichte van data/buurten.json, anders is een tweede run 'leeg')
nieuw_codes = [c for c in veranderd if c not in ruw_v]
print('buurten:', len(uit), '| nieuw:', nieuw_codes, '| andere grens:', [c for c in veranderd if c in ruw_v])

# jaar per kenmerk, ook voor de afgeleide kenmerken
afgeleid = {'bijstand_per_1000': 'aantal_personen_met_een_alg_bijstandsuitkering_tot', 'ww_per_1000': 'aantal_personen_met_een_ww_uitkering_totaal',
            'bedrijven_per_1000_inwoners': 'aantal_bedrijfsvestigingen', 'nieuwbouw_per_1000_woningen': 'aantal_nieuwbouw_woningen'}
for k, bronveld in afgeleid.items(): jaar[k] = jaar.get(bronveld, VORIG[0])
json.dump({'nieuw': NIEUW[0], 'vorig': VORIG[0], 'tabellen': {NIEUW[0]: NIEUW[1], VORIG[0]: VORIG[1]}, 'opgehaald': opg_nieuw,
           'aantal_buurten': len(uit), 'nieuwe_buurten': nieuw_codes, 'gewijzigde_buurten': [c for c in veranderd if c in ruw_v], 'jaar': jaar},
          open(os.path.join(DATA, 'kwb_jaar.json'), 'w'), ensure_ascii=False, separators=(',', ':'))

# ---------- 5. gemeenten (voor Zuid-Holland en Nederland) ----------
# titels komen in de CBS-tabel soms twee keer voor (bijv. 'Buiten Europa' bij herkomst én bij geboorteland): neem de eerste
eerste_nieuw, eerste_vorig = ({v: k for k, v in reversed(list(t.items()))} for t in (t_nieuw, t_vorig))
gm_nieuw = {q['gemeentecode']: q for q in pdok_gemeenten(NIEUW[0])['props'] if q.get('water') in (None, 'NEE')}
gem = json.load(open(os.path.join(BRON, 'cbs-gemeenten-2024-nederland.geojson')))
for f in gem['features']:
    p = f['properties']; c = p['gemeentecode']
    for k in cijfers:
        rij_j, sl_j = (r_nieuw, eerste_nieuw) if jaar.get(k) == NIEUW[0] else (r_vorig, eerste_vorig)
        if k in PCT and rij_j.get(c) and pct(rij_j[c], sl_j, k, afronden=False) is not None:
            # percentages per gemeente uit de CBS-aantallen, niet afgerond: PDOK rondt ze per gemeente af (herkomst zelfs op vijftallen)
            p[k] = pct(rij_j[c], sl_j, k, afronden=False)
        elif k in pdok_ok:
            p[k] = getal((gm_nieuw.get(c) or {}).get(k))
        elif k in bronkey:
            p[k] = waarde(bronkey[k][0].get(c), k)
    p.update({k: v for k, v in buurt_props(p, keep).items() if k in afgeleid})
json.dump(gem, open(os.path.join(DATA, 'gemeenten_kwb_mix.geojson'), 'w'))
# alle gemeenten zonder grenzen: voor de drempels van de brede-welvaartsthermometer (scripts/brede_welvaart.py; niet in de pagina)
os.makedirs(os.path.join(DATA, 'afgeleid'), exist_ok=True)
json.dump({f['properties']['gemeentecode']: {kk: f['properties'].get(kk) for kk in cijfers + list(afgeleid) + ['gemeentenaam', 'water']} for f in gem['features']},
          open(os.path.join(DATA, 'afgeleid', 'gemeenten_kwb.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ref.py'), 'gemeenten_kwb_mix.geojson'], cwd=DATA, check=True)
os.remove(os.path.join(DATA, 'gemeenten_kwb_mix.geojson'))
# Nederland: kenmerken die je niet kunt optellen over gemeenten (het CBS berekent ze per adres) uit de officiële NL-rij
NIET_OPTELBAAR = {'omgevingsadressendichtheid': 'Omgevingsadressendichtheid'}
ref = json.load(open(os.path.join(DATA, 'ref.json')))
nl_rij = next((r for c, r in r_nieuw.items() if c.startswith('NL')), None)
for k, titel in NIET_OPTELBAAR.items():
    v = getal(nl_rij.get(eerste_nieuw.get(titel))) if nl_rij else None
    if v is not None: ref['nl'][k] = v; print('Nederland officieel:', k, v)
json.dump(ref, open(os.path.join(DATA, 'ref.json'), 'w'), indent=1)
