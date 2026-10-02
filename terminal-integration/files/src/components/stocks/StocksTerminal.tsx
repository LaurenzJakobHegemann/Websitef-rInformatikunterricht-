'use client';

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import {
  FinnhubError, clearKeyProblem, fetchNextEarnings, fetchQuote, getKeyProblemState, setActiveApiKey,
  subscribeKeyProblem,
} from '@/lib/stocks/finnhub';
import { loadApiKey, loadWatchlist, saveApiKey, saveWatchlist } from '@/lib/stocks/storage';
import type { EarningsEvent } from '@/lib/stocks/types';
import CompanyDetail from './CompanyDetail';
import EarningsList from './EarningsList';
import KeyBanner from './KeyBanner';
import KeySetup from './KeySetup';
import StockSearch from './StockSearch';
import WatchlistTable, { type QuoteState } from './WatchlistTable';
import styles from './stocks.module.css';

const REFRESH_MS = 15_000;
const timeLabel = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

/** Läuft nur im Browser (wird mit ssr: false geladen), daher darf der Startzustand aus localStorage kommen. */
export default function StocksTerminal() {
  const [apiKey, setApiKey] = useState(() => {
    const key = loadApiKey();
    setActiveApiKey(key);
    return key;
  });
  const [showSetup, setShowSetup] = useState(() => !apiKey);
  const [watchlist, setWatchlist] = useState<string[]>(loadWatchlist);
  const [quotes, setQuotes] = useState<Record<string, QuoteState>>({});
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [earnings, setEarnings] = useState<Record<string, EarningsEvent | null>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [dismissedProblemId, setDismissedProblemId] = useState(0);

  const keyProblem = useSyncExternalStore(subscribeKeyProblem, getKeyProblemState, getKeyProblemState);
  const bannerProblem = keyProblem.problem && keyProblem.id !== dismissedProblemId ? keyProblem.problem : null;
  const active = Boolean(apiKey) && !showSetup;

  useEffect(() => {
    saveWatchlist(watchlist);
  }, [watchlist]);

  const refreshQuotes = useCallback(async (symbols: string[]) => {
    const results = await Promise.all(
      symbols.map(async (s): Promise<[string, QuoteState | 'limit']> => {
        try {
          return [s, await fetchQuote(s)];
        } catch (err) {
          // Bei Limit bleiben die letzten Kurse stehen; die Hinweisleiste erklärt, warum.
          return [s, err instanceof FinnhubError && err.status === 429 ? 'limit' : 'error'];
        }
      })
    );
    setQuotes((prev) => {
      const next = { ...prev };
      for (const [s, q] of results) if (q !== 'limit') next[s] = q;
      return next;
    });
    if (results.some(([, q]) => q !== 'limit' && q !== 'error')) setLastUpdate(new Date());
  }, []);

  useEffect(() => {
    if (!active || watchlist.length === 0) return;
    // Erster Abruf sofort, danach im Intervall; beides läuft asynchron.
    const first = setTimeout(() => refreshQuotes(watchlist), 0);
    const timer = setInterval(() => refreshQuotes(watchlist), REFRESH_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [active, watchlist, apiKey, refreshQuotes]);

  // Termine je Symbol nur einmal abfragen. Fehlversuche werden wieder freigegeben und beim
  // nächsten Ändern der Watchlist oder nach einem Key-Wechsel erneut versucht, nicht in einer Schleife.
  const earningsRequested = useRef(new Set<string>());

  useEffect(() => {
    if (!active) return;
    const missing = watchlist.filter((s) => !earningsRequested.current.has(s));
    if (missing.length === 0) return;
    missing.forEach((s) => earningsRequested.current.add(s));
    (async () => {
      const found = await Promise.all(
        missing.map(async (s) => {
          try {
            return [s, await fetchNextEarnings(s)] as const;
          } catch {
            earningsRequested.current.delete(s);
            return null;
          }
        })
      );
      setEarnings((prev) => {
        const next = { ...prev };
        for (const entry of found) if (entry) next[entry[0]] = entry[1];
        return next;
      });
    })();
  }, [active, watchlist, apiKey]);

  function handleKeySaved(key: string) {
    saveApiKey(key);
    setActiveApiKey(key);
    clearKeyProblem();
    earningsRequested.current.clear();
    setApiKey(key);
    setEarnings({});
    setShowSetup(false);
  }

  function openSetup() {
    setSelected(null);
    setShowSetup(true);
  }

  function addSymbol(symbol: string) {
    setWatchlist((list) => (list.includes(symbol) ? list : [...list, symbol]));
  }

  function removeSymbol(symbol: string) {
    setWatchlist((list) => list.filter((s) => s !== symbol));
  }

  const closeDetail = useCallback(() => setSelected(null), []);

  return (
    <div className={`${styles.root} ${bannerProblem ? styles.withBanner : ''}`}>
      <header className={styles.header}>
        <div className={styles.bar}>
          <Link href="/" className={styles.brand}>
            <span className={styles.wordmark}>Parity</span>
            <span className={styles.brandSub}>Terminal · Aktien</span>
          </Link>
          <nav className={styles.nav} aria-label="Aktien">
            <Link href="/" className={styles.navlink}>← Zur Karte</Link>
            {apiKey && !showSetup && (
              <button type="button" className={styles.navlink} onClick={openSetup}>API-Key ändern</button>
            )}
          </nav>
        </div>
      </header>

      {showSetup ? (
        <KeySetup isChange={Boolean(apiKey)} onSaved={handleKeySaved} onCancel={apiKey ? () => setShowSetup(false) : undefined} />
      ) : (
        <>
          <section className={`${styles.section} ${styles.sectionTight}`}>
            <div className={styles.inner}>
              <p className={styles.eyebrow}>Mitglieder-Terminal · Märkte</p>
              <h1 className={styles.title}>Aktien</h1>
              <p className={styles.lead}>
                Live-Kurse deiner Watchlist, Firmenprofile mit Finanzkennzahlen, Analysten-Einschätzungen,
                Konkurrenzvergleich und die nächsten Quartalszahlen.
              </p>
              <StockSearch onAdd={addSymbol} />
            </div>
          </section>

          <section className={`${styles.section} ${styles.sectionTight}`}>
            <div className={styles.inner}>
              <div className={styles.sectionHead}>
                <h2 className={styles.h2}>Watchlist</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  {lastUpdate && <span className={`${styles.meta} ${styles.num}`}>Stand {timeLabel.format(lastUpdate)}</span>}
                  <button type="button" className={`${styles.btn} ${styles.btnSm}`} onClick={() => refreshQuotes(watchlist)}>
                    Aktualisieren
                  </button>
                </div>
              </div>
              <WatchlistTable symbols={watchlist} quotes={quotes} onOpen={setSelected} onRemove={removeSymbol} />
            </div>
          </section>

          <section className={`${styles.section} ${styles.paper}`}>
            <div className={styles.inner}>
              <p className={styles.eyebrow}>Kalender</p>
              <h2 className={styles.h2} style={{ marginBottom: 28 }}>Nächste Quartalszahlen</h2>
              <EarningsList symbols={watchlist} earnings={earnings} onOpen={setSelected} />
            </div>
          </section>
        </>
      )}

      <footer className={styles.footer}>
        <div className={styles.footInner}>
          <span>Daten von Finnhub mit deinem eigenen API-Key. Keine Anlageberatung.</span>
          {apiKey && !showSetup && (
            <button type="button" className={`${styles.btn} ${styles.btnSm}`} onClick={openSetup}>API-Key ändern</button>
          )}
        </div>
      </footer>

      {selected && active && <CompanyDetail key={selected} symbol={selected} onClose={closeDetail} />}

      {bannerProblem && active && (
        <KeyBanner problem={bannerProblem} onChangeKey={openSetup} onDismiss={() => setDismissedProblemId(keyProblem.id)} />
      )}
    </div>
  );
}
