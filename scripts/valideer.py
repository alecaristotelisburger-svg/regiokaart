"""Datavalidatie: kloppen de cijfers op de kaart?

Vergelijkt de gemeentecijfers zoals de kaart ze laat zien (de JS rekent ze uit de buurten uit, net als in de pop-up,
Vergelijken en het gemeenteprofiel) met de cijfers die de bron zelf per gemeente publiceert. Het CBS rekent de
gemeentecijfers uit de microdata, dus dit is een onafhankelijke controle van:
  - het koppelen van de velden (juiste kolom, juist jaar),
  - het optellen en wegen van buurten (spec.json / aggregateFeats),
  - het effect van geheime buurtwaarden en afronding.
Daarnaast: Nederland zoals de kaart het berekent (som van alle gemeenten) tegen het officiële CBS-cijfer voor Nederland.

Gebruik: .venv/bin/python scripts/valideer.py        (bouw eerst de kaart; uitvoer: tests/uit/validatie.json + overzicht)
"""
import json, gzip, os, sys, collections
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
B = lambda n: json.load(gzip.open(P('bron-downloads', n + '.json.gz'), 'rt'))
GMS = {'GM0513': 'Gouda', 'GM1892': 'Zuidplas', 'GM1901': 'Bodegraven-Reeuwijk', 'GM1931': 'Krimpenerwaard', 'GM0627': 'Waddinxveen'}
getal = lambda v: v if isinstance(v, (int, float)) and v > -99990 else None
code = lambda r: (lambda c: 'NL' if c.startswith('NL') else c)(r['WijkenEnBuurten'].strip())

# ---------- 1. wat de kaart laat zien ----------
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto('file://' + P('regiokaart-midden-holland.html')); pg.wait_for_timeout(2500)
    kaart = pg.evaluate("""() => THEMES.filter(t=>!t.eigen).map(t=>({key:t.key, label:t.label, g:t.g, jaar:t.jaar||null, trend:!!t.trend,
        agg:t.agg||null, gm:Object.fromEntries(Object.keys(GM).map(c=>[c, t.trend ? trendWaarde(c, t.key.slice(3)) : gebiedWaarde(c, t, false)])),
        buurtsom:Object.fromEntries(Object.keys(GM).map(c=>[c, t.trend ? null : themeValue(gmFeats(c), t, false)])),
        regio: t.trend ? trendWaarde(null, t.key.slice(3)) : gebiedWaarde('regio', t, false),
        nl: DATA.ref && DATA.ref.nl ? (DATA.ref.nl[t.key] ?? null) : null, zh: DATA.ref && DATA.ref.zh ? (DATA.ref.zh[t.key] ?? null) : null,
        nb: buurten.features.filter(f=>{ const v=f.properties[t.key]; return v!=null && v>-99990; }).length}))""")
    totaal_buurten = pg.evaluate('buurten.features.length')
    b.close()
K = {t['key']: t for t in kaart}

# ---------- 2. officiële gemeentecijfers ----------
off = collections.defaultdict(dict)       # key -> {GMxxxx|NL01: waarde}
bronnaam = {}
kj = json.load(open(P('data', 'kwb_jaar.json')))
# 2a. KWB: PDOK-gemeenten (zelfde veldnamen) van het jaar dat de kaart gebruikt
pd25 = {p['gemeentecode']: p for p in B('pdok-gemeenten-2025-nederland')['props'] if p.get('gemeentecode') in GMS}
pd24 = {}
for f in json.load(open(P('bron-downloads', 'cbs-gemeenten-2024-nederland.geojson')))['features']:
    pr = f['properties']
    if pr.get('gemeentecode') in GMS and pr.get('water') == 'NEE': pd24[pr['gemeentecode']] = pr
NLOFF = B('cbs-nederland-officieel')
# 2b. KWB via CBS OData (voor velden die PDOK niet heeft, en voor Nederland): koppeling op titel
od = {2025: B('cbs-kwb-86165NED-regio-en-gemeenten'), 2024: B('cbs-kwb-85984NED-regio-en-gemeenten')}
od_rij = {j: {code(r): r for r in d['rijen'] + NLOFF[t]} for (j, d), t in zip(od.items(), ['86165NED', '85984NED'])}
od_titel = {j: {p['Key']: p['Title'] for p in d['props'] if p['Type'] == 'Topic'} for j, d in od.items()}
# koppel PDOK-veld -> OData-sleutel 2024 door de gemeentewaarden van 2024 te vergelijken (alle gemeenten van NL)
pd24_alle = {}
for f in json.load(open(P('bron-downloads', 'cbs-gemeenten-2024-nederland.geojson')))['features']:
    pr = f['properties']
    if pr.get('water') == 'NEE': pd24_alle[pr['gemeentecode']] = pr
