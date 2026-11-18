"""Maakt rapporten/datakwaliteit.html uit tests/uit/validatie.json (draai eerst scripts/valideer.py)."""
import json, os, sys, html, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
v = json.load(open(os.path.join(ROOT, 'tests', 'uit', 'validatie.json')))
GMS = {'GM0513': 'Gouda', 'GM1892': 'Zuidplas', 'GM1901': 'Bodegraven-Reeuwijk', 'GM1931': 'Krimpenerwaard', 'GM0627': 'Waddinxveen'}
e = html.escape
def nl(x, d=1):
    if x is None: return '–'
    s = f'{x:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return s
G = v['gecontroleerd']
n_gelijk = sum(1 for r in G if r['slechtst'] == 'gelijk'); n = len(G)
oud_afw = [(r, c, g) for r in G for c, g in r['gemeenten'].items() if g['oordeel_buurtsom'] in ('klein', 'groot') and g['officieel']]
oud_themas = len({r['key'] for r, _, _ in oud_afw})
oud_gelijk = n - oud_themas
# voorbeelden voor/na
vb = sorted(oud_afw, key=lambda x: -abs(x[2]['buurtsom'] - x[2]['officieel']) / abs(x[2]['officieel']))
gezien, voorbeelden = set(), []
for r, c, g in vb:
    if r['key'] in gezien: continue
    gezien.add(r['key']); voorbeelden.append((r, c, g))
    if len(voorbeelden) == 8: break
dec = lambda off: 0 if abs(off) >= 100 else 1 if abs(off) >= 1 or abs(off * 10 - round(off * 10)) < 1e-6 else 2
rij_vb = ''.join(f"<tr><td>{e(r['label'])}</td><td>{GMS[c]}</td><td class='num oud'>{nl(g['buurtsom'], dec(g['officieel']))}</td><td class='num'>{nl(g['officieel'], dec(g['officieel']))}</td><td class='num nu'>{nl(g['kaart'], dec(g['officieel']))}</td></tr>" for r, c, g in voorbeelden)
groepen = []
for r in G:
    if r['groep'] not in groepen: groepen.append(r['groep'])
def status(r):
    gm = [g['oordeel'] for g in r['gemeenten'].values() if g['oordeel']]
    nlx = r['nl']['oordeel'] if r['nl'] else None
    ok = sum(1 for o in gm if o == 'gelijk')
    s = f"{ok}/{len(gm)} gemeenten"
    if nlx: s += ' · NL ' + ('gelijk' if nlx == 'gelijk' else f"{nl(r['nl']['kaart'], 0)} tegen {nl(r['nl']['officieel'], 0)}")
    cls = 'ok' if r['slechtst'] == 'gelijk' else 'let'
    return f"<span class='chip {cls}'>{'gelijk' if cls == 'ok' else 'kleine afwijking'}</span> <span class='fijn'>{s}</span>"
tabel = ''
for gr in groepen:
    tabel += f"<tr class='grp'><td colspan='3'>{e(gr)}</td></tr>"
    for r in [x for x in G if x['groep'] == gr]:
        tabel += f"<tr><td>{e(r['label'])}<span class='jaar'>{r['jaar'] or ''}</span></td><td class='bron'>{e(r['bron'])}</td><td>{status(r)}</td></tr>"
NIET = {'lbm_': 'Leefbaarometer: alleen per buurt beschikbaar, de kaart weegt per gemeente naar inwoners.',
        'rt_': 'Reistijden: zelf berekend met routes over OpenStreetMap (er bestaat geen officieel cijfer).',
        'ong_': 'Verkeersongevallen: zelf geteld uit de ongevallenregistratie (BRON) van Rijkswaterstaat.',
        'tr_': 'Verandering in vijf jaar: berekend uit twee CBS-jaren; per gemeente gecontroleerd voor inwoners, huishoudens en woningen.',
        '': 'Gebruikt het officiële gemeentecijfer van het CBS, maar de automatische controle kon de kolom niet koppelen.'}
niet = {}
for k in v['niet_te_controleren']:
    pre = next(p for p in NIET if k.startswith(p)); niet.setdefault(pre, []).append(next(t['label'] for t in v['kaart'] if t['key'] == k))
niet_html = ''.join(f"<li><b>{len(lab)} thema{'' if len(lab) == 1 else '’s'}</b> ({e(', '.join(lab[:6]))}{'…' if len(lab) > 6 else ''}). {NIET[p]}</li>" for p, lab in niet.items())
vandaag = datetime.date.today().strftime('%-d-%-m-%Y')
SJABLOON = open(os.path.join(ROOT, 'rapporten', 'datakwaliteit.sjabloon.html')).read()
uit = (SJABLOON.replace('{{N}}', str(n)).replace('{{GELIJK}}', str(n_gelijk)).replace('{{OUD_GELIJK}}', str(oud_gelijk)).replace('{{OUD_THEMAS}}', str(oud_themas))
       .replace('{{OUD_COMBI}}', str(len(oud_afw))).replace('{{VOORBEELDEN}}', rij_vb).replace('{{TABEL}}', tabel).replace('{{NIET}}', niet_html)
       .replace('{{NIET_N}}', str(len(v['niet_te_controleren']))).replace('{{DATUM}}', vandaag))
# website: een volledig HTML-document; artifact (claude.ai): alleen de inhoud (daar komt het skelet er zelf omheen)
open(os.path.join(ROOT, 'rapporten', 'datakwaliteit.html'), 'w').write('<!doctype html>\n<html lang="nl">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head>\n<body>\n' + uit + '\n</body>\n</html>\n')
if len(sys.argv) > 1: open(sys.argv[1], 'w').write(uit)
print('rapporten/datakwaliteit.html', n_gelijk, '/', n)
