"""Test van de achtergrond 'Regiostijl' (vectortegels BRT met eigen kleuren, via MapLibre). Heeft internet nodig (PDOK).
Gebruik: .venv/bin/python tests/test_regiostijl.py   (start eerst de lokale server: python3 -m http.server 8080)"""
import os
from playwright.sync_api import sync_playwright
UIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uit'); os.makedirs(UIT, exist_ok=True)
U = 'http://localhost:8080/regiokaart-midden-holland.html'
ok, mis = [], []
def check(n, c, i=''):
    (ok if c else mis).append(n); print(('  ok   ' if c else '  FOUT ') + n, '' if c else i)
with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    ctx = b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True); ctx.add_init_script("try{localStorage.setItem('regiokaart-rondleiding-v1','1')}catch(e){}")
    pg = ctx.new_page(); fout = []; pg.on('pageerror', lambda e: fout.append(str(e)))
    pg.goto(U); pg.wait_for_timeout(1500)
    check('MapLibre niet geladen bij start', pg.evaluate('typeof maplibregl') == 'undefined')
    pg.click('#secAchtergrond [data-bm=regio]'); pg.wait_for_timeout(7000)
    check('regiostijl aan, tegels geladen', pg.evaluate('!!regioBg && map.hasLayer(regioBg) && regioTegelOk'))
    check('knop Regiostijl actief', pg.evaluate("document.querySelector('#secAchtergrond [data-bm=regio]').classList.contains('on')"))
    check('bronvermelding', 'eigen stijl' in pg.inner_text('.leaflet-control-attribution'))
    pg.wait_for_timeout(600); check('in de link', 'achtergrond=regio' in pg.evaluate('location.hash'))
    pg.select_option('#theme', 'gemiddelde_woningwaarde'); pg.wait_for_timeout(1500)
    with pg.expect_download() as d: pg.click('#btnMapPng')
    pad = os.path.join(UIT, 'regiostijl.png'); d.value.save_as(pad)
    import fitz; px = fitz.Pixmap(pad)
    # de achtergrondkleur van de regiostijl (#f7f3f1) moet in de afbeelding staan: dan is de GL-kaart meegekomen
    kleuren = {tuple(px.pixel(x, y)[:3]) for x in range(0, px.width, 37) for y in range(0, px.height, 37)}
    check('PNG bevat de regiostijl', (247, 243, 241) in kleuren)
    pg.click('#secAchtergrond [data-bm=kaart]'); pg.wait_for_timeout(800)
    check('terug naar Kaart: regiostijl weg', not pg.evaluate('map.hasLayer(regioBg)'))
    check('geen JS-fouten', not fout, fout)
    b.close()
print(f'{len(ok)} goed, {len(mis)} fout'); print('fouten:', mis)
