"""Test van de 3D-weergave (buurten als blokken, MapLibre). Gebruik: .venv/bin/python tests/test_3d.py"""
import os
from playwright.sync_api import sync_playwright
UIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uit'); os.makedirs(UIT, exist_ok=True)
U = 'file://' + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'regiokaart-midden-holland.html')
ok, mis = [], []
def check(n, c, i=''):
    (ok if c else mis).append(n); print(('  ok   ' if c else '  FOUT ') + n, '' if c else i)
with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    ctx = b.new_context(viewport={'width': 1440, 'height': 900}); ctx.add_init_script("try{localStorage.setItem('regiokaart-rondleiding-v1','1')}catch(e){}")
    pg = ctx.new_page(); fout = []; pg.on('pageerror', lambda e: fout.append(str(e)))
    pg.goto(U); pg.wait_for_timeout(1500)
    check('MapLibre niet geladen bij start', pg.evaluate('typeof maplibregl') == 'undefined')
    pg.click('#btn3D'); pg.wait_for_timeout(8000)
    check('3D opent en kaart is geladen', pg.is_visible('#d3') and pg.evaluate('!!d3Kaart && d3Kaart.isStyleLoaded()'))
    check('zonder thema: bevolkingsdichtheid gekozen', pg.evaluate("$('theme').value") == 'bevolkingsdichtheid_inwoners_per_km2')
    hoog = pg.evaluate("d3Data().features.filter(f=>f.properties.h>0).length"); check('blokken met hoogte', hoog > 200, hoog)
    pg.select_option('#d3Thema', 'gemiddelde_woningwaarde'); pg.wait_for_timeout(1500)
    check('thema in 3D wisselt ook de 2D-kaart', pg.evaluate("$('theme').value") == 'gemiddelde_woningwaarde' and 'WOZ' in pg.inner_text('#d3Leg'))
    pg.mouse.move(720, 520); pg.wait_for_timeout(800); check('pop-up bij aanwijzen', 'WOZ' in (pg.evaluate("document.querySelector('.d3-pop')?.innerText") or ''))
    pg.fill('#d3Hoogte', '3'); pg.dispatch_event('#d3Hoogte', 'input'); check('hoogteschuif', pg.inner_text('#d3HoogteW') == '3×')
    pg.click('#d3Draai'); pg.wait_for_timeout(700); b1 = pg.evaluate('d3Kaart.getBearing()'); pg.wait_for_timeout(700)
    check('langzaam draaien', pg.evaluate('d3Kaart.getBearing()') != b1); pg.click('#d3Draai')
    pg.click('#d3Boven'); pg.wait_for_timeout(1600); check('van boven', abs(pg.evaluate('d3Kaart.getPitch()')) < 1)
    pg.select_option('#d3Thema', 'tr_aantal_inwoners'); pg.wait_for_timeout(1200); check('uitschieters afgetopt en vermeld', 'afgetopt' in pg.inner_text('#d3Leg'))
    pg.click('#d3Schuin'); pg.wait_for_timeout(1600); pg.mouse.move(10, 880); pg.screenshot(path=os.path.join(UIT, '3d.png'))
    pg.keyboard.press('Escape'); pg.wait_for_timeout(300); check('Esc sluit', not pg.is_visible('#d3'))
    check('geen JS-fouten', not fout, fout)
    m = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True).new_page(); m.goto(U); m.wait_for_timeout(1500)
    check('mobiel: geen 3D-knop', not m.is_visible('#btn3D'))
    b.close()
print(f'{len(ok)} goed, {len(mis)} fout'); print('fouten:', mis)
