CREATE TABLE IF NOT EXISTS calculation_history (
    id              SERIAL PRIMARY KEY,
    expression      VARCHAR(500)    NOT NULL,
    result          NUMERIC         NOT NULL,
    service_type    VARCHAR(50)     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calculation_history_service_type
    ON calculation_history (service_type);

CREATE INDEX IF NOT EXISTS idx_calculation_history_created_at
    ON calculation_history (created_at DESC);
