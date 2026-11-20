#!/bin/bash
set -e

if [ -z "$DB_HOST" ]; then
  echo "ERROR: DB_HOST is not set" >&2
  exit 1
fi

ATLAS_HOST="${MIGRATIONS_DB_HOST:-$DB_HOST}"
MIGRATIONS_DB_USER="${MIGRATIONS_DB_USER:-$DB_USER}"
MIGRATIONS_DB_PASSWORD="${MIGRATIONS_DB_PASSWORD:-$ADMIN_PASSWORD}"
ATLAS_URL="postgres://${MIGRATIONS_DB_USER}:${MIGRATIONS_DB_PASSWORD}@${ATLAS_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require"

# The code reads the migrated shapes, so it must never serve an unmigrated
# schema. A few attempts absorb a database that is still waking up.
echo "Running migrations against $ATLAS_HOST..."
cd /app/database
for attempt in 1 2 3; do
  if atlas migrate apply --env azure --url "$ATLAS_URL" \
       --revisions-schema "${ATLAS_REVISIONS_SCHEMA:-public}" --allow-dirty; then
    echo "Migrations applied successfully"
    break
  fi
  if [ "$attempt" -eq 3 ]; then
    echo "ERROR: Migrations failed 3 times - check $ATLAS_HOST is reachable on port $DB_PORT" >&2
    exit 1
  fi
  echo "WARNING: Migration attempt $attempt failed; retrying in 10s"
  sleep 10
done

cd /app
unset MIGRATIONS_DB_PASSWORD POSTGRES_PASSWORD APP_USER_PASSWORD USER_PASSWORD
exec uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
