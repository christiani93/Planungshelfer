#!/bin/bash
set -e
cd "$(dirname "$0")/.."
mkdir -p logs
# .env laden (Passwort, API-Token, Secret, DB-Pfad, BIND ...)
if [ -f .env ]; then set -a; . .env; set +a; fi
# App-Objekt ist das Modul-Level "app" in app.py
exec .venv/bin/gunicorn -c deploy/gunicorn.conf.py "app:app"
