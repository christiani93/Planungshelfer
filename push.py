"""Web-Push-Versand (VAPID) — bewusst OHNE Flask-Abhaengigkeit.

Wird sowohl von app.py (Test-Push, Endpunkte) als auch vom Cron-Skript
deploy/send_reminders.py genutzt. Deshalb hier nur reine Funktionen.

Konfiguration ueber Env:
  VAPID_PRIVATE_KEY  Pfad zur PEM-Datei (oder Roh-Key-String)
  VAPID_PUBLIC_KEY   base64url Application-Server-Key (fuer den Browser)
  VAPID_SUB          "mailto:..." Kontakt fuer den Push-Dienst
"""
import os

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_SUB = os.environ.get("VAPID_SUB", "mailto:christiani93@gmail.com")


def push_configured():
    return bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY)


def send_push(subscription, payload_json, ttl=3600):
    """Sendet EINEN Push. Rueckgabe:
        "ok"    -> zugestellt (an den Push-Dienst uebergeben)
        "gone"  -> Subscription tot (404/410) -> Aufrufer soll sie loeschen
        "error" -> temporaerer Fehler (spaeter erneut versuchen)

    `subscription` = dict {"endpoint","p256dh","auth"}.
    `payload_json` = fertiger JSON-String (wird verschluesselt uebertragen).
    """
    from pywebpush import webpush, WebPushException

    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {
                    "p256dh": subscription["p256dh"],
                    "auth": subscription["auth"],
                },
            },
            data=payload_json,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUB},
            ttl=ttl,
        )
        return "ok"
    except WebPushException as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        if code in (404, 410):
            return "gone"
        return "error"
