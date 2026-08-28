import logging
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from sqlalchemy import Column, DateTime, Integer, Numeric, String, create_engine, desc, text
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from werkzeug.exceptions import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("history-service")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://calcu_user:calcu_pass@postgres:5432/calcu_db",
)

def _build_engine(url):
    """
    SQLite (used during tests) runs on SingletonThreadPool/StaticPool, which
    rejects the QueuePool-only args pool_size/max_overflow with a TypeError.
    Only pass those when connecting to a real pooled backend like PostgreSQL.
    """
    engine_kwargs = {"pool_pre_ping": True}
    if not url.startswith("sqlite"):
        engine_kwargs.update(pool_size=5, max_overflow=10)
    return create_engine(url, **engine_kwargs)


engine = _build_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()


class CalculationHistory(Base):
    __tablename__ = "calculation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expression = Column(String(500), nullable=False)
    result = Column(Numeric, nullable=False)
    service_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "expression": self.expression,
            "result": float(self.result) if self.result is not None else None,
            "service_type": self.service_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


app = Flask(__name__)


@app.errorhandler(Exception)
def handle_any_error(exc):
    """
    Flask's default error pages are HTML, which breaks the frontend's
    JSON.parse() call with a cryptic "unexpected character at line 1
    column 1" error. This guarantees EVERY error response - a 404 from a
    bad path, a 405 from a wrong HTTP method, or any other unhandled
    exception (e.g. the database being unreachable) - always comes back
    as JSON instead.
    """
    if isinstance(exc, HTTPException):
        return jsonify({"error": exc.description}), exc.code
    logger.exception("Unhandled exception")
    return jsonify({"error": "Internal server error"}), 500


@app.teardown_appcontext
def remove_session(exception=None):
    SessionLocal.remove()


@app.route("/health", methods=["GET"])
def health():
    try:
        SessionLocal.execute(text("SELECT 1"))
        return jsonify({"status": "healthy", "service": "history-service"}), 200
    except Exception as exc:
        logger.error("Health check DB failure: %s", exc)
        return jsonify({"status": "unhealthy", "error": str(exc)}), 503


@app.route("/api/history", methods=["POST"])
def create_history():
    payload = request.get_json(silent=True) or {}
    expression = payload.get("expression")
    result = payload.get("result")
    service_type = payload.get("service_type")

    if not expression or result is None or not service_type:
        return jsonify({"error": "'expression', 'result', and 'service_type' are required"}), 400

    session = SessionLocal()
    try:
        record = CalculationHistory(
            expression=str(expression),
            result=float(result),
            service_type=str(service_type),
        )
        session.add(record)
        session.commit()
        return jsonify(record.to_dict()), 201
    except (TypeError, ValueError) as exc:
        session.rollback()
        return jsonify({"error": f"Invalid payload: {exc}"}), 400
    except Exception as exc:
        session.rollback()
        logger.error("Failed to write history: %s", exc)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/history", methods=["GET"])
def list_history():
    limit = request.args.get("limit", default=20, type=int)
    limit = max(1, min(limit, 100))
    service_type = request.args.get("service_type")

    session = SessionLocal()
    query = session.query(CalculationHistory).order_by(desc(CalculationHistory.created_at))
    if service_type:
        query = query.filter(CalculationHistory.service_type == service_type)

    records = query.limit(limit).all()
    return jsonify({"count": len(records), "history": [r.to_dict() for r in records]}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
