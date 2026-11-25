"""Regiothermometer brede welvaart: scores per dimensie voor de regio en de vijf gemeenten.

Dimensies: de elf van RaboResearch (brede welvaart in de regio). Per indicator wordt de waarde van een gemeente
(of de regio) vergeleken met de verdeling over ALLE Nederlandse gemeenten: zes even grote klassen (sextielen)
geven een score van 0 tot 5. Bij indicatoren waar lager beter is (armoede, misdrijven) wordt de score omgedraaid.
Treden: basis 0–2, functioneel 2–4, excellent 4–5. Per dimensie het gemiddelde van de indicatoren.

Vaste regels (versie 1.0, 25-11-2026):
  1. Onbekend is geen nul: een ontbrekende waarde verlaagt de dekking, niet de score.
  2. De regels en drempels liggen vast; een wijziging krijgt een nieuw versienummer.
  3. Er komt geen totaalcijfer over de dimensies heen: weging is een bestuurlijke keuze.

Bronnen: de officiële gemeentecijfers (data/afgeleid/*_gemeenten.json, gemaakt door kwb_jaar.py en extra_data.py)
voor de drempels; voor de regio en de vijf gemeenten exact dezelfde waarden als de kaart (data/*.json 'gebied').
Uitvoer: data/bw.json (in de pagina).
Gebruik: .venv/bin/python scripts/brede_welvaart.py
"""
import json, os, statistics, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
L = lambda *a: json.load(open(P(*a)))
VERSIE = '1.0'
GMS = ['GM0513', 'GM1892', 'GM1901', 'GM1931', 'GM0627']   # Gouda, Zuidplas, Bodegraven-Reeuwijk, Krimpenerwaard, Waddinxveen
KJ = L('data', 'kwb_jaar.json')

# ---------- bronnen per indicator: (alle gemeenten, regio/gemeenten zoals de kaart, ZH/NL) ----------
alle = {'kwb': L('data', 'afgeleid', 'gemeenten_kwb.json')}
for n in ['sociaal', 'gezondheid', 'politie', 'statline']: alle[n] = L('data', 'afgeleid', n + '_gemeenten.json')
gebied, ref = {}, {'zh': {}, 'nl': {}}
for n in ['ref', 'sociaal', 'gezondheid', 'politie', 'statline']:
    d = L('data', n + '.json')
    for g, v in d['gebied'].items(): gebied.setdefault(g, {}).update({k: w for k, w in v.items() if w is not None})
    r = d if n == 'ref' else d['ref']
    for lv in ('zh', 'nl'): ref[lv].update({k: w for k, w in r[lv].items() if w is not None and not k.endswith('__cmp')})
JAAR_BRON = {'sociaal': {'soc_inkomen_inw': 2023, 'soc_laag_inkomen_pct': 2023}, 'gezondheid': 2024, 'politie': 2025, 'statline': 2024}
BRON = {'kwb': 'CBS Kerncijfers Wijken en Buurten', 'sociaal': 'CBS (sociaal domein en inkomen)', 'gezondheid': 'GGD’en en RIVM, Gezondheidsmonitor (schatting, 18+)',
        'politie': 'Politie, geregistreerde misdrijven en overlast (via CBS)', 'statline': 'CBS StatLine'}
def bron_van(k):
    if k.startswith('soc_'): return 'sociaal'
    if k.startswith('ggd_'): return 'gezondheid'
    if k.startswith('pol_'): return 'politie'
    if k.startswith('sl_'): return 'statline'
    return 'kwb'
def jaar_van(k):
    b = bron_van(k)
    if b == 'kwb': return KJ['jaar'].get(k)
    j = JAAR_BRON[b]; return j.get(k, 2024) if isinstance(j, dict) else j

