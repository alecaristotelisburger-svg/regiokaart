"""Eigen achtergrondkaart 'Regiostijl': de vectortegels van de BRT-achtergrondkaart (Kadaster/PDOK) met eigen kleuren.

Basis: de PDOK-stijl 'standaard__webmercatorquad' (bron-downloads/pdok-brt-vectorstijl-standaard.json), dezelfde lagen en
filters, andere kleuren en lijndiktes: licht en rustig, met paars als accent (huisstijl Regio Midden-Holland), zodat de
buurtkleuren en kaartlagen erbovenop goed te lezen zijn. Kleuren aanpassen: het blok KLEUR hieronder, dan dit script en
scripts/bouw_kaart.py draaien. Uitvoer: data/regiostijl.json (in de pagina als DATA.regiostijl).
Gebruik: .venv/bin/python scripts/regiostijl.py
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
basis = json.load(open(P('bron-downloads', 'pdok-brt-vectorstijl-standaard.json')))

KLEUR = {
    'land': '#f7f3f1',        # warm gebroken wit
    'water': '#cfe2ee',       # zacht blauw
    'water_tekst': '#557f9e',
    'bos': '#dfe9d6',         # lichtgroen
    'heide': '#ece3ea',       # vleugje lila
    'zand': '#f2ede0',
    'bebouwd': '#efe8ec',     # lila-grijs
    'gebouw': '#e3d9df',
    'weg': '#ffffff',
    'rand_snelweg': '#c2adbd', 'rand_hoofdweg': '#cdbec9', 'rand_overig': '#ddd2da', 'tunnel': '#e9e2e7',
    'fietspad': '#e6dbe3',
    'spoor': '#b6a6b2',
    'grens': '#c4adbf',
    'leiding': '#d3c7d0',
    'plaats': '#3b0042',      # donkerpaars
    'wijk': '#7b5f77', 'buurt': '#958a92', 'straat': '#8d7f89',
    'a_weg': '#8a2486', 'n_weg_tekst': '#5b0065', 'n_weg_vlak': '#f1e2ee',
}
K = KLEUR
SNELWEG = ['E-weg', 'autosnelweg', 'autosnelweg op brug', 'autosnelweg oprit/afrit']
HOOFDWEG = ['hoofdweg', 'hoofdweg op brug', 'hoofdweg oprit/afrit']
TUNNEL = ['autosnelweg in tunnel', 'regionale weg in tunnel', 'lokale weg in tunnel', 'hoofdweg in tunnel', 'straat in tunnel']
def match(paren, anders):
    m = ['match', ['get', 'vistext']]
    for waarden, v in paren: m += [waarden, v]
    return m + [anders]
def zoomschaal(expr, lo=0.55, hi=2.6):   # lijnen dunner bij uitzoomen, dikker bij inzoomen
    return ['interpolate', ['linear'], ['zoom'], 8, ['*', lo, expr], 12, expr, 16, ['*', hi, expr]]
dikte_rand = match([(['E-weg', 'autosnelweg', 'autosnelweg op brug'], 4.2), (HOOFDWEG, 3.2), (['regionale weg', 'regionale weg op brug'], 2.4)], 1.6)
dikte_weg = match([(['E-weg', 'autosnelweg', 'autosnelweg op brug'], 2.6), (HOOFDWEG, 2.0), (['regionale weg', 'regionale weg op brug'], 1.4)], 0.9)

lagen = []
for l in basis['layers']:
    l = json.loads(json.dumps(l)); i = l['id']; p = l.setdefault('paint', {})
    if i == 'Onderlegger Nederland':
        p['fill-color'] = match([('land/grens (NL)', K['land']), ('onderlegger Nederland', K['land']), ('(zee)water', K['water'])], 'transparent')
    elif i == 'waterdeelvlak':
        p['fill-color'] = match([(['zee', 'meer, plas', 'waterloop', 'droogvallend'], K['water'])], 'transparent')
    elif i == 'Bodemgebruik':
        p['fill-color'] = match([(['bos', 'bos: dras, moeras, riet'], K['bos']), (['heide', 'heide: dras, moeras, riet'], K['heide']),
                                 (['zand', 'zand: dras, moeras, riet'], K['zand']), ('bebouwd gebied', K['bebouwd']), (['zee', 'meer, plas'], K['water']),
                                 (['steenglooing', 'aanlegsteiger'], K['gebouw'])], 'transparent')
    elif i == 'Gebouw':
        p['fill-color'] = K['gebouw']; p['fill-opacity'] = ['interpolate', ['linear'], ['zoom'], 12, 0, 14, 1]
    elif i == 'wegdeellijn-contour':
        p['line-color'] = match([(SNELWEG, K['rand_snelweg']), (HOOFDWEG, K['rand_hoofdweg']), (TUNNEL, K['tunnel'])], K['rand_overig'])
        p['line-width'] = zoomschaal(dikte_rand); l.setdefault('layout', {}).update({'line-cap': 'round', 'line-join': 'round'})
    elif i == 'wegdeellijn':
        p['line-color'] = match([(TUNNEL, K['tunnel']), ('fietspad', K['fietspad'])], K['weg'])
        p['line-width'] = zoomschaal(dikte_weg); l.setdefault('layout', {}).update({'line-cap': 'round', 'line-join': 'round'})
    elif i == 'wegdeelvlak':
        p['fill-color'] = match([(TUNNEL, K['tunnel']), ('fietspad', K['fietspad'])], K['weg'])
    elif i == 'registratiefgebiedlijn':
        p['line-color'] = match([(['land/grens (NL)', 'landsgrens (NL-BE, NL-DE)', 'provinciegrens'], K['grens'])], 'transparent')
        p['line-dasharray'] = [4, 3]
    elif i == 'spoorbaandeellijn':
        p['line-color'] = K['spoor']; p['line-width'] = zoomschaal(match([('tram', 1)], 2.6), 0.5, 1.8)
    elif i == 'treinspoor':
        p['line-color'] = K['land']; p['line-width'] = zoomschaal(1.2, 0.5, 1.8)
    elif i in ('metro', 'tram', 'metro / sneltram in tunnel', 'metro / sneltram in tunnel 2'):
        p['line-color'] = K['spoor'] if i in ('metro', 'tram') else K['tunnel']
    elif i == 'inrichtingselement lijn':
        p['line-color'] = match([(['hekwerk', 'geluidswering', 'aanlegsteiger', 'hoogspanningsleiding', 'kabelbaan', 'muur'], K['leiding'])], 'transparent')
        l['minzoom'] = 13
    elif i.startswith('hoogspanningsmast'):
        p['circle-color'] = K['leiding']; p['circle-radius'] = 1.5; l['minzoom'] = 14
    elif i == 'waterdeelvlak_label':
        p.update({'text-color': K['water_tekst'], 'text-halo-color': K['land'], 'text-halo-width': 1.2})
    elif i == 'straatnamen':
        p.update({'text-color': K['straat'], 'text-halo-color': '#ffffff', 'text-halo-width': 1.2})
    elif i == 'annotatie':
        p['text-color'] = match([('plaatsnamen', K['plaats']), ('wijknamen', K['wijk']), ('buurtnamen', K['buurt']), ('A-wegnummers', '#ffffff'),
                                 ('N-wegnummers', K['n_weg_tekst']), ('fingerprint', K['water_tekst'])], 'transparent')
        p['text-halo-color'] = match([('A-wegnummers', K['a_weg']), ('N-wegnummers', K['n_weg_vlak'])], 'rgba(255,255,255,0.9)')
        p['text-halo-width'] = match([('A-wegnummers', 24), ('N-wegnummers', 14)], 1.4)
        lay = l.setdefault('layout', {})
        lay['text-font'] = match([('plaatsnamen', ['literal', ['Liberation Sans Bold']]), ('wijknamen', ['literal', ['Liberation Sans Italic']]),
                                  ('A-wegnummers', ['literal', ['Liberation Sans Bold']]), ('N-wegnummers', ['literal', ['Liberation Sans Bold']])], ['literal', ['Liberation Sans Regular']])
    lagen.append(l)
stijl = {'version': 8, 'name': 'Regiostijl Midden-Holland', 'glyphs': basis['glyphs'], 'sources': basis['sources'],
         'layers': [{'id': 'achtergrond', 'type': 'background', 'paint': {'background-color': K['land']}}] + lagen}
json.dump(stijl, open(P('data', 'regiostijl.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('data/regiostijl.json', len(stijl['layers']), 'lagen')
