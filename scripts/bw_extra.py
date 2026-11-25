"""Extra indicatoren voor de brede-welvaartsthermometer (25-11-2026): de 'ontbreekt nog'-lijst zo ver mogelijk aangevuld.

Per gemeente (alle gemeenten van Nederland, voor de drempels) en waar het kan per buurt (voor de kaart):
  soc_vermogen      Mediaan vermogen van particuliere huishoudens (x 1.000 euro)  CBS KWB 2024 (85984NED)     buurt + gemeente
  soc_ao_per_1000   Personen met een arbeidsongeschiktheidsuitkering per 1.000 inw  CBS KWB 2025 (86165NED)     buurt + gemeente
  ggd_broos65       Broze gezondheid bij 65-plussers (%)                          GGD/RIVM 2024 (50150NED, 65+) buurt + gemeente
  vsv_pct           Voortijdig schoolverlaters (%) naar woongemeente              CBS 84780NED, schooljaar 2024/'25  gemeente
  woonwerk_km       Gemiddelde woon-werkafstand van werknemers (km)               CBS 85481NED, december 2024   gemeente
  groen_m2          Groen per inwoner (m²): natuur, bos, stedelijk groen, dagrecreatie  CBS Bodemgebruik 2022 (86211NED) gemeente
  onveilig_pct      Voelt zich weleens onveilig (%)                               CBS Veiligheidsbeleving 2025 (86347NED)  alleen Gouda, ZH, NL
Niet gevonden als open cijfer per gemeente: luchtkwaliteit, tevredenheid met het leven, deelname aan onderwijs, reistijd naar banen.

Uitvoer: data/bwextra.json (in de pagina: buurt, gebied, ref) en data/afgeleid/bwextra_gemeenten.json (alle gemeenten).
Ruwe downloads: bron-downloads/bw-extra-2026.json.gz.  Gebruik: .venv/bin/python scripts/bw_extra.py [--opnieuw]
"""
import json, os, sys, gzip, time, subprocess, urllib.parse
from shapely.geometry import shape
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
GMS = ['GM0513', 'GM1892', 'GM1901', 'GM1931', 'GM0627']
OPNIEUW = '--opnieuw' in sys.argv
getal = lambda v: v if isinstance(v, (int, float)) and v > -99990 else None

def haal(url):
    for i in range(4):
        r = subprocess.run(['curl', '-s', '-f', '--max-time', '180', '-A', 'regiokaart-midden-holland/1.0', url], capture_output=True)
        if r.returncode == 0: return json.loads(r.stdout)
        time.sleep(3 + 4 * i)
    raise RuntimeError('ophalen mislukt: ' + url[:140])
def odata(basis, tabel, flt, select=None):
    q = {'$format': 'json', '$filter': flt}
    if select: q['$select'] = ','.join(select)
    rows, url = [], f'{basis}/{tabel}/TypedDataSet?' + urllib.parse.urlencode(q)
    while url:
        d = haal(url); rows += d['value']; url = d.get('odata.nextLink')
    return rows
OD, DD = 'https://opendata.cbs.nl/ODataApi/odata', 'https://dataderden.cbs.nl/ODataApi/odata'
BU = ' or '.join(f"startswith(WijkenEnBuurten,'BU{g[2:]}')" for g in GMS)

pad = P('bron-downloads', 'bw-extra-2026.json.gz')
if OPNIEUW or not os.path.exists(pad):
    print('ophalen…')
    ruw = {
      'vsv': odata(OD, '84780NED', "Geslacht eq 'T001038' and Perioden eq '2024SJ00'", ['Regiokenmerken', 'Leerlingen_1', 'VoortijdigSchoolverlaters_2', 'VoortijdigSchoolverlatersPercentage_4']),
      'woonwerk': odata(OD, '85481NED', "WerkregioS eq 'NL01  ' and Perioden eq '2024MM12'", ['WoonregioS', 'BanenVanWerknemers_1', 'WoonWerkafstand_2']),
      'bodem': odata(OD, '86211NED', "startswith(AlleRegioIndelingen,'GM') or startswith(AlleRegioIndelingen,'NL')",
                     ['AlleRegioIndelingen', 'TotaalLand_5', 'StedelijkGroen_28', 'DagrecreatiefTerrein_31', 'TotaalNatuurlijkTerrein_38']),
      'onveilig': odata(OD, '86347NED', "Perioden eq '2025JJ00' and Marges eq 'MW00000'", ['RegioS', 'VoeltZichWeleensOnveilig_1']),
      'broos': odata(DD, '50150NED', f"(startswith(WijkenEnBuurten,'GM') or startswith(WijkenEnBuurten,'NL') or {BU}) and Perioden eq '2024JJ00' and Leeftijd eq '80200' and Marges eq 'MW00000'",
                     ['WijkenEnBuurten', 'BrozeGezondheid_18']),
    }
    ruw['opgehaald'] = time.strftime('%Y-%m-%d')
    json.dump(ruw, gzip.open(pad, 'wt'), ensure_ascii=False)