gm24 = {c: r for c, r in od_rij[2024].items() if c.startswith('GM')}
koppel = {}
for k in kj['jaar']:
    pv = {c: getal(pr.get(k)) for c, pr in pd24_alle.items() if c in gm24}
    n = sum(v is not None for v in pv.values())
    best, score = None, 0
    for key in od_titel[2024]:
        s = sum(1 for c, v in pv.items() if v is not None and getal(gm24[c].get(key)) is not None and abs(getal(gm24[c][key]) - v) <= max(0.051, 0.006 * abs(v)))
        if s > score: best, score = key, s
    if n and score >= 0.9 * n: koppel[k] = od_titel[2024][best]
sleutel = {j: {v: k for k, v in t.items()} for j, t in od_titel.items()}
for k, j in kj['jaar'].items():
    src = pd25 if j == 2025 else pd24
    for c in GMS:
        v = getal(src.get(c, {}).get(k))
        if v is None and k in koppel and koppel[k] in sleutel[j]: v = getal(od_rij[j].get(c, {}).get(sleutel[j][koppel[k]]))
        if v is not None: off[k][c] = v
    if k in koppel and koppel[k] in sleutel[j]:
        v = getal(od_rij[j].get('NL', {}).get(sleutel[j][koppel[k]]))
        if v is not None: off[k]['NL'] = v
    bronnaam[k] = f'CBS Kerncijfers Wijken en Buurten {j}, gemeentecijfer'
PCT = {'percentage_personen_0_tot_15_jaar': 'k_0Tot15Jaar_8', 'percentage_personen_15_tot_25_jaar': 'k_15Tot25Jaar_9', 'percentage_personen_25_tot_45_jaar': 'k_25Tot45Jaar_10',
       'percentage_personen_45_tot_65_jaar': 'k_45Tot65Jaar_11', 'percentage_personen_65_jaar_en_ouder': 'k_65JaarOfOuder_12', 'percentage_met_herkomstland_nederland': 'Nederland_17',
       'percentage_met_herkomstland_uit_europa_excl_nl': 'EuropaExclusiefNederland_18', 'percentage_met_herkomstland_buiten_europa': 'BuitenEuropa_19'}
for k, veld in PCT.items():
    j = kj['jaar'][k]
    for c in list(GMS) + ['NL']:
        r = od_rij[j].get(c) or {}; a, n = getal(r.get(veld)), getal(r.get('AantalInwoners_5'))
        if a is not None and n: off[k][c] = a / n * 100
    bronnaam[k] = f'CBS {j}, berekend uit de aantallen per gemeente (PDOK rondt het percentage af)'
# afgeleid in buurt_props
for k, (teller, noemer, f) in {'bedrijven_per_1000_inwoners': ('aantal_bedrijfsvestigingen', 'aantal_inwoners', 1000),
                               'nieuwbouw_per_1000_woningen': ('aantal_nieuwbouwwoningen', 'woningvoorraad', 1000)}.items():
    for c in list(GMS) + ['NL']:
        a, n = off[teller].get(c), off[noemer].get(c)
        if a is not None and n: off[k][c] = a / n * f
    bronnaam[k] = 'berekend uit de officiële gemeentecijfers (teller / noemer)'
# 2c. sociaal domein (CBS 85984NED 2024 en 85618NED 2023)
s = B('cbs-sociaal-2023-2024'); g24 = {code(r): r for r in s['g24'] + NLOFF['85984NED']}; g23 = {code(r): r for r in s['g23'] + NLOFF['85618NED']}
for k, (rows, veld) in {'soc_wmo_per_1000': (g24, 'WmoClientenRelatief_94'), 'soc_jeugdzorg_pct': (g24, 'PercentageJongerenJeugdzorgInNatura_92'),
                        'soc_armoede_pct': (g24, 'PersonenInArmoede_81'), 'soc_laag_inkomen_pct': (g23, 'HuishoudensMetEenLaagInkomen_87'),
                        'soc_inkomen_inw': (g23, 'GemiddeldInkomenPerInwoner_81')}.items():
    for c in list(GMS) + ['NL']:
        v = getal((rows.get(c) or {}).get(veld))
        if v is not None and v >= 0: off[k][c] = v
    bronnaam[k] = 'CBS, gemeentecijfer'
