const API_KEY_STORAGE = "parity_finnhub_api_key";
const WATCHLIST_STORAGE = "parity_watchlist";
const REFRESH_INTERVAL_MS = 15000;

const DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"];

const setupPanel = document.getElementById("setupPanel");
const app = document.getElementById("app");
const apiKeyInput = document.getElementById("apiKeyInput");
const saveApiKeyBtn = document.getElementById("saveApiKey");
const setupError = document.getElementById("setupError");
const resetKeyBtn = document.getElementById("resetKeyBtn");

const searchInput = document.getElementById("searchInput");
const searchBtn = document.getElementById("searchBtn");
const searchResults = document.getElementById("searchResults");

const refreshBtn = document.getElementById("refreshBtn");
const lastUpdateEl = document.getElementById("lastUpdate");
const watchlistBody = document.getElementById("watchlistBody");
const emptyState = document.getElementById("emptyState");
const clockEl = document.getElementById("clock");

const detailModal = document.getElementById("detailModal");
const detailContent = document.getElementById("detailContent");
const closeModalBtn = document.getElementById("closeModalBtn");

let apiKey = localStorage.getItem(API_KEY_STORAGE) || "";
let watchlist = loadWatchlist();
let refreshTimer = null;

function loadWatchlist() {
  const raw = localStorage.getItem(WATCHLIST_STORAGE);
  if (!raw) return [...DEFAULT_WATCHLIST];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [...DEFAULT_WATCHLIST];
  } catch {
    return [...DEFAULT_WATCHLIST];
  }
}

function saveWatchlist() {
  localStorage.setItem(WATCHLIST_STORAGE, JSON.stringify(watchlist));
}

function init() {
  updateClock();
  setInterval(updateClock, 1000);

  if (!apiKey) {
    setupPanel.classList.remove("hidden");
    app.classList.add("hidden");
  } else {
    startApp();
  }

  saveApiKeyBtn.addEventListener("click", handleSaveApiKey);
  apiKeyInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSaveApiKey();
  });

  resetKeyBtn.addEventListener("click", () => {
    localStorage.removeItem(API_KEY_STORAGE);
    location.reload();
  });

  searchBtn.addEventListener("click", handleSearch);
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSearch();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-bar")) {
      searchResults.innerHTML = "";
    }
  });

  refreshBtn.addEventListener("click", refreshWatchlist);

  closeModalBtn.addEventListener("click", closeDetail);
  detailModal.addEventListener("click", (e) => {
    if (e.target === detailModal) closeDetail();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDetail();
  });
}

function updateClock() {
  clockEl.textContent = new Date().toLocaleTimeString("de-DE");
}

async function handleSaveApiKey() {
  const key = apiKeyInput.value.trim();
  if (!key) {
    setupError.textContent = "Bitte einen API-Key eingeben.";
    return;
  }

  setupError.textContent = "Prüfe Key...";
  const ok = await testApiKey(key);
  if (!ok) {
    setupError.textContent = "Key ungültig oder Finnhub nicht erreichbar. Bitte prüfen.";
    return;
  }

  apiKey = key;
  localStorage.setItem(API_KEY_STORAGE, key);
  setupPanel.classList.add("hidden");
  startApp();
}

async function testApiKey(key) {
  try {
    const res = await fetch(`https://finnhub.io/api/v1/quote?symbol=AAPL&token=${encodeURIComponent(key)}`);
    if (!res.ok) return false;
    const data = await res.json();
    return typeof data.c === "number";
  } catch {
    return false;
  }
}

function startApp() {
  app.classList.remove("hidden");
  renderWatchlist();
  refreshWatchlist();
  refreshEarnings();

  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshWatchlist, REFRESH_INTERVAL_MS);
}

async function fetchQuote(symbol) {
  const res = await fetch(
    `https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(symbol)}&token=${encodeURIComponent(apiKey)}`
  );
  if (!res.ok) throw new Error("Quote fehlgeschlagen");
  return res.json();
}

async function searchSymbol(query) {
  const res = await fetch(
    `https://finnhub.io/api/v1/search?q=${encodeURIComponent(query)}&token=${encodeURIComponent(apiKey)}`
  );
  if (!res.ok) throw new Error("Suche fehlgeschlagen");
  return res.json();
}

