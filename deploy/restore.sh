#!/usr/bin/env bash
# Restore eines Backups. Legt vorher einen Safety-Snapshot des aktuellen
# Datenordners an, damit nichts unwiederbringlich verloren geht.
set -euo pipefail

DATA_DIR="$HOME/apps/todo_data"
BACKUP_DIR="$HOME/apps/todo_backups"

echo "Verfuegbare Backups:"
ls -1 "$BACKUP_DIR"/todo-*.tar.gz 2>/dev/null || { echo "Keine Backups."; exit 1; }

read -rp "Dateiname des Backups (aus $BACKUP_DIR): " NAME
ARCHIVE="$BACKUP_DIR/$NAME"
[ -f "$ARCHIVE" ] || { echo "Nicht gefunden: $ARCHIVE"; exit 1; }

if [ -d "$DATA_DIR" ]; then
    SNAP="$BACKUP_DIR/pre-restore-$(date +%Y%m%d-%H%M%S).tar.gz"
    tar -czf "$SNAP" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
    echo "Safety-Snapshot: $SNAP"
fi

tar -xzf "$ARCHIVE" -C "$(dirname "$DATA_DIR")"
echo "Restore fertig. Service neu starten:"
echo "  supervisorctl -c ~/.services/supervisord/hostpoint.conf restart todo"
