const FIN_FIELDS = {
  simple_interest: ["fin-principal", "fin-rate", "fin-time"],
  compound_interest: ["fin-principal", "fin-rate", "fin-time"],
  emi: ["fin-principal", "fin-rate", "fin-tenure"],
};

/**
 * Reads a fetch Response as raw text FIRST, then tries to parse it as JSON.
 * Calling resp.json() directly throws a useless "unexpected character at
 * line 1 column 1" error whenever the body isn't actually JSON - an HTML
 * 404/502 page from nginx, a Flask HTML traceback page, or an empty body.
 * This instead throws an error that says exactly what HTTP status came
 * back and what the response body actually contained, so failures are
 * diagnosable instead of cryptic.
 */
async function parseJsonResponse(resp) {
  const raw = await resp.text();

  let data;
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch (parseErr) {
    const snippet = raw.slice(0, 200).replace(/\s+/g, " ").trim();
    throw new Error(
      `Server returned non-JSON response (HTTP ${resp.status}): ${snippet || "(empty body)"}`
    );
  }

  if (!resp.ok) {
    throw new Error(data.error || `Request failed with HTTP ${resp.status}`);
  }

  return data;
}

function toggleFinancialFields() {
  const op = document.getElementById("fin-operation").value;
  const visible = FIN_FIELDS[op];
  ["fin-principal", "fin-rate", "fin-time", "fin-tenure"].forEach((id) => {
    document.getElementById(id).classList.toggle("hidden", !visible.includes(id));
  });
}

async function callScientific() {
  const operation = document.getElementById("sci-operation").value;
  const value = document.getElementById("sci-value").value;
  const base = document.getElementById("sci-base").value;
  const resultEl = document.getElementById("sci-result");

  const body = { operation, value };
  if (base !== "") body.base = base;

  try {
    const resp = await fetch("/api/scientific", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJsonResponse(resp);
    resultEl.classList.remove("error");
    resultEl.textContent = `${operation}(${value}) = ${data.result}`;
    loadHistory();
  } catch (err) {
    resultEl.classList.add("error");
    resultEl.textContent = `Request failed: ${err.message}`;
  }
}

async function callFinancial() {
  const operation = document.getElementById("fin-operation").value;
  const principal = document.getElementById("fin-principal").value;
  const rate = document.getElementById("fin-rate").value;
  const resultEl = document.getElementById("fin-result");

  const body = { operation, principal, rate };
  if (operation === "emi") {
    body.annual_rate = rate;
    body.tenure_months = document.getElementById("fin-tenure").value;
  } else {
    body.time = document.getElementById("fin-time").value;
  }

  try {
    const resp = await fetch("/api/financial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJsonResponse(resp);
    resultEl.classList.remove("error");
    resultEl.textContent = JSON.stringify(data, null, 2);
    loadHistory();
  } catch (err) {
    resultEl.classList.add("error");
    resultEl.textContent = `Request failed: ${err.message}`;
  }
}

async function loadHistory() {
  const listEl = document.getElementById("history-list");
  try {
    const resp = await fetch("/api/history?limit=15");
    const data = await parseJsonResponse(resp);
    listEl.innerHTML = "";
    (data.history || []).forEach((item) => {
      const li = document.createElement("li");
      li.textContent = `[${item.service_type}] ${item.expression} = ${item.result} (${item.created_at})`;
      listEl.appendChild(li);
    });
  } catch (err) {
    listEl.innerHTML = `<li class="error">Failed to load history: ${err.message}</li>`;
  }
}

// LIVE_POLL_INTERVAL_MS controls how often the history feed re-fetches on
// its own, so it reflects calculations made by anyone (any pod, any tab) -
// not just the one you personally just ran. This is what actually makes the
// "Live Calculation History" section live; without it, the list only ever
// updated after your own manual clicks.
const LIVE_POLL_INTERVAL_MS = 4000;
let livePollTimer = null;

function startLivePolling() {
  if (livePollTimer) return; // avoid stacking multiple intervals
  livePollTimer = setInterval(loadHistory, LIVE_POLL_INTERVAL_MS);
}

function stopLivePolling() {
  clearInterval(livePollTimer);
  livePollTimer = null;
}

document.addEventListener("DOMContentLoaded", () => {
  toggleFinancialFields();
  loadHistory();
  startLivePolling();
});

// Pause polling while the tab is hidden (saves requests), resume when it's
// visible again so the feed is always fresh the moment you look back at it.
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopLivePolling();
  } else {
    loadHistory();
    startLivePolling();
  }
});