async function handleSearch() {
  const query = searchInput.value.trim();
  if (!query) return;

  searchResults.innerHTML = `<div class="search-result-item">Suche...</div>`;
  try {
    const data = await searchSymbol(query);
    renderSearchResults(data.result || []);
  } catch {
    searchResults.innerHTML = `<div class="search-result-item">Fehler bei der Suche.</div>`;
  }
}

function renderSearchResults(results) {
  searchResults.innerHTML = "";
  if (results.length === 0) {
    searchResults.innerHTML = `<div class="search-result-item">Keine Treffer.</div>`;
    return;
  }

  results.slice(0, 15).forEach((r) => {
    const item = document.createElement("div");
    item.className = "search-result-item";
    item.innerHTML = `<span class="symbol">${escapeHtml(r.symbol)}</span><span>${escapeHtml(r.description || "")}</span>`;
    item.addEventListener("click", () => addToWatchlist(r.symbol));
    searchResults.appendChild(item);
  });
}

function addToWatchlist(symbol) {
  if (!watchlist.includes(symbol)) {
    watchlist.push(symbol);
    saveWatchlist();
    renderWatchlist();
    refreshWatchlist();
    refreshEarnings();
  }
  searchResults.innerHTML = "";
  searchInput.value = "";
}

function removeFromWatchlist(symbol) {
  watchlist = watchlist.filter((s) => s !== symbol);
  saveWatchlist();
  renderWatchlist();
  renderEarnings();
}

function renderWatchlist() {
  watchlistBody.innerHTML = "";
  emptyState.classList.toggle("hidden", watchlist.length > 0);

  watchlist.forEach((symbol) => {
    const row = document.createElement("tr");
    row.id = `row-${symbol}`;
    row.innerHTML = `
      <td class="symbol">${symbol}</td>
      <td data-field="price">-</td>
      <td data-field="change">-</td>
      <td data-field="changePct">-</td>
      <td data-field="open">-</td>
      <td data-field="high">-</td>
      <td data-field="low">-</td>
      <td data-field="prevClose">-</td>
      <td><button class="remove-btn" title="Entfernen">&times;</button></td>
    `;
    row.querySelector(".remove-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      removeFromWatchlist(symbol);
    });
    row.addEventListener("click", () => openDetail(symbol));
    watchlistBody.appendChild(row);
  });
}

async function refreshWatchlist() {
  if (watchlist.length === 0) return;

  await Promise.all(watchlist.map(updateRow));
  lastUpdateEl.textContent = `Stand: ${new Date().toLocaleTimeString("de-DE")}`;
}

async function updateRow(symbol) {
  const row = document.getElementById(`row-${symbol}`);
  if (!row) return;

  try {
    const q = await fetchQuote(symbol);
    if (q.c === 0 && q.pc === 0) {
      row.querySelector('[data-field="price"]').textContent = "n/v";
      return;
    }

    const isUp = q.d >= 0;
    const cls = isUp ? "up" : "down";
    const sign = isUp ? "+" : "";

    row.querySelector('[data-field="price"]').textContent = formatNumber(q.c);
    setChangeCell(row.querySelector('[data-field="change"]'), `${sign}${formatNumber(q.d)}`, cls);
    setChangeCell(row.querySelector('[data-field="changePct"]'), `${sign}${formatNumber(q.dp)}%`, cls);
    row.querySelector('[data-field="open"]').textContent = formatNumber(q.o);
    row.querySelector('[data-field="high"]').textContent = formatNumber(q.h);
    row.querySelector('[data-field="low"]').textContent = formatNumber(q.l);
    row.querySelector('[data-field="prevClose"]').textContent = formatNumber(q.pc);
  } catch {
    row.querySelector('[data-field="price"]').textContent = "Fehler";
  }
}

function setChangeCell(el, text, cls) {
  el.textContent = text;
  el.classList.remove("up", "down");
  el.classList.add(cls);
}

function formatNumber(n) {
  if (typeof n !== "number" || Number.isNaN(n)) return "-";
  return n.toFixed(2);
}

/* ---------- Firmenprofil-Modal ---------- */

async function fetchProfile(symbol) {
  const res = await fetch(
    `https://finnhub.io/api/v1/stock/profile2?symbol=${encodeURIComponent(symbol)}&token=${encodeURIComponent(apiKey)}`
  );
  if (!res.ok) throw new Error("Profil fehlgeschlagen");
  const data = await res.json();
  if (!data || !data.name) throw new Error("Kein Profil verfügbar");
  return data;
}

