'use client';

import { useEffect, useRef, useState } from 'react';
import {
  fetchCandles, fetchCompanyNews, fetchExecutives, fetchMetrics, fetchPeers, fetchProfile, fetchQuote,
  fetchRecommendation,
} from '@/lib/stocks/finnhub';
import {
  PEER_COLUMNS, RATING_SEGMENTS, buildFinancials, formatNumber, formatUsdMillions, pick, safeUrl,
  summarizeRecommendation, type MetricTile,
} from '@/lib/stocks/financials';
import type {
  Candles, CompanyProfile, Executive, Metrics, NewsItem, Quote, Recommendation,
} from '@/lib/stocks/types';
import PriceChart from './PriceChart';
import styles from './stocks.module.css';

interface DetailData {
  profile: CompanyProfile | null;
  quote: Quote | null;
  candles: Candles | null;
  metrics: Metrics | null;
  recommendation: Recommendation | null;
  news: NewsItem[] | null;
  executives: Executive[] | null;
}

type PeerState = { status: 'loading' } | { status: 'done'; rows: { symbol: string; metric: Metrics | null }[] } | { status: 'none' };

const SEGMENT_CLASS: Record<(typeof RATING_SEGMENTS)[number]['key'], string> = {
  strongBuy: styles.segStrongBuy,
  buy: styles.segBuy,
  hold: styles.segHold,
  sell: styles.segSell,
  strongSell: styles.segStrongSell,
};

const PLAN_NOTE = 'bei Finnhub teils nur im bezahlten Plan enthalten';
const monthYear = new Intl.DateTimeFormat('de-DE', { month: 'long', year: 'numeric' });
const shortDate = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: 'short' });

function settled<T>(r: PromiseSettledResult<T>): T | null {
  return r.status === 'fulfilled' ? r.value : null;
}

export default function CompanyDetail({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [data, setData] = useState<DetailData | null>(null);
  const [peers, setPeers] = useState<PeerState>({ status: 'loading' });
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const r = await Promise.allSettled([
        fetchProfile(symbol), fetchQuote(symbol), fetchCandles(symbol), fetchMetrics(symbol),
        fetchRecommendation(symbol), fetchCompanyNews(symbol), fetchExecutives(symbol),
      ]);
      if (cancelled) return;
      const loaded: DetailData = {
        profile: settled(r[0]), quote: settled(r[1]), candles: settled(r[2]), metrics: settled(r[3]),
        recommendation: settled(r[4]), news: settled(r[5]), executives: settled(r[6]),
      };
      setData(loaded);

      try {
        const symbols = await fetchPeers(symbol);
        if (symbols.length < 2) {
          if (!cancelled) setPeers({ status: 'none' });
          return;
        }
        const metrics = await Promise.allSettled(
          symbols.map((s) => (s === symbol && loaded.metrics ? Promise.resolve(loaded.metrics) : fetchMetrics(s)))
        );
        if (!cancelled) setPeers({ status: 'done', rows: symbols.map((s, i) => ({ symbol: s, metric: settled(metrics[i]) })) });
      } catch {
        if (!cancelled) setPeers({ status: 'none' });
      }
    })();

    return () => { cancelled = true; };
  }, [symbol]);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <aside
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label={`Firmenprofil ${symbol}`}
        onClick={(e) => e.stopPropagation()}
      >
        <button ref={closeRef} type="button" className={`${styles.btn} ${styles.btnSm} ${styles.close}`} onClick={onClose}>
          Schließen
        </button>
        {!data ? <p className={styles.loading}>Lade Firmendaten für {symbol} …</p> : <DetailBody symbol={symbol} data={data} peers={peers} />}
      </aside>
    </div>
  );
}