ruw = json.load(gzip.open(pad, 'rt'))
code = lambda c: c.strip()

# ---------- per gemeente (en NL) ----------
kwb24 = {code(r['WijkenEnBuurten']): r for r in json.load(gzip.open(P('bron-downloads', 'cbs-kwb-85984NED-regio-en-gemeenten.json.gz'), 'rt'))['rijen']}
kwb25 = {code(r['WijkenEnBuurten']): r for r in json.load(gzip.open(P('bron-downloads', 'cbs-kwb-86165NED-regio-en-gemeenten.json.gz'), 'rt'))['rijen']}
nlof = json.load(gzip.open(P('bron-downloads', 'cbs-nederland-officieel.json.gz'), 'rt'))
kwb24['NL'] = nlof['85984NED'][0]; kwb25['NL'] = nlof['86165NED'][0]
gm = {}
def zet(c, k, v):
    c = 'NL' if c.startswith('NL') else c
    if v is not None and (c.startswith('GM') or c == 'NL'): gm.setdefault(c, {})[k] = v
for c, r in kwb24.items():
    zet(c, 'soc_vermogen', getal(r.get('MediaanVermogenVanParticuliereHuish_86'))); zet(c, 'bw_hh24', getal(r.get('HuishoudensTotaal_29')))
for c, r in kwb25.items():
    ao, inw = getal(r.get('PersonenPerSoortUitkeringAO_88')), getal(r.get('AantalInwoners_5'))
    zet(c, 'bw_ao_n', ao); zet(c, 'bw_inw25', inw); zet(c, 'bw_65', getal(r.get('k_65JaarOfOuder_12')))
    if ao is not None and inw: zet(c, 'soc_ao_per_1000', ao / inw * 1000)
for r in ruw['vsv']:
    c = code(r['Regiokenmerken']); n, l = getal(r['VoortijdigSchoolverlaters_2']), getal(r['Leerlingen_1'])
    zet(c, 'bw_vsv_n', n); zet(c, 'bw_leerl', l)
    zet(c, 'vsv_pct', n / l * 100 if n is not None and l else getal(r['VoortijdigSchoolverlatersPercentage_4']))   # uit de aantallen: het CBS-percentage is afgerond
for r in ruw['woonwerk']:
    c = code(r['WoonregioS']); zet(c, 'woonwerk_km', getal(r['WoonWerkafstand_2'])); zet(c, 'bw_banen', getal(r['BanenVanWerknemers_1']))
for r in ruw['bodem']:
    c = code(r['AlleRegioIndelingen']); g = sum(getal(r.get(k)) or 0 for k in ['StedelijkGroen_28', 'DagrecreatiefTerrein_31', 'TotaalNatuurlijkTerrein_38'])
    zet(c, 'bw_groen_ha', g)
for c, x in gm.items():   # groen per inwoner: oppervlakte 2022, inwoners 2025 (zelfde gemeente-indeling als de bodemkaart, anders geen waarde)
    if x.get('bw_groen_ha') is not None and x.get('bw_inw25'): x['groen_m2'] = x['bw_groen_ha'] * 10000 / x['bw_inw25']
for r in ruw['onveilig']:
    zet(code(r['RegioS']), 'onveilig_pct', getal(r['VoeltZichWeleensOnveilig_1']))
pv = {code(r['RegioS']): getal(r['VoeltZichWeleensOnveilig_1']) for r in ruw['onveilig']}
for r in ruw['broos']:
    zet(code(r['WijkenEnBuurten']), 'ggd_broos65', getal(r['BrozeGezondheid_18']))

# ---------- regels voor regio, Zuid-Holland en Nederland (uit de gemeentecijfers) ----------
REGELS = {'soc_vermogen': ('w', 'bw_hh24'), 'soc_ao_per_1000': ('ratio', 'bw_ao_n', 'bw_inw25', 1000), 'ggd_broos65': ('w', 'bw_65'),
          'vsv_pct': ('ratio', 'bw_vsv_n', 'bw_leerl', 100), 'woonwerk_km': ('w', 'bw_banen'), 'groen_m2': ('ratio', 'bw_groen_ha', 'bw_inw25', 10000)}
