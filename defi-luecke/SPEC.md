# Defi-Lücke – Projekt-Spezifikation (v0.1)

Stand: 15.11.2026 · Jugend-forscht-Nebenprojekt · Diese Datei ist der Arbeitsauftrag für einen Coding-Agenten (z. B. Claude Code).

## 0. Arbeitsregeln für den Coding-Agenten

- Arbeite die Meilensteine in Abschnitt 11 der Reihe nach ab. Nach jedem Meilenstein: kurze Zusammenfassung, was gebaut wurde, was getestet ist und welche Fragen offen sind. Dann auf Freigabe warten.
- Erfinde oder simuliere niemals Daten. Ausnahme: klar gekennzeichnete synthetische Daten in `tests/`.
- Triff keine Annahmen über Spaltennamen, Schlüssel oder Dateistrukturen. Lies die mitgelieferte Dokumentation der Datenquelle (z. B. die Datensatzbeschreibung im Zensus-ZIP) und prüfe im Code, ob die erwarteten Spalten vorhanden sind.
- Wenn ein automatischer Download scheitert: nicht umgehen, sondern den manuellen Schritt in `data/raw/SOURCES.md` dokumentieren und mit einer verständlichen Fehlermeldung abbrechen.
- Alles muss mit einem einzigen Befehl reproduzierbar sein (siehe Abschnitt 10).
- Jede inhaltliche Entscheidung, die du selbst triffst (Schwellenwerte, Filter, Vereinfachungen), kommt mit Begründung in `docs/entscheidungen.md`.
- Führe `docs/ki-protokoll.md`: Datum, Aufgabe, was generiert wurde. Das Projekt wird bei Jugend forscht eingereicht, KI-Unterstützung muss dort offengelegt werden.
- Code und Bezeichner auf Englisch, Oberfläche und Dokumentation auf Deutsch.

## 1. Ziel

Defi-Lücke zeigt, wie gut die Bevölkerung einer Region mit öffentlich zugänglichen Defibrillatoren (AED) versorgt ist, und berechnet, an welchen Standorten ein zusätzliches Gerät den größten Zugewinn bringt.

Forschungsfragen:

- F1: Welcher Anteil der Einwohner erreicht innerhalb einer festgelegten Distanz einen öffentlich zugänglichen AED, je Gemeinde, tagsüber und nachts?
- F2: Wie vollständig sind die offenen AED-Daten (OpenStreetMap) im Vergleich zu einer eigenen Erhebung vor Ort?
- F3: An welchen Standorten bringen k zusätzliche AEDs den größten Abdeckungsgewinn, und wie nah kommt ein einfaches Greedy-Verfahren an das exakte Optimum?

Zielgruppe des Werkzeugs: Gemeinden, Vereine, Sponsoren, Rettungsdienste. Es ist kein Notfall-Tool.

## 2. Umfang

In v1 enthalten:

- Pilotregion A: Landkreis Bernkastel-Wittlich (Rheinland-Pfalz). Kreisschlüssel voraussichtlich 07231, gegen den Grenzdatensatz prüfen.
- Pilotregion B: Platzhalter in der Konfiguration, wird später gesetzt (Wohnregion des zweiten Teammitglieds).
- Datenpipeline in Python, statische Web-App mit Karte, Auswertungsgrafiken für die schriftliche Arbeit.

Ausdrücklich nicht in v1:

- Keine native App, kein Login, kein Backend, keine eigene AED-Datenbank.
- Kein Notfall-Routing zum nächsten Defi (gibt es bereits, z. B. OpenAEDMap).
- Keine deutschlandweite Berechnung (erst Ausbaustufe, Abschnitt 11, M6).

## 3. Datenquellen

### 3.1 AED-Standorte: OpenStreetMap

- Abruf über die Overpass API (`https://overpass-api.de/api/interpreter`), Tag `emergency=defibrillator`, Knoten, Wege und Relationen (`nwr`, Ausgabe `out center tags`).
- Abfragegebiet: Bounding Box der Region plus 2 km Puffer. AEDs knapp außerhalb der Grenze versorgen Einwohner am Rand mit.
- Zu speichernde Tags, soweit vorhanden: `access`, `opening_hours`, `indoor`, `defibrillator:location`, `level`, `operator`, `check_date`, `survey:date`, `description`.
- Den Rohabruf mit Zeitstempel als unveränderten Snapshot ablegen (`data/raw/osm_aed_<region>_<YYYY-MM-DD>.json`). Alle Auswertungen laufen gegen einen festgelegten Snapshot, nicht gegen Live-Daten.
- Lizenz: ODbL, Quellenvermerk „© OpenStreetMap-Mitwirkende".

