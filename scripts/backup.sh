#!/usr/bin/env bash
# Backup diario de la BD PostgreSQL. Configurar en cron a las 3:00 AM:
#   0 3 * * * /home/deploy/negociosano/scripts/backup.sh >> /home/deploy/negociosano/logs/backup.log 2>&1
set -euo pipefail

BACKUP_DIR="/home/deploy/negociosano/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/negociosano_$DATE.sql.gz"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando backup..."

docker exec negociosano-db-1 pg_dump -U postgres negociosano \
  | gzip > "$BACKUP_FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup completado: $BACKUP_FILE"

# Eliminar backups con más de KEEP_DAYS días
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$KEEP_DAYS" -delete
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backups antiguos eliminados (retención: ${KEEP_DAYS} días)"
