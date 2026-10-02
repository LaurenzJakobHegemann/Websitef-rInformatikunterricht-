'use client';

import type { Quote } from '@/lib/stocks/types';
import { formatNumber } from '@/lib/stocks/financials';
import styles from './stocks.module.css';

/** `undefined` = noch nicht geladen, `'error'` = Abruf fehlgeschlagen. */
export type QuoteState = Quote | 'error' | undefined;

interface WatchlistTableProps {
  symbols: string[];
  quotes: Record<string, QuoteState>;
  onOpen: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}

function Change({ value, suffix = '' }: { value: number | null | undefined; suffix?: string }) {
  if (typeof value !== 'number') return <>–</>;
  return (
    <span className={value >= 0 ? styles.up : styles.down}>
      {value >= 0 ? '+' : ''}{formatNumber(value)}{suffix}
    </span>
  );
}

export default function WatchlistTable({ symbols, quotes, onOpen, onRemove }: WatchlistTableProps) {
  if (symbols.length === 0) {
    return <p className={styles.empty}>Noch keine Aktien in der Watchlist. Suche oben nach einer Aktie und füge sie hinzu.</p>;
  }

  return (
    <>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Symbol</th>
              <th scope="col">Kurs</th>
              <th scope="col">Änderung</th>
              <th scope="col">Änderung %</th>
              <th scope="col">Eröffnung</th>
              <th scope="col">Tageshoch</th>
              <th scope="col">Tagestief</th>
              <th scope="col">Vortag</th>
              <th scope="col"><span className="sr-only">Entfernen</span></th>
            </tr>
          </thead>
          <tbody>
            {symbols.map((symbol) => {
              const q = quotes[symbol];
              const quote = q && q !== 'error' && !(q.c === 0 && q.pc === 0) ? q : null;
              const placeholder = q === 'error' ? 'Fehler' : q ? 'n/v' : '…';
              return (
                <tr key={symbol} className={styles.rowLink} onClick={() => onOpen(symbol)} data-symbol={symbol}>
                  <td>
                    <button
                      type="button"
                      className={styles.symbolButton}
                      onClick={(e) => { e.stopPropagation(); onOpen(symbol); }}
                    >
                      {symbol}
                    </button>
                  </td>
                  <td data-field="price">{quote ? formatNumber(quote.c) : placeholder}</td>
                  <td><Change value={quote?.d} /></td>
                  <td><Change value={quote?.dp} suffix=" %" /></td>
                  <td>{quote ? formatNumber(quote.o) : '–'}</td>
                  <td>{quote ? formatNumber(quote.h) : '–'}</td>
                  <td>{quote ? formatNumber(quote.l) : '–'}</td>
                  <td>{quote ? formatNumber(quote.pc) : '–'}</td>
                  <td>
                    <button
                      type="button"
                      className={styles.removeButton}
                      onClick={(e) => { e.stopPropagation(); onRemove(symbol); }}
                      aria-label={`${symbol} aus der Watchlist entfernen`}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={styles.hint}>Tippe auf eine Aktie für Firmenprofil, Kennzahlen, Analysten und Nachrichten.</p>
    </>
  );
}
