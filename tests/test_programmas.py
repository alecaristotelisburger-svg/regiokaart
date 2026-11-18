"""Test van het blok Programma's: thema-knoppen, vinkjes, thema-knoppen, link en telefoon. Gebruik: .venv/bin/python tests/test_programmas.py"""
import sys
from playwright.sync_api import sync_playwright
import os; S=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),'uit'); os.makedirs(S,exist_ok=True); U='file:///Users/alecburger/MEGA/regiokaart/regiokaart-midden-holland.html'
ok=[];mis=[]
def check(n,c,i=''):
    (ok if c else mis).append(n); print(('  ok   ' if c else '  FOUT ')+n, '' if c else i)
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={'width':1440,'height':900}); ctx.add_init_script("try{localStorage.setItem('regiokaart-rondleiding-v1','1')}catch(e){}"); pg=ctx.new_page()
    fout=[]; pg.on('pageerror', lambda e: fout.append(str(e)))
    pg.goto(U); pg.wait_for_timeout(1500)
    print('  ontbrekende thema-sleutels:', pg.evaluate("PROGRAMMAS.flatMap(p=>p.themas.filter(k=>!THEMES.some(t=>t.key===k)))"), '| lagen:', pg.evaluate("PROGRAMMAS.flatMap(p=>p.lagen.map(l=>l[0]).filter(id=>!document.getElementById(id)))"))
    check('blok staat boven Thema per buurt', pg.evaluate("document.getElementById('secProg').nextElementSibling.querySelector('#themeH')!==null"))
    check('dicht bij start', not pg.is_visible('#progInhoud'))
    pg.screenshot(path=S+'/start.png', clip={'x':0,'y':0,'width':360,'height':900})
    for k in ['economie','wonen','mens','duurzaam','mobiliteit']:
        pg.click(f'#progKnoppen [data-p={k}]'); pg.wait_for_timeout(200)
        check(f'programma {k} toont thema\'s en lagen, geen startweergave', pg.evaluate("document.querySelectorAll('.progthema').length>0 && document.querySelectorAll('.proglagen input').length>0 && !document.querySelector('.progstart')"))
        pg.evaluate("document.getElementById('secProg').scrollIntoView()"); pg.wait_for_timeout(100)
        pg.screenshot(path=S+f'/{k}.png')
    # vinkje in programma = echte laag
    pg.click('#progKnoppen [data-p=economie]'); pg.wait_for_timeout(200)
    pg.click('.proglagen label:has-text("Bedrijventerreinen") input'); pg.wait_for_timeout(500)
    check('vinkje Bedrijventerreinen zet de laag aan', pg.evaluate("$('lyrBedr').checked"))
    pg.click('.proglagen label:has-text("onderwijs") input'); pg.wait_for_timeout(300)
    check('voorzieningen alleen onderwijs', pg.evaluate("$('lyrVz').checked && [...document.querySelectorAll('#vzcats input:checked')].map(i=>i.dataset.c).join()==='onderwijs'"))
    pg.uncheck('#lyrBedr'); pg.wait_for_timeout(200)
    check('uitzetten in Kaartlagen werkt door in programma', not pg.evaluate("document.querySelector('.proglagen label:nth-child(1) input').checked"))
    pg.click('.progmeer'); pg.wait_for_timeout(100); n=pg.evaluate("document.querySelectorAll('.progthema').length"); check('meer toont alle thema\'s', n==11, n)
    pg.click('.progthema[data-k=sl_hoog]'); pg.wait_for_timeout(200); check('thema-knop kiest thema', pg.evaluate("$('theme').value")=='sl_hoog' and pg.evaluate("document.querySelector('.progthema[data-k=sl_hoog]').classList.contains('aan')"))
    h=pg.evaluate("stateHash()"); check('programma in link', 'programma=economie' in h, h)
    p2=ctx.new_page(); p2.goto(U+h); p2.wait_for_timeout(1500); check('link opent programma', p2.is_visible('#progInhoud') and p2.evaluate("progKeuze")=='economie')
    pg.click('#progKnoppen [data-p=economie]'); pg.wait_for_timeout(100); check('nogmaals klikken sluit', not pg.is_visible('#progInhoud'))
    m=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True).new_page(); m.goto(U); m.wait_for_timeout(1200); m.tap('#toggle'); m.wait_for_timeout(300); m.tap('#progKnoppen [data-p=mens]'); m.wait_for_timeout(300)
    m.evaluate("document.getElementById('secProg').scrollIntoView()"); m.screenshot(path=S+'/mobiel.png'); check('werkt op telefoon', m.is_visible('#progInhoud'))
    print('fouten:', fout); print(f'{len(ok)} goed, {len(mis)} fout'); b.close()
