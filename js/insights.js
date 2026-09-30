// News, Analysten, Peer-Vergleich und Quartalszahlen-Kalender.
// Wird vor app.js geladen; nutzt apiKey, watchlist und Formatierer aus app.js erst beim Aufruf.

async function finnhubGet(path, params = {}) {
  const query = new URLSearchParams({ ...params, token: apiKey });
  const res = await fetch(`https://finnhub.io/api/v1${path}?${query}`);
  if (!res.ok) throw new Error(`Finnhub ${path}: HTTP ${res.status}`);
  return res.json();
}

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

function safeUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function daysFromNow(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d;
}

/* ---------- 1. Firmen-News ---------- */

async function fetchCompanyNews(symbol) {
  const items = await finnhubGet("/company-news", {
    symbol,
    from: isoDate(daysFromNow(-14)),
    to: isoDate(new Date()),
  });
  if (!Array.isArray(items)) throw new Error("Keine News");
  return items.sort((a, b) => b.datetime - a.datetime).slice(0, 6);
}

function renderNews(items) {
  if (!items || items.length === 0) {
    return `<p class="data-note">Keine Nachrichten aus den letzten 14 Tagen gefunden.</p>`;
  }
  return `<ul class="news-list">${items
    .map((n) => {
      const url = safeUrl(n.url);
      const date = new Date(n.datetime * 1000).toLocaleDateString("de-DE", { day: "2-digit", month: "short" });
      const headline = escapeHtml(n.headline);
      return `
        <li>
          <div class="news-meta">${escapeHtml(n.source)} &middot; ${date}</div>
          ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${headline}</a>` : headline}
        </li>`;
    })
    .join("")}</ul>`;
}

/* ---------- 2. Analysten-Einschätzungen ---------- */

const RATING_SEGMENTS = [
  { key: "strongBuy", label: "Stark kaufen", cls: "seg-strong-buy" },
  { key: "buy", label: "Kaufen", cls: "seg-buy" },
  { key: "hold", label: "Halten", cls: "seg-hold" },
  { key: "sell", label: "Verkaufen", cls: "seg-sell" },
  { key: "strongSell", label: "Stark verkaufen", cls: "seg-strong-sell" },
];

async function fetchRecommendation(symbol) {
  const data = await finnhubGet("/stock/recommendation", { symbol });
  if (!Array.isArray(data) || data.length === 0) throw new Error("Keine Analystendaten");
  return [...data].sort((a, b) => String(b.period).localeCompare(String(a.period)))[0];
}

function renderRecommendation(rec) {
  const total = rec ? RATING_SEGMENTS.reduce((sum, s) => sum + (rec[s.key] || 0), 0) : 0;
  if (!rec || total === 0) {
    return `<p class="data-note">Keine Analysten-Einschätzungen für dieses Symbol verfügbar.</p>`;
  }

  const bullishPct = Math.round((((rec.strongBuy || 0) + (rec.buy || 0)) / total) * 100);
  const period = new Date(rec.period).toLocaleDateString("de-DE", { month: "long", year: "numeric" });

  const bar = RATING_SEGMENTS.filter((s) => rec[s.key] > 0)
    .map((s) => `<span class="rating-seg ${s.cls}" style="flex-grow:${rec[s.key]}" title="${s.label}: ${rec[s.key]}"></span>`)
    .join("");

  const legend = RATING_SEGMENTS.map(
    (s) => `<span class="rating-legend-item"><span class="rating-swatch ${s.cls}"></span>${s.label} <strong>${rec[s.key] || 0}</strong></span>`
  ).join("");

  return `
    <div class="rating-summary">
      <strong>${bullishPct} %</strong> von ${total} Analysten empfehlen Kaufen
      <span class="metric-hint">Stand ${period}</span>
    </div>
    <div class="rating-bar">${bar}</div>
    <div class="rating-legend">${legend}</div>
  `;
}

/* ---------- 3. Peer-Vergleich ---------- */

const PEER_COLUMNS = [
  { label: "KGV", keys: ["peTTM", "peBasicExclExtraTTM", "peNormalizedAnnual"], format: (v) => formatMultiple(v) },
  { label: "KUV", keys: ["psTTM", "psAnnual"], format: (v) => formatMultiple(v) },
  { label: "KBV", keys: ["pbQuarterly", "pbAnnual"], format: (v) => formatMultiple(v) },
  { label: "Bruttomarge", keys: ["grossMarginTTM", "grossMarginAnnual"], format: (v) => formatPercent(v) },
  { label: "Nettomarge", keys: ["netProfitMarginTTM", "netProfitMarginAnnual"], format: (v) => formatPercent(v) },
  { label: "Wachstum", keys: ["revenueGrowthTTMYoy", "revenueGrowthQuarterlyYoy"], format: (v) => formatPercent(v) },
];

async function fetchPeers(symbol) {
  const peers = await finnhubGet("/stock/peers", { symbol });
  if (!Array.isArray(peers)) throw new Error("Keine Peers");
  return [symbol, ...peers.filter((p) => p !== symbol).slice(0, 4)];
}

// metricsForSymbol: bereits geladene Kennzahlen des Hauptsymbols, spart eine Anfrage.
async function loadPeerComparison(symbol, metricsForSymbol, container, isCurrent) {
  container.innerHTML = `<p class="data-note">Lade Vergleich mit Konkurrenten...</p>`;
  try {
    const symbols = await fetchPeers(symbol);
    const results = await Promise.allSettled(
      symbols.map((s) => (s === symbol && metricsForSymbol ? Promise.resolve(metricsForSymbol) : fetchMetrics(s)))
    );
    if (!isCurrent()) return;

    if (symbols.length < 2) {
      container.innerHTML = `<p class="data-note">Keine Konkurrenten für dieses Symbol gefunden.</p>`;
      return;
    }

    const rows = symbols.map((s, i) => ({
      symbol: s,
      metric: results[i].status === "fulfilled" ? results[i].value : null,
    }));
    container.innerHTML = renderPeerTable(symbol, rows);
  } catch {
    if (isCurrent()) container.innerHTML = `<p class="data-note">Peer-Vergleich für dieses Symbol nicht verfügbar.</p>`;
  }
}

function renderPeerTable(symbol, rows) {
  const head = PEER_COLUMNS.map((c) => `<th>${c.label}</th>`).join("");
  const body = rows
    .map((r) => {
      const cells = PEER_COLUMNS.map((c) => `<td>${r.metric ? c.format(pick(r.metric, c.keys)) : "-"}</td>`).join("");
      return `<tr class="${r.symbol === symbol ? "peer-current" : ""}"><td>${escapeHtml(r.symbol)}</td>${cells}</tr>`;
    })
    .join("");

  return `
    <div class="table-scroll">
      <table class="peer-table">
        <thead><tr><th>Symbol</th>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

