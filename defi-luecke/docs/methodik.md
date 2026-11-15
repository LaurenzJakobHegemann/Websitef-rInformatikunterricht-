# Methodik – Defi-Lücke

Stand: 15.11.2026. Dieses Dokument beschreibt die Methodik des Projekts für Pilotregion A (Landkreis Bernkastel-Wittlich).

Parameter mit **Platzhalter** übernehmen die Standardwerte aus `SPEC.md` (v0.1). Das Team legt die endgültigen Werte anhand der Fachliteratur fest (SPEC Abschnitt 13). Die Werte stehen in `config/params.yaml`.

---

## Ziel und Forschungsfragen

Defi-Lücke zeigt, wie gut die Bevölkerung einer Region mit öffentlich zugänglichen Defibrillatoren (AED) versorgt ist, und berechnet, an welchen Standorten ein zusätzliches Gerät den größten Zugewinn bringt.

Zielgruppe des Werkzeugs: Gemeinden, Vereine, Sponsoren, Rettungsdienste. Das Werkzeug ist **kein Notfall-Tool**. Im Notfall gilt die 112.

Forschungsfragen:

- **F1:** Welcher Anteil der Einwohner erreicht innerhalb einer festgelegten Distanz einen öffentlich zugänglichen AED, je Gemeinde, tagsüber und nachts?
- **F2:** Wie vollständig sind die offenen AED-Daten (OpenStreetMap) im Vergleich zu einer eigenen Erhebung vor Ort?
- **F3:** An welchen Standorten bringen k zusätzliche AEDs den größten Abdeckungsgewinn, und wie nah kommt ein einfaches Greedy-Verfahren an das exakte Optimum?

**Untersuchungsgebiet:** Pilotregion A, Landkreis Bernkastel-Wittlich (Rheinland-Pfalz), Kreisschlüssel (AGS) 07231. Der Kreis hat 107 Gemeinden und 6 Verbandsgemeinde-Einheiten (verbandsfreie Gemeinden zählen als eigene Einheit). Pilotregion B ist noch nicht festgelegt (SPEC Abschnitt 13).

---

## Datenquellen

Die Rohdaten und ihr Ablageort sind in `data/raw/SOURCES.md` beschrieben.

| Quelle | Inhalt und Datenstand | Lizenz und Quellenvermerk |
|---|---|---|
| OpenStreetMap, Overpass API | AED-Standorte (`emergency=defibrillator`, Knoten, Wege und Relationen, `out center tags`). Snapshot vom 15.11.2026 (`osm_aed_bernkastel-wittlich_2026-11-15.geojson`), OSM-Datenstand 15.11.2026, 08:44:04 UTC. 189 Elemente, nach Entfernung von 3 Duplikaten 186 AEDs im Abfragegebiet. | ODbL, „© OpenStreetMap-Mitwirkende“ |
| OpenStreetMap, Kandidaten (Variante B) | Öffentlich zugängliche Orte. Datei vom 15.11.2026 (`osm_candidates_bernkastel-wittlich_2026-11-15.json`), **OSM-Datenstand 28.07.2026** (Overpass-Mirror). 3.549 Elemente. | ODbL, „© OpenStreetMap-Mitwirkende“ |
| Zensus 2022, 100-m-Gitter | Bevölkerungszahlen je Gitterzelle, Stichtag 15.05.2022. 3.088.037 Zeilen gelesen, 6.474 Zellen mit Einwohnern größer null, Summe 112.552. | dl-de/by-2-0, „© Statistische Ämter des Bundes und der Länder, 2024“ |
| BKG VG250-EW | Gemeinden, Verbandsgemeinden, Kreise mit Einwohnerzahl (Attribut `EWZ`). Stand 31.12.2025. Landflächen per `GF = 4`. | dl-de/by-2-0, „© BKG (2026) dl-de/by-2-0“ |

**Abgeleitete Kandidatenorte (Variante B):** keine eigene Datenquelle. Die Tags stehen in `config/params.yaml` (`optimize.candidate_osm_tags`): `amenity` mit townhall, fire_station, community_centre, bank, pharmacy, place_of_worship und school; `leisure` mit sports_hall; `shop` mit supermarket; `highway` mit bus_stop. Die Zuordnung von Kirche (`amenity=place_of_worship`) und Sporthalle (`leisure=sports_hall`) ist eine Annahme und vom Team zu prüfen (`docs/entscheidungen.md`).

