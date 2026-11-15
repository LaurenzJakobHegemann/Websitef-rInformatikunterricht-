# Methodik – Defi-Lücke

Dieses Dokument beschreibt die Methodik des Projekts. Es ist ein Gerüst für M0; die Abschnitte werden in den jeweiligen Meilensteinen (SPEC Abschnitt 11) gefüllt.

Alle Parameter, die mit **Platzhalter** gekennzeichnet sind, übernehmen die Standardwerte aus `SPEC.md` (v0.1). Das Team legt die endgültigen Werte anhand der Fachliteratur fest (SPEC Abschnitt 13).

---

## Ziel und Forschungsfragen

Defi-Lücke zeigt, wie gut die Bevölkerung einer Region mit öffentlich zugänglichen Defibrillatoren (AED) versorgt ist, und berechnet, an welchen Standorten ein zusätzliches Gerät den größten Zugewinn bringt.

Zielgruppe des Werkzeugs: Gemeinden, Vereine, Sponsoren, Rettungsdienste. Das Werkzeug ist **kein Notfall-Tool**.

Forschungsfragen:

- **F1:** Welcher Anteil der Einwohner erreicht innerhalb einer festgelegten Distanz einen öffentlich zugänglichen AED, je Gemeinde, tagsüber und nachts?
- **F2:** Wie vollständig sind die offenen AED-Daten (OpenStreetMap) im Vergleich zu einer eigenen Erhebung vor Ort?
- **F3:** An welchen Standorten bringen k zusätzliche AEDs den größten Abdeckungsgewinn, und wie nah kommt ein einfaches Greedy-Verfahren an das exakte Optimum?

Untersuchungsgebiet: Pilotregion A, Landkreis Bernkastel-Wittlich (Rheinland-Pfalz). Pilotregion B ist noch nicht festgelegt (Platzhalter in `config/regions.yaml`, SPEC Abschnitt 13).

---

## Datenquellen

Die Rohdaten und ihre Quellenvermerke sind in `data/raw/SOURCES.md` beschrieben.

| Quelle | Inhalt | Lizenz |
|---|---|---|
| OpenStreetMap (Overpass API) | AED-Standorte, Tags wie in SPEC 3.1 | ODbL, „© OpenStreetMap-Mitwirkende" |
| Zensus 2022, 100-m-Gitter | Bevölkerungszahlen je Gitterzelle, Stichtag 15.05.2022 | TODO (M1) |
| BKG VG250 | Gemeinden, Verbandsgemeinden, Kreise | Datenlizenz Deutschland – Namensnennung – Version 2.0, „© BKG (Jahr) dl-de/by-2-0" |
| OSM-Kandidaten (abgeleitet) | Öffentlich zugängliche Orte für Variante B | ODbL, „© OpenStreetMap-Mitwirkende" |

Datenstand: Für jede Auswertung wird ein fester OSM-Snapshot verwendet (Dateiname mit Datum). Der konkrete Datenstand der übrigen Quellen wird in M1 eingetragen (TODO (M1)).

---

## Abdeckungsmodell

- **Koordinatensystem:** Rechnung in EPSG:3035 (ETRS89-LAEA, natives System des Gitters). Export für die Web-App in EPSG:4326 (WGS84).
- **Nachfragepunkt:** Mittelpunkt jeder bewohnten 100-m-Zelle, gewichtet mit ihrer Einwohnerzahl.
- **Distanz v1:** Luftlinie mal Umwegfaktor. Umwegfaktor **1,3 (Platzhalter)**.
- **Distanz v2 (optional):** Fußweg im OSM-Wegenetz (M6).
- **Abgedeckt:** Eine Zelle gilt als abgedeckt, wenn die Distanz zum nächsten zulässigen AED höchstens R beträgt.
- **Radien (Platzhalter):** 100 m, 200 m, 300 m, 500 m.
- **Zeitmodell (Hilfsfunktion):** Umrechnung einer maximalen Hin-und-Rück-Zeit mit einer Gehgeschwindigkeit in einen Radius. Gehgeschwindigkeit **1,4 m/s (Platzhalter)**. Die Hilfsfunktion ersetzt nicht die Festlegung der Radien; diese muss das Team mit Fachliteratur begründen (SPEC Abschnitt 13).

### Szenarien

- **`all`:** alle AEDs außer `access=private` und `access=no`.
- **`night_strict`:** nur AEDs mit `opening_hours=24/7` (untere Schranke).
- **`night_optimistic`:** zusätzlich AEDs ohne Öffnungszeiten-Tag, die laut `indoor=no` außen hängen (obere Schranke).

Für jeden AED wird die Klasse gespeichert: 24/7, eingeschränkt, unbekannt. Der Anteil „unbekannt" wird immer ausgewiesen.

### Kennzahlen

Je Gemeinde, Verbandsgemeinde und Kreis, jeweils pro Radius und Szenario:

- Einwohner gesamt, abgedeckte Einwohner, Abdeckungsquote
- bevölkerungsgewichteter Mittelwert und Median der Distanz zum nächsten AED
- AEDs je 10.000 Einwohner
- Anteil der AEDs mit fehlenden Angaben zu Zugang oder Öffnungszeiten

---

## Szenarien

