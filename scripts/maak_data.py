"""Zet de ruwe downloads in bron-downloads/ om naar de kaartdata in data/.

Gebruik (vanuit de projectmap):
    npm install
    pip install shapely pyproj
    python3 scripts/maak_data.py

Stappen: buurten -> gemeentegrenzen -> natuur -> wegen -> trein -> bus ->
voorzieningen -> Zuid-Holland/Nederland-referentie.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRON = os.path.join(ROOT, 'bron-downloads')
DATA = os.path.join(ROOT, 'data')
SCRIPTS = os.path.join(ROOT, 'scripts')
MAPSHAPER = os.path.join(ROOT, 'node_modules', '.bin', 'mapshaper')

REGIO = {'Bodegraven-Reeuwijk', 'Gouda', 'Krimpenerwaard', 'Waddinxveen', 'Zuidplas'}


def ms(*args):
    """mapshaper aanroepen in de data-map."""
    subprocess.run([MAPSHAPER, *args], cwd=DATA, check=True)


def run_script(name, *args):
    subprocess.run([sys.executable, os.path.join(SCRIPTS, name), *args], cwd=DATA, check=True)


def buurt_props(p, keep):
    """Eigenschappen die een buurt in de kaart krijgt (ook gebruikt door ververs_buurtcijfers.py)."""
    q = {k: p.get(k) for k in keep}
    inw = p.get('aantal_inwoners') or 0
    for src, dst in [('aantal_personen_met_een_alg_bijstandsuitkering_tot', 'bijstand_per_1000'),
                     ('aantal_personen_met_een_ww_uitkering_totaal', 'ww_per_1000')]:
        v = p.get(src)
        # per 1.000 inwoners, alleen voor buurten vanaf 200 inwoners
        q[dst] = round(v / inw * 1000, 1) if isinstance(v, (int, float)) and v >= 0 and inw >= 200 else None
    # relatieve varianten van absolute aantallen (toegevoegd 7-11-2026)
    v = p.get('aantal_bedrijfsvestigingen')
    q['bedrijven_per_1000_inwoners'] = round(v / inw * 1000, 1) if isinstance(v, (int, float)) and v >= 0 and inw >= 200 else None
    won = p.get('woningvoorraad') or 0
    v = p.get('aantal_nieuwbouw_woningen')
    q['nieuwbouw_per_1000_woningen'] = round(v / won * 1000, 1) if isinstance(v, (int, float)) and v >= 0 and won >= 50 else None
    return q


# Toegevoegd op 7-11-2026 (tweede ronde thema's). Elk veld hier heeft ook een regel in data/spec.json en THEMES.
KEEP_EXTRA = [
    'percentage_personen_15_tot_25_jaar', 'percentage_personen_25_tot_45_jaar', 'percentage_personen_45_tot_65_jaar',
    'percentage_met_herkomstland_nederland', 'percentage_met_herkomstland_uit_europa_excl_nl',
    'percentage_met_herkomstland_buiten_europa', 'geboorte_totaal', 'geboortes_per_1000_inwoners',
    'gemiddelde_huishoudsgrootte', 'omgevingsadressendichtheid',
    'percentage_huurwoningen', 'perc_huurwoningen_in_bezit_overige_verhuurders', 'percentage_eengezinswoning',
    'percentage_meergezinswoning', 'percentage_onbewoond',
    'percentage_aardgaswoningen', 'gemiddelde_elektriciteitsteruglevering',
    'voortgezet_onderwijs_gem_afstand_in_km', 'vmbo_gemiddelde_afstand_in_km', 'havo_vwo_gemiddelde_afstand_in_km',
    'kinderdagverblijf_gemiddelde_afstand_in_km', 'buitenschoolse_opvang_gem_afstand_in_km',
    'apotheek_gemiddelde_afstand_in_km', 'huisartsenpost_gemiddelde_afstand_in_km',
    'brandweerkazerne_gemiddelde_afstand_in_km', 'overstapstation_gemiddelde_afstand_in_km',
    'bibliotheek_gemiddelde_afstand_in_km', 'zwembad_gemiddelde_afstand_in_km',
]


def keep_list(first_props):
    keep = ['buurtcode', 'buurtnaam', 'wijknaam', 'gemeentecode', 'gemeentenaam',
            'aantal_inwoners', 'bevolkingsdichtheid_inwoners_per_km2',
            'percentage_personen_65_jaar_en_ouder', 'percentage_personen_0_tot_15_jaar',
            'perc_huurwoningen_in_bezit_woningcorporaties', 'percentage_koopwoningen',
            'gemiddelde_woningwaarde', 'aantal_bedrijfsvestigingen',
            'treinstation_gemiddelde_afstand_in_km', 'percentage_woningen_met_zonnestroom',
            'percentage_aardgasvrije_woningen', 'woningvoorraad', 'aantal_huishoudens',
            'oppervlakte_land_in_ha', 'huisartsenpraktijk_gemiddelde_afstand_in_km',
            'grote_supermarkt_gemiddelde_afstand_in_km', 'basisonderwijs_gemiddelde_afstand_in_km',
            'ziekenhuis_incl_buitenpolikliniek_gem_afst_in_km',
            'oprit_hoofdverkeersweg_gemiddelde_afstand_in_km',
            'aantal_personen_met_een_alg_bijstandsuitkering_tot',
            'aantal_personen_met_een_ww_uitkering_totaal', 'percentage_eenpersoonshuishoudens',
            'percentage_huishoudens_met_kinderen', 'personenautos_per_huishouden',
            'aantal_nieuwbouw_woningen', 'perc_bouwjaar_afgelopen_10_jaar', 'gemiddeld_aardgasverbruik']
    keep += [k for k in first_props if k.startswith('aantal_bedrijven_')]
    return keep + KEEP_EXTRA


def buurten():
    d = json.load(open(os.path.join(BRON, 'cbs-buurten-2024-regio.geojson')))
    keep = keep_list(d['features'][0]['properties'])
    out = []
    for f in d['features']:
        p = f['properties']
        if p['gemeentenaam'] not in REGIO:
            continue
        out.append({'type': 'Feature', 'properties': buurt_props(p, keep), 'geometry': f['geometry']})
    json.dump({'type': 'FeatureCollection', 'features': out}, open(os.path.join(DATA, 'region.geojson'), 'w'))
    ms('region.geojson', '-simplify', '12%', 'keep-shapes', '-o', 'buurten.json', 'force',
       'precision=0.00001', 'format=geojson')
    ms('region.geojson', '-dissolve', 'gemeentecode', 'copy-fields=gemeentenaam', '-simplify', '12%',
       'keep-shapes', '-o', 'gemeenten.json', 'force', 'precision=0.00001', 'format=geojson')
    print('buurten:', len(out))


def natuur():
    d = json.load(open(os.path.join(BRON, 'natuurnetwerk-zh.json')))
    d.pop('crs', None)
    for f in d['features']:
        f['properties'] = {'type': f['properties'].get('Onderverdeling'), 'ha': f['properties'].get('Oppervlakte')}
    json.dump(d, open(os.path.join(DATA, 'nnn_in.json'), 'w'))
    d = json.load(open(os.path.join(BRON, 'natura2000.geojson')))
    for f in d['features']:
        p = f['properties']
        f['properties'] = {'naam': p.get('naam_n2k'), 'bescherming': p.get('beschermin'), 'status': p.get('status')}
    json.dump(d, open(os.path.join(DATA, 'n2k_in.json'), 'w'))
    ms('nnn_in.json', '-clip', 'gemeenten.json', '-simplify', '15%', 'keep-shapes',
       '-each', 'ha=Math.round(this.area/10000*10)/10', '-o', 'nnn.json', 'force', 'precision=0.00001', 'format=geojson')
    ms('n2k_in.json', '-clip', 'gemeenten.json', '-simplify', '20%', 'keep-shapes',
       '-each', 'ha=Math.round(this.area/10000)', '-o', 'n2k.json', 'force', 'precision=0.00001', 'format=geojson')
    n2k = json.load(open(os.path.join(DATA, 'n2k.json')))
    n2k['features'] = [f for f in n2k['features'] if f['properties']['ha'] > 0]   # snippers langs de grens weg
    json.dump(n2k, open(os.path.join(DATA, 'n2k.json'), 'w'), separators=(',', ':'))
    # oppervlakte natuur per gemeente (voor het gemeenteprofiel)
    from shapely.geometry import shape
    from shapely.ops import transform
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 28992, always_xy=True).transform
    gm = {f['properties']['gemeentenaam']: transform(tr, shape(f['geometry'])).buffer(0)
          for f in json.load(open(os.path.join(DATA, 'gemeenten.json')))['features']}

    def area_by_gm(fn):
        res = {g: 0 for g in gm}
        for f in json.load(open(os.path.join(DATA, fn)))['features']:
            s = transform(tr, shape(f['geometry'])).buffer(0)
            for g, G in gm.items():
                res[g] += s.intersection(G).area / 1e4
        return {g: round(v) for g, v in res.items()}
    nat = {'nnn': area_by_gm('nnn.json'), 'n2k': area_by_gm('n2k.json'),
           'land': {g: round(G.area / 1e4) for g, G in gm.items()}}
    json.dump(nat, open(os.path.join(DATA, 'natuur_gm.json'), 'w'))
    print('natuur:', nat)


def wegen():
    d = json.load(open(os.path.join(BRON, 'osm-hoofdwegen.json')))
    out = []
    for e in d['elements']:
        g = e.get('geometry')
        if not g:
            continue
        t = e.get('tags', {})
        ms_ = t.get('maxspeed') or t.get('maxspeed:forward') or ''
        out.append({'type': 'Feature',
                    'properties': {'h': t.get('highway'), 'ref': t.get('ref', ''), 'naam': t.get('name', ''),
                                   'beheer': t.get('operator', ''), 'max': ms_},
                    'geometry': {'type': 'LineString', 'coordinates': [[p['lon'], p['lat']] for p in g]}})
    json.dump({'type': 'FeatureCollection', 'features': out}, open(os.path.join(DATA, 'roads_in.json'), 'w'))
    ms('roads_in.json', '-clip', 'gemeenten.json', '-dissolve', 'h,ref,naam,beheer,max', '-simplify', '25%',
       '-o', 'roads.json', 'force', 'precision=0.00001', 'format=geojson')


def ov_en_voorzieningen():
    run_script('trains.py')
    ms('rail_in.json', '-clip', 'gemeenten.json', '-dissolve', 'stop,door,n', '-simplify', '30%',
       '-o', 'rail.json', 'force', 'precision=0.00001', 'format=geojson')
    run_script('bus.py')
    ms('buslines_in.json', '-clip', 'gemeenten.json', '-simplify', '20%', '-o', 'buslines.json', 'force',
       'precision=0.00001', 'format=geojson')
    run_script('voorz.py')
    run_script('locaties.py')
    run_script('netcongestie.py')
    run_script('erfgoed.py')
    run_script('trend.py')


def referentie():
    run_script('ref.py', os.path.join(BRON, 'cbs-gemeenten-2024-nederland.geojson'))


if __name__ == '__main__':
    buurten(); natuur(); wegen(); ov_en_voorzieningen(); referentie()
    for tmp in ['region.geojson', 'nnn_in.json', 'n2k_in.json', 'roads_in.json', 'rail_in.json', 'buslines_in.json']:
        p = os.path.join(DATA, tmp)
        if os.path.exists(p):
            os.remove(p)
    print('Klaar. Bouw de kaart met: python3 scripts/bouw_kaart.py')
