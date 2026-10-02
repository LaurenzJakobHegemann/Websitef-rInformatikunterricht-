'use client';

import { useEffect, useRef, useState } from 'react';
import { searchSymbols } from '@/lib/stocks/finnhub';
import type { SymbolSearchResult } from '@/lib/stocks/types';
import styles from './stocks.module.css';

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; results: SymbolSearchResult[] }
  | { status: 'error' };

export default function StockSearch({ onAdd }: { onAdd: (symbol: string) => void }) {
  const [query, setQuery] = useState('');
  const [state, setState] = useState<SearchState>({ status: 'idle' });
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setState({ status: 'idle' });
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setState({ status: 'loading' });
    try {
      setState({ status: 'done', results: await searchSymbols(q) });
    } catch {
      setState({ status: 'error' });
    }
  }

  function add(symbol: string) {
    onAdd(symbol);
    setQuery('');
    setState({ status: 'idle' });
  }

  return (
    <div className={styles.search} ref={wrapRef}>
      <form onSubmit={handleSubmit} role="search">
        <label className={styles.label} htmlFor="stock-search">Aktie suchen</label>
        <div className={styles.inputRow}>
          <input
            id="stock-search"
            className={styles.input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Escape') setState({ status: 'idle' }); }}
            placeholder="Name oder Symbol, z. B. Siemens oder AAPL"
            autoComplete="off"
          />
          <button type="submit" className={`${styles.btn} ${styles.btnSolid}`}>Suchen</button>
        </div>
      </form>

      {state.status !== 'idle' && (
        <ul className={styles.results}>
          {state.status === 'loading' && <li className={styles.resultEmpty}>Suche …</li>}
          {state.status === 'error' && <li className={styles.resultEmpty}>Die Suche hat nicht geklappt. Versuche es gleich noch einmal.</li>}
          {state.status === 'done' && state.results.length === 0 && <li className={styles.resultEmpty}>Keine Treffer.</li>}
          {state.status === 'done' && state.results.map((r) => (
            <li key={r.symbol}>
              <button type="button" className={styles.resultItem} onClick={() => add(r.symbol)}>
                <span className={styles.resultSymbol}>{r.symbol}</span>
                <span className={styles.resultName}>{r.description}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