/* ---------- 4. Quartalszahlen-Kalender ---------- */

const EARNINGS_WINDOW_DAYS = 120;
const earningsCache = new Map();

const EARNINGS_HOUR_LABELS = {
  bmo: "vor Börsenstart",
  amc: "nach Börsenschluss",
  dmh: "während des Handels",
};

async function fetchNextEarnings(symbol) {
  const data = await finnhubGet("/calendar/earnings", {
    symbol,
    from: isoDate(new Date()),
    to: isoDate(daysFromNow(EARNINGS_WINDOW_DAYS)),
  });
  const list = (data && Array.isArray(data.earningsCalendar) ? data.earningsCalendar : [])
    .filter((e) => e.symbol === symbol && e.date)
    .sort((a, b) => a.date.localeCompare(b.date));
  return list[0] || null;
}

async function refreshEarnings() {
  const missing = watchlist.filter((s) => !earningsCache.has(s));
  await Promise.all(
    missing.map(async (s) => {
      try {
        earningsCache.set(s, await fetchNextEarnings(s));
      } catch {
        earningsCache.set(s, null);
      }
    })
  );
  renderEarnings();
}

function renderEarnings() {
  const container = document.getElementById("earningsList");
  if (!container) return;

  const entries = watchlist
    .map((s) => earningsCache.get(s))
    .filter(Boolean)
    .sort((a, b) => a.date.localeCompare(b.date));

  if (entries.length === 0) {
    container.innerHTML = `<p class="data-note">Keine Termine in den nächsten ${EARNINGS_WINDOW_DAYS} Tagen für deine Watchlist gefunden.</p>`;
    return;
  }

  const today = new Date(isoDate(new Date()));
  container.innerHTML = `<ul class="earnings-list">${entries
    .map((e) => {
      const date = new Date(e.date);
      const daysLeft = Math.round((date - today) / 86_400_000);
      const when = daysLeft === 0 ? "heute" : daysLeft === 1 ? "morgen" : `in ${daysLeft} Tagen`;
      const estimate = typeof e.epsEstimate === "number" ? `EPS-Schätzung ${e.epsEstimate.toFixed(2)} USD` : "";
      const quarter = e.quarter && e.year ? `Q${e.quarter} ${e.year}` : "";
      return `
        <li>
          <div class="earnings-date">
            <span class="earnings-day">${date.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "short" })}</span>
            <span class="metric-hint">${when}</span>
          </div>
          <div class="earnings-info">
            <span class="symbol">${escapeHtml(e.symbol)}</span>
            <span class="metric-hint">${[quarter, EARNINGS_HOUR_LABELS[e.hour], estimate].filter(Boolean).join(" · ")}</span>
          </div>
        </li>`;
    })
    .join("")}</ul>`;
}
