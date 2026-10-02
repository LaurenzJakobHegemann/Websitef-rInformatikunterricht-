'use client';

import { useMemo, useRef, useState } from 'react';
import type { Candles } from '@/lib/stocks/types';
import { formatNumber } from '@/lib/stocks/financials';
import styles from './stocks.module.css';

const WIDTH = 640;
const HEIGHT = 220;
const PAD_TOP = 10;
const PAD_BOTTOM = 26;
const PAD_LEFT = 56; // Platz für die Kursbeschriftung links, damit sie nie auf der Linie liegt
const PAD_RIGHT = 4;
const TICKS = 5;

const monthLabel = new Intl.DateTimeFormat('de-DE', { month: 'short', year: '2-digit' });
const dayLabel = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: 'short', year: 'numeric' });

export default function PriceChart({ candles, currency = 'USD' }: { candles: Candles; currency?: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const geometry = useMemo(() => {
    const prices = candles.c;
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const x = (i: number) => PAD_LEFT + (i / (prices.length - 1)) * (WIDTH - PAD_LEFT - PAD_RIGHT);
    const y = (p: number) => PAD_TOP + (1 - (p - min) / range) * (HEIGHT - PAD_TOP - PAD_BOTTOM);
    const line = prices.map((p, i) => `${x(i)},${y(p)}`).join(' ');
    const base = HEIGHT - PAD_BOTTOM;
    const area = `${x(0)},${base} ${line} ${x(prices.length - 1)},${base}`;
    const ticks = Array.from({ length: TICKS }, (_, i) => {
      const idx = Math.round((i / (TICKS - 1)) * (prices.length - 1));
      return { x: x(idx), label: monthLabel.format(new Date(candles.t[idx] * 1000)) };
    });
    return { prices, min, max, x, y, line, area, ticks, base };
  }, [candles]);

  const { prices, min, max, x, y, line, area, ticks, base } = geometry;
  const first = prices[0];
  const last = prices[prices.length - 1];
  const yearChange = ((last - first) / first) * 100;

  function handlePointer(clientX: number) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const rel = ((clientX - rect.left) / rect.width) * WIDTH;
    const idx = Math.round(((rel - PAD_LEFT) / (WIDTH - PAD_LEFT - PAD_RIGHT)) * (prices.length - 1));
    setHover(Math.max(0, Math.min(prices.length - 1, idx)));
  }

  return (
    <div className={styles.chart}>
      <p className={styles.chartChange}>
        <span className={yearChange >= 0 ? styles.up : styles.down}>
          {yearChange >= 0 ? '+' : ''}{formatNumber(yearChange, 1)} %
        </span>{' '}
        <span className={styles.meta}>in 12 Monaten</span>
      </p>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Kursverlauf über ein Jahr, von ${formatNumber(first)} auf ${formatNumber(last)} ${currency}`}
        onPointerMove={(e) => handlePointer(e.clientX)}
        onPointerDown={(e) => handlePointer(e.clientX)}
        onPointerLeave={() => setHover(null)}
      >
        <line className={styles.chartGrid} x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={PAD_TOP} y2={PAD_TOP} />
        <line className={styles.chartGrid} x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={(PAD_TOP + base) / 2} y2={(PAD_TOP + base) / 2} />
        <line className={styles.chartGrid} x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={base} y2={base} />
        <polygon className={styles.chartArea} points={area} />
        <polyline className={styles.chartLine} points={line} />
        <text className={styles.chartLabel} x={0} y={PAD_TOP + 4}>{formatNumber(max)}</text>
        <text className={styles.chartLabel} x={0} y={(PAD_TOP + base) / 2 + 4}>{formatNumber((min + max) / 2)}</text>
        <text className={styles.chartLabel} x={0} y={base + 4}>{formatNumber(min)}</text>
        {ticks.map((t, i) => (
          <text
            key={i}
            className={styles.chartLabel}
            x={t.x}
            y={HEIGHT - 6}
            textAnchor={i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'}
          >
            {t.label}
          </text>
        ))}
        {hover !== null && (
          <>
            <line className={styles.chartCrosshair} x1={x(hover)} x2={x(hover)} y1={PAD_TOP} y2={base} />
            <circle className={styles.chartDot} cx={x(hover)} cy={y(prices[hover])} r={4.5} />
          </>
        )}
      </svg>
      {hover !== null && (
        <div
          className={styles.chartTooltip}
          style={{ left: `${(x(hover) / WIDTH) * 100}%`, top: `${(y(prices[hover]) / HEIGHT) * 100}%` }}
        >
          {dayLabel.format(new Date(candles.t[hover] * 1000))}: {formatNumber(prices[hover])} {currency}
        </div>
      )}
    </div>
  );
}
