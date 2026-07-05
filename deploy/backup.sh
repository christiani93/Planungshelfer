#!/usr/bin/env bash
# Taegliches Backup der SQLite-DB (Datenordner), 30 Tage Rotation.
set -euo pipefail

DATA_DIR="$HOME/apps/todo_data"
BACKUP_DIR="$HOME/apps/todo_backups"
LOG="$(dirname "$0")/../logs/backup.log"
mkdir -p "$BACKUP_DIR" "$(dirname "$LOG")"

STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$BACKUP_DIR/todo-$STAMP.tar.gz"

if [ -d "$DATA_DIR" ]; then
    tar -czf "$ARCHIVE" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
    echo "[$(date)] Backup ok: $ARCHIVE" >> "$LOG"
    # Rotation: alles aelter als 30 Tage loeschen
    find "$BACKUP_DIR" -name 'todo-*.tar.gz' -mtime +30 -delete
else
    echo "[$(date)] Datenordner fehlt: $DATA_DIR" >> "$LOG"
fi
