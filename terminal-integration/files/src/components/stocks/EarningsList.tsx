'use client';

import type { EarningsEvent } from '@/lib/stocks/types';
import { EARNINGS_WINDOW_DAYS, parseIsoDate } from '@/lib/stocks/finnhub';
import { EARNINGS_HOUR_LABELS, daysUntil, formatNumber, relativeDayLabel } from '@/lib/stocks/financials';
import styles from './stocks.module.css';

const dateLabel = new Intl.DateTimeFormat('de-DE', { weekday: 'short', day: '2-digit', month: 'long' });

interface EarningsListProps {
  symbols: string[];
  /** `undefined` = noch nicht geladen, `null` = kein Termin im Zeitraum. */
  earnings: Record<string, EarningsEvent | null | undefined>;
  onOpen: (symbol: string) => void;
}

export default function EarningsList({ symbols, earnings, onOpen }: EarningsListProps) {
  const loading = symbols.some((s) => earnings[s] === undefined);
  const entries = symbols
    .map((s) => earnings[s])
    .filter((e): e is EarningsEvent => Boolean(e))
    .sort((a, b) => a.date.localeCompare(b.date));

  if (entries.length === 0) {
    return (
      <p className={styles.dataNote}>
        {loading ? 'Lade Termine …' : `Keine Termine in den nächsten ${EARNINGS_WINDOW_DAYS} Tagen für deine Watchlist.`}
      </p>
    );
  }

  return (
    <ul className={styles.earnings}>
      {entries.map((e) => {
        const date = parseIsoDate(e.date);
        const details = [
          e.quarter && e.year ? `Q${e.quarter} ${e.year}` : null,
          e.hour ? EARNINGS_HOUR_LABELS[e.hour] : null,
          typeof e.epsEstimate === 'number' ? `EPS-Schätzung ${formatNumber(e.epsEstimate)} USD` : null,
        ].filter(Boolean);
        return (
          <li key={e.symbol} className={styles.earningsCard}>
            <div className={styles.earningsDate}>{dateLabel.format(date)}</div>
            <div className={styles.earningsWhen}>{relativeDayLabel(daysUntil(date))}</div>
            <button type="button" className={styles.symbolButton} onClick={() => onOpen(e.symbol)}>
              {e.symbol}
            </button>
            {details.length > 0 && <div className={styles.earningsDetail}>{details.join(' · ')}</div>}
          </li>
        );
      })}
    </ul>
  );
}
