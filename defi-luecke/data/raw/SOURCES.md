# Datenquellen (Rohdaten)

Dieses Dokument beschreibt alle Rohdaten, die die Pipeline für die Pilotregion verwendet. Die Angaben sind am 15.11.2026 gegen die tatsächlichen Dateien geprüft (siehe auch `docs/schnittstellen.md`).

**Hinweis:** Der Ordner `data/raw/` liegt nicht im Repository. Die Inhalte werden per `.gitignore` ausgeschlossen; versioniert ist nur diese Datei. Der Befehl `python -m pipeline.cli fetch --region bernkastel-wittlich` lädt ZIP-Dateien selbst herunter, wenn sie fehlen (vorhandene werden nicht erneut geladen). Scheitert ein Download, bricht die Pipeline mit einer Anleitung ab (SPEC, Abschnitt 0); der manuelle Schritt steht jeweils unten.

---

## 1. AED-Standorte: OpenStreetMap (Overpass API)

**Was:** Öffentlich erfasste Defibrillatoren aus OpenStreetMap (Grundlage für F1 und F2).

**Woher:** Overpass API. Endpunkte in `config/params.yaml` (`osm.overpass_urls`), jeder wird einmal in dieser Reihenfolge versucht (Verbindungs-Timeout 8 s, Antwort-Timeout `timeout_s` + 30 s).

**Abfragegebiet:** Kreisfläche (VG250, GF = 4) in EPSG:3035 um `query_buffer_m` = 2000 m gepuffert, nach WGS84 umgerechnet, Bounding Box auf 4 Nachkommastellen. Für Bernkastel-Wittlich (Süd, West, Nord, Ost): `49.6550, 6.6534, 50.1495, 7.2916`.

**AED-Abfrage:**

```
[out:json][timeout:180];
nwr["emergency"="defibrillator"](49.6550,6.6534,50.1495,7.2916);
out center tags;
```

**Kandidaten-Abfrage (Variante B)**, Tags aus `optimize.candidate_osm_tags`:

```
[out:json][timeout:180];
(
  nwr["amenity"~"^(townhall|fire_station|community_centre|bank|pharmacy|place_of_worship|school)$"](49.6550,6.6534,50.1495,7.2916);
  nwr["leisure"="sports_hall"](49.6550,6.6534,50.1495,7.2916);
  nwr["shop"="supermarket"](49.6550,6.6534,50.1495,7.2916);
  node["highway"="bus_stop"](49.6550,6.6534,50.1495,7.2916);
);
out center tags;
```

Die Pipeline schreibt beide Abfragen bei jedem Lauf nach `data/raw/overpass_query_aed_<region>.overpassql` und `data/raw/overpass_query_candidates_<region>.overpassql`.

**Gespeicherte Tags (AEDs):** `access`, `opening_hours`, `indoor`, `defibrillator:location`, `level`, `operator`, `check_date`, `survey:date`, `description`. Wege und Relationen werden über `center` zum Punkt.

**Lizenz:** ODbL. **Quellenvermerk:** „© OpenStreetMap-Mitwirkende".

**Snapshot-Dateien:**

```
data/raw/osm_aed_<region>_<YYYY-MM-DD>.json
data/raw/osm_candidates_<region>_<YYYY-MM-DD>.json
```

Datum = Abruftag. Die Datei ist die unveränderte Overpass-Antwort. Auswahl: `osm.snapshot_date` (wenn gesetzt, wird genau dieser Snapshot verwendet und nichts geladen), sonst existiert für heute ein Snapshot (kein Download), sonst wird ein Abruf versucht und bei Misserfolg der neueste vorhandene Snapshot verwendet. Das verwendete Datum steht im Fetch-Report.

**Manueller Download (wenn kein Overpass-Server erreichbar ist, Exit-Code 4):**

1. Abfrage ausführen, entweder per Direktlink (Muster `https://overpass-api.de/api/interpreter?data=<URL-kodierte Abfrage>`; die Pipeline gibt den fertigen Link in der Fehlermeldung aus) oder: Inhalt der `.overpassql`-Datei auf https://overpass-turbo.eu einfügen, ausführen, Export > Rohdaten (JSON) speichern.
2. Antwort **unverändert** als `data/raw/osm_aed_<region>_<heutiges Datum>.json` bzw. `data/raw/osm_candidates_<region>_<heutiges Datum>.json` speichern.
3. `python -m pipeline.cli fetch --region <region>` erneut ausführen. Grenzen und Zensus sind dann bereits verarbeitet, die ZIP-Dateien werden nicht erneut geladen.

Bei Zeitüberschreitung oder Ablehnung (z. B. HTTP 429) probiert die Pipeline den nächsten Server; sind alle erfolglos, gilt der manuelle Schritt.

---

## 2. Bevölkerung: Zensus 2022, 100-m-Gitter