**Datenstand und Reproduzierbarkeit:** Die OSM-Snapshots liegen im Repository, weil sie eingefrorene Eingangsdaten sind und sich nicht identisch neu abrufen lassen. Zensus und VG250 liegen nicht im Repository und lassen sich neu laden. Der Overpass-Abruf ist aus der Cloud-Umgebung nicht gelungen; der AED-Snapshot wurde manuell über overpass-turbo abgerufen (GeoJSON-Export). Welcher Snapshot verwendet wird, legt `osm.snapshot_date` fest; er ist auf den 15.11.2026 fixiert.

---

## Datenaufbereitung

- **Gitterzellen:** Die 100-m-CSV wird mit Trennzeichen `;` gelesen. Die Wertespalte heißt in der Datei „Einwohner“, die Datensatzbeschreibung nennt „Bevoelkerungszahl“; der Code akzeptiert beide und protokolliert den gefundenen Namen. Das Zeichen „–“ bedeutet „genau null oder auf null geändert“ und wird als 0 gelesen. Verwendet werden nur Zellen mit Einwohnern größer null, deren Mittelpunkt in der Kreisfläche liegt (EPSG:3035).
- **Gebiete:** Aus VG250-EW werden Kreis, Gemeinden und Verbandsgemeinden mit Landflächenfilter `GF = 4` übernommen. Die Zuordnung Gemeinde zu Verbandsgemeinde erfolgt über die ersten 9 Stellen des ARS. Zellen ohne Gemeindezuordnung werden verworfen; die Pipeline gibt dazu eine Warnung aus.
- **AEDs:** Gespeichert werden die Tags `access`, `opening_hours`, `indoor`, `defibrillator:location`, `level`, `operator`, `check_date`, `survey:date` und `description`. Weg- und Relationstreffer erhalten den Mittelpunkt (`center`). Die Klasse `access_class` ist `24/7`, wenn `opening_hours` den Wert „24/7“ hat, `restricted`, wenn ein anderer Wert vorhanden ist, sonst `unknown`.
- **Duplikate:** AEDs mit einem Abstand von höchstens 5 m (Platzhalter) gelten als doppelt; der erste bleibt erhalten. Entfernt wurden 3 Duplikate.
- Alle Ebenen liegen in `data/interim/bernkastel-wittlich.gpkg` in EPSG:3035.

---

## Abdeckungsmodell

- **Koordinatensystem:** Die Rechnung erfolgt in EPSG:3035 (ETRS89-LAEA, natives System des Gitters). Für die Web-App werden die Daten nach EPSG:4326 (WGS84) exportiert.
- **Nachfragepunkt:** Mittelpunkt jeder bewohnten 100-m-Zelle, gewichtet mit ihrer Einwohnerzahl.
- **Distanz v1:** Luftlinie mal Umwegfaktor. Umwegfaktor **1,3 (Platzhalter)**. Sensitivität: Umwegfaktor 1,0 bis 1,6.
- **Distanz v2 (optional):** Fußweg im OSM-Wegenetz, nicht umgesetzt (M6).
- **Abgedeckt:** Eine Zelle gilt als abgedeckt, wenn die effektive Distanz (Luftlinie mal Umwegfaktor) zum nächsten zulässigen AED höchstens R beträgt. Der nächste AED wird per KD-Tree gesucht.
- **Pufferzone:** AEDs im 2-km-Puffer um den Kreis zählen für die Distanzen, nicht aber für die Kennzahl „AEDs im Gebiet“.
- **Radien (Platzhalter):** 100 m, 200 m, 300 m, 500 m. Die Hilfsfunktion rechnet eine maximale Hin-und-Rück-Zeit mit einer Gehgeschwindigkeit von **1,4 m/s (Platzhalter)** in einen Radius um. Sie ersetzt nicht die Festlegung der Radien, die das Team mit Fachliteratur begründen muss.

### Szenarien

- **`all`:** alle öffentlichen AEDs (`is_public`). Nicht öffentlich sind AEDs mit `access=private` oder `access=no`. Eine fehlende Angabe `is_public` gilt als nicht öffentlich.
- **`night_strict`:** öffentliche AEDs mit `opening_hours=24/7` (untere Schranke).
- **`night_optimistic`:** `night_strict` plus öffentliche AEDs ohne Öffnungszeiten, die laut `indoor=no` außen hängen (obere Schranke). Leere `opening_hours` gelten als fehlend.

Für jeden AED wird die Klasse gespeichert: 24/7, eingeschränkt oder unbekannt. Der Anteil „unbekannt“ wird immer ausgewiesen.

