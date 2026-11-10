// Ausführen mit: node --test js/labor-engine.test.js
const test = require('node:test');
const assert = require('node:assert');
const L = require('./labor-engine.js');

const base = { mu: 0.07, sigma: 0.2, years: 10, seed: 42, capital: 10000, feeBps: 10 };

test('gleicher Seed ergibt denselben Markt', () => {
  const a = L.generateMarket(base).prices, b = L.generateMarket(base).prices;
  assert.deepStrictEqual(Array.from(a), Array.from(b));
  assert.strictEqual(a.length, 2521);
  assert.ok(a.every((x) => x > 0 && Number.isFinite(x)));
});

test('SMA und RSI auf bekannten Werten', () => {
  assert.deepStrictEqual(Array.from(L.sma([1, 2, 3, 4, 5], 2)).slice(1), [1.5, 2.5, 3.5, 4.5]);
  const up = L.rsi(Array.from({ length: 30 }, (_, i) => i + 1));
  assert.strictEqual(up[29], 100);
  const down = L.rsi(Array.from({ length: 30 }, (_, i) => 100 - i));
  assert.strictEqual(down[29], 0);
});

test('Buy & Hold ohne Gebühren folgt exakt dem Kurs', () => {
  const { prices } = L.generateMarket(base);
  const r = L.backtest(prices, L.positions(prices, 'hold'), { capital: 10000, feeBps: 0 });
  const expected = 10000 * prices[prices.length - 1] / prices[0];
  assert.ok(Math.abs(r.stats.final - expected) < 1e-6);
  assert.strictEqual(r.stats.exposure, 1);
});

test('Gebühren kosten Geld, Cash bleibt konstant', () => {
  const prices = Float64Array.from([100, 110, 121, 121, 121]);
  const pos = Uint8Array.from([1, 1, 0, 0, 0]);
  const r = L.backtest(prices, pos, { capital: 1000, feeBps: 100 });
  assert.ok(Math.abs(r.stats.final - 1000 * 0.99 * 1.21 * 0.99) < 1e-9);
  assert.strictEqual(r.stats.rounds, 1);
  assert.strictEqual(r.stats.winRate, 1);
});

test('Strategie schaut nicht in die Zukunft', () => {
  const { prices } = L.generateMarket(base);
  const full = L.positions(prices, 'sma', 20, 100);
  const cut = L.positions(prices.slice(0, 1000), 'sma', 20, 100);
  assert.deepStrictEqual(Array.from(full.slice(0, 1000)), Array.from(cut));
});

test('Monte Carlo liefert geordnete Bänder', () => {
  const mc = L.monteCarlo({ ...base, strategy: 'sma', p1: 20, p2: 100 }, 60);
  const last = mc.bands.map((b) => b[b.length - 1]);
  for (let k = 1; k < last.length; k++) assert.ok(last[k] >= last[k - 1]);
  assert.ok(mc.beat >= 0 && mc.beat <= 1);
  assert.strictEqual(mc.bands[2][0], 10000);
});
