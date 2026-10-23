#!/usr/bin/env bash
# Restore db/database_backup.sql (schema + COPY data) in one transaction.
#
# Default target: db/database_snapshot.sql (the submission artifact). A newer
# db/database_backup.sql from db_backup.sh takes precedence over it.
#
# Connection settings mirror db_backup.sh: environment wins, then
# uplift-backend/.env, then peer-auth localhost defaults.
# NOTE: the target database must exist beforehand on a fresh server:
#   createdb uplift_rwanda_db
set -euo pipefail

cd "$(dirname "$0")/../.."

BACKUP_FILE="db/database_backup.sql"
[ -f "$BACKUP_FILE" ] || BACKUP_FILE="db/database_snapshot.sql"

[ -f "uplift-backend/.env" ] && { set -a; source "uplift-backend/.env"; set +a; }

DB_NAME="${DB_NAME:-uplift_rwanda_db}"
CONN=()
[ "${DB_HOST:-}" ] && CONN+=(--host "$DB_HOST")
[ "${DB_PORT:-}" ] && CONN+=(--port "$DB_PORT")
[ "${DB_USER:-}" ] && CONN+=(--username "$DB_USER")
export PGPASSWORD="${DB_PASSWORD:-${PGPASSWORD:-}}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Error: neither $PWD/$BACKUP_FILE (snapshot) nor db/database_backup.sql found (run db/scripts/db_backup.sh)." >&2
  exit 1
fi

echo "Restoring $BACKUP_FILE into database '$DB_NAME' ..."

# The snapshot artifact is built without --clean (fresh createdb target), so any
# pre-existing analytics tables must go first. --clean backups contain their
# own DROPs, making this a harmless no-op double for them. FK-safe order.
psql "${CONN[@]}" --dbname="$DB_NAME" --set=ON_ERROR_STOP=1 <<SQL
DROP TABLE IF EXISTS survey_metrics CASCADE;
DROP TABLE IF EXISTS district_cfsva_metrics CASCADE;
DROP TABLE IF EXISTS national_targets CASCADE;
DROP TABLE IF EXISTS indicators CASCADE;
DROP TABLE IF EXISTS regions CASCADE;
SQL

psql "${CONN[@]}" \
  --dbname="$DB_NAME" \
  --single-transaction \
  --set=ON_ERROR_STOP=1 \
  --file="$BACKUP_FILE"

echo "Restore from $BACKUP_FILE completed successfully."
