#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Sync mit origin/main (force, ueberschreibt lokale Aenderungen) ==="
git fetch origin
git reset --hard origin/main
chmod +x deploy/*.sh 2>/dev/null || true
mkdir -p logs

echo "=== Venv ==="
[ ! -d ".venv" ] && python3 -m venv .venv
. .venv/bin/activate

echo "=== Requirements ==="
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo "=== Service-Restart ==="
HOSTPOINT_CONF="$HOME/.services/supervisord/hostpoint.conf"
if [ -f "$HOSTPOINT_CONF" ]; then
    supervisorctl -c "$HOSTPOINT_CONF" restart todo
    sleep 1
    supervisorctl -c "$HOSTPOINT_CONF" status todo
else
    echo "supervisord-Config nicht gefunden — bitte manuell pruefen."
fi
echo "Done."
