# Datenquellen (Rohdaten)

Dieses Dokument beschreibt alle Rohdaten, die die Pipeline für die Pilotregion verwendet. Quelle der Angaben ist `SPEC.md`, Abschnitt 3. Alles, was dort nicht steht, ist als **TODO (M1)** markiert und wird im Meilenstein M1 (Daten) ergänzt.

**Hinweis:** Der Ordner `data/raw/` liegt nicht im Repository. Die Inhalte werden per `.gitignore` ausgeschlossen; versioniert ist nur diese Datei (`data/raw/SOURCES.md`). Die Rohdaten müssen daher bei jeder neuen Einrichtung neu abgerufen bzw. manuell abgelegt werden.

Falls ein automatischer Download scheitert, wird er nicht umgangen. Stattdessen wird der manuelle Schritt unten beschrieben, und die Pipeline bricht mit einer verständlichen Fehlermeldung ab (SPEC, Abschnitt 0).

---

## 1. AED-Standorte: OpenStreetMap (Overpass API)

**Was:** Öffentlich erfasste Defibrillatoren aus OpenStreetMap. Grundlage für alle Abdeckungsberechnungen (F1) und für die Validierung der Datenvollständigkeit (F2).

**Woher:** Overpass API, `https://overpass-api.de/api/interpreter`

**Abfrage (SPEC 3.1):**

- Tag `emergency=defibrillator`
- Elementtypen Knoten, Wege und Relationen (`nwr`), Ausgabe `out center tags`
- Abfragegebiet: Bounding Box der Region plus 2 km Puffer (`query_buffer_m: 2000` in `config/params.yaml`)
- Zu speichernde Tags, soweit vorhanden: `access`, `opening_hours`, `indoor`, `defibrillator:location`, `level`, `operator`, `check_date`, `survey:date`, `description`

**Lizenz:** ODbL

**Quellenvermerk:** „© OpenStreetMap-Mitwirkende"

**Erwarteter Dateiname (Snapshot):**

```
data/raw/osm_aed_<region>_<YYYY-MM-DD>.json
```

Beispiel: `data/raw/osm_aed_bernkastel-wittlich_<YYYY-MM-DD>.json`, wobei das Datum der Abruftag ist.

Der Rohabruf wird unverändert mit Zeitstempel als Snapshot abgelegt. Alle Auswertungen laufen gegen einen festgelegten Snapshot, nicht gegen Live-Daten (SPEC 3.1).

**Manueller Download:**

- TODO (M1): Schritte für den manuellen Abruf über die Overpass API festlegen (Abfragetext mit Bounding Box, Ausgabeformat, Speicherort und Umbenennung nach Snapshot-Konvention).
- TODO (M1): Verhalten bei Zeitüberschreitung (Konfigurationswert `timeout_s: 180`) und bei Ablehnung durch den Server dokumentieren.

---

## 2. Bevölkerung: Zensus 2022, 100-m-Gitter

**Was:** Datensatz „Bevölkerungszahlen in Gitterzellen" des Zensus 2022. Grundlage für die Nachfragepunkte (Mittelpunkte der bewohnten 100-m-Zellen, gewichtet mit der Einwohnerzahl).

**Woher:** zensus2022.de, Bereich Ergebnisse, Gitterdaten.

- TODO (M1): Direkte URL der Download-Seite bzw. der ZIP-Datei eintragen. SPEC nennt nur den Bereich, nicht die Adresse.

**Inhalt des ZIP (SPEC 3.2):**

- CSV-Dateien für das 10-km-, 1-km- und 100-m-Gitter
- eine Datensatzbeschreibung als Excel-Datei

Verwendet wird ausschließlich die **100-m-Datei**. Spaltennamen und deren Bedeutung werden aus der Datensatzbeschreibung übernommen und nicht geraten. Die Pipeline prüft im Code, ob die erwarteten Spalten vorhanden sind (SPEC 0).

- TODO (M1): Spaltennamen aus der Datensatzbeschreibung in dieses Dokument übernehmen (nicht vorher festlegen).

**Koordinatensystem:** ETRS89-LAEA (EPSG:3035)

