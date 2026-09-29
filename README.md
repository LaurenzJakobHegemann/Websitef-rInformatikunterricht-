# Parity Terminal

Erweiterung von [terminal.parityinitiative.org](https://terminal.parityinitiative.org/) um eine
Aktien-Watchlist mit aktuellen Tageskursen.

## Funktionen

- Suche nach Aktien (Symbol oder Firmenname)
- Watchlist mit Live-Kursen (Kurs, Änderung, Änderung %, Eröffnung, Tageshoch/-tief, Vortagesschluss)
- Automatische Aktualisierung alle 15 Sekunden
- Klick auf eine Aktie öffnet ein Firmenprofil: Branche, Land, Marktkapitalisierung, IPO-Datum,
  Management/CEO (falls im Finnhub-Plan verfügbar) und ein 1-Jahres-Kurschart mit Hover-Tooltip
- Kein Server nötig – reine HTML/CSS/JS-Seite

## Setup

1. Kostenlosen API-Key bei [finnhub.io/register](https://finnhub.io/register) holen (keine Kreditkarte nötig).
2. Seite öffnen (siehe unten) und den Key beim ersten Start einfügen.
   Der Key wird nur lokal im Browser gespeichert (`localStorage`), nicht im Code oder auf GitHub.

## Lokal starten

Da die Seite `fetch`-Requests macht, am besten über einen kleinen lokalen Server öffnen (nicht per Doppelklick auf die Datei):

```bash
python3 -m http.server 8000
```

Dann im Browser `http://localhost:8000` öffnen.

## Deployment

Die Seite besteht nur aus statischen Dateien (`index.html`, `css/`, `js/`) und kann z. B. direkt über
**GitHub Pages** gehostet werden (Settings → Pages → Branch auswählen).

## Projektstruktur

```
index.html       Hauptseite
css/style.css    Styling (Terminal-Look)
js/app.js        Logik: Aktien-Suche, Watchlist, Kursabruf über Finnhub-API
```

## Hinweis zur API

Es wird die kostenlose [Finnhub](https://finnhub.io/)-API verwendet. Der kostenlose Plan hat ein
Rate-Limit (60 Anfragen/Minute), das für eine private Watchlist mit einigen Aktien ausreicht.

Zwei Endpunkte im Firmenprofil (Management/CEO über `/stock/executive` und historische Kurse über
`/stock/candle`) sind bei Finnhub für manche Symbole nur im bezahlten Plan enthalten. Die Seite fängt
das ab und zeigt dann einen Hinweistext statt eines Fehlers an.