async function fetchExecutives(symbol) {
  const res = await fetch(
    `https://finnhub.io/api/v1/stock/executive?symbol=${encodeURIComponent(symbol)}&token=${encodeURIComponent(apiKey)}`
  );
  if (!res.ok) throw new Error("Executives nicht verfügbar (evtl. nur im bezahlten Plan)");
  const data = await res.json();
  if (!data || !Array.isArray(data.executive) || data.executive.length === 0) {
    throw new Error("Keine Management-Daten verfügbar");
  }
  return data.executive;
}

async function fetchCandles(symbol) {
  const to = Math.floor(Date.now() / 1000);
  const from = to - 365 * 24 * 60 * 60;
  const res = await fetch(
    `https://finnhub.io/api/v1/stock/candle?symbol=${encodeURIComponent(symbol)}&resolution=W&from=${from}&to=${to}&token=${encodeURIComponent(apiKey)}`
  );
  if (!res.ok) throw new Error("Historische Kurse nicht verfügbar (evtl. nur im bezahlten Plan)");
  const data = await res.json();
  if (!data || data.s !== "ok" || !Array.isArray(data.c) || data.c.length < 2) {
    throw new Error("Keine historischen Kurse für dieses Symbol");
  }
  return data;
}

async function fetchMetrics(symbol) {
  const res = await fetch(
    `https://finnhub.io/api/v1/stock/metric?symbol=${encodeURIComponent(symbol)}&metric=all&token=${encodeURIComponent(apiKey)}`
  );
  if (!res.ok) throw new Error("Kennzahlen nicht verfügbar");
  const data = await res.json();
  if (!data || !data.metric || Object.keys(data.metric).length === 0) {
    throw new Error("Keine Kennzahlen für dieses Symbol");
  }
  return data.metric;
}

function formatUsdMillions(millions) {
  if (typeof millions !== "number" || !Number.isFinite(millions)) return "-";
  const sign = millions < 0 ? "-" : "";
  const abs = Math.abs(millions);
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(2)} Bio. USD`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(2)} Mrd. USD`;
  return `${sign}${abs.toFixed(0)} Mio. USD`;
}

function formatMultiple(v) {
  if (v === null) return "-";
  if (v < 0) return "neg.";
  return `${v.toFixed(1)}x`;
}

function formatPercent(v) {
  if (v === null) return "-";
  return `${v.toFixed(Math.abs(v) < 1 ? 2 : 1)} %`;
}

