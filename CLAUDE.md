# Regiokaart Midden-Holland – projectoverdracht

Dit project is gestart in een gesprek met Claude op claude.ai (7 november 2026) en gaat hier verder in Claude Code. Lees dit bestand eerst. Het beschrijft wat er is, waarom het zo gebouwd is, en wat nog openstaat.

## Wat het is

Een interactieve kaart en kennisbank voor **Regio Midden-Holland**: de intergemeentelijke samenwerking van Bodegraven-Reeuwijk, Gouda, Krimpenerwaard, Waddinxveen en Zuidplas (CBS 2024: 251.955 inwoners). De regio wil een plek worden waar ambtenaren en bestuurders informatie halen. De kaart is daar het eerste product van.

De gebruiker werkt bij de regio. Hij is geen ontwikkelaar: hij communiceert in het Nederlands, werkt vaak vanaf zijn telefoon en wil resultaten die hij direct kan delen. Schrijf alle teksten in de kaart en in antwoorden in helder Nederlands.

## Hoe het gebouwd is

- **Eén zelfstandig HTML-bestand** (`regiokaart-midden-holland.html`, ca. 2 MB). Alle data, Leaflet 1.9.4 en jsPDF 2.5.1 zitten erin. Er is geen server nodig.
- **Waarom zelfstandig:** het bestand wordt ook gepubliceerd als artifact (gedeelde link op claude.ai). Die omgeving blokkeert `fetch` en externe afbeeldingen. Daarom werkt de link zonder achtergrondkaart. Achtergrondkaart (BRT), satelliet (PDOK-luchtfoto) en NAP-hoogte (AHN-WMS) laden alleen als je het bestand in een gewone browser opent. Een melding in het paneel legt dat uit.
- **Bron versus resultaat:** bewerk altijd `src/src.html`, nooit het gebouwde bestand. `src.html` bevat placeholders (`<!--LEAFLET_CSS-->`, `<!--LEAFLET_JS-->`, `/*DATA*/null`) die `scripts/bouw_kaart.py` vult.
- **Rendering:** Leaflet met `preferCanvas: true`. Dat is nodig voor de PDF-export: die tekent de canvassen en tegels van de kaart in één canvas.
- **Downloads in de artifact** lopen via de `downloads`-capability (`window.claude.use('downloads')`). In een gewone browser valt de code terug op een normale `<a download>`. Zie `saveFile()` in `src.html`.

## Mappen

```
src/src.html            bron van de pagina (HTML/CSS/JS)
src/logo.jpg            logo Regio Midden-Holland (aangeleverd door gebruiker)
data/*.json             voorbewerkte kaartdata (uitvoer van maak_data.py) + spec.json (handmatig)
data/provincie_2024.geojson  CBS-provinciegrenzen (cartomap/nl) voor het afbakenen van Zuid-Holland
bron-downloads/         ruwe bestanden zoals de gebruiker ze heeft gedownload
scripts/maak_data.py    ruwe downloads -> data/ (roept trains.py, bus.py, voorz.py, ref.py aan)
scripts/bouw_kaart.py   src + data + bibliotheken -> regiokaart-midden-holland.html
tests/test_kaart.py     rooktest (offline, maakt beide PDF's)
```

## Werkwijze

```
npm install                      # leaflet, jspdf, mapshaper
pip install shapely pyproj playwright && playwright install chromium
python3 scripts/maak_data.py     # alleen nodig als bron-downloads veranderen
python3 scripts/bouw_kaart.py
python3 tests/test_kaart.py      # moet "OK" geven; bekijk tests/uit/*.pdf en kaart.png
```

**Op de Mac van de gebruiker (vanaf 7 november 2026):** er is geen Node. Leaflet en jsPDF zijn met `curl` van cdnjs in `node_modules/<pakket>/dist/` gezet (zelfde versies, gecontroleerd tegen de eerdere bouw). Python-pakketten en Playwright staan in `.venv/`: gebruik `.venv/bin/python tests/test_kaart.py`. `pdftoppm` ontbreekt; PDF's zijn met het Read-hulpmiddel te bekijken (hele PDF) of met PyMuPDF (`fitz`, in `.venv`) uit te snijden.
**Zonder mapshaper een CBS-veld toevoegen:** zet het in `KEEP_EXTRA` (`scripts/maak_data.py`), in `data/spec.json` en in `THEMES` (`src.html`) en draai `.venv/bin/python scripts/ververs_buurtcijfers.py`. Dat ververst alleen de eigenschappen in `data/buurten.json` (grenzen blijven) en draait `ref.py`. Afstandsthema's met locaties: `LOCS` in `src.html` + soort in `scripts/locaties.py`.