# ---------- de dimensies (RaboResearch) en indicatoren: (sleutel, label, richting) ----------
# richting +1: hoger is gunstiger; -1: lager is gunstiger; 0: context (wel getoond, niet gescoord)
DIM = [
  ('inkomen', 'Inkomen', [('soc_inkomen_inw', 'Gemiddeld inkomen per inwoner', 1), ('soc_laag_inkomen_pct', 'Huishoudens met een laag inkomen', -1),
     ('soc_armoede_pct', 'Personen in armoede', -1), ('ggd_rondkomen', 'Moeite met rondkomen', -1)], ['Vermogen']),
  ('baan', 'Baanzekerheid', [('sl_arbeid', 'Nettoarbeidsparticipatie', 1), ('ww_per_1000', 'WW-uitkeringen per 1.000 inwoners', -1),
     ('bijstand_per_1000', 'Bijstandsuitkeringen per 1.000 inwoners', -1)], ['Arbeidsongeschiktheidsuitkeringen', 'Werkgelegenheid naar sector']),
  ('gezondheid', 'Gezondheid', [('ggd_gezond', 'Goed ervaren gezondheid', 1), ('ggd_langdurig', 'Eén of meer langdurige aandoeningen', -1),
     ('ggd_overgewicht', 'Overgewicht', -1)], ['Broze gezondheid bij 65-plussers']),
  ('welzijn', 'Subjectief welzijn', [('ggd_regie', 'Regie over het eigen leven', 1), ('ggd_veerkracht', 'Hoge veerkracht', 1),
     ('ggd_stress', '(Heel) veel stress', -1)], ['Tevredenheid met het leven']),
  ('veiligheid', 'Veiligheid', [('pol_totaal', 'Geregistreerde misdrijven per 1.000 inwoners', -1), ('pol_inbraak', 'Woninginbraken per 1.000 inwoners', -1),
     ('pol_geweld', 'Geweldsmisdrijven per 1.000 inwoners', -1), ('pol_overlast', 'Overlastmeldingen per 1.000 inwoners', -1)], ['Ervaren onveiligheid']),
  ('ontwikkeling', 'Persoonlijke ontwikkeling', [('sl_hoog', 'Hoogopgeleiden (15–75 jaar)', 1), ('sl_laag', 'Laagopgeleiden (15–75 jaar)', -1)],
     ['Voortijdig schoolverlaten', 'Deelname aan onderwijs']),
  ('huisvesting', 'Huisvesting', [('ggd_woning', 'Tevreden met de woning', 1), ('ggd_woonomgeving', 'Tevreden met de woonomgeving', 1),
     ('nieuwbouw_per_1000_woningen', 'Nieuwbouw per 1.000 woningen', 1), ('gemiddelde_woningwaarde', 'Gemiddelde WOZ-waarde', 0),
     ('percentage_koopwoningen', 'Koopwoningen', 0), ('perc_huurwoningen_in_bezit_woningcorporaties', 'Corporatiewoningen', 0)], []),
  ('betrokkenheid', 'Maatschappelijke betrokkenheid', [('ggd_vrijwilliger', 'Vrijwilligerswerk', 1), ('ggd_mantelzorg', 'Mantelzorg', 1)], []),
  ('balans', 'Werk-privébalans', [('treinstation_gemiddelde_afstand_in_km', 'Afstand tot een treinstation', -1),
     ('oprit_hoofdverkeersweg_gemiddelde_afstand_in_km', 'Afstand tot een oprit van een hoofdweg', -1)], ['Woon-werkpendel en reisafstand', 'Reistijd naar banen met OV en auto']),
  ('milieu', 'Milieu', [('ggd_geluid', 'Ernstige geluidhinder door wegverkeer', -1), ('ggd_groen', 'Tevreden met het groen', 1),
     ('ggd_verkoeling', 'Kan binnen goed verkoeling vinden', 1)], ['Luchtkwaliteit', 'Groen per inwoner', 'Klimaatrisico’s (staan als kaartlaag, niet als cijfer per gemeente)']),
  ('contacten', 'Sociale contacten', [('ggd_eenzaam', 'Eenzaamheid', -1), ('ggd_sterk_eenzaam', 'Sterke eenzaamheid', -1), ('ggd_steun', 'Krijgt steun van anderen', 1)],
     ['Sociale samenhang in de buurt (alleen per buurt: Leefbaarometer)']),
]
VOORUIT = [('percentage_personen_65_jaar_en_ouder', '65-plussers', 0), ('percentage_aardgasvrije_woningen', 'Aardgasvrije woningen', 1),
           ('percentage_woningen_met_zonnestroom', 'Woningen met zonnestroom', 1)]