### 3.2 Bevölkerung: Zensus 2022, 100-m-Gitter

- Datensatz „Bevölkerungszahlen in Gitterzellen" von zensus2022.de (Bereich Ergebnisse, Gitterdaten). Das ZIP enthält CSV-Dateien für 10-km-, 1-km- und 100-m-Gitter sowie eine Datensatzbeschreibung als Excel-Datei.
- Verwendet wird die 100-m-Datei. Koordinatensystem ETRS89-LAEA (EPSG:3035). Spaltennamen und Bedeutung aus der Datensatzbeschreibung übernehmen, nicht raten.
- Stichtag 15.05.2022. Kleine Zellwerte sind durch ein Geheimhaltungsverfahren verändert. Beides in `docs/methodik.md` als Einschränkung festhalten.
- Lizenz und exakten Quellenvermerk von der Downloadseite übernehmen.

### 3.3 Verwaltungsgrenzen: BKG VG250

- Open-Data-Produkt „Verwaltungsgebiete 1:250 000" des Bundesamts für Kartographie und Geodäsie, Download über gdz.bkg.bund.de oder per WFS (`https://sgx.geodatenzentrum.de/wfs_vg250`).
- Benötigte Ebenen: Gemeinden, Verwaltungsgemeinschaften (in Rheinland-Pfalz die Verbandsgemeinden), Kreise.
- Nur Landflächen verwenden; das dafür zuständige Attribut der Produktdokumentation entnehmen.
- Lizenz: Datenlizenz Deutschland – Namensnennung – Version 2.0, Quellenvermerk „© BKG (Jahr) dl-de/by-2-0".

### 3.4 Kandidatenstandorte für neue AEDs

- Variante A (theoretisch): Mittelpunkte aller bewohnten Gitterzellen.
- Variante B (praxisnah): öffentlich zugängliche Orte aus OpenStreetMap, z. B. Rathaus, Feuerwehr, Gemeindehaus, Bank, Apotheke, Kirche, Schule, Sporthalle, Supermarkt, Bushaltestelle. Die genaue Tag-Liste in `config/params.yaml` pflegen.

## 4. Abdeckungsmodell

- Rechenkoordinatensystem: EPSG:3035 (natives System des Gitters). Export für die Web-App in WGS84 (EPSG:4326).
- Nachfragepunkt: Mittelpunkt jeder bewohnten 100-m-Zelle, gewichtet mit ihrer Einwohnerzahl.
- Distanz v1: Luftlinie mal Umwegfaktor (Standard 1,3, konfigurierbar). Distanz v2 (optional): Fußweg im OSM-Wegenetz.
- Eine Zelle gilt als abgedeckt, wenn die Distanz zum nächsten zulässigen AED höchstens R beträgt.
- Radien als Parameterliste, Standard: 100 m, 200 m, 300 m, 500 m. Zusätzlich eine Hilfsfunktion, die eine maximale Hin-und-Rück-Zeit und eine Gehgeschwindigkeit in einen Radius umrechnet.
- Hinweis: Die Standardwerte sind Platzhalter. Das Team legt die endgültigen Schwellen anhand der Fachliteratur fest (siehe Abschnitt 13).

Szenarien für die Zugänglichkeit:

- `all`: alle AEDs außer `access=private` und `access=no`.
- `night_strict`: nur AEDs mit `opening_hours=24/7` (untere Schranke).
- `night_optimistic`: zusätzlich AEDs ohne Öffnungszeiten-Tag, die laut `indoor=no` außen hängen (obere Schranke).
- Für jeden AED die Klasse speichern: 24/7, eingeschränkt, unbekannt. Den Anteil „unbekannt" immer mit ausweisen.

Kennzahlen je Gemeinde, Verbandsgemeinde und Kreis, jeweils pro Radius und Szenario:

- Einwohner gesamt, abgedeckte Einwohner, Abdeckungsquote
- bevölkerungsgewichteter Mittelwert und Median der Distanz zum nächsten AED
- AEDs je 10.000 Einwohner
- Anteil der AEDs mit fehlenden Angaben zu Zugang oder Öffnungszeiten

## 5. Standort-Optimierer

Problemtyp: Maximal Covering Location Problem. Gegeben bestehende AEDs, Nachfragepunkte mit Gewichten, Kandidatenstandorte und Radius R; gesucht sind k neue Standorte, die möglichst viele bisher nicht abgedeckte Einwohner abdecken.

