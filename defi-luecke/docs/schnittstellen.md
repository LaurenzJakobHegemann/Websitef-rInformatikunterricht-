# Schnittstellen zwischen den Pipeline-Schritten

Verbindlicher Datenvertrag zwischen den Modulen. Feldnamen sind englisch, damit sie im Code gleich heißen. Alle Pfade relativ zum Projektordner `defi-luecke/`, `<region>` ist der Schlüssel aus `config/regions.yaml`.

## Belegte Fakten zu den Rohdaten (geprüft am 15.11.2026)

### Zensus 2022, 100-m-Gitter
- Download: `https://www.destatis.de/static/DE/zensus/gitterdaten/Zensus2022_Bevoelkerungszahl.zip` (zensus2022.de leitet inzwischen auf destatis.de um).
- ZIP-Inhalt: `Zensus2022_Bevoelkerungszahl_100m-Gitter.csv` (Trennzeichen `;`), `Datensatzbeschreibung_Bevoelkerungszahl_Gitterzellen.xlsx` und 1-km- bzw. 10-km-Dateien.
- Spalten laut Datensatzbeschreibung: `GITTER_ID_100m`, `x_mp_100m`, `y_mp_100m`, `Bevoelkerungszahl`.
- **Tatsächliche Kopfzeile der CSV:** `GITTER_ID_100m;x_mp_100m;y_mp_100m;Einwohner`. Die Wertespalte heißt also anders als dokumentiert. Der Code akzeptiert beide Namen und protokolliert, welcher gefunden wurde.
- `x_mp_100m`/`y_mp_100m` sind Zellmittelpunkte in EPSG:3035.
- Sonderzeichen `–` in Wertespalten bedeutet „genau null oder auf null geändert“. Zellen ohne Einwohner fehlen in der Datei.
- Geheimhaltung: Cell-Key-Methode (stochastische Überlagerung), Summen können abweichen.
- Lizenz: dl-de/by-2-0. Vermerk: „© Statistische Ämter des Bundes und der Länder, 2024“.

### BKG VG250-EW (Stand 31.12.2025)
- Download: `https://daten.gdz.bkg.bund.de/produkte/vg/vg250-ew_ebenen_1231/aktuell/vg250-ew_12-31.utm32s.gpkg.ebenen.zip`
- GeoPackage `vg250-ew_ebenen_1231/DE_VG250.gpkg`, CRS EPSG:25832. Ebenen `vg250_gem`, `vg250_vwg`, `vg250_krs`. Attributnamen in Großbuchstaben (`AGS`, `ARS`, `GEN`, `BEZ`, `GF`, `EWZ`, `KFL`, `SN_L`, `SN_R`, `SN_K`, `SN_V1`, `SN_V2`, `SN_G`).
- Landflächen: Produktdokumentation `dokumentation/vg250.pdf`, Abschnitt 3.2.3: „Zur ausschließlichen Darstellung ohne die Gebiete auf Nord- oder Ostsee bzw. Bodensee ist auf GF = 4 zu filtern.“
- `EWZ`: Einwohnerzahl des Statistischen Bundesamtes zum 31.12. des Jahres.
- Kreis 07231 = „Bernkastel-Wittlich“, Landkreis, EWZ 112751, KFL 1167.9 km².
- Gemeinde → Verbandsgemeinde: `ARS` der Gemeinde beginnt mit den 9 Stellen des `ARS` der Verwaltungsgemeinschaft (`SN_L`+`SN_R`+`SN_K`+`SN_V1`+`SN_V2`).
- Quellenvermerk laut `nutzungsbedingungen_vg250.pdf`: „© BKG (Jahr des letzten Datenbezugs) dl-de/by-2-0“, mit Links auf https://www.bkg.bund.de und https://www.govdata.de/dl-de/by-2-0.

### OpenStreetMap
- Overpass-Endpunkte konfigurierbar in `config/params.yaml` (`osm.overpass_urls`, in dieser Reihenfolge versucht).
- Scheitern alle Endpunkte, bricht `fetch` mit einer Anleitung ab: Abfrage manuell ausführen und als Snapshot-Datei ablegen (siehe `data/raw/SOURCES.md`).

## Dateien