Die drei Szenarien (`all`, `night_strict`, `night_optimistic`) bilden die Zugänglichkeit ab. Sie werden im Abschnitt „Abdeckungsmodell" beschrieben. Tag- und Nachtwerte werden in der Auswertung gegenübergestellt (SPEC Abschnitt 8).

---

## Standort-Optimierer

- **Problemtyp:** Maximal Covering Location Problem. Gegeben sind bestehende AEDs, Nachfragepunkte mit Gewichten, Kandidatenstandorte und Radius R. Gesucht sind k neue Standorte, die möglichst viele bisher nicht abgedeckte Einwohner abdecken.
- **Greedy-Verfahren (Pflicht):** In jedem Schritt wird der Kandidat gewählt, der die meisten noch nicht abgedeckten Einwohner erreicht. Läufe für k = 1 bis K (Standard **K = 20 je Kreis**) sowie k = 1 bis 3 je Gemeinde.
- **Exaktes Verfahren (optional, M6):** Ganzzahliges lineares Programm mit einem freien Solver (z. B. PuLP mit CBC oder OR-Tools) für einzelne Gemeinden. Ausgabe: Abstand Greedy zu Optimum in Prozent.
- **Effizienz:** Nachbarschaftssuche über einen räumlichen Index (KD-Tree oder BallTree), Abdeckungsbeziehungen als dünn besetzte Matrix.
- **Ausgabe je Standort:** Koordinate, Name des nächstgelegenen Ortes oder POI, zusätzlich abgedeckte Einwohner, kumulierte Abdeckungsquote. Dazu die Abdeckungskurve (Quote über k).
- **Kandidatenvarianten:** Getrennte Läufe für Variante A und Variante B.

---

## Validierung

Die Validierung prüft die Datenvollständigkeit der OSM-AEDs in einem Teilgebiet (F2).

- **Vorgehen:** Das Team erhebt in klar abgegrenzten Teilgebieten (z. B. je eine Gemeinde pro Region) alle tatsächlich vorhandenen AEDs. Erhebungsvorlage: `validation/field_survey_template.csv`.
- **Zuordnung:** Erhobene AEDs werden den OSM-AEDs zugeordnet. Standard-Toleranz **50 m** (`match_tolerance_m` in `config/params.yaml`).
- **Kennzahlen:**
  - Recall: Anteil der real vorhandenen AEDs, die in OSM stehen
  - Precision: Anteil der OSM-AEDs, die vor Ort bestätigt wurden
  - jeweils mit Wilson-Konfidenzintervall (Konfidenzniveau 0,95)
- **Optional:** Schätzung der wahren AED-Zahl per Capture-Recapture (Chapman-Schätzer), falls eine zweite unabhängige Liste vorliegt, etwa von einer Kommune.
- **Reihenfolge (wichtig):** Zuerst wird der OSM-Snapshot eingefroren, dann erhoben. Neu gefundene AEDs werden erst nach der Auswertung in OSM nachgetragen.
- **Erhebungsfelder:** `access_type` mit den Werten 24/7, Öffnungszeiten, nicht öffentlich; `method` mit den Werten Begehung, Anruf, Website (SPEC Abschnitt 6).
- **Teilgebiete:** TODO (Team): Auswahl der Teilgebiete für die Erhebung vor Ort (SPEC Abschnitt 13).

---

## Plausibilitätsprüfungen

- Summe der Einwohner aller Zellen einer Region weicht höchstens **3 % (Platzhalter für „wenige Prozent")** von der amtlichen Einwohnerzahl ab. Die Abweichung wird protokolliert.
- Anzahl AEDs größer null; Koordinaten liegen im Abfragegebiet.
- Keine doppelten AEDs: gleicher Ort innerhalb von **5 m (Platzhalter für „wenige Meter")**.
- Die amtliche Einwohnerzahl der Pilotregion ist noch nicht eingetragen (TODO (M1): Wert und Quelle in `config/regions.yaml`).

---

## Grenzen

Diese Einschränkungen müssen in der App und in der schriftlichen Arbeit stehen.

- OpenStreetMap ist unvollständig. Die berechnete Abdeckung ist deshalb eher eine untere Schranke. Die Validierung (Abschnitt „Validierung") schätzt, wie groß die Lücke in den Daten ist.
- Bevölkerungsdaten vom Stichtag 15.05.2022. Kleine Zellwerte sind durch ein Geheimhaltungsverfahren verändert.
- Abgebildet wird nur die Wohnbevölkerung, nicht Arbeitsplätze, Veranstaltungen oder Tourismus.
- Luftlinie mal Umwegfaktor ist eine Näherung; Steigungen und Barrieren fehlen.
- Ob ein Gerät funktionsbereit ist, lässt sich aus den Daten nicht ablesen.
- Das Werkzeug ersetzt keine fachliche Planung durch Rettungsdienst oder Kommune.

---

## Offene Entscheidungen des Teams

Diese Punkte trifft das Team, nicht der Agent (SPEC Abschnitt 13):

- Pilotregion B festlegen
- Endgültige Radien bzw. Zeitmodell mit Fachliteratur begründen
- Fachgebiet für die Anmeldung: Mathematik/Informatik oder Geo- und Raumwissenschaften
- Projekttitel und Kurzbeschreibung für die Anmeldung (Frist 30.11.2026)
- Projektbetreuung klären und bei der Wettbewerbsleitung nachfragen, wie KI-Unterstützung anzugeben ist
- Teilgebiete für die Erhebung vor Ort auswählen
