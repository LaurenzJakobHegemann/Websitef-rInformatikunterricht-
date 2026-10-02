import { describe, it, expect } from 'vitest';
import {
  buildFinancials, daysUntil, formatMultiple, formatPercent, formatUsdMillions, pick,
  relativeDayLabel, safeUrl, summarizeRecommendation,
} from './financials';

const values = (tiles: { label: string; value: string }[]) => Object.fromEntries(tiles.map((t) => [t.label, t.value]));

describe('buildFinancials', () => {
  const metric = {
    peTTM: 35.2, psTTM: 9.1, pbQuarterly: 52.3, revenuePerShareTTM: 25.5, ebitdPerShareTTM: 8.6,
    epsTTM: 6.4, enterpriseValue: 3_500_000, grossMarginTTM: 46.2, operatingMarginTTM: 31.5,
    netProfitMarginTTM: 24.3, roeTTM: 150.1, revenueGrowthTTMYoy: 4.9, dividendYieldIndicatedAnnual: 0.45,
  };

  it('derives totals, margins and EV multiples from per-share values', () => {
    const f = buildFinancials(metric, { shareOutstanding: 15_000 });
    expect(values(f.valuation)).toEqual({
      'KGV (P/E)': '35,2x', 'KUV (P/S)': '9,1x', 'KBV (P/B)': '52,3x', 'EV / EBITDA': '27,1x', 'EV / Umsatz': '9,2x',
    });
    expect(values(f.profitability)['EBITDA-Marge']).toBe('33,7 %');
    expect(values(f.absolute)).toMatchObject({
      Umsatz: '382,50 Mrd. USD', EBITDA: '129,00 Mrd. USD', Nettogewinn: '96,00 Mrd. USD',
      'Gewinn je Aktie': '6,40 USD', Dividendenrendite: '0,45 %',
    });
  });

  it('prefers reported EV multiples over computed ones', () => {
    const f = buildFinancials({ ...metric, evEbitdaTTM: 20 }, { shareOutstanding: 15_000 });
    const tile = f.valuation.find((t) => t.label === 'EV / EBITDA')!;
    expect(tile.value).toBe('20,0x');
    expect(tile.hint).not.toBe('berechnet');
  });

  it('shows dashes instead of wrong numbers when inputs are missing', () => {
    const f = buildFinancials({ peTTM: -12 }, { shareOutstanding: undefined });
    expect(values(f.valuation)['KGV (P/E)']).toBe('neg.');
    expect(values(f.valuation)['EV / EBITDA']).toBe('–');
    expect(values(f.profitability)['EBITDA-Marge']).toBe('–');
    expect(values(f.absolute).Umsatz).toBe('–');
  });
});

describe('formatters', () => {
  it('formats money, multiples and percentages the German way', () => {
    expect(formatUsdMillions(3_520_000)).toBe('3,52 Bio. USD');
    expect(formatUsdMillions(-950)).toBe('-950 Mio. USD');
    expect(formatMultiple(null)).toBe('–');
    expect(formatPercent(-8)).toBe('-8,0 %');
  });

  it('pick ignores non-numeric and non-finite values', () => {
    expect(pick({ a: 'x', b: Number.NaN, c: 4 }, ['a', 'b', 'c'])).toBe(4);
    expect(pick({}, ['a'])).toBeNull();
  });
});

describe('summarizeRecommendation', () => {
  it('computes the share of buy ratings', () => {
    expect(summarizeRecommendation({ period: '2026-09-01', strongBuy: 12, buy: 20, hold: 8, sell: 2, strongSell: 1 }))
      .toEqual({ total: 43, bullishPercent: 74 });
  });

  it('returns null when nobody rated the stock', () => {
    expect(summarizeRecommendation({ period: '2026-09-01', strongBuy: 0, buy: 0, hold: 0, sell: 0, strongSell: 0 })).toBeNull();
  });
});

describe('dates and urls', () => {
  it('counts calendar days in local time', () => {
    expect(daysUntil(new Date(2026, 9, 14, 1), new Date(2026, 9, 2, 23))).toBe(12);
    expect(relativeDayLabel(0)).toBe('heute');
    expect(relativeDayLabel(1)).toBe('morgen');
  });

  it('only allows http(s) links', () => {
    expect(safeUrl('https://example.com/a')).toBe('https://example.com/a');
    expect(safeUrl('javascript:alert(1)')).toBeNull();
    expect(safeUrl('')).toBeNull();
  });
});