NOOT = {'nieuwbouw_per_1000_woningen': 'Richting is een keuze: de regio wil groeien, dus meer nieuwbouw telt als gunstig.',
        'ggd_mantelzorg': 'Meer mantelzorg telt als meer betrokkenheid; het kan ook op zware zorg wijzen.',
        'treinstation_gemiddelde_afstand_in_km': 'Benadering van bereikbaarheid van werk: hoe dichter een station, hoe beter.',
        'oprit_hoofdverkeersweg_gemiddelde_afstand_in_km': 'Benadering van bereikbaarheid van werk met de auto.'}

def kwantielen(vals, n=6):
    v = sorted(vals); out = []
    for i in range(1, n):
        q = i / n * (len(v) - 1); lo = int(q); f = q - lo
        out.append(v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * f)
    return out
def score(v, cuts, richting):
    if v is None or not richting: return None
    k = sum(1 for c in cuts if v > c)
    return k if richting > 0 else 5 - k
trede = lambda s: None if s is None else 'basis' if s < 2 else 'functioneel' if s < 4 else 'excellent'
GEBIEDEN = GMS + ['regio']

def indicator(k, label, richting):
    b = bron_van(k)
    vals = [x.get(k) for c, x in alle[b].items() if c.startswith('GM') and (b != 'kwb' or x.get('water') != 'JA')]
    vals = [v for v in vals if isinstance(v, (int, float)) and v >= 0]
    cuts = kwantielen(vals) if len(vals) >= 30 else None
    w = {g: gebied.get(g, {}).get(k) for g in GEBIEDEN}
    w.update({'zh': ref['zh'].get(k), 'nl': ref['nl'].get(k)})
    sc = {g: (score(w[g], cuts, richting) if cuts else None) for g in GEBIEDEN + ['zh', 'nl']}
    return {'key': k, 'label': label, 'richting': richting, 'bron': BRON[b], 'jaar': jaar_van(k), 'n': len(vals),
            'mediaan': statistics.median(vals) if vals else None, 'drempels': cuts, 'waarden': w, 'scores': sc, 'noot': NOOT.get(k)}

dims = []
for k, naam, inds, mist in DIM:
    I = [indicator(*x) for x in inds]
    gescoord = [i for i in I if i['richting']]
    d = {'k': k, 'naam': naam, 'indicatoren': I, 'ontbreekt': mist, 'per_gebied': {}}
    for g in GEBIEDEN + ['zh', 'nl']:
        s = [i['scores'][g] for i in gescoord if i['scores'][g] is not None]
        gem = round(sum(s) / len(s), 1) if s else None
        d['per_gebied'][g] = {'score': gem, 'trede': trede(gem), 'dekking': round(len(s) / (len(gescoord) + len(mist)) * 100)}
    dims.append(d)
prog = L('data', 'prognose.json')
def groei(p):
    try: return (p['p']['2040'] / p['p']['2024'] - 1) * 100
    except Exception: return None
vooruit = {'indicatoren': [indicator(*x) for x in VOORUIT],
           'groei': {**{g: groei(prog['gm'].get(g, {})) for g in GMS}, 'regio': groei(prog['regio']), 'zh': groei(prog['zh']), 'nl': groei(prog['nl'])},
           'bron_groei': prog['bron']}
uit = {'versie': VERSIE, 'gemaakt': datetime.date.today().isoformat(), 'editie': 1,
       'referentie': f"alle {max(i['n'] for d in dims for i in d['indicatoren'])} Nederlandse gemeenten",
       'regels': ['Onbekend is geen nul: een ontbrekende waarde verlaagt de dekking, niet de score.',
                  'De regels en drempels liggen vast vóór de meting en veranderen alleen met een nieuw versienummer, zodat jaren vergelijkbaar blijven.',
                  'Er komt geen totaalcijfer over de dimensies heen: de weging tussen dimensies is een bestuurlijke keuze, geen rekenstap.'],
       'dimensies': dims, 'vooruitblik': vooruit}
json.dump(uit, open(P('data', 'bw.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('data/bw.json', round(os.path.getsize(P('data', 'bw.json')) / 1e3), 'kB ·', uit['referentie'])
for d in dims:
    print(f"{d['naam']:32}", ' '.join(f"{(d['per_gebied'][g]['score'] if d['per_gebied'][g]['score'] is not None else '–'):>4}" for g in GEBIEDEN), ' dekking regio', d['per_gebied']['regio']['dekking'], '%')
