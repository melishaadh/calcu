#!/usr/bin/env bash
#
# deploy.sh — build and (re)start the calcu stack. Use it for the first
# deploy and for every update afterwards. Idempotent.
#
# Runs from anywhere; it cd's to the repo root itself.
#
# Usage:
#   ./deploy/deploy.sh            # local: uses docker-compose.yml only
#   ENV=prod ./deploy/deploy.sh   # EC2:  adds docker-compose.prod.yml overrides
#
# Requires a .env file at the repo root (copy from .env.example first).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run:  cp .env.example .env  and edit it." >&2
  exit 1
fi

COMPOSE_FILES=(-f docker-compose.yml)
if [ "${ENV:-local}" = "prod" ]; then
  COMPOSE_FILES+=(-f docker-compose.prod.yml)
  echo "==> Deploying with PRODUCTION overrides"
else
  echo "==> Deploying LOCAL configuration"
fi

echo "==> Pulling latest source (if this is a git checkout)"
git pull --ff-only 2>/dev/null || echo "   (not a git pull context — skipping)"

echo "==> Building images"
docker compose "${COMPOSE_FILES[@]}" build

echo "==> Starting / updating containers"
docker compose "${COMPOSE_FILES[@]}" up -d --remove-orphans

echo "==> Waiting for health checks"
sleep 5
docker compose "${COMPOSE_FILES[@]}" ps

echo "==> Pruning dangling images"
docker image prune -f >/dev/null

echo
echo "Done. Stack status above. Tail logs with:"
echo "  docker compose ${COMPOSE_FILES[*]} logs -f"