# 2d. gezondheid (RIVM/GGD 50150NED)
GGD = {'GoedErvarenGezondheid_4': 'ggd_gezond', 'HoogRisicoAngststoornisOfDepressie_14': 'ggd_angst', 'HeelVeelStressAfg4Weken_17': 'ggd_stress',
       'Eenzaam_25': 'ggd_eenzaam', 'SterkEenzaam_26': 'ggd_sterk_eenzaam', 'Mantelzorger_30': 'ggd_mantelzorg', 'Vrijwilligerswerk_31': 'ggd_vrijwilliger',
       'MoeiteMetRondkomen_32': 'ggd_rondkomen', 'Overgewicht_33': 'ggd_overgewicht', 'RooktTabak_35': 'ggd_roken', 'VoldoetAanDeBeweegrichtlijn_40': 'ggd_bewegen',
       'ErnstigeGeluidhinderWegverkeer_45': 'ggd_geluid', 'TevredenMetDeWoonomgeving_57': 'ggd_woonomgeving', 'KanGoedVerkoelingVindenBinnen_59': 'ggd_verkoeling'}
gg = {code(r): r for r in B('rivm-ggd-gezondheid-2024')['g'] + NLOFF['50150NED']}
for veld, k in GGD.items():
    for c in list(GMS) + ['NL']:
        v = getal((gg.get(c) or {}).get(veld))
        if v is not None: off[k][c] = v
    bronnaam[k] = 'RIVM/GGD Gezondheidsmonitor 2024, gemeentecijfer'
# 2e. StatLine extra
x = B('cbs-statline-extra-2024'); kg = {code(r): r for r in x['kg']}
for k, veld in {'sl_arbeid': 'Nettoarbeidsparticipatie_71', 'sl_zzp': 'PercentageZelfstandigen_75', 'sl_stroom': 'GemiddeldeElektriciteitslevering_53'}.items():
    for c in list(GMS) + ['NL']:
        v = getal((kg.get(c) or {}).get(veld))
        if v is not None: off[k][c] = v
    bronnaam[k] = 'CBS KWB 2024, gemeentecijfer'
og = collections.defaultdict(dict)
for r in x['og']: og[code(r)][r['Opleidingsniveau'].strip()] = getal(r['Bevolking15Tot75Jaar_2'])
for c in list(GMS) + ['NL']:
    o = og.get(c, {}); t = sum(v for v in o.values() if v)
    if t: off['sl_hoog'][c] = o.get('2018790', 0) / t * 100; off['sl_laag'][c] = o.get('2018700', 0) / t * 100
bronnaam['sl_hoog'] = bronnaam['sl_laag'] = 'CBS 86232NED, berekend uit de gemeentecijfers'
for r in x['eg']:
    if code(r) in GMS or code(r) == 'NL':
        v = getal(r.get('GemiddeldeNettoElektriciteitslevering_6'))
        if v is not None: off['sl_stroom_netto'][code(r)] = v
bronnaam['sl_stroom_netto'] = 'CBS 86159NED, gemeentecijfer'
# 2f. politie: geregistreerd aantal per gemeente / inwoners (KWB 2024) x 1000
pol = B('politie-misdrijven-overlast-2025'); inw24 = {c: getal(r.get('AantalInwoners_5')) for c, r in od_rij[2024].items()}
GR = {'pol_totaal': ['0.0.0'], 'pol_inbraak': ['1.1.1'], 'pol_fiets': ['1.2.3'], 'pol_geweld': ['1.4.2', '1.4.3', '1.4.4', '1.4.5', '1.4.6', '1.4.7'], 'pol_vernieling': ['2.2.1']}
OV = {'pol_overlast': ['0.0.0'], 'pol_jeugd': ['E35']}
for rows, veld, dim, groepen in [(pol['mg'], 'GeregistreerdeMisdrijven_1', 'SoortMisdrijf', GR), (pol['og'], 'GeregistreerdeOverlast_1', 'Overlast', OV)]:
    for k, codes in groepen.items():
        for c in list(GMS) + ['NL']:
            n = sum(getal(r[veld]) or 0 for r in rows if code(r) == c and any(r[dim].strip().startswith(cc) for cc in codes))
            if inw24.get(c) and n: off[k][c] = n / inw24[c] * 1000
        bronnaam[k] = 'Politie via CBS, gemeentetotaal per 1.000 inwoners'
# 2g. trend: inwoners en woningen 2020 per gemeente (CBS 84799NED) -> verandering t.o.v. het officiële cijfer van nu
t20 = {code(r): r for r in B('cbs-kwb-2020-regio')['rijen']}
for k, (v20, vnu) in {'tr_aantal_inwoners': ('inw', 'aantal_inwoners'), 'tr_aantal_huishoudens': ('hh', 'aantal_huishoudens'), 'tr_woningvoorraad': ('won', 'woningvoorraad')}.items():
    for c in GMS:
        a, nu = (t20.get(c) or {}).get(v20), off[vnu].get(c)
        if a and nu: off[k][c] = (nu - a) / a * 100
    bronnaam[k] = 'berekend uit de officiële gemeentecijfers 2020 en nu'

