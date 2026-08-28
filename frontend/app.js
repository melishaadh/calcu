const FIN_FIELDS = {
  simple_interest: ["fin-principal", "fin-rate", "fin-time"],
  compound_interest: ["fin-principal", "fin-rate", "fin-time"],
  emi: ["fin-principal", "fin-rate", "fin-tenure"],
};

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
    const data = await resp.json();
    resultEl.classList.toggle("error", !resp.ok);
    resultEl.textContent = resp.ok
      ? `${operation}(${value}) = ${data.result}`
      : `Error: ${data.error}`;
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
    const data = await resp.json();
    resultEl.classList.toggle("error", !resp.ok);
    resultEl.textContent = resp.ok ? JSON.stringify(data, null, 2) : `Error: ${data.error}`;
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
    const data = await resp.json();
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
