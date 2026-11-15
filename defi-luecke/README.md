# Defi-Lücke

Defi-Lücke zeigt, wie gut die Bevölkerung einer Region mit öffentlich zugänglichen Defibrillatoren (AED) versorgt ist, und berechnet, an welchen Standorten ein zusätzliches Gerät den größten Zugewinn bringt. Das Projekt ist ein Jugend-forscht-Nebenprojekt.

**Kein Notfall-Tool. Im Notfall die 112 wählen.** Die Karte zeigt keine Echtzeitdaten und keine Funktionsbereitschaft der Geräte.

Zielgruppe: Gemeinden, Vereine, Sponsoren, Rettungsdienste.

## Installation

Voraussetzung: Python 3.11 oder neuer (getestet mit Python 3.13).

```bash
cd defi-luecke
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Eine Installation mit `pip install -e .` ist nicht nötig.

## Nutzung

Konfiguration prüfen:

```bash
python -m pipeline.cli check-config --region bernkastel-wittlich
```

Gesamtlauf:

```bash
python -m pipeline.cli run --region bernkastel-wittlich
```

Einzelschritte:

```bash
python -m pipeline.cli fetch --region bernkastel-wittlich
python -m pipeline.cli coverage --region bernkastel-wittlich
python -m pipeline.cli optimize --region bernkastel-wittlich
python -m pipeline.cli validate --region bernkastel-wittlich
python -m pipeline.cli figures --region bernkastel-wittlich
python -m pipeline.cli export-web --region bernkastel-wittlich
```

Die Rohdaten liegen nicht im Repository. Welche Quellen wie beschafft werden, steht in `data/raw/SOURCES.md`.

## Tests und Linting

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

## Projektstand

Aktuell: **M0 Setup** (Repo-Gerüst, Konfiguration, CLI-Grundgerüst, Tests).

Meilensteine (SPEC Abschnitt 11):

- **M0 Setup:** Repo-Gerüst, Konfiguration, CLI-Grundgerüst, Tests laufen.
- **M1 Daten:** AEDs, Gitter und Grenzen für Pilotregion A abrufen und aufbereiten.
- **M2 Abdeckung:** Kennzahlen für alle Radien und Szenarien.
- **M3 Optimierer:** Greedy-Verfahren für Kandidatenvarianten A und B.
- **M4 Web-App:** Karte, Steckbriefe, Empfehlungen; lokal und als statischer Build.
- **M5 Validierung und Grafiken:** Erhebungsvergleich und Auswertungsgrafiken.
- **M6 Ausbau (optional):** Fußweg im Wegenetz, exaktes Optimierungsverfahren, Pilotregion B, ganz Rheinland-Pfalz.

## Projektstruktur

```
defi-luecke/
  README.md          diese Datei
  SPEC.md            Projekt-Spezifikation (Arbeitsauftrag)
  config/            Regionen (regions.yaml) und Parameter (params.yaml)
  pipeline/          Python-Pipeline und CLI (pipeline/cli.py)
  data/              raw (nicht im Repo), interim, processed
  validation/        Vorlage für die Erhebung vor Ort
  web/               statische Web-App
  tests/             pytest-Tests
  docs/              Methodik, Entscheidungen, KI-Protokoll
```

## Dokumentation

- [SPEC.md](SPEC.md): Ziel, Forschungsfragen, Datenquellen, Meilensteine
- [docs/methodik.md](docs/methodik.md): Methodik und Grenzen
- [docs/entscheidungen.md](docs/entscheidungen.md): Entscheidungen mit Begründung
- [docs/ki-protokoll.md](docs/ki-protokoll.md): KI-Unterstützung im Projekt
- [data/raw/SOURCES.md](data/raw/SOURCES.md): Datenquellen und Quellenvermerke
