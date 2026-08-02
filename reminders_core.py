"""Wiederholungs-Logik fuer Erinnerungen — reine Funktionen, ohne Flask.

Von app.py (Anlegen/Bearbeiten) UND deploy/send_reminders.py (Vorruecken)
genutzt. Zeiten sind naive lokale datetimes (Server-TZ = Europe/Zurich).

recur:
  'none'    einmalig
  'daily'   jeden Tag zur Uhrzeit
  'weekly'  an den ausgewaehlten Wochentagen (weekdays) zur Uhrzeit
weekdays: Liste von Wochentagen 0=Mo .. 6=So (nur bei 'weekly').
"""
from datetime import timedelta

WEEKDAY_LABELS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def parse_weekdays(value):
    """'0,2,4' / [0,2,4] -> sortierte, eindeutige Liste [0,2,4] (0..6)."""
    if not value:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = list(value)
    out = set()
    for p in parts:
        s = str(p).strip()
        if s.isdigit() and 0 <= int(s) <= 6:
            out.add(int(s))
    return sorted(out)


def weekdays_to_str(weekdays):
    return ",".join(str(w) for w in parse_weekdays(weekdays))


def next_fire(recur, weekdays, hour, minute, after):
    """Naechster Fire-Zeitpunkt STRIKT nach `after` (datetime).

    Fuer 'none' gibt es keine Wiederholung -> None (Aufrufer nutzt die
    urspruengliche Zeit direkt bzw. deaktiviert danach).
    """
    hour, minute = int(hour), int(minute)
    base = after.replace(second=0, microsecond=0)

    if recur == "daily":
        cand = base.replace(hour=hour, minute=minute)
        while cand <= after:
            cand += timedelta(days=1)
        return cand

    if recur == "weekly":
        wds = parse_weekdays(weekdays) or [after.weekday()]
        for add in range(0, 8):
            cand = (base + timedelta(days=add)).replace(hour=hour, minute=minute)
            if cand > after and cand.weekday() in wds:
                return cand
        # Sollte nie erreicht werden; sicherer Fallback.
        return base.replace(hour=hour, minute=minute) + timedelta(days=7)

    return None


def describe(recur, weekdays):
    """Kurzbeschreibung fuer die UI/Serverseite (z.B. 'woechentlich Mo, Mi')."""
    if recur == "daily":
        return "taeglich"
    if recur == "weekly":
        wds = parse_weekdays(weekdays)
        if not wds:
            return "woechentlich"
        return "woechentlich " + ", ".join(WEEKDAY_LABELS[w] for w in wds)
    return "einmalig"
