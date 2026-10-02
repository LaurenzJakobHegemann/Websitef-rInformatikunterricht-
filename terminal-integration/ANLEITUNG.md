# Aktien-Bereich für das Parity Terminal

Dieser Ordner bringt den Aktien-Bereich aus diesem Repo als neue Seite **`/aktien`** in das
Parity Terminal (Next.js 16, `terminal.parityinitiative.org`). Gestaltet ist er im Parity-Design
(`parity-design.css`: Blau `#013479`, Tinos/Archivo, eckige Buttons, Karten mit Linie oben).

## Was drin ist

- **Einrichtung beim ersten Öffnen:** Schritt-für-Schritt-Anleitung für den kostenlosen Finnhub-Key,
  Key wird vor dem Speichern geprüft.
- **Watchlist** mit Live-Kursen (alle 15 Sekunden), Suche nach Aktien.
- **Firmenprofil:** Kurs, Firmendaten, 1-Jahres-Chart, Analysten-Einschätzungen, Finanzkennzahlen
  (KGV, KUV, KBV, EV/EBITDA, EV/Umsatz, Margen, ROE, Umsatz, EBITDA, Nettogewinn, EPS …),
  Vergleich mit Konkurrenten, Nachrichten, Management.
- **Nächste Quartalszahlen** der Watchlist-Aktien.
- **Hinweisleiste** bei erreichtem Limit oder ungültigem Key mit „Neuen Key eingeben“.
- **Einstieg im Terminal:** Button in der rechten Werkzeugleiste (Desktop) und Tab „AKTIEN“ in
  der unteren Navigation (Handy).

Jeder Nutzer gibt seinen **eigenen** Finnhub-Key ein (nur im Browser gespeichert). Es gibt keinen
Server-Key, keine neue API-Route und keine neuen Pakete.

## Inhalt dieses Ordners

| Pfad | Zweck |
|---|---|
| `parity-aktien.patch` | Alle Änderungen als Git-Patch, relativ zum Terminal-Hauptordner |
| `files/src/...` | Die 16 neuen Dateien einzeln, falls der Patch nicht passt |
| `ANLEITUNG.md` | Diese Datei |

Neue Dateien im Terminal:

```
src/app/aktien/page.tsx                 Route /aktien
src/components/stocks/*.tsx             Oberfläche (Client-Komponenten)
src/components/stocks/stocks.module.css Parity-Design, nur für /aktien gültig
src/lib/stocks/finnhub.ts               Finnhub-Client, erkennt Limit (429) und ungültigen Key (401)
src/lib/stocks/financials.ts            Kennzahlen und deutsche Zahlenformate
src/lib/stocks/financials.test.ts       Vitest-Tests
src/lib/stocks/storage.ts               Key und Watchlist im localStorage
src/lib/stocks/types.ts                 Typen der Finnhub-Antworten
```

Geändert wird nur `src/app/page.tsx` (12 Zeilen):

1. Import ergänzen: `import Link from 'next/link';` und `TrendingUp` im `lucide-react`-Import.
2. In der rechten Werkzeugleiste (Desktop) nach dem Markets-Button:
   ```tsx
   <Link href="/aktien" title="Aktien" aria-label="Aktien: Watchlist und Firmenprofile" className="w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:bg-black/5">
     <TrendingUp className="w-4 h-4 text-[var(--text-muted)]" />
   </Link>
   ```
3. In der mobilen Navigation nach den Tabs (`].map(tab => …)`):
   ```tsx
   <Link href="/aktien" className="mobile-nav-btn">
     <TrendingUp className="w-4 h-4" />
     <span>AKTIEN</span>
   </Link>
   ```

## Einbauen

Im Hauptordner des Terminals (dort, wo `package.json` und `PARITY_HANDOVER.md` liegen):

```bash
git apply --check /pfad/zu/parity-aktien.patch   # prüfen
git apply /pfad/zu/parity-aktien.patch           # anwenden
```

Passt der Patch nicht, weil `src/app/page.tsx` inzwischen anders aussieht: die 16 Dateien aus
`files/src/` an dieselben Pfade kopieren und die 3 Änderungen oben von Hand in `page.tsx` einbauen.

## Prüfen

```bash
npm install
npx vitest run src/lib/stocks        # 9 Tests grün
npx tsc --noEmit                      # nur die 2 Fehler, die schon vorher da waren
                                      # (src/app/api/cctv/proxy/route.ts, src/app/api/geo/route.ts)
npx eslint src/lib/stocks src/components/stocks src/app/aktien   # keine Meldungen
npm run dev                           # dann http://localhost:3000/aktien öffnen
```

Im Browser: Anleitung erscheint, echten Finnhub-Key eingeben, Watchlist lädt Kurse, eine Aktie
antippen, Firmenprofil prüfen. Bei AAPL sollten alle Kennzahlen-Kacheln gefüllt sein; steht dort
überall „–“, liefert Finnhub die Felder unter anderen Namen (Liste in `METRIC_KEYS` in
`src/lib/stocks/financials.ts`).

Danach wie gewohnt deployen: `npm run cf:deploy`.

## Getestet

- Vitest (9 Tests), TypeScript, ESLint, `next build --webpack` (Route `/aktien` wird statisch gebaut)
- Durchklick im Browser gegen `next dev` mit simulierten Finnhub-Antworten, Desktop und 390 px
  Handybreite: Einrichtung, falscher Key, Watchlist, Suche, Firmenprofil, Limit-Leiste,
  Key-Wechsel, Neuladen, Einstiegspunkte im Terminal
- **Nicht** getestet mit echten Finnhub-Daten: Die Entwicklungsumgebung hatte keinen Zugriff auf
  finnhub.io. Der erste Test mit einem echten Key zeigt, ob alle Felder ankommen.

## Hinweise

- Die Content-Security-Policy in `next.config.ts` erlaubt `https:`; Aufrufe an `finnhub.io` aus dem
  Browser sind damit zugelassen.
- Die Oberfläche ist auf Deutsch, das restliche Terminal auf Englisch. Texte stehen direkt in den
  Komponenten unter `src/components/stocks/`.
- Kursverlauf und Management liefert Finnhub im kostenlosen Plan nicht für jedes Symbol; die Seite
  zeigt dann einen Hinweis statt eines Fehlers.
