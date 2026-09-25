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
    item.innerHTML = `<span class="symbol">${r.symbol}</span><span>${r.description || ""}</span>`;
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
  }
  searchResults.innerHTML = "";
  searchInput.value = "";
}

function removeFromWatchlist(symbol) {
  watchlist = watchlist.filter((s) => s !== symbol);
  saveWatchlist();
  renderWatchlist();
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
    row.querySelector(".remove-btn").addEventListener("click", () => removeFromWatchlist(symbol));
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

init();
