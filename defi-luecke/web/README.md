# Defi-Lücke – Web-App

Statische Seite (Vite + TypeScript + Leaflet), die nur vorberechnete Dateien aus der Pipeline lädt.
Kein Backend, keine Cookies, keine Tracker, keine externen Schriftarten (alles wird gebündelt).
Einzige externe Anfrage: Kartenkacheln von `tile.openstreetmap.org` (URL in `src/config.ts`).

## Befehle

```bash
npm install          # einmalig
npm run dev          # Entwicklungsserver
npm run typecheck    # TypeScript prüfen
npm run build        # Typprüfung + statischer Build nach dist/
npm run preview      # fertigen Build lokal ansehen
```

## Daten

Die Web-App erwartet `public/data/regions.json` und je Region `public/data/<region>/…`.
Sie werden von der Pipeline erzeugt (im Projektordner `defi-luecke/`):

```bash
python -m pipeline.cli export-web --region bernkastel-wittlich
```

Fehlen die Dateien, zeigt die Seite einen freundlichen Hinweis. Es werden keine Beispieldaten mitgeliefert.
Dateien: `meta.json`, `metrics.json`, `municipalities.geojson`, `aeds.geojson`,
`recommendations.json`, `gaps_<szenario>_<radius>.json`.

## Veröffentlichen

`dist/` enthält relative Pfade (`base: './'`) und läuft deshalb auch in einem Unterordner
(z. B. GitHub Pages). Vor dem Build die Daten nach `public/data/` exportieren.
