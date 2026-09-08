const API_URL = window.APP_CONFIG.API_URL;

document.getElementById("calculateBtn").addEventListener("click", async () => {
  const a = parseFloat(document.getElementById("inputA").value);
  const b = parseFloat(document.getElementById("inputB").value);
  const operation = document.getElementById("operation").value;
  const resultEl = document.getElementById("result");

  if (isNaN(a) || isNaN(b)) {
    resultEl.textContent = "Please enter both numbers";
    return;
  }

  resultEl.textContent = "Calculating...";

  try {
    const response = await fetch(`${API_URL}/calculate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation, a, b }),
    });

    const data = await response.json();

    if (!response.ok) {
      resultEl.textContent = data.detail || "Error";
      return;
    }

    resultEl.textContent = `Result: ${data.result}`;
  } catch (err) {
    resultEl.textContent = "Could not reach backend";
  }
});
