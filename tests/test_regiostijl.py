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
    pg.wait_for_timeout(6000)
    check('Kaart = eigen stijl, tegels geladen', pg.evaluate("basemap==='kaart' && !!regioBg && map.hasLayer(regioBg) && regioTegelOk && !map.hasLayer(brt)"))
    check('drie knoppen', pg.evaluate("[...document.querySelectorAll('#secAchtergrond .seg button')].map(b=>b.dataset.bm).join()") == 'kaart,sat,geen')
    check('bronvermelding', 'eigen stijl' in pg.inner_text('.leaflet-control-attribution'))
    pg.click('#secAchtergrond [data-bm=sat]'); pg.wait_for_timeout(500); check('satelliet: eigen stijl weg', not pg.evaluate('map.hasLayer(regioBg)'))
    pg.click('#secAchtergrond [data-bm=kaart]'); pg.wait_for_timeout(2500); check('terug naar kaart', pg.evaluate('map.hasLayer(regioBg)'))
    pg.select_option('#theme', 'gemiddelde_woningwaarde'); pg.wait_for_timeout(1500)
    with pg.expect_download() as d: pg.click('#btnMapPng')
    pad = os.path.join(UIT, 'regiostijl.png'); d.value.save_as(pad)
    import fitz; px = fitz.Pixmap(pad)
    # de achtergrondkleur van de regiostijl (#f7f3f1) moet in de afbeelding staan: dan is de GL-kaart meegekomen
    kleuren = {tuple(px.pixel(x, y)[:3]) for x in range(0, px.width, 37) for y in range(0, px.height, 37)}
    check('PNG bevat de regiostijl', (247, 243, 241) in kleuren)
    pg.click('#secAchtergrond [data-bm=geen]'); pg.wait_for_timeout(500); check('geen achtergrond', not pg.evaluate('map.hasLayer(regioBg) || map.hasLayer(brt)'))
    pg.goto(U + '#achtergrond=regio'); pg.reload(); pg.wait_for_timeout(5000); check('oude link achtergrond=regio werkt', pg.evaluate("basemap==='kaart'"))
    check('geen JS-fouten', not fout, fout)
    b.close()
print(f'{len(ok)} goed, {len(mis)} fout'); print('fouten:', mis)