- Greedy-Verfahren (Pflicht): in jedem Schritt den Kandidaten wählen, der die meisten noch nicht abgedeckten Einwohner erreicht. Für k = 1 bis K (Standard K = 20 je Kreis) sowie k = 1 bis 3 je Gemeinde.
- Exaktes Verfahren (optional, M6): ganzzahliges lineares Programm mit einem freien Solver (z. B. PuLP mit CBC oder OR-Tools) für einzelne Gemeinden. Ausgabe: Abstand Greedy zu Optimum in Prozent.
- Effizienz: Nachbarschaftssuche über einen räumlichen Index (KD-Tree oder BallTree), Abdeckungsbeziehungen als dünn besetzte Matrix.
- Ausgabe je empfohlenem Standort: Koordinate, Name des nächstgelegenen Ortes oder POI, zusätzlich abgedeckte Einwohner, kumulierte Abdeckungsquote. Dazu die Abdeckungskurve (Quote über k).
- Getrennte Läufe für Kandidatenvariante A und B.

## 6. Validierung der Datenvollständigkeit

- Vorlage `validation/field_survey_template.csv` mit den Spalten: `region`, `lat`, `lon`, `location_description`, `access_type` (24/7, Öffnungszeiten, nicht öffentlich), `found_on`, `method` (Begehung, Anruf, Website), `photo_ref`, `notes`.
- Das Team erhebt in klar abgegrenzten Teilgebieten (z. B. je eine Gemeinde pro Region) alle tatsächlich vorhandenen AEDs.
- Skript `validate.py`: ordnet erhobene AEDs den OSM-AEDs zu (Standard-Toleranz 50 m) und berechnet für das Teilgebiet
  - den Anteil real vorhandener AEDs, die in OSM stehen (Recall),
  - den Anteil der OSM-AEDs, die vor Ort bestätigt wurden (Precision),
  - jeweils mit Wilson-Konfidenzintervall.
- Optional: Schätzung der wahren AED-Zahl per Capture-Recapture (Chapman-Schätzer), falls eine zweite unabhängige Liste vorliegt, etwa von einer Kommune.
- Wichtig für die Methodik: erst den OSM-Snapshot einfrieren, dann erheben. Neu gefundene AEDs erst nach der Auswertung in OSM nachtragen.

## 7. Web-App

Statische Seite ohne Backend, die ausschließlich vorberechnete Dateien aus der Pipeline lädt.

- Technik: schlankes Setup (z. B. Vite mit TypeScript) und eine freie Kartenbibliothek (Leaflet oder MapLibre GL JS). Basemap mit korrekter Attribution; Nutzungsbedingungen des Kachelanbieters beachten.
- Hosting: statisch (z. B. GitHub Pages oder Cloudflare Pages).

Funktionen:

- Karte der Gemeinden, eingefärbt nach Abdeckungsquote, mit Umschaltern für Radius und Szenario.
- AED-Punkte mit Popup: Ortsbeschreibung, Zugangsklasse, Datenstand.
- Ebene „Lücken": bewohnte, nicht abgedeckte Zellen.
- Ebene „Empfehlungen": die besten k neuen Standorte mit Zugewinn in Einwohnern.
- Gemeinde-Suche mit Steckbrief: Quote, Rang im Kreis, Distanzkennzahlen, empfohlene Standorte.
- „Fehlenden Defi melden": Anleitung und Link zum Eintragen in OpenStreetMap/OpenAEDMap. Keine eigene Datenspeicherung.
- Seite „Methodik und Grenzen" mit Datenquellen, Datenstand und Quellenvermerken.
- Dauerhaft sichtbarer Hinweis: kein Notfall-Tool, im Notfall 112.

Anforderungen:

- Deutschsprachig, auf dem Handy bedienbar.
- Farbskala auch bei Farbfehlsichtigkeit lesbar; Werte zusätzlich als Zahl.
- Keine Tracker, keine externen Schriftarten, keine Cookies.

## 8. Auswertungsgrafiken für die schriftliche Arbeit

`figures.py` erzeugt reproduzierbar (PNG und SVG, deutsche Beschriftung):

- Verteilung der Abdeckungsquoten über die Gemeinden
- Abdeckungsquote gegen Bevölkerungsdichte
- Vergleich der Szenarien Tag und Nacht
- Sensitivität gegenüber Radius und Umwegfaktor
- Abdeckungskurve des Optimierers (Quote über k), Variante A gegen B
- Ergebnis der Validierung (Recall, Precision mit Intervallen)

Zusätzlich eine CSV mit allen Kennzahlen je Gemeinde.

## 9. Projektstruktur

