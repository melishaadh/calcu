import math
import logging
import os

import requests
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scientific-engine")

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_any_error(exc):
    """
    Flask's default error pages are HTML, which breaks the frontend's
    JSON.parse() call with a cryptic "unexpected character at line 1
    column 1" error. This guarantees EVERY error response - a 404 from a
    bad path, a 405 from a wrong HTTP method, a math OverflowError, or any
    other unhandled exception - always comes back as JSON instead.
    """
    if isinstance(exc, HTTPException):
        return jsonify({"error": exc.description}), exc.code
    logger.exception("Unhandled exception")
    return jsonify({"error": "Internal server error"}), 500

HISTORY_SERVICE_URL = os.environ.get("HISTORY_SERVICE_URL", "http://history-service:5003")

SUPPORTED_OPERATIONS = {
    "sin", "cos", "tan", "asin", "acos", "atan",
    "log", "log10", "ln", "exp", "sqrt", "pow", "factorial",
}


def record_history(expression, result, service_type="scientific"):
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
    return jsonify({"status": "healthy", "service": "scientific-engine"}), 200


@app.route("/api/scientific", methods=["POST"])
def scientific():
    payload = request.get_json(silent=True) or {}
    operation = payload.get("operation")
    value = payload.get("value")
    base = payload.get("base")

    if operation not in SUPPORTED_OPERATIONS:
        return jsonify({"error": f"Unsupported operation '{operation}'"}), 400

    if value is None:
        return jsonify({"error": "'value' is required"}), 400

    try:
        value = float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "'value' must be numeric"}), 400

    if base is not None:
        try:
            base = float(base)
        except (TypeError, ValueError):
            return jsonify({"error": "'base' must be numeric"}), 400

    try:
        if operation == "sin":
            result = math.sin(math.radians(value))
        elif operation == "cos":
            result = math.cos(math.radians(value))
        elif operation == "tan":
            result = math.tan(math.radians(value))
        elif operation == "asin":
            result = math.degrees(math.asin(value))
        elif operation == "acos":
            result = math.degrees(math.acos(value))
        elif operation == "atan":
            result = math.degrees(math.atan(value))
        elif operation == "log":
            result = math.log(value)
        elif operation == "log10":
            result = math.log10(value)
        elif operation == "ln":
            result = math.log(value)
        elif operation == "exp":
            result = math.exp(value)
        elif operation == "sqrt":
            result = math.sqrt(value)
        elif operation == "pow":
            if base is None:
                return jsonify({"error": "'base' is required for pow"}), 400
            result = math.pow(value, base)
        elif operation == "factorial":
            # factorial needs a non-negative integer, and a huge argument
            # (factorial(1e6) is ~5.5M digits) would pin a CPU for seconds -
            # reject both instead of hanging the worker.
            if value < 0 or not value.is_integer():
                return jsonify({"error": "factorial requires a non-negative integer"}), 400
            # 170! is the largest factorial that still fits in a float (and so
            # in the history NUMERIC column); 171! overflows to infinity.
            if value > 170:
                return jsonify({"error": "factorial argument too large (max 170)"}), 400
            result = float(math.factorial(int(value)))
        else:
            return jsonify({"error": "Unsupported operation"}), 400
    except ValueError as exc:
        return jsonify({"error": f"Math domain error: {exc}"}), 400
    except OverflowError:
        return jsonify({"error": "Result is too large to represent"}), 400

    expression = f"{operation}({value}{', ' + str(base) if base is not None else ''})"
    record_history(expression, result)

    return jsonify({"operation": operation, "value": value, "result": result}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
