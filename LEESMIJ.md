# Regiokaart Midden-Holland

Interactieve kaart en kennisbank voor Bodegraven-Reeuwijk, Gouda, Krimpenerwaard, Waddinxveen en Zuidplas.

**Direct bekijken:** open `regiokaart-midden-holland.html` in Chrome of Edge.

**Verder bouwen met Claude Code:**
1. Pak deze map uit, bijvoorbeeld in `Documenten/regiokaart`.
2. Open een terminal in die map en start `claude`.
3. Claude Code leest `CLAUDE.md` met de volledige overdracht. Zeg bijvoorbeeld: "Lees CLAUDE.md en bouw de kaart opnieuw."

Voor wie het zelf wil doen:

```
npm install
pip install shapely pyproj playwright && playwright install chromium
python3 scripts/maak_data.py    # ruwe downloads -> data/
python3 scripts/bouw_kaart.py   # data -> regiokaart-midden-holland.html
python3 tests/test_kaart.py     # controle
```

Bronnen: CBS (CC BY 4.0) via PDOK, Provincie Zuid-Holland, RVO, Rijkswaterstaat (AHN), Kadaster/PDOK, © OpenStreetMap-bijdragers (ODbL).
