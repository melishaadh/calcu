import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    create_engine,
    desc,
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from werkzeug.exceptions import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("history-service")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://calcu_user:calcu_pass@postgres:5432/calcu_db",
)


def _int_env(name, default):
    """Read an int from the environment, falling back to `default` on anything unparseable."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Connection-pool sizing.
#
# Postgres accepts ~100 connections by default. This service runs with
# GUNICORN_WORKERS processes per container and N container replicas, and each
# process opens its own pool of up to (POOL_SIZE + MAX_OVERFLOW) connections.
# The defaults below (5 + 5 = 10) keep 2 workers x 3 replicas = 6 processes
# under 60 connections, well inside the Postgres ceiling. Raise them only if
# you also raise Postgres `max_connections`.
DB_POOL_SIZE = _int_env("DB_POOL_SIZE", 5)
DB_MAX_OVERFLOW = _int_env("DB_MAX_OVERFLOW", 5)
DB_POOL_TIMEOUT = _int_env("DB_POOL_TIMEOUT", 30)

# How long a calculation stays in the history before it is deleted
# automatically. Enforced two ways: opportunistically after every write (see
# create_history), and by a background thread (see _cleanup_loop) so old rows
# still get purged even during a stretch with no new calculations.
HISTORY_RETENTION_DAYS = _int_env("HISTORY_RETENTION_DAYS", 7)
CLEANUP_INTERVAL_SECONDS = _int_env("CLEANUP_INTERVAL_SECONDS", 3600)


def _build_engine(url):
    """
    SQLite (used during tests) runs on SingletonThreadPool/StaticPool, which
    rejects the QueuePool-only args pool_size/max_overflow with a TypeError.
    Only pass those when connecting to a real pooled backend like PostgreSQL.
    """
    engine_kwargs = {"pool_pre_ping": True}
    if not url.startswith("sqlite"):
        engine_kwargs.update(
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_timeout=DB_POOL_TIMEOUT,
            pool_recycle=1800,
        )
    return create_engine(url, **engine_kwargs)


engine = _build_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()


class CalculationHistory(Base):
    __tablename__ = "calculation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expression = Column(String(500), nullable=False)
    result = Column(Numeric, nullable=False)
    service_type = Column(String(50), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "expression": self.expression,
            "result": float(self.result) if self.result is not None else None,
            "service_type": self.service_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db(retries=None, delay=None):
    """
    Create the `calculation_history` table if it does not exist.

    In Docker Compose the schema is also bootstrapped by db/init.sql, but a
    bare Postgres (Kubernetes StatefulSet, a hand-run container, RDS, ...) has
    no such hook - without this, the first POST /api/history fails with
    'relation "calculation_history" does not exist'. create_all() is
    idempotent, so running it in every environment is safe.

    Postgres often is not accepting connections the instant this container
    starts, so retry a bounded number of times before giving up and letting
    the readiness probe keep the pod out of rotation.
    """
    retries = _int_env("DB_INIT_RETRIES", 10) if retries is None else retries
    delay = _int_env("DB_INIT_RETRY_DELAY", 2) if delay is None else delay

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(engine)
            logger.info("Database schema is ready")
            return True
        except SQLAlchemyError as exc:
            last_err = exc
            logger.warning(
                "Database not ready yet (attempt %s/%s): %s", attempt, retries, exc
            )
            time.sleep(delay)
    logger.error("Gave up initialising database schema: %s", last_err)
    return False


def cleanup_old_history():
    """Delete every history row older than HISTORY_RETENTION_DAYS. Returns the count removed."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
    session = SessionLocal()
    try:
        deleted = (
            session.query(CalculationHistory)
            .filter(CalculationHistory.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        if deleted:
            logger.info("Cleanup removed %s history record(s) older than %s days", deleted, HISTORY_RETENTION_DAYS)
        return deleted
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("History cleanup failed: %s", exc)
        return 0
    finally:
        SessionLocal.remove()


def _cleanup_loop():
    """Background thread: purge history older than the retention window on a
    fixed interval, so cleanup happens even without new writes."""
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        cleanup_old_history()


app = Flask(__name__)

# Runs once, in the Gunicorn master, because the container starts Gunicorn with
# --preload (the module is imported before workers are forked). Skipped for the
# SQLite in-memory test runs, which build their own schema in test_app.py.
#
# engine.dispose() then drops every pooled connection so each forked worker
# opens its own — inheriting a live socket across fork() corrupts the protocol.
if not DATABASE_URL.startswith("sqlite"):
    init_db()
    engine.dispose()
    cleanup_old_history()
    threading.Thread(target=_cleanup_loop, daemon=True).start()


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

    try:
        # A giant integer (e.g. factorial results) raises OverflowError here
        # rather than silently becoming inf.
        numeric_result = float(result)
    except (TypeError, ValueError, OverflowError) as exc:
        return jsonify({"error": f"Invalid 'result' value: {exc}"}), 400

    session = SessionLocal()
    try:
        record = CalculationHistory(
            expression=str(expression)[:500],
            result=numeric_result,
            service_type=str(service_type)[:50],
        )
        session.add(record)
        session.commit()
        result_dict = record.to_dict()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Failed to write history: %s", exc)
        return jsonify({"error": "Internal server error"}), 500

    cleanup_old_history()
    return jsonify(result_dict), 201


@app.route("/api/history", methods=["GET"])
def list_history():
    # A non-integer ?limit= must not 500 the endpoint.
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 100))
    service_type = request.args.get("service_type")
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)

    session = SessionLocal()
    try:
        query = (
            session.query(CalculationHistory)
            .filter(CalculationHistory.created_at >= cutoff)
            .order_by(desc(CalculationHistory.created_at))
        )
        if service_type:
            query = query.filter(CalculationHistory.service_type == service_type)
        records = query.limit(limit).all()
    except SQLAlchemyError as exc:
        logger.error("Failed to read history: %s", exc)
        return jsonify({"error": "Internal server error"}), 500

    return jsonify({"count": len(records), "history": [r.to_dict() for r in records]}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
