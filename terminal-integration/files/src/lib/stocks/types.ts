// Antwortformate der Finnhub-Endpunkte, soweit die Aktienansicht sie nutzt.

export interface Quote {
  c: number; // aktueller Kurs
  d: number | null; // Veränderung absolut
  dp: number | null; // Veränderung in %
  h: number;
  l: number;
  o: number;
  pc: number; // Vortagesschluss
}

export interface SymbolSearchResult {
  symbol: string;
  description: string;
  type?: string;
}

export interface CompanyProfile {
  name: string;
  ticker?: string;
  exchange?: string;
  finnhubIndustry?: string;
  country?: string;
  currency?: string;
  ipo?: string;
  logo?: string;
  weburl?: string;
  marketCapitalization?: number; // Mio.
  shareOutstanding?: number; // Mio. Stück
}

export interface Executive {
  name: string;
  title?: string;
}

export interface Candles {
  c: number[];
  t: number[]; // Unix-Sekunden
  s: string;
}

export type Metrics = Record<string, number | string | null | undefined>;

export interface NewsItem {
  id?: number;
  datetime: number;
  headline: string;
  source: string;
  url: string;
}

export interface Recommendation {
  period: string;
  strongBuy: number;
  buy: number;
  hold: number;
  sell: number;
  strongSell: number;
}

export interface EarningsEvent {
  symbol: string;
  date: string; // YYYY-MM-DD
  hour?: string; // bmo | amc | dmh
  quarter?: number;
  year?: number;
  epsEstimate?: number | null;
}