Controleer na elke wijziging de PDF's en de schermafbeelding visueel (bijvoorbeeld met `pdftoppm -png`). Het gemeenteprofiel heeft eerder last gehad van afgekapte kolommen en lege pagina's.

## Data en bronnen

| Laag | Bron | Bestand |
|---|---|---|
| Buurtcijfers + grenzen | CBS Wijken en Buurten 2024, PDOK OGC API (`collections/buurten`, bbox regio) | `cbs-buurten-2024-regio.geojson` |
| Zuid-Holland / Nederland | CBS gemeenten 2024, PDOK (`collections/gemeenten`) | `cbs-gemeenten-2024-nederland.geojson` |
| Natuurnetwerk Nederland | Provincie Zuid-Holland WFS `landelijk_gebied:NNN` | `natuurnetwerk-zh.json` |
| Natura 2000 | RVO via PDOK OGC API | `natura2000.geojson` |
| Hoofdwegen | OpenStreetMap (Overpass) | `osm-hoofdwegen.json` |
| Treinroutes | OpenStreetMap (Overpass, `route=train`) | `osm-treinroutes.json` |
| Buslijnen en haltes | OpenStreetMap (Overpass Turbo-export, 3 stroken) | `osm-busroutes/*.geojson` |
| Voorzieningen | OpenStreetMap (Overpass Turbo-export) | `osm-voorzieningen.geojson` |
| Locaties bij afstandsthema's ("Toon … op de kaart") | OpenStreetMap (Overpass, door Claude Code opgehaald op 7-11-2026, bbox `51.81,4.44,52.20,4.98`, in 2 delen wegens 504) → `scripts/locaties.py` houdt regio + 5 km | `osm-locaties-1.json` (supermarkt, ziekenhuis, motorway_junction, railway=station), `osm-locaties-2.json` (doctors/general_practitioner, school), `osm-locaties-3.json` (pharmacy, childcare/kindergarten, fire_station, library, zwembaden). Geen vinkje bij huisartsenpost en kinderopvang (OSM te onvolledig) en overstapstation (OSM kent geen intercitystops) |
| Achtergrond, luchtfoto, AHN | PDOK, live | – |

Belangrijk:
- **CBS-geheimhouding:** de waarden -99997 en -99995 betekenen geheim of onbekend. `clean()` maakt er `null` van.
- **Aggregatie:** gemeente-, regio-, ZH- en NL-waarden worden op dezelfde manier berekend volgens `data/spec.json`: `sum`, `w` (gewogen naar inwoners, woningen of huishoudens) of `ratio` (bijvoorbeeld per 1.000 inwoners). De JS (`aggregateFeats`) en Python (`ref.py`) moeten dezelfde regels volgen. Voeg je een thema toe, zet het dan in `THEMES` (src.html) én in `spec.json`.
- **Zorg en inkomen** (Wmo, jeugdzorg, laag inkomen) zijn voor 2024 nog niet per buurt gepubliceerd. Gebruik daarvoor eventueel 2023.
- **Stationsnamen** staan niet in de OSM-export. Ze worden in `trains.py` gekoppeld via de vaste coördinaten in `KNOWN`.
- **OpenStreetMap** is niet volledig (bijvoorbeeld 7 "gemeentehuizen" voor 5 gemeenten, mogelijk ontbrekende buslijnen). De kaart zegt dat ook. Voor officieel gebruik: DUO (scholen), LRZa (huisartsen), Qbuzz/NDOV (OV).

## Downloads verkrijgen

De sandbox van Claude kon PDOK en Overpass niet bereiken. De gebruiker opende daarom de links zelf en uploadde het resultaat. Overpass-api.de gaf soms "too busy" of 406. Wat wel werkte:
- **Zware vragen opknippen** in stroken (zie de buslijnen).
- **Overpass Turbo gebruiken** (`https://overpass-turbo.eu/?Q=<query>&R`, daarna Export → GeoJSON → download).
- **Een andere server proberen:** overpass.private.coffee als reserve.

