#!/bin/bash
# Database backup script for BMAD Wyckoff system
# Usage: ./scripts/backup-db.sh
# Runs pg_dump against the production database container
# Stores timestamped backups in ./backups/ with 30-day retention

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/bmad_wyckoff_${TIMESTAMP}.dump"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting database backup..."

# Run pg_dump inside the postgres container and compress
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-bmad}" -d "${POSTGRES_DB:-bmad_wyckoff}" \
  --format=custom --compress=9 \
  > "$BACKUP_FILE"

# Verify backup was created and has content
if [ -s "$BACKUP_FILE" ]; then
  SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
  echo "[$(date)] Backup successful: $BACKUP_FILE ($SIZE)"
else
  echo "[$(date)] ERROR: Backup file is empty or missing!" >&2
  rm -f "$BACKUP_FILE"
  exit 1
fi

# Clean up old backups beyond retention period
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "bmad_wyckoff_*.dump" -mtime +${RETENTION_DAYS} -delete
REMAINING=$(find "$BACKUP_DIR" -name "bmad_wyckoff_*.dump" | wc -l)
echo "[$(date)] Backup complete. ${REMAINING} backup(s) retained."
