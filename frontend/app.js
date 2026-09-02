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
  const contentType = resp.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    const snippet = raw.slice(0, 200).replace(/\s+/g, " ").trim();
    throw new Error(
      `Expected JSON but got "${contentType || "unknown"}" (HTTP ${resp.status}): ${snippet || "(empty body)"}`
    );
  }

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

async function calculate() {
  const operation = document.getElementById("operation").value;
  const operand1 = document.getElementById("operand1").value;
  const operand2 = document.getElementById("operand2").value;
  const resultEl = document.getElementById("result");

  try {
    const resp = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation, operand1, operand2 }),
    });
    const data = await parseJsonResponse(resp);
    resultEl.classList.remove("error");
    resultEl.textContent = `= ${data.result}`;
    loadHistory();
  } catch (err) {
    resultEl.classList.add("error");
    resultEl.textContent = `Error: ${err.message}`;
  }
}

async function loadHistory() {
  const listEl = document.getElementById("history-list");
  try {
    const resp = await fetch("/api/history");
    const data = await parseJsonResponse(resp);
    listEl.innerHTML = "";
    (data.history || []).forEach((item) => {
      const li = document.createElement("li");
      li.textContent = `${item.expression} = ${item.result} (${item.created_at})`;
      listEl.appendChild(li);
    });
  } catch (err) {
    listEl.innerHTML = `<li class="error">Failed to load history: ${err.message}</li>`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("calculate-btn").addEventListener("click", calculate);
  document.getElementById("refresh-btn").addEventListener("click", loadHistory);
  loadHistory();
});
