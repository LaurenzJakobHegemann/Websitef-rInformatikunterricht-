// Browser-Speicher für die Aktienansicht. Fehlt localStorage (privater Modus o. ä.),
// gelten Key und Watchlist nur für die aktuelle Sitzung.

const KEY_STORAGE = 'parity_finnhub_api_key';
const WATCHLIST_STORAGE = 'parity_watchlist';

export const DEFAULT_WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'SAP'];

export function loadApiKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? '';
  } catch {
    return '';
  }
}

export function saveApiKey(key: string): void {
  try {
    localStorage.setItem(KEY_STORAGE, key);
  } catch {
    /* nur für diese Sitzung */
  }
}

export function loadWatchlist(): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(WATCHLIST_STORAGE) ?? 'null');
    if (Array.isArray(parsed) && parsed.every((s) => typeof s === 'string')) return parsed;
  } catch {
    /* Standardliste */
  }
  return [...DEFAULT_WATCHLIST];
}

export function saveWatchlist(symbols: string[]): void {
  try {
    localStorage.setItem(WATCHLIST_STORAGE, JSON.stringify(symbols));
  } catch {
    /* nur für diese Sitzung */
  }
}
