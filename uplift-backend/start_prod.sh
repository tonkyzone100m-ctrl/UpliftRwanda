#!/usr/bin/env bash
# Production launcher for the UpliftRwanda FastAPI service.
#
#   ./start_prod.sh                 # foreground (systemd / tmux friendly)
#   PORT=8080 ./start_prod.sh       # any override through the environment
#
# Hard production gate: UPLIFT_ADMIN_PASSWORD (or UPLIFT_ADMIN_PASSWORD_HASH)
# must be present in the environment or uplift-backend/.env — the fallback dev
# password is not allowed to boot in production mode. All knobs (HOST, PORT,
# WORKERS, DB_*, UPLIFT_*) mirror uplift-backend/.env.example.
set -euo pipefail
cd "$(dirname "$0")"

set -a
source .env
set +a

if [ -z "${UPLIFT_ADMIN_PASSWORD:-}" ] && [ -z "${UPLIFT_ADMIN_PASSWORD_HASH:-}" ]; then
  echo "start_prod.sh: refusing to boot — UPLIFT_ADMIN_PASSWORD / UPLIFT_ADMIN_PASSWORD_HASH not set." >&2
  echo "Set it in .env (see .env.example) before production launch." >&2
  exit 1
fi

PY="${PY:-venv/bin/python}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

exec "$PY" -m uvicorn main:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WORKERS" \
  --proxy-headers
