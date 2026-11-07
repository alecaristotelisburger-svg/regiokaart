"""Rooktest: opent de gebouwde kaart offline in headless Chromium, zet lagen aan,
maakt beide PDF's en controleert dat er geen JavaScript-fouten zijn.

Gebruik: pip install playwright && playwright install chromium
         python3 tests/test_kaart.py
Uitvoer: tests/uit/ (schermafbeelding + twee PDF's)
"""
import asyncio, os, pathlib
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
UIT = ROOT / 'tests' / 'uit'; UIT.mkdir(exist_ok=True)

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        ctx = await br.new_context(viewport={'width': 1400, 'height': 900}, accept_downloads=True)
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        # alles van buiten blokkeren, zoals in de gedeelde link-weergave
        async def route(r):
            return await (r.continue_() if r.request.url.startswith('file:') else r.abort())
        await pg.route('**/*', route)
        await pg.goto((ROOT / 'regiokaart-midden-holland.html').as_uri()); await pg.wait_for_timeout(1200)
        await pg.select_option('#theme', 'perc_huurwoningen_in_bezit_woningcorporaties')
        for lyr in ['#lyrRail', '#lyrOv', '#lyrVz', '#lyrRoads', '#lyrNnn', '#lyrN2k']:
            await pg.check(lyr)
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(UIT / 'kaart.png'))
        async with pg.expect_download() as d: await pg.click('#btnMapPdf')
        await (await d.value).save_as(str(UIT / 'kaart.pdf'))
        await pg.select_option('#profGm', 'GM0513')
        async with pg.expect_download() as d: await pg.click('#btnProfPdf')
        await (await d.value).save_as(str(UIT / 'gemeenteprofiel-gouda.pdf'))
        status = await pg.inner_text('#status')
        await br.close()
    assert '248 buurten' in status, status
    assert not errs, errs
    print('OK:', status, '| uitvoer in', UIT)

asyncio.run(main())