# ---------- 3. vergelijken ----------
def stap(v):   # hoe nauwkeurig is het officiële cijfer gepubliceerd? (CBS rondt vaak af op hele getallen of tienden)
    if v is None: return 0
    if abs(v - round(v)) < 1e-9: return 1 if abs(v) < 1000 else 10 if abs(v - round(v, -1)) < 1e-9 else 1
    if abs(v * 10 - round(v * 10)) < 1e-6: return 0.1
    return 0
def oordeel(kaartw, offw, isprc):
    if kaartw is None or offw is None: return None, None
    d = kaartw - offw
    if abs(d) <= stap(offw) / 2 + 1e-9: return d, 'gelijk'   # verschil valt binnen de afronding van het officiële cijfer
    rel = abs(d) / abs(offw) * 100 if offw else (0 if d == 0 else 999)
    # percentages: verschil in procentpunten telt; CBS rondt percentages per gemeente op hele procenten
    if isprc: return d, ('gelijk' if abs(d) <= 0.6 else 'klein' if abs(d) <= 1.6 else 'groot')
    return d, ('gelijk' if rel <= 0.6 else 'klein' if rel <= 2.5 else 'groot')
uit = []
for t in kaart:
    k = t['key']
    if k not in off or not off[k]: continue
    isprc = (k.startswith('perc') or k.startswith('soc_') and k.endswith('pct') or k.startswith('ggd_') or k.startswith('sl_') and k not in ('sl_stroom', 'sl_stroom_netto')
             or k.startswith('tr_')) and k not in ('soc_inkomen_inw',)
    rij = {'key': k, 'label': t['label'], 'groep': t['g'], 'jaar': t['jaar'], 'bron': bronnaam.get(k, ''), 'procent': isprc, 'gemeenten': {}, 'nl': None}
    for c in GMS:
        d, o = oordeel(t['gm'][c], off[k].get(c), isprc)
        rij['gemeenten'][c] = {'kaart': t['gm'][c], 'officieel': off[k].get(c), 'verschil': d, 'oordeel': o, 'buurtsom': t['buurtsom'][c], 'oordeel_buurtsom': oordeel(t['buurtsom'][c], off[k].get(c), isprc)[1]}
    if 'NL' in off[k]:
        d, o = oordeel(t['nl'], off[k]['NL'], isprc); rij['nl'] = {'kaart': t['nl'], 'officieel': off[k]['NL'], 'verschil': d, 'oordeel': o}
    oo = [g['oordeel'] for g in rij['gemeenten'].values() if g['oordeel']] + ([rij['nl']['oordeel']] if rij['nl'] and rij['nl']['oordeel'] else [])
    rij['slechtst'] = 'groot' if 'groot' in oo else 'klein' if 'klein' in oo else 'gelijk' if oo else None
    uit.append(rij)
niet = [t['key'] for t in kaart if t['key'] not in {r['key'] for r in uit}]
os.makedirs(P('tests', 'uit'), exist_ok=True)
json.dump({'gecontroleerd': uit, 'niet_te_controleren': niet, 'buurten': totaal_buurten, 'kaart': kaart}, open(P('tests', 'uit', 'validatie.json'), 'w'), ensure_ascii=False, indent=1)

tel = collections.Counter(r['slechtst'] for r in uit)
oud = collections.Counter(('groot' if any(g['oordeel_buurtsom']=='groot' for g in r['gemeenten'].values()) else 'klein' if any(g['oordeel_buurtsom']=='klein' for g in r['gemeenten'].values()) else 'gelijk') for r in uit)
print('ter vergelijking, oude rekenwijze (opgeteld uit de buurten):', dict(oud))
print(f"{len(uit)} thema's gecontroleerd tegen het officiële gemeentecijfer: {dict(tel)}; niet te controleren: {len(niet)}")
f = lambda v: '–' if v is None else (f'{v:,.1f}' if abs(v) < 1000 else f'{v:,.0f}')
for r in sorted(uit, key=lambda r: {'groot': 0, 'klein': 1, 'gelijk': 2}.get(r['slechtst'], 3)):
    if r['slechtst'] == 'gelijk': continue
    print(f"\n[{r['slechtst']}] {r['key']} – {r['label']} ({r['jaar']})")
    for c, g in r['gemeenten'].items(): print(f"   {GMS[c]:20} kaart {f(g['kaart']):>10}  officieel {f(g['officieel']):>10}  {g['oordeel']}")
    if r['nl']: print(f"   {'Nederland':20} kaart {f(r['nl']['kaart']):>10}  officieel {f(r['nl']['officieel']):>10}  {r['nl']['oordeel']}")
print('\nniet te controleren:', niet)
