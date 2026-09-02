-- init.sql — schema bootstrap for the history-service database.
--
-- Docker Compose runs this automatically via the postgres image's
-- /docker-entrypoint-initdb.d hook, so the table exists the moment Postgres
-- finishes its first start.
--
-- Environments without that hook (a bare `docker run postgres`, a Kubernetes
-- StatefulSet, Amazon RDS, ...) rely on history-service calling
-- SQLAlchemy's create_all() on startup instead — see init_db() in
-- services/history-service/app.py. Both paths are idempotent and produce the
-- same table, so it does not matter which one runs first.
--
-- Indexes are intentionally NOT declared here: the ORM model owns them
-- (Column(..., index=True)), which keeps a single source of truth and avoids
-- duplicate indexes when both this file and create_all() run.
--
-- Rows are kept for 7 days: history-service deletes anything older than that
-- automatically (after every write, and on an hourly background sweep) - see
-- HISTORY_RETENTION_DAYS in services/history-service/app.py.

CREATE TABLE IF NOT EXISTS calculation_history (
    id              SERIAL PRIMARY KEY,
    expression      VARCHAR(500)    NOT NULL,
    result          NUMERIC         NOT NULL,
    service_type    VARCHAR(50)     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
