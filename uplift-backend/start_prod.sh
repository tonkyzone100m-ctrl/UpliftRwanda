#!/usr/bin/env bash
# Production launcher for the UpliftRwanda FastAPI service.
#
#   ./start_prod.sh                 # foreground (systemd / tmux / Procfile)
#   PORT=8080 ./start_prod.sh       # any override through the environment
#
# Hard production gate: UPLIFT_ADMIN_PASSWORD (or UPLIFT_ADMIN_PASSWORD_HASH)
# must be present in the environment or uplift-backend/.env — the fallback dev
# password is not allowed to boot in production mode. All knobs (HOST, PORT,
# WORKERS, DB_*, UPLIFT_*) mirror uplift-backend/.env.example.
set -euo pipefail
cd "$(dirname "$0")"

# Hosted platforms (Render, Railway, Fly) inject env vars directly; .env is
# optional and only sourced when it exists so a fresh clone still boots.
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "${UPLIFT_ADMIN_PASSWORD:-}" ] && [ -z "${UPLIFT_ADMIN_PASSWORD_HASH:-}" ]; then
  echo "start_prod.sh: refusing to boot — UPLIFT_ADMIN_PASSWORD / UPLIFT_ADMIN_PASSWORD_HASH not set." >&2
  echo "Set it in the environment or .env (see .env.example) before production launch." >&2
  exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

# Local checkouts use the checked-in venv; hosted runtimes already install
# requirements into the platform interpreter.
PY="${PY:-}"
if [ -z "$PY" ]; then
  if [ -x venv/bin/python ]; then PY=venv/bin/python; else PY=python3; fi
fi

exec "$PY" -m uvicorn main:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WORKERS" \
  --proxy-headers
