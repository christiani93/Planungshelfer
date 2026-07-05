"""Beispiel: aus einem anderen Projekt eine Aufgabe in den Planungshelfer legen.

Aufruf (nachdem der Planungshelfer auf dem Server laeuft):
    python add_task.py "Sicherung Baustelle Meier pruefen"

Voraussetzung: die App laeuft mit gesetztem PLANUNG_API_TOKEN.
"""
import os
import sys
import urllib.request
import json

# Auf dem Server z.B. https://todo.z-b.tech ; lokal http://127.0.0.1:5005
BASE = os.environ.get("PLANUNG_URL", "http://127.0.0.1:5005")
TOKEN = os.environ.get("PLANUNG_API_TOKEN", "")


def add(title, priority=2, is_today=True, source="Skript"):
    payload = json.dumps({
        "title": title,
        "priority": priority,
        "is_today": is_today,
        "source": source,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ingest",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "Test-Aufgabe vom Skript"
    print(add(text))
