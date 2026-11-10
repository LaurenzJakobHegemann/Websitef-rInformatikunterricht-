// Strategie-Labor: Rechenkern ohne DOM. Läuft im Browser und in Node (für Tests).
(function (root) {
  'use strict';

  const DAYS = 252;

  // Kleiner, schneller Zufallsgenerator mit Startwert – gleicher Seed, gleicher Markt.
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function gauss(rng) {
    let u = 0;
    while (u === 0) u = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rng());
  }

  // Geometrische Brownsche Bewegung mit zwei Marktphasen (Bulle/Bär).
  // Die Phasen sind so gewichtet, dass die mittlere Drift ungefähr mu bleibt.
  function generateMarket({ mu, sigma, years, seed, start = 100 }) {
    const n = Math.round(years * DAYS);
    const dt = 1 / DAYS;
    const rng = mulberry32(seed);
    const prices = new Float64Array(n + 1);
    const regimes = new Uint8Array(n + 1);
    prices[0] = start;
    let bear = 0;
    for (let i = 1; i <= n; i++) {
      if (rng() < (bear ? 0.02 : 0.008)) bear ^= 1;
      const m = bear ? mu - 0.25 : mu + 0.10;
      const s = bear ? sigma * 1.5 : sigma * 0.85;
      const r = (m - 0.5 * s * s) * dt + s * Math.sqrt(dt) * gauss(rng);
      prices[i] = prices[i - 1] * Math.exp(r);
      regimes[i] = bear;
    }
    return { prices, regimes };
  }

  function sma(data, period) {
    const out = new Float64Array(data.length).fill(NaN);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      sum += data[i];
      if (i >= period) sum -= data[i - period];
      if (i >= period - 1) out[i] = sum / period;
    }
    return out;
  }

  // RSI nach Wilder
  function rsi(data, period = 14) {
    const out = new Float64Array(data.length).fill(NaN);
    let gain = 0, loss = 0;
    for (let i = 1; i < data.length; i++) {
      const d = data[i] - data[i - 1];
      const g = d > 0 ? d : 0, l = d < 0 ? -d : 0;
      if (i <= period) {
        gain += g / period; loss += l / period;
      } else {
        gain = (gain * (period - 1) + g) / period;
        loss = (loss * (period - 1) + l) / period;
      }
      if (i >= period) out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    }
    return out;
  }

  // Position (0 = Cash, 1 = investiert), entschieden zum Schlusskurs von Tag i,
  // wirksam für die Rendite von Tag i auf i+1. Kein Blick in die Zukunft.
  function positions(prices, strategy, p1, p2) {
    const n = prices.length;
    const pos = new Uint8Array(n);
    if (strategy === 'hold') return pos.fill(1);
    if (strategy === 'sma') {
      const f = sma(prices, p1), s = sma(prices, p2);
      for (let i = 0; i < n; i++) pos[i] = f[i] > s[i] ? 1 : 0;
    } else if (strategy === 'momentum') {
      for (let i = p1; i < n; i++) pos[i] = prices[i] > prices[i - p1] ? 1 : 0;
    } else if (strategy === 'rsi') {
      const r = rsi(prices, 14);
      let cur = 0;
      for (let i = 0; i < n; i++) {
        if (r[i] < p1) cur = 1;
        else if (r[i] > p2) cur = 0;
        pos[i] = cur;
      }
    }
    return pos;
  }

  function backtest(prices, pos, { capital = 10000, feeBps = 0 } = {}) {
    const n = prices.length - 1;
    const fee = feeBps / 10000;
    const equity = new Float64Array(n + 1);
    const trades = [];
    equity[0] = capital;
    let eq = capital, prev = 0, entryEq = 0, wins = 0, rounds = 0, inMarket = 0;
    let peak = capital, maxDD = 0, sumR = 0, sumR2 = 0;
    for (let i = 0; i < n; i++) {
      const before = eq;
      if (pos[i] !== prev) {
        eq *= 1 - fee;
        trades.push({ i, buy: pos[i] === 1 });
        if (pos[i] === 1) entryEq = eq;
        else { rounds++; if (eq > entryEq) wins++; }
        prev = pos[i];
      }
      if (prev) { eq *= prices[i + 1] / prices[i]; inMarket++; }
      equity[i + 1] = eq;
      if (eq > peak) peak = eq;
      const dd = 1 - eq / peak;
      if (dd > maxDD) maxDD = dd;
      const r = eq / before - 1;
      sumR += r; sumR2 += r * r;
    }
    const years = n / DAYS;
    const mean = sumR / n;
    const vol = Math.sqrt(Math.max(0, sumR2 / n - mean * mean) * DAYS);
    return {
      equity, trades,
      stats: {
        final: eq,
        total: eq / capital - 1,
        cagr: Math.pow(eq / capital, 1 / years) - 1,
        vol,
        sharpe: vol > 0 ? (mean * DAYS) / vol : 0,
        maxDD,
        rounds,
        winRate: rounds ? wins / rounds : NaN,
        exposure: inMarket / n,
      },
    };
  }

  function quantile(sorted, q) {
    const pos = (sorted.length - 1) * q;
    const lo = Math.floor(pos), hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }

  // Dieselbe Strategie auf vielen zufälligen Märkten mit denselben Parametern.
  function monteCarlo(p, runs = 300) {
    const n = Math.round(p.years * DAYS);
    const step = Math.max(1, Math.floor(n / 120));
    const cols = Math.floor(n / step) + 1;
    const paths = Array.from({ length: cols }, () => new Float64Array(runs));
    const strat = new Float64Array(runs), hold = new Float64Array(runs);
    const ddS = new Float64Array(runs), ddH = new Float64Array(runs);
    let beat = 0;
    for (let r = 0; r < runs; r++) {
      const { prices } = generateMarket({ ...p, seed: p.seed * 7919 + r + 1 });
      const a = backtest(prices, positions(prices, p.strategy, p.p1, p.p2), p);
      const b = backtest(prices, positions(prices, 'hold'), p);
      strat[r] = a.stats.total; hold[r] = b.stats.total;
      ddS[r] = a.stats.maxDD; ddH[r] = b.stats.maxDD;
      if (strat[r] > hold[r]) beat++;
      for (let c = 0; c < cols; c++) paths[c][r] = a.equity[c * step];
    }
    const qs = [0.05, 0.25, 0.5, 0.75, 0.95];
    const bands = qs.map(() => new Float64Array(cols));
    for (let c = 0; c < cols; c++) {
      const s = paths[c].sort();
      qs.forEach((q, k) => { bands[k][c] = quantile(s, q); });
    }
    const med = (a) => quantile(Float64Array.from(a).sort(), 0.5);
    return {
      runs, bands, strat, hold,
      beat: beat / runs,
      medStrat: med(strat), medHold: med(hold),
      medDDStrat: med(ddS), medDDHold: med(ddH),
      lossStrat: strat.filter((x) => x < 0).length / runs,
      lossHold: hold.filter((x) => x < 0).length / runs,
    };
  }

  const api = { DAYS, mulberry32, generateMarket, sma, rsi, positions, backtest, quantile, monteCarlo };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Labor = api;
})(typeof self !== 'undefined' ? self : this);
