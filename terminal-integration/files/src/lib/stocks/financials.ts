/**
 * Kennzahlen und Formatierung für die Aktienansicht (rein, ohne Browser-APIs).
 */

import type { CompanyProfile, Metrics, Recommendation } from './types';

const NUMBER_FORMATS = new Map<number, Intl.NumberFormat>();

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '–';
  let fmt = NUMBER_FORMATS.get(digits);
  if (!fmt) {
    fmt = new Intl.NumberFormat('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    NUMBER_FORMATS.set(digits, fmt);
  }
  return fmt.format(value);
}

export function formatUsdMillions(millions: number | null | undefined): string {
  if (typeof millions !== 'number' || !Number.isFinite(millions)) return '–';
  const sign = millions < 0 ? '-' : '';
  const abs = Math.abs(millions);
  if (abs >= 1_000_000) return `${sign}${formatNumber(abs / 1_000_000)} Bio. USD`;
  if (abs >= 1_000) return `${sign}${formatNumber(abs / 1_000)} Mrd. USD`;
  return `${sign}${formatNumber(abs, 0)} Mio. USD`;
}

export function formatMultiple(value: number | null): string {
  if (value === null) return '–';
  if (value < 0) return 'neg.';
  return `${formatNumber(value, 1)}x`;
}

export function formatPercent(value: number | null): string {
  if (value === null) return '–';
  return `${formatNumber(value, Math.abs(value) < 1 ? 2 : 1)} %`;
}

/** Finnhub-Feldnamen variieren je nach Symbol; der erste vorhandene Zahlenwert gewinnt. */
export function pick(metric: Metrics, keys: string[]): number | null {
  for (const key of keys) {
    const v = metric[key];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
  }
  return null;
}

export const METRIC_KEYS = {
  pe: ['peTTM', 'peBasicExclExtraTTM', 'peNormalizedAnnual', 'peAnnual'],
  ps: ['psTTM', 'psAnnual'],
  pb: ['pbQuarterly', 'pbAnnual', 'pb'],
  evEbitda: ['evEbitdaTTM', 'ev/ebitdaTTM', 'currentEv/ebitdaTTM'],
  evRevenue: ['evRevenueTTM', 'ev/revenueTTM', 'currentEv/revenueTTM'],
  revenuePerShare: ['revenuePerShareTTM', 'revenuePerShareAnnual'],
  ebitdaPerShare: ['ebitdPerShareTTM', 'ebitdPerShareAnnual'],
  eps: ['epsTTM', 'epsInclExtraItemsTTM', 'epsBasicExclExtraItemsTTM', 'epsAnnual'],
  enterpriseValue: ['enterpriseValue'],
  grossMargin: ['grossMarginTTM', 'grossMarginAnnual'],
  operatingMargin: ['operatingMarginTTM', 'operatingMarginAnnual'],
  netMargin: ['netProfitMarginTTM', 'netProfitMarginAnnual'],
  roe: ['roeTTM', 'roeRfy'],
  revenueGrowth: ['revenueGrowthTTMYoy', 'revenueGrowthQuarterlyYoy'],
  dividendYield: ['dividendYieldIndicatedAnnual', 'currentDividendYieldTTM'],
} as const;

export interface MetricTile {
  label: string;
  value: string;
  hint: string;
}

export interface FinancialGroups {
  valuation: MetricTile[];
  profitability: MetricTile[];
  absolute: MetricTile[];
}

/**
 * Beträge in Mio. USD: Finnhub liefert shareOutstanding in Mio. Stück und *PerShare-Werte in USD.
 * Umsatz, EBITDA und Nettogewinn werden daraus hochgerechnet und als "berechnet" markiert.
 */
