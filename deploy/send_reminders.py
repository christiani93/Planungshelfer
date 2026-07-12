#!/usr/bin/env python3
"""Cron-Skript: verschickt faellige Erinnerungen als Web-Push.

Laeuft jede Minute (siehe deploy/install-reminders-cron.sh). Cron hat eine
minimale Umgebung -> wir laden .env selbst, BEVOR push importiert wird
(push.py liest die VAPID-Vars beim Import).

Ablauf:
  1. .env laden, DB oeffnen
  2. faellige Erinnerungen (active=1, remind_at <= jetzt) holen
  3. an alle registrierten Geraete pushen; tote Subscriptions loeschen
  4. woechentliche +7 Tage vorruecken, einmalige deaktivieren
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_env(path):
    """Simple .env-Parser (KEY=VALUE, optionale Quotes) -> os.environ."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)


def main():
    load_env(os.path.join(ROOT, ".env"))
    sys.path.insert(0, ROOT)
    from push import push_configured, send_push  # nach load_env importieren!

    db_path = os.environ.get("PLANUNG_DB") or os.path.join(ROOT, "planung.db")
    if not os.path.exists(db_path):
        return
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    now = datetime.now()  # Server-TZ = Europe/Zurich
    now_iso = now.isoformat(timespec="minutes")

    due = db.execute(
        "SELECT * FROM reminders WHERE active=1 AND remind_at <= ? ORDER BY remind_at",
        (now_iso,),
    ).fetchall()
    if not due:
        db.close()
        return

    subs = db.execute("SELECT * FROM push_subs").fetchall()
    configured = push_configured()

    def log(msg):
        print(f"{now_iso} {msg}", flush=True)

    for rem in due:
        results = {"ok": 0, "gone": 0, "error": 0}
        if configured and subs:
            payload = json.dumps({
                "title": "Planungshelfer",
                "body": rem["message"],
                "tag": f"rem-{rem['id']}",
                "reminder_id": rem["id"],
                "kind": rem["kind"],
            })
            for s in subs:
                result = send_push(
                    {"endpoint": s["endpoint"], "p256dh": s["p256dh"], "auth": s["auth"]},
                    payload,
                )
                results[result] = results.get(result, 0) + 1
                if result == "gone":
                    db.execute("DELETE FROM push_subs WHERE id=?", (s["id"],))
        log(f"gesendet id={rem['id']} kind={rem['kind']} "
            f"'{rem['message']}' subs={len(subs)} -> {results}")

        # Bei Bestaetigungs-Erinnerungen: 'pending' setzen, damit die App auch
        # bei blossem Oeffnen (ohne Button-Tipp) das Ja/Nein-Banner zeigt.
        pending = now_iso if rem["kind"] == "confirm" else None

        # Naechste Faelligkeit setzen bzw. einmalige deaktivieren.
        if rem["recur"] == "weekly":
            nxt = datetime.fromisoformat(rem["remind_at"])
            while nxt <= now:
                nxt += timedelta(days=7)
            db.execute(
                "UPDATE reminders SET remind_at=?, last_sent=?, pending_since=? WHERE id=?",
                (nxt.isoformat(timespec="minutes"), now_iso, pending, rem["id"]),
            )
        else:
            db.execute(
                "UPDATE reminders SET active=0, last_sent=?, pending_since=? WHERE id=?",
                (now_iso, pending, rem["id"]),
            )

    db.commit()
    db.close()


if __name__ == "__main__":
    main()