// Finnhub-Feldnamen variieren je nach Symbol; der erste vorhandene Wert gewinnt.
function pick(metric, keys) {
  for (const key of keys) {
    const v = metric[key];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return null;
}

// Beträge in Mio. USD: Finnhub liefert shareOutstanding in Mio. Stück, *PerShare-Werte in USD.
function buildFinancials(metric, profile) {
  const shares = typeof profile.shareOutstanding === "number" ? profile.shareOutstanding : null;
  const perShareTotal = (v) => (v !== null && shares ? v * shares : null);

  const revenue = perShareTotal(pick(metric, ["revenuePerShareTTM", "revenuePerShareAnnual"]));
  const ebitda = perShareTotal(pick(metric, ["ebitdPerShareTTM", "ebitdPerShareAnnual"]));
  const eps = pick(metric, ["epsTTM", "epsInclExtraItemsTTM", "epsBasicExclExtraItemsTTM", "epsAnnual"]);
  const netIncome = perShareTotal(eps);
  const ev = pick(metric, ["enterpriseValue"]);

  const evEbitdaReported = pick(metric, ["evEbitdaTTM", "ev/ebitdaTTM", "currentEv/ebitdaTTM"]);
  const evRevenueReported = pick(metric, ["evRevenueTTM", "ev/revenueTTM", "currentEv/revenueTTM"]);

  return {
    valuation: [
      { label: "KGV (P/E)", value: formatMultiple(pick(metric, ["peTTM", "peBasicExclExtraTTM", "peNormalizedAnnual", "peAnnual"])), hint: "Kurs / Gewinn je Aktie" },
      { label: "KUV (P/S)", value: formatMultiple(pick(metric, ["psTTM", "psAnnual"])), hint: "Börsenwert / Umsatz" },
      { label: "KBV (P/B)", value: formatMultiple(pick(metric, ["pbQuarterly", "pbAnnual", "pb"])), hint: "Kurs / Buchwert je Aktie" },
      {
        label: "EV / EBITDA",
        value: formatMultiple(evEbitdaReported ?? (ev !== null && ebitda > 0 ? ev / ebitda : null)),
        hint: evEbitdaReported === null ? "berechnet" : "Unternehmenswert / EBITDA",
      },
      {
        label: "EV / Umsatz",
        value: formatMultiple(evRevenueReported ?? (ev !== null && revenue > 0 ? ev / revenue : null)),
        hint: evRevenueReported === null ? "berechnet" : "Unternehmenswert / Umsatz",
      },
    ],
    profitability: [
      { label: "EBITDA-Marge", value: formatPercent(ebitda !== null && revenue > 0 ? (ebitda / revenue) * 100 : null), hint: "berechnet" },
      { label: "Bruttomarge", value: formatPercent(pick(metric, ["grossMarginTTM", "grossMarginAnnual"])), hint: "TTM" },
      { label: "Operative Marge", value: formatPercent(pick(metric, ["operatingMarginTTM", "operatingMarginAnnual"])), hint: "TTM" },
      { label: "Nettomarge", value: formatPercent(pick(metric, ["netProfitMarginTTM", "netProfitMarginAnnual"])), hint: "TTM" },
      { label: "Eigenkapitalrendite", value: formatPercent(pick(metric, ["roeTTM", "roeRfy"])), hint: "ROE, TTM" },
    ],
    absolute: [
      { label: "Umsatz", value: formatUsdMillions(revenue), hint: "TTM, berechnet" },
      { label: "EBITDA", value: formatUsdMillions(ebitda), hint: "TTM, berechnet" },
      { label: "Nettogewinn", value: formatUsdMillions(netIncome), hint: "TTM, berechnet" },
      { label: "Gewinn je Aktie", value: eps === null ? "-" : `${eps.toFixed(2)} USD`, hint: "EPS, TTM" },
      { label: "Umsatzwachstum", value: formatPercent(pick(metric, ["revenueGrowthTTMYoy", "revenueGrowthQuarterlyYoy"])), hint: "ggü. Vorjahr" },
      { label: "Dividendenrendite", value: formatPercent(pick(metric, ["dividendYieldIndicatedAnnual", "currentDividendYieldTTM"])), hint: "p.a." },
    ],
  };
}

function renderMetricGroup(title, items) {
  return `
    <div class="metric-group">
      <div class="metric-group-title">${title}</div>
      <div class="metric-grid">
        ${items
          .map(
            (i) => `
          <div class="metric-tile">
            <span class="label">${i.label}</span>
            <span class="value">${i.value}</span>
            <span class="metric-hint">${i.hint}</span>
          </div>`
          )
          .join("")}
      </div>
    </div>
  `;
}

// Verhindert, dass eine langsame Antwort ein inzwischen geöffnetes anderes Profil überschreibt.
let detailRequestId = 0;

async function openDetail(symbol) {
  const requestId = ++detailRequestId;
  const isCurrent = () => requestId === detailRequestId;

  detailModal.classList.remove("hidden");
  detailContent.innerHTML = `<p class="detail-loading">Lade Firmendaten für ${escapeHtml(symbol)}...</p>`;

  const results = await Promise.allSettled([
    fetchProfile(symbol),
    fetchExecutives(symbol),
    fetchCandles(symbol),
    fetchMetrics(symbol),
    fetchCompanyNews(symbol),
    fetchRecommendation(symbol),
  ]);
  if (!isCurrent()) return;

  const [profile, executives, candles, metrics, news, recommendation] = results.map((r) =>
    r.status === "fulfilled" ? r.value : null
  );

  if (!profile) {
    detailContent.innerHTML = `<p class="detail-error">Firmenprofil für ${escapeHtml(symbol)} konnte nicht geladen werden.</p>`;
    return;
  }

  renderDetail(symbol, { profile, executives, candles, metrics, news, recommendation });
  loadPeerComparison(symbol, metrics, document.getElementById("peerSection"), isCurrent);
}

function closeDetail() {
  detailRequestId++;
  detailModal.classList.add("hidden");
  detailContent.innerHTML = "";
}

function renderDetail(symbol, { profile, executives, candles, metrics, news, recommendation }) {
  const logoUrl = safeUrl(profile.logo);
  const logo = logoUrl ? `<img src="${escapeHtml(logoUrl)}" alt="" onerror="this.remove()">` : "";
  const webUrl = safeUrl(profile.weburl);

  let financialsHtml = `<p class="data-note">Finanzkennzahlen für dieses Symbol nicht verfügbar.</p>`;
  if (metrics) {
    const f = buildFinancials(metrics, profile);
    financialsHtml =
      renderMetricGroup("Bewertung (Multiples)", f.valuation) +
      renderMetricGroup("Profitabilität", f.profitability) +
      renderMetricGroup("Umsatz &amp; Gewinn", f.absolute);
  }

  detailContent.innerHTML = `
    <div class="detail-header">
      ${logo}
      <div>
        <h2>${escapeHtml(profile.name)}</h2>
        <div class="ticker-sub">${escapeHtml(symbol)} &middot; ${escapeHtml(profile.exchange || "-")}</div>
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-field">
        <span class="label">Branche</span>
        <span class="value">${escapeHtml(profile.finnhubIndustry || "-")}</span>
      </div>
      <div class="detail-field">
        <span class="label">Land</span>
        <span class="value">${escapeHtml(profile.country || "-")}</span>
      </div>
      <div class="detail-field">
        <span class="label">Marktkapitalisierung</span>
        <span class="value">${formatUsdMillions(profile.marketCapitalization)}</span>
      </div>
      <div class="detail-field">
        <span class="label">Börsengang (IPO)</span>
        <span class="value">${escapeHtml(profile.ipo || "-")}</span>
      </div>
      <div class="detail-field">
        <span class="label">Ausstehende Aktien</span>
        <span class="value">${profile.shareOutstanding ? profile.shareOutstanding.toFixed(1) + " Mio." : "-"}</span>
      </div>
      <div class="detail-field">
        <span class="label">Website</span>
        <span class="value">
          ${webUrl ? `<a class="website-link" href="${escapeHtml(webUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(webUrl)}</a>` : "-"}
        </span>
      </div>
    </div>

    <div class="detail-section-title">Kursverlauf (1 Jahr)</div>
    <div id="chartSection" class="chart-wrap">
      ${candles ? "" : `<p class="data-note">Historischer Kursverlauf für dieses Symbol nicht verfügbar (bei Finnhub teils nur im bezahlten Plan enthalten).</p>`}
    </div>

    <div class="detail-section-title">Analysten-Einschätzungen</div>
    ${renderRecommendation(recommendation)}

    <div class="detail-section-title">Finanzkennzahlen</div>
    ${financialsHtml}

    <div class="detail-section-title">Vergleich mit Konkurrenten</div>
    <div id="peerSection"></div>

    <div class="detail-section-title">Aktuelle Nachrichten</div>
    ${renderNews(news)}

    <div class="detail-section-title">Management</div>
    <div id="execSection">
      ${
        executives
          ? `<ul class="exec-list">${executives
              .slice(0, 6)
              .map((e) => `<li><span>${escapeHtml(e.name)}</span><span class="exec-title">${escapeHtml(e.title || "")}</span></li>`)
              .join("")}</ul>`
          : `<p class="data-note">Management-Daten sind für dieses Symbol nicht verfügbar (bei Finnhub teils nur im bezahlten Plan enthalten).</p>`
      }
    </div>
  `;

  if (candles) {
    renderPriceChart(document.getElementById("chartSection"), candles);
  }
}

function renderPriceChart(container, candles) {
  const width = 600;
  const height = 200;
  const padTop = 10;
  const padBottom = 24;
  const padSide = 4;

  const prices = candles.c;
  const times = candles.t;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;

  const xFor = (i) => padSide + (i / (prices.length - 1)) * (width - padSide * 2);
  const yFor = (p) => padTop + (1 - (p - min) / range) * (height - padTop - padBottom);

  const linePoints = prices.map((p, i) => `${xFor(i)},${yFor(p)}`).join(" ");
  const areaPoints = `${padSide},${height - padBottom} ${linePoints} ${width - padSide},${height - padBottom}`;

  const isUp = prices[prices.length - 1] >= prices[0];
  const lineColor = isUp ? "var(--green)" : "var(--red)";

  const tickCount = 5;
  const tickLabels = [];
  for (let i = 0; i < tickCount; i++) {
    const idx = Math.round((i / (tickCount - 1)) * (times.length - 1));
    const date = new Date(times[idx] * 1000);
    tickLabels.push({ x: xFor(idx), label: date.toLocaleDateString("de-DE", { month: "short", year: "2-digit" }) });
  }

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" id="priceChartSvg">
      <defs>
        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" style="stop-color:${lineColor}; stop-opacity:0.28" />
          <stop offset="100%" style="stop-color:${lineColor}; stop-opacity:0" />
        </linearGradient>
      </defs>
      <line x1="${padSide}" y1="${padTop}" x2="${width - padSide}" y2="${padTop}" style="stroke:var(--border); stroke-width:1" />
      <line x1="${padSide}" y1="${(height - padBottom + padTop) / 2}" x2="${width - padSide}" y2="${(height - padBottom + padTop) / 2}" style="stroke:var(--border); stroke-width:1" />
      <line x1="${padSide}" y1="${height - padBottom}" x2="${width - padSide}" y2="${height - padBottom}" style="stroke:var(--border); stroke-width:1" />
      <polygon points="${areaPoints}" fill="url(#areaFill)" stroke="none" />
      <polyline points="${linePoints}" fill="none" style="stroke:${lineColor}; stroke-width:2; stroke-linecap:round; stroke-linejoin:round" />
      ${tickLabels
        .map((t, i) => {
          const anchor = i === 0 ? "start" : i === tickLabels.length - 1 ? "end" : "middle";
          return `<text x="${t.x}" y="${height - 6}" font-size="9" style="fill:var(--muted)" text-anchor="${anchor}">${t.label}</text>`;
        })
        .join("")}
      <text x="${padSide}" y="${padTop + 8}" font-size="9" style="fill:var(--muted)">${formatNumber(max)}</text>
      <text x="${padSide}" y="${height - padBottom - 4}" font-size="9" style="fill:var(--muted)">${formatNumber(min)}</text>
      <line class="chart-crosshair-line" id="crosshairLine" x1="0" y1="${padTop}" x2="0" y2="${height - padBottom}" />
      <circle id="crosshairDot" r="3.5" style="fill:${lineColor}" opacity="0" />
      <rect x="0" y="0" width="${width}" height="${height}" fill="transparent" id="chartOverlay" style="cursor: crosshair;" />
    </svg>
    <div class="chart-tooltip" id="chartTooltip"></div>
  `;

  const svg = container.querySelector("#priceChartSvg");
  const overlay = container.querySelector("#chartOverlay");
  const crosshairLine = container.querySelector("#crosshairLine");
  const crosshairDot = container.querySelector("#crosshairDot");
  const tooltip = container.querySelector("#chartTooltip");

  function handleMove(clientX) {
    const rect = svg.getBoundingClientRect();
    const relX = ((clientX - rect.left) / rect.width) * width;
    const idx = Math.max(
      0,
      Math.min(prices.length - 1, Math.round(((relX - padSide) / (width - padSide * 2)) * (prices.length - 1)))
    );
    const px = xFor(idx);
    const py = yFor(prices[idx]);

    crosshairLine.setAttribute("x1", px);
    crosshairLine.setAttribute("x2", px);
    crosshairLine.style.opacity = 1;
    crosshairDot.setAttribute("cx", px);
    crosshairDot.setAttribute("cy", py);
    crosshairDot.style.opacity = 1;

    const date = new Date(times[idx] * 1000).toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" });
    tooltip.textContent = `${date}: ${formatNumber(prices[idx])} USD`;
    tooltip.style.left = `${(px / width) * 100}%`;
    tooltip.style.top = `${(py / height) * 100}%`;
    tooltip.style.opacity = 1;
  }

  function handleLeave() {
    crosshairLine.style.opacity = 0;
    crosshairDot.style.opacity = 0;
    tooltip.style.opacity = 0;
  }

  overlay.addEventListener("mousemove", (e) => handleMove(e.clientX));
  overlay.addEventListener("mouseleave", handleLeave);
  overlay.addEventListener(
    "touchmove",
    (e) => {
      if (e.touches[0]) handleMove(e.touches[0].clientX);
    },
    { passive: true }
  );
  overlay.addEventListener("touchend", handleLeave);
}

init();
