# Defi-Lücke

Defi-Lücke zeigt, wie gut die Bevölkerung einer Region mit öffentlich zugänglichen Defibrillatoren (AED) versorgt ist, und berechnet, an welchen Standorten ein zusätzliches Gerät den größten Zugewinn bringt. Das Projekt ist ein Jugend-forscht-Nebenprojekt.

**Kein Notfall-Tool. Im Notfall die 112 wählen.** Die Karte zeigt keine Echtzeitdaten und keine Funktionsbereitschaft der Geräte.

Zielgruppe: Gemeinden, Vereine, Sponsoren, Rettungsdienste.

## Projektstand

Pilotregion A (Landkreis Bernkastel-Wittlich): **M0 bis M5 umgesetzt, M6 offen.** Pilotregion B ist noch nicht festgelegt.

- M0 Setup, M1 Daten, M2 Abdeckung, M3 Optimierer, M4 Web-App, M5 Validierung und Grafiken: umgesetzt
- M6 Ausbau (Fußweg im Wegenetz, exaktes Optimierungsverfahren, Pilotregion B, ganz Rheinland-Pfalz): offen, einzeln freizugeben

## Schnellstart

Voraussetzung: Python 3.11 oder neuer (getestet mit Python 3.13).

```bash
cd defi-luecke
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
source .venv/bin/activate
python -m pipeline.cli run --region bernkastel-wittlich
```

**Hinweis zu OSM-Daten:** Die Overpass API war aus der Cloud-Umgebung nicht erreichbar. Bricht `fetch` mit Exit-Code 4 ab, gehen Sie so vor:

1. Die Abfrage aus `data/raw/overpass_query_aed_bernkastel-wittlich.overpassql` in [overpass-turbo](https://overpass-turbo.eu) ausführen und als GeoJSON exportieren.
2. Die Datei unverändert als `data/raw/osm_aed_<region>_<YYYY-MM-DD>.geojson` speichern (Datum = Abruftag).
3. `python -m pipeline.cli fetch --region bernkastel-wittlich` erneut starten.

Die ausführliche Anleitung steht in `data/raw/SOURCES.md`. Zensus und VG250 lädt die Pipeline selbst herunter.

Einzelschritte:

```bash
python -m pipeline.cli check-config --region bernkastel-wittlich
python -m pipeline.cli fetch --region bernkastel-wittlich
python -m pipeline.cli coverage --region bernkastel-wittlich
python -m pipeline.cli optimize --region bernkastel-wittlich
python -m pipeline.cli validate --region bernkastel-wittlich
python -m pipeline.cli figures --region bernkastel-wittlich
python -m pipeline.cli export-web --region bernkastel-wittlich
```

## Web-App

Die Web-App ist eine statische Seite (Vite, TypeScript, Leaflet) ohne Backend. Sie lädt nur vorberechnete Dateien.

```bash
# Zuerst die Daten aus der Pipeline exportieren (im Ordner defi-luecke/)
python -m pipeline.cli export-web --region bernkastel-wittlich

cd web
npm ci
npm run dev       # Entwicklungsserver
npm run build     # Typprüfung und statischer Build nach web/dist/
```

Die einzige externe Anfrage sind die Kartenkacheln von `tile.openstreetmap.org`. Es gibt keine Cookies, Tracker oder externen Schriftarten.

## Ergebnisse

| Pfad | Inhalt |
|---|---|
| `data/interim/<region>.gpkg` | Ebenen AEDs, Zellen, Gemeinden, VG, Kreis, Kandidaten (EPSG:3035) |
| `data/interim/<region>_fetch_report.json` | Snapshot-Dateien, Datenstände, Plausibilitätsprüfungen |
| `data/processed/<region>/metrics_<level>.csv` | Kennzahlen je Gemeinde, Verbandsgemeinde und Kreis |
| `data/processed/<region>/optimize_<variant>_<scope>.csv` | Optimierer-Ranglisten für Variante A und B |
| `data/processed/<region>/validation_<area>.json` | Validierung: Recall, Precision, Intervalle |
| `data/processed/<region>/figures/` | Auswertungsgrafiken (PNG und SVG) |
| `web/public/data/<region>/` | Daten für die Web-App |

Die Methodik und die Grenzen stehen in `docs/methodik.md`. Die Datenverträge zwischen den Modulen beschreibt `docs/schnittstellen.md`.

## Tests und Linting

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

## Dokumentation

- [SPEC.md](SPEC.md): Ziel, Forschungsfragen, Datenquellen, Meilensteine
- [docs/methodik.md](docs/methodik.md): Methodik, Ergebnisse und Grenzen
- [docs/schnittstellen.md](docs/schnittstellen.md): Datenverträge zwischen den Pipeline-Schritten
- [docs/entscheidungen.md](docs/entscheidungen.md): Entscheidungen mit Begründung und Status
- [docs/ki-protokoll.md](docs/ki-protokoll.md): KI-Unterstützung im Projekt
- [data/raw/SOURCES.md](data/raw/SOURCES.md): Datenquellen und Quellenvermerke
