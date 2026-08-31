# syntax=docker/dockerfile:1

# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY app.py wsgi.py ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5003

# start-period covers the worst-case wait for Postgres on a cold start
# (init_db() retries DB_INIT_RETRIES x 2s before the app serves traffic).
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5003/health')" || exit 1

# --preload: import the app once in the master so init_db() (schema create +
#   Postgres wait) runs a single time, not once per worker.
# --timeout 60: a slow first DB connection during boot must not trip Gunicorn's
#   worker-timeout kill.
CMD ["gunicorn", "--preload", "--bind", "0.0.0.0:5003", "--workers", "2", "--threads", "2", "--timeout", "60", "wsgi:app"]