```
defi-luecke/
  README.md
  SPEC.md
  config/
    regions.yaml
    params.yaml
  pipeline/
    cli.py
    fetch_osm.py
    fetch_boundaries.py
    load_census.py
    coverage.py
    optimize.py
    validate.py
    figures.py
    export_web.py
  data/
    raw/          (nicht im Repo, mit SOURCES.md)
    interim/
    processed/
  validation/
    field_survey_template.csv
  web/
  tests/
  docs/
    methodik.md
    entscheidungen.md
    ki-protokoll.md
```

## 10. Technik und Qualität

- Python 3.11 oder neuer; Kernbibliotheken: pandas, geopandas, shapely, pyproj, scipy oder scikit-learn, requests, matplotlib, pyyaml. Abhängigkeiten festschreiben.
- Ein Befehl für den Gesamtlauf, z. B. `python -m pipeline.cli run --region bernkastel-wittlich`, plus Einzelschritte (`fetch`, `coverage`, `optimize`, `validate`, `figures`, `export-web`).
- Tests mit pytest: Distanzberechnung, Abdeckungslogik, Szenariofilter, Greedy an einem kleinen Beispiel mit bekanntem Optimum, Zuordnung in der Validierung.
- Plausibilitätsprüfungen im Lauf:
  - Summe der Einwohner aller Zellen einer Region weicht höchstens wenige Prozent von der amtlichen Einwohnerzahl ab (Schwelle konfigurierbar, Abweichung protokollieren).
  - Anzahl AEDs größer null; Koordinaten liegen im Abfragegebiet.
  - Keine doppelten AEDs (gleicher Ort innerhalb weniger Meter).
- Linting und Formatierung (z. B. ruff). Keine Zugangsdaten im Repo.

## 11. Meilensteine

- **M0 Setup:** Repo-Gerüst, Konfiguration, CLI-Grundgerüst, Tests laufen.
  - Abnahme: `pytest` grün, `README.md` erklärt Installation und Lauf.
- **M1 Daten:** Abruf und Aufbereitung von AEDs, Gitter und Grenzen für Pilotregion A.
  - Abnahme: eine GeoPackage-Datei mit den Ebenen AEDs, Zellen, Gemeinden; Plausibilitätsprüfungen bestanden; Snapshot abgelegt.
- **M2 Abdeckung:** Kennzahlen nach Abschnitt 4 für alle Radien und Szenarien.
  - Abnahme: Kennzahlen-CSV je Gemeinde; Tests für die Abdeckungslogik.
- **M3 Optimierer:** Greedy-Verfahren für Variante A und B.
  - Abnahme: Rangliste und Abdeckungskurve; Test mit bekanntem Optimum.
- **M4 Web-App:** Funktionen nach Abschnitt 7 mit den Daten aus M1 bis M3.
  - Abnahme: läuft lokal und als statischer Build, auf dem Handy bedienbar.
- **M5 Validierung und Grafiken:** Abschnitte 6 und 8.
  - Abnahme: Validierung läuft mit einer Beispieldatei aus `tests/`; alle Grafiken werden erzeugt.
- **M6 Ausbau (optional, einzeln freigeben):** Fußweg-Distanz im Wegenetz, exaktes Optimierungsverfahren mit Vergleich, Pilotregion B, ganz Rheinland-Pfalz.

## 12. Grenzen, die in App und Arbeit stehen müssen

- OpenStreetMap ist unvollständig. Die berechnete Abdeckung ist deshalb eher eine untere Schranke; Abschnitt 6 schätzt, wie groß die Lücke in den Daten ist.
- Bevölkerungsdaten vom Mai 2022, kleine Zellwerte verfälscht.
- Abgebildet wird nur die Wohnbevölkerung, nicht Arbeitsplätze, Veranstaltungen oder Tourismus.
- Luftlinie mal Umwegfaktor ist eine Näherung; Steigungen und Barrieren fehlen.
- Ob ein Gerät funktionsbereit ist, lässt sich aus den Daten nicht ablesen.
- Das Werkzeug ersetzt keine fachliche Planung durch Rettungsdienst oder Kommune.

## 13. Offene Entscheidungen für das Team (nicht vom Agenten zu treffen)

- Pilotregion B festlegen.
- Endgültige Radien bzw. Zeitmodell mit Fachliteratur begründen.
- Fachgebiet für die Anmeldung: Mathematik/Informatik oder Geo- und Raumwissenschaften.
- Projekttitel und Kurzbeschreibung für die Anmeldung (Frist 30.11.2026).
- Projektbetreuung klären und bei der Wettbewerbsleitung nachfragen, wie KI-Unterstützung anzugeben ist.
- Teilgebiete für die Erhebung vor Ort auswählen.