| Datei | Erzeugt von | Inhalt |
|---|---|---|
| `data/raw/osm_aed_<region>_<YYYY-MM-DD>.json` oder `.geojson` | fetch_osm | unveränderte Overpass-Antwort (AEDs); `.geojson` = Export aus overpass-turbo |
| `data/raw/osm_candidates_<region>_<YYYY-MM-DD>.json` oder `.geojson` | fetch_osm | unveränderte Overpass-Antwort (Kandidatenorte Variante B) |
| `data/raw/zensus2022/…` | load_census | ZIP und Datensatzbeschreibung |
| `data/raw/vg250/…` | fetch_boundaries | ZIP, entpackt |
| `data/interim/<region>.gpkg` | fetch (M1) | Ebenen siehe unten, alle in EPSG:3035 |
| `data/interim/<region>_fetch_report.json` | fetch (M1) | Snapshot-Dateinamen, Datenstände, Plausibilitätsergebnisse |
| `data/processed/<region>/metrics_<level>.csv` | coverage | Kennzahlen, `level` ∈ `municipality`, `vg`, `district` |
| `data/processed/<region>/cell_coverage.parquet` oder `.csv` | coverage | Distanz je Zelle und Szenario |
| `data/processed/<region>/optimize_<variant>_<scope>.csv` | optimize | Ranglisten |
| `data/processed/<region>/validation_<area>.json` | validate | Recall, Precision, Intervalle |
| `data/processed/<region>/figures/*.png|svg` | figures | Grafiken |
| `web/public/data/<region>/*.json|geojson` | export_web | Daten für die Web-App |

Welcher Snapshot verwendet wird: `osm.snapshot_date` in `config/params.yaml`. Ist er leer, nimmt die Pipeline den neuesten vorhandenen Snapshot und schreibt dessen Datum in den Fetch-Report.

## Ebenen in `data/interim/<region>.gpkg` (EPSG:3035)

**`aeds`** (Punkte; bei Wegen und Relationen der `center`)
- `osm_type` (node/way/relation), `osm_id` (int), `osm_url`
- die Tags aus `osm.aed_tags_to_keep`, Spaltenname = Tag mit `:` → `_` (z. B. `defibrillator_location`, `survey_date`); fehlend = leer/None
- `access_class` ∈ `24/7`, `restricted`, `unknown`: `24/7` wenn `opening_hours == "24/7"`, `restricted` wenn ein anderer `opening_hours`-Wert vorhanden ist, sonst `unknown`
- `is_public` (bool): False bei `access` ∈ `coverage.excluded_access_values`
- `in_region` (bool): liegt innerhalb der Kreisgrenze (sonst im 2-km-Puffer)

**`cells`** (Punkte = Zellmittelpunkte)
- `cell_id` (= `GITTER_ID_100m`), `population` (int ≥ 0; nur Zellen > 0)
- `municipality_ags` (8-stellig), `vg_ars` (9-stellig oder None)
- Nur Zellen, deren Mittelpunkt in der Kreisfläche (GF = 4) liegt.

**`municipalities`** (Polygone): `ags`, `ars`, `name`, `type` (BEZ), `vg_ars`, `ewz`, `area_km2`
**`vg`** (Polygone): `ars` (9-stellig), `name`, `type`, `ewz`
**`district`** (Polygon): `ags`, `name`, `type`, `ewz`, `area_km2`
**`candidates`** (Punkte, Variante B): `osm_type`, `osm_id`, `name`, `category` (z. B. `amenity=pharmacy`)

## Szenariofilter (coverage)

- `all`: `is_public`
- `night_strict`: `is_public` und `access_class == "24/7"`
- `night_optimistic`: `night_strict` oder (`is_public` und `opening_hours` fehlt und `indoor == "no"`)

## Kennzahlen-CSV `metrics_<level>.csv` (long format)

Spalten: `level`, `id`, `name`, `radius_m`, `scenario`, `population`, `covered_population`, `coverage_rate` (0–1), `mean_distance_m`, `median_distance_m` (bevölkerungsgewichtet, effektive Distanz = Luftlinie × Umwegfaktor), `aeds_in_area`, `aeds_per_10k`, `share_aeds_missing_info` (Anteil AEDs ohne `access`- oder ohne `opening_hours`-Angabe), `share_access_unknown` (Anteil `access_class == unknown`).
AED-Zählung je Gebiet: AEDs des Szenarios, die im Gebietspolygon liegen.

## Optimierer-Ausgabe `optimize_<variant>_<scope>.csv`

`variant` ∈ `A`, `B`. `scope` ∈ `district` oder `municipality`. Spalten: `scope_id`, `radius_m`, `scenario`, `rank` (k), `x`, `y` (EPSG:3035), `lon`, `lat`, `label` (Name des POI bzw. der Gemeinde), `added_population`, `cumulative_covered`, `cumulative_rate`.
Standardlauf: Szenario `all`, alle Radien.
