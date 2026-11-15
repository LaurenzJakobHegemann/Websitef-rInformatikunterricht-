# Entscheidungen – Defi-Lücke

Jede inhaltliche Entscheidung, die der Coding-Agent selbst getroffen hat (Schwellenwerte, Filter, Vereinfachungen, Strukturfragen), steht hier mit Begründung. Der Status zeigt, ob das Team die Entscheidung noch bestätigen muss.

| Datum | Entscheidung | Begründung | Status |
|---|---|---|---|
| 2026-11-15 | Projektordner `defi-luecke/` als Unterordner im bestehenden Repository. | Das Team hat kein separates Repository angelegt. Der Unterordner lässt sich später in ein eigenes Repository verschieben. | Umgesetzt (später verschiebbar) |
| 2026-11-15 | Plausibilitätsschwelle für die Einwohnersumme: 3 % als Platzhalter für „wenige Prozent". | SPEC Abschnitt 10 verlangt eine konfigurierbare Schwelle für „wenige Prozent", ohne Zahlenwert. 3 % ist der Startwert in `config/params.yaml`. | Vom Team zu bestätigen |
| 2026-11-15 | Duplikat-Abstand für AEDs: 5 m als Platzhalter für „wenige Meter". | SPEC Abschnitt 10 nennt „wenige Meter", ohne Zahlenwert. 5 m ist der Startwert in `config/params.yaml`. | Vom Team zu bestätigen |
| 2026-11-15 | Gehgeschwindigkeit für die Radius-Hilfsfunktion: 1,4 m/s als Platzhalter. | SPEC Abschnitt 4 verlangt eine Hilfsfunktion, die Hin-und-Rück-Zeit und Gehgeschwindigkeit in einen Radius umrechnet, nennt aber keinen Wert. 1,4 m/s ist der Startwert in `config/params.yaml`. Der Wert muss mit Fachliteratur begründet werden (SPEC Abschnitt 13). | Vom Team zu bestätigen |
| 2026-11-15 | Kandidaten-Tags für Variante B: Liste aus der Beispielliste der SPEC übernommen. Kirche = `amenity=place_of_worship`, Sporthalle = `leisure=sports_hall`. | SPEC Abschnitt 3.4 nennt Orte als Beispiele, aber keine OSM-Tags. Die Zuordnung von Kirche und Sporthalle zu den OSM-Tags ist eine Annahme des Agenten und muss geprüft werden. Die Liste steht in `config/params.yaml` und ist dort pflegbar. | Vom Team zu bestätigen |
| 2026-11-15 | Abhängigkeiten in `requirements.txt` exakt gepinnt, getestet mit Python 3.13. | SPEC Abschnitt 10 verlangt festgeschriebene Abhängigkeiten, damit der Lauf reproduzierbar ist. Mindestversion bleibt Python 3.11. | Umgesetzt |
