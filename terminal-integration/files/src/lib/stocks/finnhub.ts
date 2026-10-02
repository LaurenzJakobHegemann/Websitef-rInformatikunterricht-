/**
 * Finnhub-Client für die Aktienansicht. Läuft im Browser: jeder Nutzer verwendet
 * seinen eigenen kostenlosen Key (localStorage), es gibt keinen Server-Key.
 * Limit (429) und ungültiger Key (401) werden an die Oberfläche gemeldet.
 */

import type {
  Candles, CompanyProfile, EarningsEvent, Executive, Metrics, NewsItem, Quote,
  Recommendation, SymbolSearchResult,
} from './types';

const BASE = 'https://finnhub.io/api/v1';
const TIMEOUT_MS = 10_000;

export class FinnhubError extends Error {
  constructor(public status: number, path: string) {
    super(`Finnhub ${path}: HTTP ${status}`);
  }
}

let apiKey = '';

export function setActiveApiKey(key: string): void {
  apiKey = key;
}

/* ---------- Key-Probleme an die Oberfläche melden (für useSyncExternalStore) ---------- */

export type KeyProblem = 'limit' | 'invalid';

/** `id` steigt bei jedem neuen Problem, damit ein geschlossener Hinweis beim nächsten Mal wieder erscheint. */
export interface KeyProblemState {
  problem: KeyProblem | null;
  id: number;
}

let problemState: KeyProblemState = { problem: null, id: 0 };
const problemListeners = new Set<() => void>();

function setKeyProblem(problem: KeyProblem | null): void {
  if (problem === problemState.problem) return;
  problemState = { problem, id: problem ? problemState.id + 1 : problemState.id };
  problemListeners.forEach((l) => l());
}

export function clearKeyProblem(): void {
  setKeyProblem(null);
}

export function getKeyProblemState(): KeyProblemState {
  return problemState;
}

export function subscribeKeyProblem(listener: () => void): () => void {
  problemListeners.add(listener);
  return () => {
    problemListeners.delete(listener);
  };
}

/* ---------- Anfragen ---------- */

async function finnhubGet<T>(path: string, params: Record<string, string | number> = {}): Promise<T> {
  const query = new URLSearchParams({ ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])), token: apiKey });
  const res = await fetch(`${BASE}${path}?${query}`, { signal: AbortSignal.timeout(TIMEOUT_MS) });

  if (res.status === 429) {
    setKeyProblem('limit');
    throw new FinnhubError(res.status, path);
  }
  if (res.status === 401) {
    setKeyProblem('invalid');
    throw new FinnhubError(res.status, path);
  }
  // 403 heißt bei Finnhub meist "nur im bezahlten Plan" und ist kein Key-Problem.
  if (!res.ok) throw new FinnhubError(res.status, path);

  clearKeyProblem();
  return res.json() as Promise<T>;
}

export type KeyCheckResult = 'ok' | 'invalid' | 'limit' | 'unreachable';

/** Prüft einen neuen Key, ohne die Hinweisleiste auszulösen. */
export async function checkApiKey(key: string): Promise<KeyCheckResult> {
  try {
    const res = await fetch(`${BASE}/quote?${new URLSearchParams({ symbol: 'AAPL', token: key })}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (res.status === 401 || res.status === 403) return 'invalid';
    if (res.status === 429) return 'limit';
    if (!res.ok) return 'unreachable';
    const data = (await res.json()) as Partial<Quote>;
    return typeof data.c === 'number' ? 'ok' : 'invalid';
  } catch {
    return 'unreachable';
  }
}

/* ---------- Datum-Helfer (lokale Zeit, nicht UTC) ---------- */

export function isoDate(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${m}-${d}`;
}

export function parseIsoDate(value: string): Date {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function daysFromNow(days: number): Date {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d;
}

/* ---------- Endpunkte ---------- */

export function fetchQuote(symbol: string): Promise<Quote> {
  return finnhubGet<Quote>('/quote', { symbol });
}

export async function searchSymbols(query: string): Promise<SymbolSearchResult[]> {
  const data = await finnhubGet<{ result?: SymbolSearchResult[] }>('/search', { q: query });
  return (data.result ?? []).slice(0, 15);
}

export async function fetchProfile(symbol: string): Promise<CompanyProfile> {
  const data = await finnhubGet<CompanyProfile>('/stock/profile2', { symbol });
  if (!data?.name) throw new Error('Kein Profil verfügbar');
  return data;
}

export async function fetchExecutives(symbol: string): Promise<Executive[]> {
  const data = await finnhubGet<{ executive?: Executive[] }>('/stock/executive', { symbol });
  if (!data?.executive?.length) throw new Error('Keine Management-Daten');
  return data.executive.slice(0, 6);
}

export async function fetchCandles(symbol: string): Promise<Candles> {
  const to = Math.floor(Date.now() / 1000);
  const from = to - 365 * 24 * 60 * 60;
  const data = await finnhubGet<Candles>('/stock/candle', { symbol, resolution: 'W', from, to });
  if (data?.s !== 'ok' || !Array.isArray(data.c) || data.c.length < 2) {
    throw new Error('Keine historischen Kurse');
  }
  return data;
}

export async function fetchMetrics(symbol: string): Promise<Metrics> {
  const data = await finnhubGet<{ metric?: Metrics }>('/stock/metric', { symbol, metric: 'all' });
  if (!data?.metric || Object.keys(data.metric).length === 0) throw new Error('Keine Kennzahlen');
  return data.metric;
}

export async function fetchCompanyNews(symbol: string): Promise<NewsItem[]> {
  const items = await finnhubGet<NewsItem[]>('/company-news', {
    symbol,
    from: isoDate(daysFromNow(-14)),
    to: isoDate(new Date()),
  });
  if (!Array.isArray(items)) throw new Error('Keine News');
  return [...items].sort((a, b) => b.datetime - a.datetime).slice(0, 6);
}

export async function fetchRecommendation(symbol: string): Promise<Recommendation> {
  const data = await finnhubGet<Recommendation[]>('/stock/recommendation', { symbol });
  if (!Array.isArray(data) || data.length === 0) throw new Error('Keine Analystendaten');
  return [...data].sort((a, b) => String(b.period).localeCompare(String(a.period)))[0];
}

/** Liefert das Symbol selbst plus bis zu 4 Konkurrenten. */
export async function fetchPeers(symbol: string): Promise<string[]> {
  const peers = await finnhubGet<string[]>('/stock/peers', { symbol });
  if (!Array.isArray(peers)) throw new Error('Keine Peers');
  return [symbol, ...peers.filter((p) => p !== symbol).slice(0, 4)];
}

export const EARNINGS_WINDOW_DAYS = 120;

export async function fetchNextEarnings(symbol: string): Promise<EarningsEvent | null> {
  const data = await finnhubGet<{ earningsCalendar?: EarningsEvent[] }>('/calendar/earnings', {
    symbol,
    from: isoDate(new Date()),
    to: isoDate(daysFromNow(EARNINGS_WINDOW_DAYS)),
  });
  const upcoming = (data?.earningsCalendar ?? [])
    .filter((e) => e.symbol === symbol && e.date)
    .sort((a, b) => a.date.localeCompare(b.date));
  return upcoming[0] ?? null;
}
