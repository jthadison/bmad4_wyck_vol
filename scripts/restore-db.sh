#!/bin/bash
# Database restore script for BMAD Wyckoff system
# Usage: ./scripts/restore-db.sh <backup_file>
# WARNING: This will overwrite the current database!

set -euo pipefail

BACKUP_FILE="${1:?Usage: $0 <backup_file.dump>}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

echo "WARNING: This will overwrite the current database!"
echo "Backup file: $BACKUP_FILE"
read -p "Are you sure? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Restore cancelled."
  exit 0
fi

echo "[$(date)] Starting database restore from $BACKUP_FILE..."

# Drop and recreate the database
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "${POSTGRES_USER:-bmad}" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${POSTGRES_DB:-bmad_wyckoff}' AND pid <> pg_backend_pid();"

docker compose -f docker-compose.prod.yml exec -T postgres \
  dropdb -U "${POSTGRES_USER:-bmad}" --if-exists "${POSTGRES_DB:-bmad_wyckoff}"

docker compose -f docker-compose.prod.yml exec -T postgres \
  createdb -U "${POSTGRES_USER:-bmad}" "${POSTGRES_DB:-bmad_wyckoff}"

# Restore from backup
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U "${POSTGRES_USER:-bmad}" -d "${POSTGRES_DB:-bmad_wyckoff}" \
  --no-owner --no-acl < "$BACKUP_FILE"

echo "[$(date)] Restore complete. Verifying..."

# Verify restore
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "${POSTGRES_USER:-bmad}" -d "${POSTGRES_DB:-bmad_wyckoff}" \
  -c "SELECT count(*) as table_count FROM information_schema.tables WHERE table_schema='public';"

echo "[$(date)] Database restore finished successfully."