### Kennzahlen

Je Gemeinde, Verbandsgemeinde und Kreis, jeweils pro Radius und Szenario (`metrics_<level>.csv`, Langformat):

- Einwohner gesamt, abgedeckte Einwohner, Abdeckungsquote
- bevölkerungsgewichteter Mittelwert und Median der effektiven Distanz zum nächsten AED
- AEDs je 10.000 Einwohner
- Anteil der AEDs mit fehlenden Angaben zu Zugang oder Öffnungszeiten sowie Anteil der Klasse „unbekannt“

Der **gewichtete Median** ist der kleinste Distanzwert, bei dem das kumulierte Gewicht mindestens 50 % erreicht. Bei exakt 50 % wird das Mittel aus diesem und dem nächsten Wert gebildet.

---

## Standort-Optimierer

- **Problemtyp:** Maximal Covering Location Problem. Gegeben sind bestehende AEDs, gewichtete Nachfragepunkte, Kandidatenstandorte und der Radius R. Gesucht sind k neue Standorte, die möglichst viele bisher nicht abgedeckte Einwohner erreichen.
- **Greedy-Verfahren (Pflicht):** In jedem Schritt wird der Kandidat gewählt, der die meisten noch nicht abgedeckten Einwohner erreicht. Die Implementierung ist exakt und verwendet eine Lazy-Auswertung mit Heap. Bei Gleichstand gewinnt der kleinste Index. Das Verfahren bricht ab, wenn kein Zugewinn mehr entsteht.
- **Nachfrage:** Einwohner der Zellen, die im Szenario `all` nicht abgedeckt sind. Die Quote `cumulative_rate` enthält die bereits abgedeckten Einwohner.
- **Läufe:** k = 1 bis 20 je Kreis (`k_max_district`) sowie k = 1 bis 3 je Gemeinde (`k_max_municipality`). Getrennte Läufe für Variante A und Variante B.
- **Varianten:** Variante A (theoretisch) sind die Mittelpunkte aller bewohnten Zellen. Variante B (praxisnah) sind öffentlich zugängliche OSM-Orte, beschriftet mit Name oder Kategorie.
- **Test:** Der Greedy-Algorithmus wird gegen das Brute-Force-Optimum an kleinen Beispielen geprüft und gegen die (1−1/e)-Schranke.
- **Exaktes Verfahren (optional, M6):** Ganzzahliges lineares Programm für einzelne Gemeinden, bisher nicht umgesetzt.

---

## Validierung

Die Validierung prüft die Datenvollständigkeit der OSM-AEDs in einem Teilgebiet (F2).

- **Vorgehen:** Das Team erhebt in klar abgegrenzten Teilgebieten alle tatsächlich vorhandenen AEDs. Erhebungsvorlage: `validation/field_survey_template.csv`.
- **Zuordnung:** Erhobene AEDs werden 1:1 per `linear_sum_assignment` den OSM-AEDs zugeordnet, Toleranz **50 m** (`validation.match_tolerance_m`).
- **Recall:** Anteil der real vorhandenen AEDs, die in OSM stehen. Zeilen mit `access_type` „nicht öffentlich“ zählen nicht.
- **Precision:** Anteil der OSM-AEDs, die vor Ort bestätigt wurden. Berücksichtigt werden nur öffentliche OSM-AEDs.
- **Intervalle:** Wilson-Konfidenzintervall, Konfidenzniveau 0,95.
- **Optional:** Schätzung der wahren AED-Zahl nach Chapman, wenn eine zweite unabhängige Liste vorliegt (Dateiname `<region>_<gebiet>_list2.csv`).
- **Teilgebiete:** `validation.areas` ist in `config/params.yaml` derzeit leer. Es liegen noch keine Erhebungsergebnisse vor. Die Auswahl der Teilgebiete ist offen (Team).
- **Reihenfolge (wichtig):** Zuerst wird der OSM-Snapshot eingefroren, dann erhoben. Neu gefundene AEDs werden erst nach der Auswertung in OSM nachgetragen.

---

## Plausibilitätsprüfungen

