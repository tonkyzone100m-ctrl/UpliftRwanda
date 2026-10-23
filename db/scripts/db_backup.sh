#!/usr/bin/env bash
# Dump schema + all data (seed) of the uplift_rwanda_db database into
# database_backup.sql next to this script, ready for psql restore.
#
# Connection settings come from the environment when set; otherwise the script
# falls back to `uplift-backend/.env` (DB_USER / DB_PASSWORD / DB_HOST / DB_PORT /
# DB_NAME) or plain peer-auth localhost defaults, matching the warning line
# 'PEER/TRUST local installs can leave DB_PASSWORD blank' in .env.
#
# The output is continuously refreshed into db/database_snapshot.sql's format
# (schema + COPY data, no owner / no privileges) and is safe for a fresh judge
# restore:
#   createdb uplift_rwanda_db && psql -d uplift_rwanda_db -f database_backup.sql
set -euo pipefail

cd "$(dirname "$0")/../.."
BACKUP_FILE="db/database_backup.sql"
[ -f "uplift-backend/.env" ] && { set -a; source "uplift-backend/.env"; set +a; }

DB_NAME="${DB_NAME:-uplift_rwanda_db}"
CONN=()
[ "${DB_HOST:-}" ] && CONN+=(--host "$DB_HOST")
[ "${DB_PORT:-}" ] && CONN+=(--port "$DB_PORT")
[ "${DB_USER:-}" ] && CONN+=(--username "$DB_USER")
export PGPASSWORD="${DB_PASSWORD:-${PGPASSWORD:-}}"

umask 077
pg_dump "${CONN[@]}" "$DB_NAME" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --verbose \
  --file="$BACKUP_FILE"

printf 'Backup written to %s (%s rows of SQL)\n' \
  "$PWD/$BACKUP_FILE" "$(wc -l < "$BACKUP_FILE")"
