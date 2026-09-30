// Zentrale Finnhub-Anbindung. Meldet Limit (429) und ungültigen Key (401) an die Oberfläche.
// Wird zuerst geladen; nutzt apiKey und die Banner-Funktionen aus app.js erst beim Aufruf.

const FINNHUB_BASE = "https://finnhub.io/api/v1";

class FinnhubError extends Error {
  constructor(status, path) {
    super(`Finnhub ${path}: HTTP ${status}`);
    this.status = status;
  }
}

async function finnhubGet(path, params = {}) {
  const query = new URLSearchParams({ ...params, token: apiKey });
  const res = await fetch(`${FINNHUB_BASE}${path}?${query}`);

  if (res.status === 429) {
    showKeyProblem("limit");
    throw new FinnhubError(res.status, path);
  }
  if (res.status === 401) {
    showKeyProblem("invalid");
    throw new FinnhubError(res.status, path);
  }
  // 403 heißt bei Finnhub meist "nur im bezahlten Plan" und ist kein Key-Problem.
  if (!res.ok) throw new FinnhubError(res.status, path);

  clearKeyProblem();
  return res.json();
}

// Prüft einen neuen Key, ohne die Hinweisleiste auszulösen.
async function checkApiKey(key) {
  try {
    const res = await fetch(`${FINNHUB_BASE}/quote?${new URLSearchParams({ symbol: "AAPL", token: key })}`);
    if (res.status === 401 || res.status === 403) return "invalid";
    if (res.status === 429) return "limit";
    if (!res.ok) return "unreachable";
    const data = await res.json();
    return typeof data.c === "number" ? "ok" : "invalid";
  } catch {
    return "unreachable";
  }
}