export function buildFinancials(metric: Metrics, profile: Pick<CompanyProfile, 'shareOutstanding'>): FinancialGroups {
  const shares = typeof profile.shareOutstanding === 'number' && profile.shareOutstanding > 0 ? profile.shareOutstanding : null;
  const total = (perShare: number | null) => (perShare !== null && shares !== null ? perShare * shares : null);
  const k = METRIC_KEYS;

  const revenue = total(pick(metric, [...k.revenuePerShare]));
  const ebitda = total(pick(metric, [...k.ebitdaPerShare]));
  const eps = pick(metric, [...k.eps]);
  const netIncome = total(eps);
  const ev = pick(metric, [...k.enterpriseValue]);

  const evEbitdaReported = pick(metric, [...k.evEbitda]);
  const evRevenueReported = pick(metric, [...k.evRevenue]);
  const evEbitda = evEbitdaReported ?? (ev !== null && ebitda !== null && ebitda > 0 ? ev / ebitda : null);
  const evRevenue = evRevenueReported ?? (ev !== null && revenue !== null && revenue > 0 ? ev / revenue : null);

  return {
    valuation: [
      { label: 'KGV (P/E)', value: formatMultiple(pick(metric, [...k.pe])), hint: 'Kurs / Gewinn je Aktie' },
      { label: 'KUV (P/S)', value: formatMultiple(pick(metric, [...k.ps])), hint: 'Börsenwert / Umsatz' },
      { label: 'KBV (P/B)', value: formatMultiple(pick(metric, [...k.pb])), hint: 'Kurs / Buchwert je Aktie' },
      { label: 'EV / EBITDA', value: formatMultiple(evEbitda), hint: evEbitdaReported === null ? 'berechnet' : 'Unternehmenswert / EBITDA' },
      { label: 'EV / Umsatz', value: formatMultiple(evRevenue), hint: evRevenueReported === null ? 'berechnet' : 'Unternehmenswert / Umsatz' },
    ],
    profitability: [
      { label: 'EBITDA-Marge', value: formatPercent(ebitda !== null && revenue !== null && revenue > 0 ? (ebitda / revenue) * 100 : null), hint: 'berechnet' },
      { label: 'Bruttomarge', value: formatPercent(pick(metric, [...k.grossMargin])), hint: 'TTM' },
      { label: 'Operative Marge', value: formatPercent(pick(metric, [...k.operatingMargin])), hint: 'TTM' },
      { label: 'Nettomarge', value: formatPercent(pick(metric, [...k.netMargin])), hint: 'TTM' },
      { label: 'Eigenkapitalrendite', value: formatPercent(pick(metric, [...k.roe])), hint: 'ROE, TTM' },
    ],
    absolute: [
      { label: 'Umsatz', value: formatUsdMillions(revenue), hint: 'TTM, berechnet' },
      { label: 'EBITDA', value: formatUsdMillions(ebitda), hint: 'TTM, berechnet' },
      { label: 'Nettogewinn', value: formatUsdMillions(netIncome), hint: 'TTM, berechnet' },
      { label: 'Gewinn je Aktie', value: eps === null ? '–' : `${formatNumber(eps)} USD`, hint: 'EPS, TTM' },
      { label: 'Umsatzwachstum', value: formatPercent(pick(metric, [...k.revenueGrowth])), hint: 'ggü. Vorjahr' },
      { label: 'Dividendenrendite', value: formatPercent(pick(metric, [...k.dividendYield])), hint: 'p.a.' },
    ],
  };
}

export const PEER_COLUMNS: { label: string; keys: readonly string[]; format: (v: number | null) => string }[] = [
  { label: 'KGV', keys: METRIC_KEYS.pe, format: formatMultiple },
  { label: 'KUV', keys: METRIC_KEYS.ps, format: formatMultiple },
  { label: 'KBV', keys: METRIC_KEYS.pb, format: formatMultiple },
  { label: 'Bruttomarge', keys: METRIC_KEYS.grossMargin, format: formatPercent },
  { label: 'Nettomarge', keys: METRIC_KEYS.netMargin, format: formatPercent },
  { label: 'Wachstum', keys: METRIC_KEYS.revenueGrowth, format: formatPercent },
];

export const RATING_SEGMENTS = [
  { key: 'strongBuy', label: 'Stark kaufen' },
  { key: 'buy', label: 'Kaufen' },
  { key: 'hold', label: 'Halten' },
  { key: 'sell', label: 'Verkaufen' },
  { key: 'strongSell', label: 'Stark verkaufen' },
] as const;

export function summarizeRecommendation(rec: Recommendation): { total: number; bullishPercent: number } | null {
  const total = RATING_SEGMENTS.reduce((sum, s) => sum + (rec[s.key] || 0), 0);
  if (total === 0) return null;
  return { total, bullishPercent: Math.round((((rec.strongBuy || 0) + (rec.buy || 0)) / total) * 100) };
}

export function daysUntil(target: Date, today = new Date()): number {
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const end = new Date(target.getFullYear(), target.getMonth(), target.getDate());
  return Math.round((end.getTime() - start.getTime()) / 86_400_000);
}

export function relativeDayLabel(days: number): string {
  if (days === 0) return 'heute';
  if (days === 1) return 'morgen';
  return `in ${days} Tagen`;
}

export const EARNINGS_HOUR_LABELS: Record<string, string> = {
  bmo: 'vor Börsenstart',
  amc: 'nach Börsenschluss',
  dmh: 'während des Handels',
};

export function safeUrl(url: string | undefined | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
  } catch {
    return null;
  }
}