- **Einwohnersumme:** Zensus-Summe 112.552 gegen amtliche Einwohnerzahl 112.751 (EWZ des Kreises, Stand 31.12.2025). Abweichung **−0,18 %**, Schwelle 3 % (Platzhalter für „wenige Prozent“). Die Stichtage sind verschieden (15.05.2022 gegen 31.12.2025); das ist in der Prüfmeldung vermerkt.
- **AED-Anzahl:** größer null (189 Elemente im Snapshot).
- **Koordinaten:** 0 von 189 AED-Koordinaten liegen außerhalb des Abfragegebiets.
- **Duplikate:** 3 AEDs mit einem Abstand von höchstens 5 m (Platzhalter) entfernt.
- **Kreisschlüssel:** 07231 = „Bernkastel-Wittlich“ im VG250-EW bestätigt.

---

## Erste Ergebnisse (Stand 15.11.2026, Platzhalter-Parameter)

**Vorläufig.** Die Werte hängen von den Platzhalter-Parametern ab (Umwegfaktor 1,3, Radien, Gehgeschwindigkeit) und davon, wie vollständig die OSM-Daten sind. Sie sind keine belastbaren Befunde und dürfen nicht als Aussage über die tatsächliche Versorgung zitiert werden.

- **Bevölkerung:** 112.552 Einwohner in 6.474 bewohnten Zellen.
- **AEDs im Kreis:** 53 öffentliche AEDs (Szenario `all`). Im Abfragegebiet liegen nach Duplikatentfernung 186 AEDs.
- **Öffnungszeiten:** 47,2 % der öffentlichen AEDs im Kreis haben keine Öffnungszeiten (Klasse „unbekannt“).
- **Abdeckung nach Szenario** (Anteil der Einwohner innerhalb des Radius):

| Radius | `all` | `night_strict` | `night_optimistic` |
|---|---|---|---|
| 300 m | 9,9 % | 5,1 % | 8,3 % |
| 500 m | 19,1 % | 9,6 % | 15,4 % |

- **Gemeinden ohne Abdeckung:** Bei 300 m (Szenario `all`) haben 68 von 107 Gemeinden keine abgedeckten Einwohner.
- **Optimierer (Greedy, 20 neue Standorte, 300 m, Szenario `all`):** Die kumulierte Abdeckungsquote erreicht bei Variante A **24,3 %**, bei Variante B **21,1 %**.

---

## Grenzen

Diese Einschränkungen stehen in der App und in der schriftlichen Arbeit.

- **OpenStreetMap ist unvollständig.** Die berechnete Abdeckung ist deshalb eher eine untere Schranke. Die Validierung schätzt, wie groß die Lücke in den Daten ist (noch ohne Erhebungsergebnisse).
- **OSM-Datenstand:** Der AED-Snapshot stammt vom 15.11.2026. Die Kandidatenorte stammen aus einem Overpass-Mirror mit OSM-Datenstand 28.07.2026 und sind damit älter.
- **Bevölkerungsdaten vom Stichtag 15.05.2022.** Kleine Zellwerte sind durch ein Geheimhaltungsverfahren (Cell-Key-Methode) verändert; Summen können abweichen. Die amtliche Vergleichszahl ist vom 31.12.2025.
- **Nur Wohnbevölkerung.** Arbeitsplätze, Veranstaltungen oder Tourismus sind nicht abgebildet.
- **Luftlinie mal Umwegfaktor** ist eine Näherung. Steigungen und Barrieren fehlen.
- **Funktionsbereitschaft** eines Geräts lässt sich aus den Daten nicht ablesen.
- **Keine Ersatzplanung.** Das Werkzeug ersetzt keine fachliche Planung durch Rettungsdienst oder Kommune.
- **Platzhalter-Parameter:** Umwegfaktor, Radien, Gehgeschwindigkeit, Plausibilitäts- und Duplikat-Schwellen sind Platzhalter (siehe `docs/entscheidungen.md`).

---

## Offene Entscheidungen des Teams

Diese Punkte trifft das Team, nicht der Agent (SPEC Abschnitt 13):

- Pilotregion B festlegen
- Endgültige Radien bzw. Zeitmodell mit Fachliteratur begründen
- Fachgebiet für die Anmeldung: Mathematik/Informatik oder Geo- und Raumwissenschaften
- Projekttitel und Kurzbeschreibung für die Anmeldung (Frist 30.11.2026)
- Projektbetreuung klären und bei der Wettbewerbsleitung nachfragen, wie KI-Unterstützung anzugeben ist
- Teilgebiete für die Erhebung vor Ort auswählen
- Kandidaten-Datenstand (28.07.2026) akzeptieren oder neu abrufen
- Zuordnung der Kandidaten-Tags Kirche und Sporthalle prüfen
- Nutzungsbedingungen des Kachelanbieters für die Web-App prüfen