def agg(rijen):
    out = {}
    for k, rg in REGELS.items():
        if rg[0] == 'w':
            a = sum(x[k] * x[rg[1]] for x in rijen if x.get(k) is not None and x.get(rg[1])); b = sum(x[rg[1]] for x in rijen if x.get(k) is not None and x.get(rg[1]))
        else:
            a = sum(x[rg[1]] for x in rijen if x.get(rg[1]) is not None and x.get(rg[2])) * rg[3]; b = sum(x[rg[2]] for x in rijen if x.get(rg[1]) is not None and x.get(rg[2]))
        out[k] = a / b if b else None
    return out
prov = [f for f in json.load(open(P('data', 'provincie_2024.geojson')))['features'] if f['properties']['statnaam'] == 'Zuid-Holland'][0]
ZH = shape(prov['geometry']).buffer(0)
zh = {f['properties']['gemeentecode'] for f in json.load(open(P('bron-downloads', 'cbs-gemeenten-2024-nederland.geojson')))['features']
      if f['properties'].get('water') == 'NEE' and ZH.contains(shape(f['geometry']).representative_point())}
alle = {c: x for c, x in gm.items() if c.startswith('GM')}
gebied = {c: {k: alle.get(c, {}).get(k) for k in list(REGELS) + ['onveilig_pct']} for c in GMS}
gebied['regio'] = agg([alle[c] for c in GMS if c in alle])
ref = {'zh': agg([x for c, x in alle.items() if c in zh]), 'nl': agg(list(alle.values()))}
# officieel Nederland waar de bron het heeft
for k in ['vsv_pct', 'woonwerk_km', 'ggd_broos65', 'soc_vermogen']:
    if gm.get('NL', {}).get(k) is not None: ref['nl'][k] = gm['NL'][k]
ref['nl']['onveilig_pct'] = pv.get('NL01'); ref['zh']['onveilig_pct'] = pv.get('PV28')

# ---------- per buurt (voor de kaart) ----------
buurten = {f['properties']['buurtcode']: f['properties'] for f in json.load(open(P('data', 'buurten.json')))['features']}
buurt = {}
for c in buurten:
    x = {}
    r24, r25 = kwb24.get(c, {}), kwb25.get(c, {})
    if getal(r24.get('MediaanVermogenVanParticuliereHuish_86')) is not None: x['soc_vermogen'] = r24['MediaanVermogenVanParticuliereHuish_86']; x['bw_hh24'] = getal(r24.get('HuishoudensTotaal_29'))
    ao, inw = getal(r25.get('PersonenPerSoortUitkeringAO_88')), getal(r25.get('AantalInwoners_5'))
    if ao is not None and inw and inw >= 100: x['soc_ao_per_1000'] = ao / inw * 1000; x['bw_ao_n'] = ao; x['bw_inw25'] = inw
    x['bw_65'] = getal(r25.get('k_65JaarOfOuder_12'))
    if x: buurt[c] = {k: v for k, v in x.items() if v is not None}
for r in ruw['broos']:
    c = code(r['WijkenEnBuurten'])
    if c in buurten and getal(r['BrozeGezondheid_18']) is not None: buurt.setdefault(c, {})['ggd_broos65'] = r['BrozeGezondheid_18']

json.dump({'bron': 'CBS (KWB 2024 en 2025, voortijdig schoolverlaten, woon-werkafstand, bodemgebruik, veiligheidsbeleving) en GGD/RIVM', 'opgehaald': ruw['opgehaald'],
           'buurt': buurt, 'gebied': gebied, 'ref': ref}, open(P('data', 'bwextra.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(alle, open(P('data', 'afgeleid', 'bwextra_gemeenten.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('gemeenten:', len(alle), '| buurten:', len(buurt))
for k in list(REGELS) + ['onveilig_pct']:
    n = sum(1 for x in alle.values() if x.get(k) is not None)
    print(f'{k:18} n={n:3}', {c[2:]: (round(gebied[c][k], 1) if gebied[c].get(k) is not None else None) for c in GMS + ['regio']}, 'ZH', ref['zh'].get(k) and round(ref['zh'][k], 1), 'NL', ref['nl'].get(k) and round(ref['nl'][k], 1))
