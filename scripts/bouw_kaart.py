"""Bouwt regiokaart-midden-holland.html uit src/src.html + data/ + bibliotheken.

Gebruik (vanuit de projectmap): python3 scripts/bouw_kaart.py
Resultaat: één zelfstandig HTML-bestand met alle data, Leaflet en jsPDF erin.
"""
import base64, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
s = open(P('src', 'src.html')).read()
css = open(P('node_modules', 'leaflet', 'dist', 'leaflet.css')).read()
js = open(P('node_modules', 'leaflet', 'dist', 'leaflet.js')).read().replace('</script>', '<\\/script>')
pdf = open(P('node_modules', 'jspdf', 'dist', 'jspdf.umd.min.js')).read().replace('</script>', '<\\/script>')
s = s.replace('<!--LEAFLET_CSS-->', '<style>' + css + '</style>')
s = s.replace('<!--LEAFLET_JS-->', '<script>' + js + '</script>\n<script>' + pdf + '</script>')
names = ['buurten', 'gemeenten', 'nnn', 'n2k', 'roads', 'rail', 'stations', 'buslines', 'busstops', 'voorz', 'locaties', 'net', 'erfgoed']
data = {k: json.load(open(P('data', k + '.json'))) for k in names}
data['natuur'] = json.load(open(P('data', 'natuur_gm.json')))
data['spec'] = json.load(open(P('data', 'spec.json')))
data['ref'] = json.load(open(P('data', 'ref.json'))) if os.path.exists(P('data', 'ref.json')) else None
data['logo'] = 'data:image/jpeg;base64,' + base64.b64encode(open(P('src', 'logo.jpg'), 'rb').read()).decode()
out = P('regiokaart-midden-holland.html')
open(out, 'w').write(s.replace('/*DATA*/null', json.dumps(data, separators=(',', ':'), ensure_ascii=False)))
print('Gebouwd:', out, round(os.path.getsize(out) / 1e6, 1), 'MB')