function DetailBody({ symbol, data, peers }: { symbol: string; data: DetailData; peers: PeerState }) {
  const { profile, quote, candles, metrics, recommendation, news, executives } = data;

  if (!profile) {
    return <p className={styles.loading}>Das Firmenprofil für {symbol} konnte nicht geladen werden. Versuche es gleich noch einmal.</p>;
  }

  const logo = safeUrl(profile.logo);
  const web = safeUrl(profile.weburl);
  const currency = profile.currency || 'USD';

  return (
    <>
      <div className={styles.profileHead}>
        {/* Externe Logos unbekannter Größe; next/image bräuchte dafür eine Image-Optimierung im Worker. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {logo && <img className={styles.logo} src={logo} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />}
        <div>
          <p className={styles.eyebrow} style={{ marginBottom: 6 }}>Firmenprofil</p>
          <h2 className={styles.profileName}>{profile.name}</h2>
        </div>
      </div>
      <div className={styles.badges}>
        <span className={`${styles.badge} ${styles.badgeActive}`}>{symbol}</span>
        {profile.exchange && <span className={styles.badge}>{profile.exchange}</span>}
        {profile.country && <span className={styles.badge}>{profile.country}</span>}
      </div>

      {quote && quote.c > 0 && (
        <div className={styles.priceLine}>
          <span className={styles.price}>{formatNumber(quote.c)} {currency}</span>
          {typeof quote.dp === 'number' && (
            <span className={quote.dp >= 0 ? styles.up : styles.down}>
              {quote.dp >= 0 ? '+' : ''}{formatNumber(quote.d)} ({quote.dp >= 0 ? '+' : ''}{formatNumber(quote.dp)} %) heute
            </span>
          )}
        </div>
      )}

      <section className={styles.block}>
        <dl className={styles.facts}>
          <Fact label="Branche" value={profile.finnhubIndustry} />
          <Fact label="Marktkapitalisierung" value={formatUsdMillions(profile.marketCapitalization)} />
          <Fact label="Börsengang" value={profile.ipo} />
          <Fact label="Ausstehende Aktien" value={profile.shareOutstanding ? `${formatNumber(profile.shareOutstanding, 1)} Mio.` : undefined} />
          <Fact label="Währung" value={profile.currency} />
          <div>
            <dt>Website</dt>
            <dd>{web ? <a href={web} target="_blank" rel="noopener noreferrer">{new URL(web).hostname.replace(/^www\./, '')}</a> : '–'}</dd>
          </div>
        </dl>
      </section>

      <section className={styles.block}>
        <p className={styles.eyebrow}>Kursverlauf · 1 Jahr</p>
        {candles ? <PriceChart candles={candles} currency={currency} /> : <p className={styles.dataNote}>Kein Kursverlauf verfügbar ({PLAN_NOTE}).</p>}
      </section>

      <section className={styles.block}>
        <p className={styles.eyebrow}>Analysten-Einschätzungen</p>
        <AnalystRatings recommendation={recommendation} />
      </section>

      <section className={styles.block}>
        <p className={styles.eyebrow}>Finanzkennzahlen</p>
        {metrics ? <Financials metrics={metrics} profile={profile} /> : <p className={styles.dataNote}>Keine Finanzkennzahlen verfügbar.</p>}
      </section>

      <section className={styles.block}>
        <p className={styles.eyebrow}>Vergleich mit Konkurrenten</p>
        <PeerTable symbol={symbol} peers={peers} />
      </section>

      <section className={styles.block}>
        <p className={styles.eyebrow}>Aktuelle Nachrichten</p>
        <NewsList news={news} />
      </section>

      <section className={styles.block}>
        <p className={styles.eyebrow}>Management</p>
        {executives ? (
          <ul className={styles.execs}>
            {executives.map((e) => (
              <li key={`${e.name}-${e.title}`}><span>{e.name}</span><span className={styles.execTitle}>{e.title}</span></li>
            ))}
          </ul>
        ) : (
          <p className={styles.dataNote}>Keine Management-Daten verfügbar ({PLAN_NOTE}).</p>
        )}
      </section>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value || '–'}</dd>
    </div>
  );
}

function AnalystRatings({ recommendation }: { recommendation: Recommendation | null }) {
  const summary = recommendation ? summarizeRecommendation(recommendation) : null;
  if (!recommendation || !summary) return <p className={styles.dataNote}>Keine Analysten-Einschätzungen verfügbar.</p>;

  return (
    <>
      <p className={styles.ratingSummary}>
        <strong>{summary.bullishPercent} %</strong>
        von {summary.total} Analysten empfehlen Kaufen
        <span className={styles.meta}> · Stand {monthYear.format(new Date(recommendation.period))}</span>
      </p>
      <div className={styles.ratingBar} aria-hidden="true">
        {RATING_SEGMENTS.filter((s) => recommendation[s.key] > 0).map((s) => (
          <span key={s.key} className={`${styles.ratingSeg} ${SEGMENT_CLASS[s.key]}`} style={{ flexGrow: recommendation[s.key] }} />
        ))}
      </div>
      <ul className={styles.ratingLegend}>
        {RATING_SEGMENTS.map((s) => (
          <li key={s.key}>
            <span className={`${styles.swatch} ${SEGMENT_CLASS[s.key]}`} />
            {s.label} <strong>{recommendation[s.key] || 0}</strong>
          </li>
        ))}
      </ul>
    </>
  );
}

function Financials({ metrics, profile }: { metrics: Metrics; profile: CompanyProfile }) {
  const f = buildFinancials(metrics, profile);
  return (
    <>
      <MetricGroup title="Bewertung" tiles={f.valuation} />
      <MetricGroup title="Profitabilität" tiles={f.profitability} />
      <MetricGroup title="Umsatz und Gewinn" tiles={f.absolute} />
    </>
  );
}

function MetricGroup({ title, tiles }: { title: string; tiles: MetricTile[] }) {
  return (
    <div className={styles.metricGroup}>
      <h3 className={styles.metricGroupTitle}>{title}</h3>
      <div className={styles.metricGrid}>
        {tiles.map((t) => (
          <div key={t.label} className={styles.metric}>
            <span className={styles.metricLabel}>{t.label}</span>
            <span className={styles.metricValue}>{t.value}</span>
            <span className={styles.metricHint}>{t.hint}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PeerTable({ symbol, peers }: { symbol: string; peers: PeerState }) {
  if (peers.status === 'loading') return <p className={styles.dataNote}>Lade Vergleich …</p>;
  if (peers.status === 'none') return <p className={styles.dataNote}>Kein Vergleich mit Konkurrenten verfügbar.</p>;

  return (
    <div className={styles.tableScroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Symbol</th>
            {PEER_COLUMNS.map((c) => <th key={c.label} scope="col">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {peers.rows.map((row) => (
            <tr key={row.symbol} className={row.symbol === symbol ? styles.peerCurrent : undefined}>
              <td>{row.symbol}</td>
              {PEER_COLUMNS.map((c) => <td key={c.label}>{row.metric ? c.format(pick(row.metric, [...c.keys])) : '–'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NewsList({ news }: { news: NewsItem[] | null }) {
  if (!news || news.length === 0) return <p className={styles.dataNote}>Keine Nachrichten aus den letzten 14 Tagen gefunden.</p>;

  return (
    <ul className={styles.news}>
      {news.map((n) => {
        const url = safeUrl(n.url);
        return (
          <li key={n.id ?? `${n.datetime}-${n.headline}`} className={styles.newsItem}>
            <div className={styles.newsMeta}>{n.source} · {shortDate.format(new Date(n.datetime * 1000))}</div>
            {url ? (
              <a className={styles.newsLink} href={url} target="_blank" rel="noopener noreferrer">{n.headline}</a>
            ) : (
              <span className={styles.newsLink}>{n.headline}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
