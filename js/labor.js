// Strategie-Labor: Oberfläche und Diagramme. Rechnen übernimmt labor-engine.js.
(function () {
  'use strict';
  const L = window.Labor;
  const $ = (id) => document.getElementById(id);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const C = { accent: css('--accent'), blue: css('--blue'), green: css('--green'), red: css('--red'),
    muted: css('--muted'), border: css('--border'), text: css('--text') };
  const CAPITAL = 10000, RUNS = 400;

  const STRATS = {
    sma: {
      p1: { label: 'Schneller Durchschnitt', min: 5, max: 100, step: 5, value: 20, unit: ' Tage' },
      p2: { label: 'Langsamer Durchschnitt', min: 50, max: 300, step: 10, value: 100, unit: ' Tage' },
      rule: (a, b) => `Regel: Kaufen, sobald der Durchschnitt der letzten ${a} Tage über dem der letzten ${b} Tage liegt. Verkaufen, sobald er darunter fällt.`,
    },
    momentum: {
      p1: { label: 'Rückblick', min: 20, max: 250, step: 10, value: 120, unit: ' Tage' },
      rule: (a) => `Regel: Investiert bleiben, solange der Kurs höher steht als vor ${a} Tagen. Sonst in Cash warten.`,
    },
    rsi: {
      p1: { label: 'Kaufen bei RSI unter', min: 10, max: 45, step: 1, value: 30, unit: '' },
      p2: { label: 'Verkaufen bei RSI über', min: 55, max: 90, step: 1, value: 70, unit: '' },
      rule: (a, b) => `Regel: Kaufen, wenn der RSI (ein Maß für „überverkauft“, 0 bis 100) unter ${a} fällt. Verkaufen, wenn er über ${b} steigt.`,
    },
    hold: { rule: () => 'Regel: Am ersten Tag kaufen und nie verkaufen. Das ist der Maßstab, an dem sich jede andere Strategie messen muss.' },
  };

  let seed = 1 + Math.floor(Math.random() * 9999);
  let state = null, mc = null, mcTimer = 0;

  // ---------- Formatierung ----------
  const pct = (x, d = 1) => (x >= 0 ? '+' : '−') + Math.abs(x * 100).toFixed(d).replace('.', ',') + ' %';
  const pctPlain = (x, d = 0) => (x * 100).toFixed(d).replace('.', ',') + ' %';
  const eur = (x) => Math.round(x).toLocaleString('de-DE') + ' €';
  const short = (x) => x >= 1e6 ? (x / 1e6).toFixed(1).replace('.', ',') + ' Mio' : x >= 1e4 ? Math.round(x / 1e3) + ' Tsd' : Math.round(x).toLocaleString('de-DE');
  const sign = (x) => (x >= 0 ? 'pos' : 'neg');

  // ---------- Zeichnen ----------
  function prep(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const r = canvas.getBoundingClientRect();
    canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
    const c = canvas.getContext('2d');
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.font = '11px "Courier New", monospace';
    return { c, w: r.width, h: r.height, l: 58, r: 8, t: 8, b: 20 };
  }

  // Logarithmische Y-Achse: gleiche prozentuale Bewegung = gleiche Höhe.
  function frame(g, lo, hi, years, fmt) {
    const { c, w, h, l, r, t, b } = g;
    lo = Math.log(lo * 0.97); hi = Math.log(hi * 1.03);
    const y = (v) => t + (h - t - b) * (1 - (Math.log(v) - lo) / (hi - lo));
    c.clearRect(0, 0, w, h);
    c.strokeStyle = C.border; c.fillStyle = C.muted; c.lineWidth = 1;
    c.textAlign = 'right'; c.textBaseline = 'middle';
    for (let k = 0; k <= 4; k++) {
      const v = Math.exp(lo + (hi - lo) * (k / 4)), yy = Math.round(y(v)) + 0.5;
      c.beginPath(); c.moveTo(l, yy); c.lineTo(w - r, yy); c.stroke();
      c.fillText(fmt(v), l - 6, yy);
    }
    c.textAlign = 'center'; c.textBaseline = 'alphabetic';
    const stepY = years > 15 ? 5 : years > 6 ? 2 : 1;
    for (let k = 0; k <= years; k += stepY) {
      const x = l + (w - l - r) * (k / years);
      c.fillText(k === 0 ? 'Start' : 'Jahr ' + k, Math.min(Math.max(x, l + 16), w - r - 24), h - 5);
    }
    return y;
  }

  function line(g, data, y, color, width = 1.5, from = 0) {
    const { c, w, l, r } = g, n = data.length - 1;
    c.beginPath(); c.strokeStyle = color; c.lineWidth = width; c.lineJoin = 'round';
    let started = false;
    for (let i = from; i <= n; i++) {
      if (!(data[i] > 0)) continue;
      const x = l + (w - l - r) * (i / n);
      if (started) c.lineTo(x, y(data[i])); else { c.moveTo(x, y(data[i])); started = true; }
    }
    c.stroke();
  }

  function range(...arrays) {
    let lo = Infinity, hi = -Infinity;
    for (const a of arrays) for (const v of a) { if (v > 0 && v < lo) lo = v; if (v > hi) hi = v; }
    return [lo, hi];
  }

  function drawPrice() {
    const { prices, regimes, pos, trades, p } = state;
    const g = prep($('priceChart')), n = prices.length - 1;
    const [lo, hi] = range(prices);
    const y = frame(g, lo, hi, p.years, (v) => v.toFixed(0));
    const X = (i) => g.l + (g.w - g.l - g.r) * (i / n);
    // Zeiten, in denen die Strategie investiert ist
    g.c.fillStyle = 'rgba(46, 204, 113, 0.09)';
    for (let i = 0, s = -1; i <= n; i++) {
      if (pos[i] && s < 0) s = i;
      if ((!pos[i] || i === n) && s >= 0) { g.c.fillRect(X(s), g.t, X(i) - X(s), g.h - g.t - g.b); s = -1; }
    }
    // Abschwungphasen des simulierten Marktes als Streifen unten
    g.c.fillStyle = 'rgba(255, 77, 77, 0.55)';
    for (let i = 1, s = -1; i <= n; i++) {
      if (regimes[i] && s < 0) s = i;
      if ((!regimes[i] || i === n) && s >= 0) { g.c.fillRect(X(s), g.h - g.b - 3, Math.max(1, X(i) - X(s)), 3); s = -1; }
    }
    if (p.strategy === 'sma') {
      line(g, L.sma(prices, p.p2), y, C.blue, 1);
      line(g, L.sma(prices, p.p1), y, C.accent, 1);
    }
    line(g, prices, y, C.text, 1.4);
    if (trades.length <= 160) {
      for (const tr of trades) {
        const x = X(tr.i), yy = y(prices[tr.i]), d = tr.buy ? 1 : -1;
        g.c.fillStyle = tr.buy ? C.green : C.red;
        g.c.beginPath(); g.c.moveTo(x, yy + d * 5); g.c.lineTo(x - 4.5, yy + d * 13); g.c.lineTo(x + 4.5, yy + d * 13); g.c.fill();
      }
    }
    $('priceLegend').innerHTML =
      `<i style="background:${C.text}"></i>Kurs` +
      (p.strategy === 'sma' ? `<i style="background:${C.accent}"></i>schnell <i style="background:${C.blue}"></i>langsam` : '') +
      (p.strategy !== 'hold' ? '<i class="tri-up"></i>Kauf <i class="tri-down"></i>Verkauf' : '') +
      '<i style="background:rgba(46,204,113,.35);height:10px"></i>investiert <i style="background:rgba(255,77,77,.7)"></i>Abschwung';
  }

  function drawEquity() {
    const { strat, hold, p } = state;
    const g = prep($('equityChart'));
    const [lo, hi] = range(strat.equity, hold.equity);
    const y = frame(g, lo, hi, p.years, short);
    line(g, hold.equity, y, C.blue, 1.5);
    line(g, strat.equity, y, C.accent, 2);
  }

  function drawFan() {
    const g = prep($('fanChart')), b = mc.bands, n = b[0].length - 1;
    const [lo, hi] = range(b[0], b[4]);
    const y = frame(g, lo, hi, state.p.years, short);
    const X = (i) => g.l + (g.w - g.l - g.r) * (i / n);
    const band = (a, z, alpha) => {
      g.c.beginPath();
      for (let i = 0; i <= n; i++) g.c.lineTo(X(i), y(z[i]));
      for (let i = n; i >= 0; i--) g.c.lineTo(X(i), y(a[i]));
      g.c.fillStyle = `rgba(255, 140, 0, ${alpha})`; g.c.fill();
    };
    band(b[0], b[4], 0.14); band(b[1], b[3], 0.24);
    line(g, b[2], y, C.accent, 2);
    // Startkapital als Bezugslinie
    g.c.setLineDash([4, 4]); g.c.strokeStyle = C.muted; g.c.lineWidth = 1;
    g.c.beginPath(); g.c.moveTo(g.l, y(CAPITAL)); g.c.lineTo(g.w - g.r, y(CAPITAL)); g.c.stroke();
    g.c.setLineDash([]);
  }

  function drawHist() {
    const g = prep($('histChart')), { c, w, h, l, r, t, b } = g;
    c.clearRect(0, 0, w, h);
    const all = Float64Array.from([...mc.strat, ...mc.hold]).sort();
    const lo = Math.min(L.quantile(all, 0.01), 0), hi = L.quantile(all, 0.97);
    const BINS = 36, count = (a) => {
      const out = new Array(BINS).fill(0);
      for (const v of a) out[Math.max(0, Math.min(BINS - 1, Math.floor((v - lo) / (hi - lo) * BINS)))]++;
      return out;
    };
    const hs = count(mc.strat), hh = count(mc.hold), top = Math.max(...hs, ...hh);
    const X = (v) => l + (w - l - r) * ((v - lo) / (hi - lo));
    const Y = (k) => t + (h - t - b) * (1 - k / top);
    const bw = (w - l - r) / BINS;
    c.fillStyle = 'rgba(255, 140, 0, 0.6)';
    hs.forEach((k, i) => c.fillRect(l + i * bw + 1, Y(k), bw - 2, h - b - Y(k)));
    c.strokeStyle = C.blue; c.lineWidth = 2; c.beginPath(); c.moveTo(l, h - b);
    hh.forEach((k, i) => { c.lineTo(l + i * bw, Y(k)); c.lineTo(l + (i + 1) * bw, Y(k)); });
    c.lineTo(w - r, h - b); c.stroke();
    // Achse: Nulllinie (Gewinn/Verlust) und Beschriftung
    c.strokeStyle = C.border; c.lineWidth = 1; c.beginPath(); c.moveTo(l, h - b + 0.5); c.lineTo(w - r, h - b + 0.5); c.stroke();
    c.setLineDash([4, 4]); c.strokeStyle = C.muted; c.beginPath(); c.moveTo(X(0), t); c.lineTo(X(0), h - b); c.stroke(); c.setLineDash([]);
    c.fillStyle = C.muted; c.font = '11px "Courier New", monospace'; c.textBaseline = 'alphabetic';
    c.textAlign = 'center';
    for (let k = 0; k <= 4; k++) {
      const v = lo + (hi - lo) * k / 4;
      c.fillText((k === 4 ? 'ab ' : '') + pct(v, 0), Math.min(Math.max(X(v), l + 22), w - r - 36), h - 5);
    }
    c.textAlign = 'right'; c.textBaseline = 'middle';
    c.fillText('Läufe', l - 6, t + 6); c.fillText(String(top), l - 6, t + 20);
    c.textAlign = 'left'; c.fillText('Gewinn →', X(0) + 6, t + 6);
  }

  // ---------- Kennzahlen ----------
  const tile = (k, v, s = '', cls = '') => `<div class="lab-tile"><div class="k">${k}</div><div class="v ${cls}">${v}</div><div class="s">${s}</div></div>`;

  function renderTiles() {
    const s = state.strat.stats, h = state.hold.stats, isHold = state.p.strategy === 'hold';
    const vs = (txt) => (isHold ? '' : txt);
    $('tiles').innerHTML =
      tile('Endwert', eur(s.final), vs('Halten: ' + eur(h.final)), sign(s.total)) +
      tile('Gesamtrendite', pct(s.total, 0), vs('Halten: ' + pct(h.total, 0)), sign(s.total)) +
      tile('Rendite pro Jahr', pct(s.cagr), vs('Halten: ' + pct(h.cagr)), sign(s.cagr)) +
      tile('Größter Einbruch', '−' + pctPlain(s.maxDD), vs('Halten: −' + pctPlain(h.maxDD)), 'neg') +
      tile('Sharpe-Kennzahl', s.sharpe.toFixed(2).replace('.', ','), 'Rendite je Risiko' + vs(' · Halten: ' + h.sharpe.toFixed(2).replace('.', ','))) +
      tile('Abgeschlossene Trades', s.rounds, Number.isNaN(s.winRate) ? 'noch keiner beendet' : pctPlain(s.winRate) + ' mit Gewinn') +
      tile('Zeit im Markt', pctPlain(s.exposure), 'Rest liegt in Cash');
  }

  function renderMC() {
    const isHold = state.p.strategy === 'hold';
    $('mcRuns').textContent = mc.runs;
    const b = Math.round(mc.beat * 100);
    $('verdict').innerHTML = isHold
      ? `Kaufen und Halten endet in <strong>${pctPlain(1 - mc.lossHold)}</strong> der Märkte im Plus, mit einer mittleren Rendite von <strong>${pct(mc.medHold, 0)}</strong>.`
      : `Die Strategie schlägt Kaufen und Halten in <strong class="${b >= 50 ? 'pos' : 'neg'}">${b} von 100</strong> Märkten. ` +
        (b >= 50 ? 'Unter diesen Annahmen hat die Regel einen echten Vorteil.'
          : mc.medDDStrat < mc.medDDHold - 0.03
            ? `Sie bringt meist weniger Rendite, dafür fallen die Einbrüche kleiner aus (−${pctPlain(mc.medDDStrat)} statt −${pctPlain(mc.medDDHold)}).`
            : 'Ein guter Einzelchart oben wäre hier also eher Glück als Können.');
    $('mcTiles').innerHTML =
      tile('Mittlere Rendite', pct(mc.medStrat, 0), 'Halten: ' + pct(mc.medHold, 0), sign(mc.medStrat)) +
      tile('Mittlerer größter Einbruch', '−' + pctPlain(mc.medDDStrat), 'Halten: −' + pctPlain(mc.medDDHold), 'neg') +
      tile('Läufe mit Verlust', pctPlain(mc.lossStrat), 'Halten: ' + pctPlain(mc.lossHold)) +
      tile('Schlechte 5 % enden unter', eur(mc.bands[0][mc.bands[0].length - 1]), 'Start: ' + eur(CAPITAL)) +
      tile('Gute 5 % enden über', eur(mc.bands[4][mc.bands[4].length - 1]), 'Start: ' + eur(CAPITAL));
    drawFan(); drawHist();
  }

  // ---------- Ablauf ----------
  function setupParams() {
    const def = STRATS[$('strategy').value];
    for (const key of ['p1', 'p2']) {
      const d = def[key], el = $(key);
      $(key + 'Wrap').classList.toggle('hidden', !d);
      if (!d) continue;
      Object.assign(el, { min: d.min, max: d.max, step: d.step, value: d.value });
      $(key + 'Label').textContent = d.label;
    }
  }

  function readParams() {
    const strategy = $('strategy').value, def = STRATS[strategy];
    let p1 = +$('p1').value, p2 = +$('p2').value;
    // Der schnelle Durchschnitt muss kürzer sein als der langsame.
    if (strategy === 'sma' && p1 >= p2) { p1 = p2 - 5; $('p1').value = p1; }
    $('p1Out').textContent = def.p1 ? p1 + def.p1.unit : '';
    $('p2Out').textContent = def.p2 ? p2 + def.p2.unit : '';
    $('muOut').textContent = pct(+$('mu').value / 100);
    $('sigmaOut').textContent = $('sigma').value + ' %';
    $('yearsOut').textContent = $('years').value + ' Jahre';
    $('feeOut').textContent = (+$('fee').value / 100).toFixed(2).replace('.', ',') + ' %';
    $('seedOut').textContent = seed;
    $('ruleText').textContent = def.rule(p1, p2);
    return { strategy, p1, p2, mu: +$('mu').value / 100, sigma: +$('sigma').value / 100,
      years: +$('years').value, feeBps: +$('fee').value, capital: CAPITAL, seed };
  }

  function update() {
    const p = readParams();
    const { prices, regimes } = L.generateMarket(p);
    const pos = L.positions(prices, p.strategy, p.p1, p.p2);
    const strat = L.backtest(prices, pos, p);
    const hold = L.backtest(prices, L.positions(prices, 'hold'), p);
    state = { p, prices, regimes, pos, strat, hold, trades: strat.trades };
    renderTiles(); drawPrice(); drawEquity();
    clearTimeout(mcTimer);
    mcTimer = setTimeout(() => { mc = L.monteCarlo(p, RUNS); renderMC(); }, 120);
  }

  $('strategy').addEventListener('change', () => { setupParams(); update(); });
  for (const id of ['p1', 'p2', 'mu', 'sigma', 'years', 'fee']) $(id).addEventListener('input', update);
  $('newMarket').addEventListener('click', () => { seed = 1 + Math.floor(Math.random() * 9999); update(); });
  let resizeTimer = 0;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { drawPrice(); drawEquity(); if (mc) { drawFan(); drawHist(); } }, 100);
  });

  setupParams();
  update();
})();
