#!/usr/bin/env bash
# Idempotent: fuegt taeglichen Backup-Cron um 03:15 hinzu, ohne bestehende
# Eintraege zu ueberschreiben.
set -euo pipefail

SCRIPT="$HOME/apps/todo/deploy/backup.sh"
LINE="15 3 * * * $SCRIPT >/dev/null 2>&1"

chmod +x "$SCRIPT" 2>/dev/null || true

if crontab -l 2>/dev/null | grep -Fq "$SCRIPT"; then
    echo "Cron-Job existiert bereits — nichts geaendert."
else
    ( crontab -l 2>/dev/null; echo "$LINE" ) | crontab -
    echo "Cron-Job hinzugefuegt: $LINE"
fi
