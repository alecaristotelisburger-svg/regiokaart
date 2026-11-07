"""Werkt alleen de cijfers in data/buurten.json bij, zonder de grenzen opnieuw te maken.

Handig als je een veld toevoegt aan maak_data.py (keep_list / KEEP_EXTRA) en geen
mapshaper (Node) hebt: de vereenvoudigde grenzen blijven staan, de eigenschappen
komen opnieuw uit bron-downloads/cbs-buurten-2024-regio.geojson (gekoppeld op buurtcode).
Draai daarna ref.py (Zuid-Holland/Nederland) en bouw de kaart:

    .venv/bin/python scripts/ververs_buurtcijfers.py
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maak_data import BRON, DATA, REGIO, keep_list, buurt_props

raw = json.load(open(os.path.join(BRON, 'cbs-buurten-2024-regio.geojson')))['features']
keep = keep_list(raw[0]['properties'])
by_code = {f['properties']['buurtcode']: f['properties'] for f in raw if f['properties']['gemeentenaam'] in REGIO}
pad = os.path.join(DATA, 'buurten.json')
b = json.load(open(pad))
for f in b['features']:
    f['properties'] = buurt_props(by_code[f['properties']['buurtcode']], keep)
json.dump(b, open(pad, 'w'), ensure_ascii=False, separators=(',', ':'))
print('buurten bijgewerkt:', len(b['features']), '| velden per buurt:', len(keep) + 2)
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ref.py'),
                os.path.join(BRON, 'cbs-gemeenten-2024-nederland.geojson')], cwd=DATA, check=True)