Kan Claude Code hier wel het internet op, dan kunnen deze downloads ook direct.

## Huisstijl

Afgeleid van het aangeleverde logo. De website zelf kon niet worden uitgelezen.
- Paars `#5b0065` (hoofdkleur, koppen, knoppen), magenta `#ed56c2` (kicker, accenten), oranje `#fc7c00` (hover, trein, accent), crème `#fbf2ee` (tekst op paars).
- Sequentiële buurtkleuren: `#f1d4ec → #d995ce → #bb55ae → #8a2486 → #5b0065` (kwintielen, dubbele klassegrenzen worden samengevoegd).
- Lagen: wegen grijs, trein oranje, bus `#d63fae`, NNN groen, Natura 2000 donkergroen. Voorzieningen: onderwijs `#2a78d6`, zorg `#d6392f`, sport `#00968a`, maatschappelijk `#b07d00` (gevalideerd op kleurenblindheid).
- Letter: Barlow / Barlow Semi Condensed (Google Fonts). Dit is een benadering, het echte huisstijllettertype is niet bekend.

## Wensen en open punten

1. **Woningbouwlocaties:** de projectenlijst van het regionale woningbouwprogramma (bij de regio of gemeenten). Daarna de **opgavenkaart**: woningbouw naast netcongestie en bodemdaling, het idee met de meeste meerwaarde voor bestuurders.
2. **Netcongestie:** capaciteitskaart Netbeheer Nederland / Stedin open data.
3. **Bodemkwaliteit:** opvragen bij de Omgevingsdienst Midden-Holland. **Bodemdaling:** bodemdalingskaart.nl.
4. **Klimaat:** Klimaateffectatlas (wateroverlast, overstromingsdiepte, hitte).
5. **Bevolkingsprognose** 2030/2040 (provincie). **Trends** over meerdere CBS-jaren.
6. **Sociaal domein 2023**, GGD Hollands Midden-gezondheidsmonitor, Leefbaarometer.
7. **Reistijdkaarten** (isochronen) voor de bereikbaarheidslobby, verkeersongevallen.
8. **Regionale afspraken en projecten op de kaart**, met contactpersonen (de kennisbankfunctie).
9. **Hosting op een eigen domein** van de regio. Sinds 7-11-2026 staat de kaart op GitHub Pages (zie onder), waar de achtergrondkaart werkt. Een eigen domein kan later aan GitHub Pages worden gekoppeld (CNAME).

## Gepubliceerde versie

**Website (hoofdlink om te delen):** https://alecaristotelisburger-svg.github.io/regiokaart/ via GitHub Pages, branch `main`, map `/`. `index.html` stuurt door naar `regiokaart-midden-holland.html`. Hier laden achtergrondkaart, luchtfoto en AHN wel. Openbaar: iedereen met het adres kan de kaart openen.

**Repository:** https://github.com/alecaristotelisburger-svg/regiokaart (openbaar). De projectmap staat lokaal in `~/MEGA/regiokaart` (MEGA-cloudmap; `.venv` en `node_modules` staan niet in git en moeten na een nieuwe checkout opnieuw worden gemaakt, zie Werkwijze).

**Git-werkwijze met de gebruiker:** Claude maakt commits; de gebruiker pusht zelf met **GitHub Desktop** ("Push origin"), want Claude kan niet bij GitHub inloggen en `gh` is niet geïnstalleerd. Alleen wat op `main` staat komt op de website. Werk je op een andere branch, zeg dan dat die nog in GitHub Desktop moet worden samengevoegd (of via een pull request op github.com) voordat het online staat. Bouw `regiokaart-midden-holland.html` altijd opnieuw vóór een commit, want de website toont het gebouwde bestand.

**Artifact op claude.ai** (tweede link, privé tenzij de gebruiker hem deelt), eigendom van de gebruiker: https://claude.ai/artifact/DRHUJLsJ6em15MuwMzyrEE (slug `6491aa31-26c0-46a2-96dc-77d86591b833`, capability `downloads`). Bijwerken kan alleen vanuit een Claude-sessie met de artifact-tools. Anders levert Claude Code het gebouwde HTML-bestand aan.
