import logging
import os

import requests
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calculator-engine")

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_any_error(exc):
    """
    Flask's default error pages are HTML, which breaks the frontend's
    JSON.parse() call with a cryptic "unexpected character at line 1
    column 1" error. This guarantees EVERY error response - a 404 from a
    bad path, a 405 from a wrong HTTP method, or any other unhandled
    exception - always comes back as JSON instead.
    """
    if isinstance(exc, HTTPException):
        return jsonify({"error": exc.description}), exc.code
    logger.exception("Unhandled exception")
    return jsonify({"error": "Internal server error"}), 500


HISTORY_SERVICE_URL = os.environ.get("HISTORY_SERVICE_URL", "http://history-service:5003")

OPERATION_SYMBOLS = {
    "add": "+",
    "subtract": "-",
    "multiply": "×",
    "divide": "÷",
}


def record_history(expression, result, service_type="calculator"):
    try:
        requests.post(
            f"{HISTORY_SERVICE_URL}/api/history",
            json={"expression": expression, "result": result, "service_type": service_type},
            timeout=2,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to record history: %s", exc)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "calculator-engine"}), 200


@app.route("/api/calculate", methods=["POST"])
def calculate():
    payload = request.get_json(silent=True) or {}
    operation = payload.get("operation")
    operand1 = payload.get("operand1")
    operand2 = payload.get("operand2")

    if operation not in OPERATION_SYMBOLS:
        return jsonify({"error": f"Unsupported operation '{operation}'"}), 400

    if operand1 is None or operand2 is None:
        return jsonify({"error": "'operand1' and 'operand2' are required"}), 400

    try:
        operand1 = float(operand1)
        operand2 = float(operand2)
    except (TypeError, ValueError):
        return jsonify({"error": "'operand1' and 'operand2' must be numeric"}), 400

    if operation == "add":
        result = operand1 + operand2
    elif operation == "subtract":
        result = operand1 - operand2
    elif operation == "multiply":
        result = operand1 * operand2
    elif operation == "divide":
        if operand2 == 0:
            return jsonify({"error": "Division by zero"}), 400
        result = operand1 / operand2

    expression = f"{operand1} {OPERATION_SYMBOLS[operation]} {operand2}"
    record_history(expression, result)

    return jsonify({"operation": operation, "operand1": operand1, "operand2": operand2, "result": result}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