**Was:** Datensatz „Bevölkerungszahl" in 100-m-Gitterzellen. Grundlage für die Nachfragepunkte.

**Woher:** `https://www.destatis.de/static/DE/zensus/gitterdaten/Zensus2022_Bevoelkerungszahl.zip` (zensus2022.de leitet auf destatis.de um). Ablage: `data/raw/zensus2022/Zensus2022_Bevoelkerungszahl.zip`.

**ZIP-Inhalt:** `Zensus2022_Bevoelkerungszahl_100m-Gitter.csv` (verwendet), `…_1km-Gitter.csv`, `…_10km-Gitter.csv`, `Datensatzbeschreibung_Bevoelkerungszahl_Gitterzellen.xlsx`.

**Spalten der 100-m-CSV (Trennzeichen `;`):** `GITTER_ID_100m`, `x_mp_100m`, `y_mp_100m`, Wertespalte. Die Datensatzbeschreibung nennt die Wertespalte `Bevoelkerungszahl`, die tatsächliche Kopfzeile lautet aber `Einwohner`. Der Code akzeptiert beide (`census.population_columns`) und schreibt den gefundenen Namen in den Fetch-Report. Fehlt beides, bricht er mit einer Fehlermeldung ab.

**Koordinaten:** `x_mp_100m`/`y_mp_100m` sind Zellmittelpunkte in EPSG:3035. Das Zeichen `–` in der Wertespalte heißt „genau null oder auf null geändert" und wird als 0 gelesen. Zellen ohne Einwohner fehlen in der Datei. Die Pipeline behält nur Zellen mit Einwohnern > 0, deren Mittelpunkt im Kreis liegt.

**Stichtag:** 15.05.2022. Geheimhaltung per Cell-Key-Methode (stochastische Überlagerung), Summen können abweichen.

**Lizenz:** Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0). **Quellenvermerk:** „© Statistische Ämter des Bundes und der Länder, 2024".

**Manueller Download:** ZIP von der obigen URL im Browser laden und unter `data/raw/zensus2022/` ablegen (nicht entpacken, die Pipeline liest die CSV direkt aus dem ZIP).

---

## 3. Verwaltungsgrenzen: BKG VG250-EW

**Was:** „Verwaltungsgebiete 1:250 000 mit Einwohnerzahlen" (Stand 31.12.2025) des BKG.

**Woher:** `https://daten.gdz.bkg.bund.de/produkte/vg/vg250-ew_ebenen_1231/aktuell/vg250-ew_12-31.utm32s.gpkg.ebenen.zip`. Ablage: ZIP und entpackt in `data/raw/vg250/`; GeoPackage `data/raw/vg250/vg250-ew_ebenen_1231/DE_VG250.gpkg` (EPSG:25832).

**Ebenen:** `vg250_krs`, `vg250_vwg` (Verbandsgemeinden), `vg250_gem`. Attribute in Großbuchstaben: `AGS`, `ARS`, `GEN`, `BEZ`, `GF`, `EWZ`, `KFL`, …

**Landflächen:** Filter `GF = 4` (`vg250.pdf`, Abschnitt 3.2.3; Konfiguration `boundaries.land_gf_value`).

**Kreisschlüssel:** `07231` = „Bernkastel-Wittlich", Landkreis, EWZ 112751; die Pipeline prüft ihn bei jedem Lauf. Zuordnung Gemeinde → Verbandsgemeinde: die ersten 9 Stellen des Gemeinde-`ARS` entsprechen dem `ARS` der Verwaltungsgemeinschaft.

**Lizenz:** dl-de/by-2-0. **Quellenvermerk:** „© BKG (2026) dl-de/by-2-0", Links https://www.bkg.bund.de und https://www.govdata.de/dl-de/by-2-0 (`dokumentation/nutzungsbedingungen_vg250.pdf`).

**Manueller Download:** ZIP von der obigen URL laden, nach `data/raw/vg250/` legen und dort entpacken. Alternativ WFS `https://sgx.geodatenzentrum.de/wfs_vg250` (von der Pipeline nicht automatisch genutzt).

---

## 4. Kandidatenstandorte für neue AEDs

Keine eigene Datenquelle.

- **Variante A:** Mittelpunkte der bewohnten Zellen (Ebene `cells` der Interim-Datei).
- **Variante B:** OSM-Orte aus der Kandidaten-Abfrage (Abschnitt 1), Ebene `candidates` mit `category` (z. B. `amenity=pharmacy`).

Ablage der Ergebnisse: `data/interim/<region>.gpkg` (Ebenen `aeds`, `cells`, `municipalities`, `vg`, `district`, `candidates`, alle EPSG:3035) und `data/interim/<region>_fetch_report.json` (Snapshot-Dateien, Datenstände, Quellenvermerke, Plausibilitätsergebnisse, verwendete Bevölkerungsspalte).
