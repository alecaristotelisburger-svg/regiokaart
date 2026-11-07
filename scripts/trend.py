"""Trend 2019 -> 2024: CBS Kerncijfers wijken en buurten 2019 (tabel 84583NED) naast de cijfers van 2024.

Per buurt: alleen als de buurt in 2019 dezelfde code had EN de landoppervlakte nauwelijks veranderde
(anders is de grens verschoven en zegt de verandering niets). Per gemeente en voor de regio: alle buurten
van 2019 opgeteld (de gemeentegrenzen zijn sinds 2015 niet veranderd), met dezelfde regels als data/spec.json.
Bedrijfsvestigingen doen niet mee: die stijgen 2019-2024 met ca. 50%, wat op een andere telwijze wijst.

Uitvoer data/trend.json:
  jaar:   2019
  ind:    lijst met indicatoren (sleutel van 2024, soort 'pct' = procentuele verandering of 'pp' = procentpunten)
  buurt:  {buurtcode: {sleutel: verandering}}   (alleen vergelijkbare buurten; ontbrekend = niet vergelijkbaar)
  gm:     {gemeentecode: {sleutel: waarde 2019}}
  regio:  {sleutel: waarde 2019}

Gebruik (vanuit de projectmap): .venv/bin/python scripts/trend.py [--opnieuw]
"""
import json, os, sys, gzip, time, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
TABEL = '84583NED'  # Kerncijfers wijken en buurten 2019
BRON = P('bron-downloads', 'cbs-kwb-2019-regio.json.gz')
GMS = ['0513', '1892', '1901', '1931', '0627']

# sleutel 2024 -> (soort, hoe uit 2019 te halen, aggregatie zoals in spec.json)
IND = {
    'aantal_inwoners':        ('pct', lambda r: r['AantalInwoners_5'], ('sum',)),
    'aantal_huishoudens':     ('pct', lambda r: r['HuishoudensTotaal_28'], ('sum',)),
    'woningvoorraad':         ('pct', lambda r: r['Woningvoorraad_34'], ('sum',)),
    'gemiddelde_woningwaarde': ('pct', lambda r: r['GemiddeldeWOZWaardeVanWoningen_35'], ('w', 'woningvoorraad')),
    'percentage_personen_0_tot_15_jaar':   ('pp', lambda r: deel(r['k_0Tot15Jaar_8'], r['AantalInwoners_5']), ('w', 'aantal_inwoners')),
    'percentage_personen_65_jaar_en_ouder': ('pp', lambda r: deel(r['k_65JaarOfOuder_12'], r['AantalInwoners_5']), ('w', 'aantal_inwoners')),
    'percentage_eenpersoonshuishoudens':   ('pp', lambda r: deel(r['Eenpersoonshuishoudens_29'], r['HuishoudensTotaal_28']), ('w', 'aantal_huishoudens')),
    'percentage_koopwoningen':             ('pp', lambda r: r['Koopwoningen_40'], ('w', 'woningvoorraad')),
    'perc_huurwoningen_in_bezit_woningcorporaties': ('pp', lambda r: r['InBezitWoningcorporatie_42'], ('w', 'woningvoorraad')),
}
# minimale basis per buurt, zodat kleine aantallen geen extreme percentages geven
MIN = {'aantal_inwoners': ('aantal_inwoners', 50), 'aantal_huishoudens': ('aantal_huishoudens', 25),
       'woningvoorraad': ('woningvoorraad', 25), 'gemiddelde_woningwaarde': ('woningvoorraad', 25),
       }
MIN_PP = ('aantal_inwoners', 100)
VELDEN = ['WijkenEnBuurten', 'SoortRegio_2', 'OppervlakteLand_111', 'AantalInwoners_5', 'HuishoudensTotaal_28',
          'Woningvoorraad_34', 'GemiddeldeWOZWaardeVanWoningen_35', 'BedrijfsvestigingenTotaal_91', 'k_0Tot15Jaar_8',
          'k_65JaarOfOuder_12', 'Eenpersoonshuishoudens_29', 'Koopwoningen_40', 'InBezitWoningcorporatie_42']


