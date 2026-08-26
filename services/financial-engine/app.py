import logging
import os

import requests
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("financial-engine")

app = Flask(__name__)

HISTORY_SERVICE_URL = os.environ.get("HISTORY_SERVICE_URL", "http://history-service:5003")

SUPPORTED_OPERATIONS = {"simple_interest", "compound_interest", "emi"}


def record_history(expression, result, service_type="financial"):
    try:
        requests.post(
            f"{HISTORY_SERVICE_URL}/api/history",
            json={"expression": expression, "result": result, "service_type": service_type},
            timeout=2,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to record history: %s", exc)


def _to_float(payload, key, required=True, default=None):
    value = payload.get(key, default)
    if value is None:
        if required:
            raise ValueError(f"'{key}' is required")
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{key}' must be numeric")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "financial-engine"}), 200


@app.route("/api/financial", methods=["POST"])
def financial():
    payload = request.get_json(silent=True) or {}
    operation = payload.get("operation")

    if operation not in SUPPORTED_OPERATIONS:
        return jsonify({"error": f"Unsupported operation '{operation}'"}), 400

    try:
        if operation == "simple_interest":
            principal = _to_float(payload, "principal")
            rate = _to_float(payload, "rate")
            time = _to_float(payload, "time")
            interest = (principal * rate * time) / 100
            result = {"interest": interest, "total_amount": principal + interest}
            expression = f"SI(P={principal}, R={rate}, T={time})"

        elif operation == "compound_interest":
            principal = _to_float(payload, "principal")
            rate = _to_float(payload, "rate")
            time = _to_float(payload, "time")
            n = _to_float(payload, "compounds_per_year", required=False, default=1) or 1
            amount = principal * ((1 + (rate / (100 * n))) ** (n * time))
            interest = amount - principal
            result = {"interest": interest, "total_amount": amount}
            expression = f"CI(P={principal}, R={rate}, T={time}, n={n})"

        elif operation == "emi":
            principal = _to_float(payload, "principal")
            annual_rate = _to_float(payload, "annual_rate")
            tenure_months = _to_float(payload, "tenure_months")
            monthly_rate = annual_rate / (12 * 100)
            if monthly_rate == 0:
                emi = principal / tenure_months
            else:
                emi = (principal * monthly_rate * (1 + monthly_rate) ** tenure_months) / (
                    ((1 + monthly_rate) ** tenure_months) - 1
                )
            total_payment = emi * tenure_months
            result = {
                "emi": emi,
                "total_payment": total_payment,
                "total_interest": total_payment - principal,
            }
            expression = f"EMI(P={principal}, R={annual_rate}, N={tenure_months})"

        else:
            return jsonify({"error": "Unsupported operation"}), 400

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except ZeroDivisionError:
        return jsonify({"error": "Division by zero in calculation"}), 400

    record_history(expression, result.get("emi", result.get("total_amount")))

    return jsonify({"operation": operation, **result}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
