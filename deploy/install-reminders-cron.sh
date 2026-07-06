#!/usr/bin/env bash
# Idempotent: laesst jede Minute den Erinnerungs-Sender laufen. Output in ein
# Log (nicht nach stdout) -> kein Mail-Spam trotz MAILTO in der Crontab.
set -euo pipefail

APP="$HOME/apps/todo"
PY="$APP/.venv/bin/python3"
SCRIPT="$APP/deploy/send_reminders.py"
LOG="$APP/logs/reminders.log"
LINE="* * * * * $PY $SCRIPT >> $LOG 2>&1"

mkdir -p "$APP/logs"

if crontab -l 2>/dev/null | grep -Fq "$SCRIPT"; then
    echo "Reminder-Cron existiert bereits — nichts geaendert."
else
    ( crontab -l 2>/dev/null; echo "$LINE" ) | crontab -
    echo "Reminder-Cron hinzugefuegt: $LINE"
fi