def deel(a, b):
    return a / b * 100 if a is not None and b else None


def haal():
    flt = ' or '.join(f"startswith(WijkenEnBuurten,'BU{g}') or WijkenEnBuurten eq 'GM{g}'" for g in GMS)
    q = urllib.parse.urlencode({'$format': 'json', '$select': ','.join(VELDEN), '$filter': flt})
    u = f'https://opendata.cbs.nl/ODataApi/odata/{TABEL}/TypedDataSet?{q}'
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'regiokaart-midden-holland/1.0'}), timeout=120) as r:
        return json.load(r)['value']


if '--opnieuw' in sys.argv or not os.path.exists(BRON):
    json.dump({'opgehaald': time.strftime('%Y-%m-%d'), 'tabel': TABEL, 'rijen': haal()}, gzip.open(BRON, 'wt'))
d = json.load(gzip.open(BRON, 'rt'))
rij = {}
for r in d['rijen']:
    r = {k: (None if isinstance(v, (int, float)) and v < 0 else v) for k, v in r.items()}
    rij[r['WijkenEnBuurten'].strip()] = r
b19 = {k: r for k, r in rij.items() if k.startswith('BU')}


def basis19(r):
    """2019-waarden onder de sleutels van 2024 (ook de gewichten)."""
    return {k: f(r) for k, (_, f, _) in IND.items()}


def agg(rows, key):
    soort = IND[key][2]
    if soort[0] == 'sum':
        vs = [x[key] for x in rows if x[key] is not None]
        return sum(vs) if vs else None
    s = w = 0
    for x in rows:
        v, ww = x[key], x[soort[1]]
        if v is not None and ww:
            s += v * ww; w += ww
    return s / w if w else None


rows19 = {g: [basis19(r) for k, r in b19.items() if k[2:6] == g] for g in GMS}
gm = {g: {k: agg(rows19[g], k) for k in IND} for g in GMS}
regio = {k: agg([x for g in GMS for x in rows19[g]], k) for k in IND}

buurt, niet = {}, []
for f in json.load(open(P('data', 'buurten.json')))['features']:
    p = f['properties']; code = p['buurtcode']; r = b19.get(code)
    a24, a19 = p.get('oppervlakte_land_in_ha'), (r or {}).get('OppervlakteLand_111')
    if not r or not a24 or not a19 or abs(a24 - a19) > max(2, 0.03 * a19):
        niet.append(code); continue
    v19 = basis19(r); out = {}
    for k, (soort, _, _) in IND.items():
        a, b = v19[k], p.get(k)
        if a is None or b is None or b < 0:
            continue
        if soort == 'pct':
            mk, mn = MIN[k]
            if (v19[mk] or 0) < mn or a <= 0:
                continue
            out[k] = round((b - a) / a * 100, 1)
        else:
            mk, mn = MIN_PP
            if (v19[mk] or 0) < mn or (p.get(mk) or 0) < mn:
                continue
            # CBS publiceert de aandelen van 2024 per buurt afgerond op hele procenten; rond 2019 net zo af,
            # zodat de verandering geen schijnnauwkeurigheid heeft (hele procentpunten)
            out[k] = round(b - round(a))
    buurt[code] = out

ind = [{'key': k, 'soort': s} for k, (s, _, _) in IND.items()]
json.dump({'jaar': 2019, 'tabel': TABEL, 'opgehaald': d['opgehaald'], 'ind': ind, 'buurt': buurt,
           'gm': {g: {k: (round(v, 3) if v is not None else None) for k, v in x.items()} for g, x in gm.items()},
           'regio': {k: (round(v, 3) if v is not None else None) for k, v in regio.items()}},
          open(P('data', 'trend.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(f'buurten vergelijkbaar met 2019: {len(buurt)} van {len(buurt) + len(niet)}')
print('regio 2019:', {k: round(v, 1) for k, v in regio.items() if v is not None})
for g in GMS:
    print(' ', g, 'inwoners 2019:', gm[g]['aantal_inwoners'], 'woningen:', gm[g]['woningvoorraad'])