**Stichtag:** 15.05.2022. Kleine Zellwerte sind durch ein Geheimhaltungsverfahren verändert. Beides wird in `docs/methodik.md` als Einschränkung festgehalten.

**Lizenz:** TODO (M1): Lizenz von der Downloadseite übernehmen.

**Quellenvermerk:** TODO (M1): exakten Quellenvermerk von der Downloadseite übernehmen.

**Erwarteter Dateiname:**

- TODO (M1): Dateiname der 100-m-CSV aus dem ZIP übernehmen und die Ablagekonvention in `data/raw/` festlegen. SPEC legt für diese Quelle keine Snapshot-Benennung fest.

**Manueller Download:**

- TODO (M1): Schritte für den manuellen Download des ZIP festlegen (Seite, Auswahl des Datensatzes, Entpacken nach `data/raw/`).

---

## 3. Verwaltungsgrenzen: BKG VG250

**Was:** Open-Data-Produkt „Verwaltungsgebiete 1:250 000" des Bundesamts für Kartographie und Geodäsie (BKG). Grundlage für die Zuordnung der Zellen und AEDs zu Gemeinden, Verbandsgemeinden und Kreisen.

**Woher:**

- Download über `gdz.bkg.bund.de`
- oder per WFS: `https://sgx.geodatenzentrum.de/wfs_vg250`

**Benötigte Ebenen (SPEC 3.3):**

- Gemeinden
- Verwaltungsgemeinschaften (in Rheinland-Pfalz die Verbandsgemeinden)
- Kreise

**Nur Landflächen verwenden.** Das dafür zuständige Attribut wird der Produktdokumentation entnommen.

- TODO (M1): Name des Attributs für Landflächen aus der Produktdokumentation eintragen.

**Kreisschlüssel:** Der Kreisschlüssel des Landkreises Bernkastel-Wittlich (erwartet `07231`) ist in `config/regions.yaml` noch nicht verifiziert (`district_key_verified: false`). Die Pipeline muss ihn in M1 gegen diesen Datensatz prüfen.

**Lizenz:** Datenlizenz Deutschland – Namensnennung – Version 2.0

**Quellenvermerk:** „© BKG (Jahr) dl-de/by-2-0"

- TODO (M1): Platzhalter „(Jahr)" mit dem Jahr aus der Produktdokumentation ersetzen.

**Erwarteter Dateiname:**

- TODO (M1): Dateiname bzw. Ebenennamen des Downloads und die Ablagekonvention in `data/raw/` festlegen.

**Manueller Download:**

- TODO (M1): Schritte für den manuellen Download über gdz.bkg.bund.de festlegen (Produkt, Format, Auswahl der Ebenen).
- TODO (M1): Schritte für den WFS-Abruf festlegen, falls der automatische Abruf scheitert.

---

## 4. Kandidatenstandorte für neue AEDs

Für die Kandidatenstandorte wird **keine eigene Datenquelle** heruntergeladen. Sie werden aus den bereits genannten Quellen abgeleitet (SPEC 3.4).

**Variante A (theoretisch):** Mittelpunkte aller bewohnten Gitterzellen aus Abschnitt 2 (Zensus 2022).

**Variante B (praxisnah):** öffentlich zugängliche Orte aus OpenStreetMap, z. B. Rathaus, Feuerwehr, Gemeindehaus, Bank, Apotheke, Kirche, Schule, Sporthalle, Supermarkt, Bushaltestelle. Die genaue Tag-Liste wird in `config/params.yaml` (Abschnitt `optimize.candidate_osm_tags`) gepflegt.

**Lizenz:** ODbL (wie Abschnitt 1, weil aus OpenStreetMap abgeleitet)

**Quellenvermerk:** „© OpenStreetMap-Mitwirkende"

**Erwarteter Dateiname:** Keine eigene Datei im Rohdatenordner. Die Ableitung aus dem OSM-Snapshot und dem Zensus-Gitter erfolgt in der Pipeline.

- TODO (M1): Ablage der abgeleiteten Kandidatenliste (z. B. in `data/interim/`) festlegen.

**Manueller Download:** nicht nötig, da keine eigene Quelle. Die Kandidaten hängen vom OSM-Snapshot (Abschnitt 1) ab.
