"""Test van het tekenen op de kaart: balk, pen, rechthoek, cirkel, pijl, tekst, selecteren, verplaatsen,
formaat, kleur, gum, ongedaan maken, bewaren in de browser en export naar PNG/PDF.
Gebruik: .venv/bin/python tests/test_tekenen.py   (schermafbeeldingen in tests/uit/)"""
import os, sys
from playwright.sync_api import sync_playwright
UIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uit'); os.makedirs(UIT, exist_ok=True)
U = 'file://' + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'regiokaart-midden-holland.html')
ok, mis = [], []
def check(n, c, i=''):
    (ok if c else mis).append(n); print(('  ok   ' if c else '  FOUT ') + n, '' if c else i)
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
    ctx.add_init_script("try{localStorage.setItem('regiokaart-rondleiding-v1','1')}catch(e){}")
    pg = ctx.new_page(); fout = []; pg.on('pageerror', lambda e: fout.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(U); pg.wait_for_timeout(1500)
    n = lambda: pg.evaluate('tkItems.length')
    check('balk dicht bij start', pg.evaluate("getComputedStyle(document.getElementById('tekenBalk')).opacity") == '0')
    pg.click('#btnTekenen'); pg.wait_for_timeout(500)
    check('balk rolt uit, pen actief', pg.evaluate("getComputedStyle(document.getElementById('tekenBalk')).opacity") == '1' and pg.evaluate('tkTool') == 'pen')
    def sleep(x0, y0, x1, y1, stappen=12):
        pg.mouse.move(x0, y0); pg.mouse.down()
        for i in range(1, stappen + 1): pg.mouse.move(x0 + (x1 - x0) * i / stappen, y0 + (y1 - y0) * i / stappen + (8 if 0 < i < stappen else 0))
        pg.mouse.up(); pg.wait_for_timeout(100)
    c0 = pg.evaluate('JSON.stringify(map.getCenter())'); sleep(700, 300, 900, 360); check('kaart schuift niet mee', pg.evaluate('JSON.stringify(map.getCenter())') == c0); check('pen tekent een lijn', n() == 1 and pg.evaluate("tkItems[0].t==='pen' && tkItems[0].pts.length>5"))
    zonder_klik = pg.evaluate('document.querySelector(".leaflet-popup") === null'); check('tekenen opent geen buurt-pop-up', zonder_klik)
    pg.click('[data-tool=rect]'); pg.click('[data-c="#fc7c00"]'); pg.click('.tk-dikte[data-w="8"]'); sleep(950, 250, 1150, 420, 4)
    check('rechthoek oranje en dik', pg.evaluate("tkItems[1].t==='rect' && tkItems[1].c==='#fc7c00' && tkItems[1].w===8"))
    pg.click('[data-tool=cirkel]'); pg.click('[data-c="#5b0065"]'); pg.click('.tk-dikte[data-w="4"]'); sleep(800, 600, 880, 600, 4)
    check('cirkel', pg.evaluate("tkItems[2].t==='cirkel'"))
    pg.click('[data-tool=pijl]'); sleep(600, 700, 760, 620, 4); check('pijl', pg.evaluate("tkItems[3].t==='pijl'"))
    pg.click('[data-tool=tekst]'); pg.mouse.click(1000, 600); pg.wait_for_timeout(200)
    pg.keyboard.type('Hier komt de nieuwe wijk'); pg.keyboard.press('Enter'); pg.wait_for_timeout(200)
    check('tekstblokje', pg.evaluate("tkItems[4] && tkItems[4].s==='Hier komt de nieuwe wijk'") and pg.is_visible('.tk-tekst'))
    pg.click('[data-tool=tekst]'); pg.mouse.click(1200, 700); pg.wait_for_timeout(100); pg.keyboard.press('Escape'); pg.wait_for_timeout(100)
    check('leeg tekstblokje verdwijnt', n() == 5)
    pg.screenshot(path=os.path.join(UIT, 'tekenen.png'))
    # selecteren, verplaatsen, kleur, formaat
    pg.click('[data-tool=selecteer]'); pg.mouse.click(1050, 252); pg.wait_for_timeout(100)
    check('rechthoek geselecteerd met handvatten', pg.evaluate('tkSel') == 1 and pg.evaluate("document.querySelectorAll('.tk-handvat').length") == 2)
    voor = pg.evaluate('JSON.stringify(tkItems[1].pts)'); sleep(1050, 252, 1100, 302, 5)
    check('verplaatsen', pg.evaluate('JSON.stringify(tkItems[1].pts)') != voor)
    pg.click('[data-c="#1d1d1b"]'); check('kleur van selectie wijzigt', pg.evaluate("tkItems[1].c") == '#1d1d1b')
    h = pg.locator('.tk-handvat').nth(1).bounding_box(); voor = pg.evaluate('JSON.stringify(tkItems[1].pts)')
    sleep(h['x'] + 6, h['y'] + 6, h['x'] + 60, h['y'] + 40, 5); check('formaat aanpassen', pg.evaluate('JSON.stringify(tkItems[1].pts)') != voor)
    # zoomen: tekening blijft op dezelfde plek op de kaart
    ll = pg.evaluate('JSON.stringify(tkItems[2].pts)'); pg.evaluate('map.setZoom(map.getZoom()+1); 0'); pg.wait_for_timeout(600)
    check('zoomen verandert de tekening niet', pg.evaluate('JSON.stringify(tkItems[2].pts)') == ll); pg.evaluate('regioInBeeld(false); 0'); pg.wait_for_timeout(400)
    # gum en ongedaan maken
    pg.click('[data-tool=gum]'); a = n(); pt = pg.evaluate("(()=>{const q=map.latLngToContainerPoint(L.latLng(...tkItems[3].pts[0])); const r=map.getContainer().getBoundingClientRect(); return [q.x+r.left,q.y+r.top]})()")
    pg.mouse.click(pt[0], pt[1]); pg.wait_for_timeout(100); check('gum wist de pijl', n() == a - 1)
    pg.keyboard.press('Meta+z'); pg.wait_for_timeout(100); check('ongedaan maken zet hem terug', n() == a)
    # bewaren in de browser
    pg.reload(); pg.wait_for_timeout(1500); check('na herladen nog aanwezig', n() == 5 and pg.is_visible('.tk-tekst'))
    check('balk dicht na herladen, kaart te bewegen', not pg.evaluate("document.getElementById('tekenvlak').classList.contains('aan')"))
    # export
    with pg.expect_download(timeout=60000) as d: pg.click('#btnMapPng')
    d.value.save_as(os.path.join(UIT, 'tekenen-export.png'))
    with pg.expect_download(timeout=60000) as d: pg.click('#btnMapPdf')
    d.value.save_as(os.path.join(UIT, 'tekenen-export.pdf')); check('export PNG en PDF', True)
    # dataweergave
    pg.click('#wissel button[data-w=data]'); pg.wait_for_timeout(400); pg.click('#btnTekenen'); pg.wait_for_timeout(400)
    check('werkt in de dataweergave', pg.evaluate("document.getElementById('tekenvlak').classList.contains('aan')"))
    pg.click('#tkWis'); pg.wait_for_timeout(200); check('alles wissen', n() == 0)
    print('fouten:', fout); print(f'{len(ok)} goed, {len(mis)} fout'); b.close()
sys.exit(1 if mis or fout else 0)
