"""Planungshelfer — Kleiner Helfer, der motiviert, ToDos zu erledigen.

Flask-App mit SQLite. Motivation statt reiner Verwaltung:
- "Heute im Fokus": nur wenige Aufgaben sichtbar -> keine Ueberforderung
- Streak: Tage in Folge mit mind. 1 erledigten Aufgabe (Gewohnheit)
- Level/XP + Sofort-Belohnung beim Abhaken
- "Nur eine Sache": pickt eine kleine Aufgabe zum Sofort-Starten

Server-tauglich:
- Login (Session) fuer die Weboberflaeche  -> aktiv, wenn PLANUNG_PASSWORD gesetzt
- API-Token (Bearer) fuer Machine-to-Machine -> aktiv, wenn PLANUNG_API_TOKEN gesetzt
  Damit koennen andere Projekte (vorgesehen: AdminPortal, Claude-MultiPC)
  per POST /api/ingest Aufgaben anlegen. Die Auftragsverwaltung speist
  bewusst KEINE ToDos ein.

Lokal (ohne gesetzte Env-Variablen) laeuft alles offen wie gehabt.
"""
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB-Pfad ueberschreibbar (Server: Datenordner ausserhalb vom Repo)
DB_PATH = os.environ.get("PLANUNG_DB") or os.path.join(BASE_DIR, "planung.db")
SECRET_FILE = os.path.join(BASE_DIR, ".secret")

# --- Konfiguration ueber Env (auf dem Server via Supervisor gesetzt) ----------
PASSWORD = os.environ.get("PLANUNG_PASSWORD")      # None => kein Login (lokal)
API_TOKEN = os.environ.get("PLANUNG_API_TOKEN")    # None => /api/ingest deaktiviert


def _load_secret():
    """Session-Secret: aus Env, sonst persistente Datei (lokal), sonst neu."""
    env = os.environ.get("PLANUNG_SECRET")
    if env:
        return env
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE) as f:
            return f.read().strip()
    val = secrets.token_hex(32)
    try:
        with open(SECRET_FILE, "w") as f:
            f.write(val)
    except OSError:
        pass
    return val


app = Flask(__name__)
app.secret_key = _load_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # hinter HTTPS-Reverse-Proxy (Server): Cookie nur ueber HTTPS senden
    SESSION_COOKIE_SECURE=os.environ.get("HTTPS_ONLY") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

# Punkte pro Prioritaet (1 = klein, 2 = normal, 3 = wichtig)
POINTS = {1: 10, 2: 20, 3: 30}
XP_PER_LEVEL = 100

MOTIVATION = [
    "Stark! Wieder eine Sache weniger im Kopf. 💪",
    "Genau so — Schritt fuer Schritt. 🚀",
    "Erledigt! Dein zukuenftiges Ich dankt dir. 🙌",
    "Boom. Das hast du jetzt hinter dir. ✅",
    "Weiter so, du bist im Flow! 🔥",
    "Klasse — kleine Siege summieren sich. ⭐",
    "Abgehakt! Das fuehlt sich gut an, oder? 😎",
]


# ---------------------------------------------------------------- DB helpers
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            notes      TEXT DEFAULT '',
            priority   INTEGER DEFAULT 2,
            est_min    INTEGER DEFAULT 0,
            due_date   TEXT,
            is_today   INTEGER DEFAULT 0,
            status     TEXT DEFAULT 'open',   -- open | done
            points     INTEGER DEFAULT 0,
            source     TEXT DEFAULT 'manuell',
            created_at TEXT NOT NULL,
            done_at    TEXT
        )
        """
    )
    # Leichte Migration: 'source' nachruesten, falls DB aus alter Version stammt.
    cols = {r[1] for r in db.execute("PRAGMA table_info(tasks)")}
    if "source" not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN source TEXT DEFAULT 'manuell'")

    # Push-Subscriptions (ein Geraet = eine Zeile, per endpoint eindeutig).
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS push_subs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint   TEXT UNIQUE NOT NULL,
            p256dh     TEXT NOT NULL,
            auth       TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    # Zeitbezogene Erinnerungen. remind_at = naive lokale Zeit (Europe/Zurich,
    # Server-TZ). recur: 'none' | 'weekly'. kind: 'info' | 'confirm'.
    # followup = JSON {"message","weekday","hour","minute"} — bei 'confirm'
    # nach Bestaetigung angelegt (z.B. Mi "vorbereiten?" -> Do 06:00 "mitnehmen").
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id    INTEGER,
            message    TEXT NOT NULL,
            remind_at  TEXT NOT NULL,
            recur      TEXT DEFAULT 'none',
            kind       TEXT DEFAULT 'info',
            followup   TEXT,
            active     INTEGER DEFAULT 1,
            last_sent  TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------- auth
def auth_enabled():
    return bool(PASSWORD)


def login_required(fn):
    """Fuer Seiten + Session-API. Bei Env ohne Passwort: kein Schutz (lokal)."""
    @wraps(fn)
    def wrapper(*a, **k):
        if not auth_enabled() or session.get("auth"):
            return fn(*a, **k)
        if request.path.startswith("/api/"):
            return jsonify({"error": "nicht angemeldet"}), 401
        return redirect(url_for("login", next=request.path))
    return wrapper


def token_ok():
    """Prueft Bearer-Token / X-API-Key gegen PLANUNG_API_TOKEN."""
    if not API_TOKEN:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        supplied = auth[7:].strip()
    else:
        supplied = request.headers.get("X-API-Key", "")
    return bool(supplied) and secrets.compare_digest(supplied, API_TOKEN)


# ---------------------------------------------------------------- logic
def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "notes": row["notes"] or "",
        "priority": row["priority"],
        "est_min": row["est_min"],
        "due_date": row["due_date"],
        "is_today": bool(row["is_today"]),
        "status": row["status"],
        "points": row["points"],
        "source": row["source"] if "source" in row.keys() else "manuell",
        "done_at": row["done_at"],
        "overdue": (
            row["status"] == "open"
            and row["due_date"] is not None
            and row["due_date"] < date.today().isoformat()
        ),
    }


def insert_task(db, title, priority=2, est_min=0, due_date=None, is_today=0,
                notes="", source="manuell"):
    priority = min(3, max(1, int(priority or 2)))
    db.execute(
        "INSERT INTO tasks (title, notes, priority, est_min, due_date, is_today, "
        "source, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (title, notes, priority, int(est_min or 0), due_date or None,
         1 if is_today else 0, source or "manuell", datetime.now().isoformat()),
    )
    db.commit()


def compute_streak(db):
    """Tage in Folge (bis heute) mit mind. einer erledigten Aufgabe."""
    rows = db.execute(
        "SELECT DISTINCT substr(done_at,1,10) AS d FROM tasks "
        "WHERE status='done' AND done_at IS NOT NULL ORDER BY d DESC"
    ).fetchall()
    done_days = {r["d"] for r in rows}
    if not done_days:
        return 0
    today = date.today()
    if today.isoformat() not in done_days and (today - timedelta(days=1)).isoformat() not in done_days:
        return 0
    streak = 0
    day = today
    if today.isoformat() not in done_days:
        day = today - timedelta(days=1)
    while day.isoformat() in done_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def build_stats(db):
    total_xp = db.execute(
        "SELECT COALESCE(SUM(points),0) AS xp FROM tasks WHERE status='done'"
    ).fetchone()["xp"]
    level = total_xp // XP_PER_LEVEL + 1
    xp_in_level = total_xp % XP_PER_LEVEL

    today_iso = date.today().isoformat()
    done_today = db.execute(
        "SELECT COUNT(*) AS c FROM tasks WHERE status='done' AND substr(done_at,1,10)=?",
        (today_iso,),
    ).fetchone()["c"]
    today_total = db.execute(
        "SELECT COUNT(*) AS c FROM tasks WHERE is_today=1 AND "
        "(status='open' OR substr(done_at,1,10)=?)",
        (today_iso,),
    ).fetchone()["c"]

    return {
        "total_xp": total_xp,
        "level": level,
        "xp_in_level": xp_in_level,
        "xp_per_level": XP_PER_LEVEL,
        "streak": compute_streak(db),
        "done_today": done_today,
        "today_total": today_total,
    }


# ---------------------------------------------------------------- reminders
def next_weekday_time(weekday, hour, minute=0, after=None):
    """Naechster Zeitpunkt strikt nach `after` (default jetzt), der auf den
    Wochentag `weekday` (Mo=0 .. So=6) und die Uhrzeit faellt."""
    now = after or datetime.now()
    target = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    target += timedelta(days=(int(weekday) - now.weekday()) % 7)
    if target <= now:
        target += timedelta(days=7)
    return target


def reminder_to_dict(row):
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "message": row["message"],
        "remind_at": row["remind_at"],
        "recur": row["recur"],
        "kind": row["kind"],
        "has_followup": bool(row["followup"]),
        "active": bool(row["active"]),
    }


# ---------------------------------------------------------------- auth routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth_enabled():
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if secrets.compare_digest(pw, PASSWORD):
            session["auth"] = True
            session.permanent = True
            nxt = request.args.get("next") or url_for("index")
            return redirect(nxt)
        error = "Falsches Passwort."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- app routes
@app.route("/")
@login_required
def index():
    return render_template("index.html", auth=auth_enabled())


@app.route("/sw.js")
def service_worker():
    """Service-Worker im Root-Scope ausliefern (PWA-Installierbarkeit)."""
    response = send_from_directory(app.static_folder, "sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/api/state")
@login_required
def api_state():
    db = get_db()
    today_iso = date.today().isoformat()
    today_rows = db.execute(
        "SELECT * FROM tasks WHERE is_today=1 AND "
        "(status='open' OR substr(done_at,1,10)=?) "
        "ORDER BY status ASC, priority DESC, id ASC",
        (today_iso,),
    ).fetchall()
    backlog_rows = db.execute(
        "SELECT * FROM tasks WHERE status='open' AND is_today=0 "
        "ORDER BY priority DESC, "
        "CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date ASC, id ASC"
    ).fetchall()
    return jsonify(
        {
            "today": [task_to_dict(r) for r in today_rows],
            "backlog": [task_to_dict(r) for r in backlog_rows],
            "stats": build_stats(db),
        }
    )


@app.route("/api/tasks", methods=["POST"])
@login_required
def api_add():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Titel fehlt"}), 400
    insert_task(
        get_db(),
        title=title,
        priority=data.get("priority"),
        est_min=data.get("est_min"),
        due_date=(data.get("due_date") or "").strip() or None,
        is_today=bool(data.get("is_today")),
        notes=(data.get("notes") or "").strip(),
        source="manuell",
    )
    return jsonify({"ok": True})


@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    """Machine-to-Machine: andere Projekte legen hier Aufgaben an.

    Header:  Authorization: Bearer <PLANUNG_API_TOKEN>   (oder X-API-Key)
    Body:    {"title": "...", "priority": 1-3, "notes": "...",
              "due_date": "YYYY-MM-DD", "is_today": true, "source": "AppName"}
    Nur 'title' ist Pflicht.
    """
    if not token_ok():
        return jsonify({"error": "ungueltiges oder fehlendes Token"}), 401
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Titel fehlt"}), 400
    insert_task(
        get_db(),
        title=title,
        priority=data.get("priority"),
        est_min=data.get("est_min"),
        due_date=(data.get("due_date") or "").strip() or None,
        is_today=bool(data.get("is_today")),
        notes=(data.get("notes") or "").strip(),
        source=(data.get("source") or "extern").strip()[:40],
    )
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:tid>/done", methods=["POST"])
@login_required
def api_done(tid):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if row is None:
        return jsonify({"error": "nicht gefunden"}), 404
    if row["status"] == "done":
        return jsonify({"ok": True, "points": 0})
    pts = POINTS.get(row["priority"], 20)
    db.execute(
        "UPDATE tasks SET status='done', done_at=?, points=? WHERE id=?",
        (datetime.now().isoformat(), pts, tid),
    )
    db.commit()
    idx = (tid + pts) % len(MOTIVATION)
    return jsonify({"ok": True, "points": pts, "message": MOTIVATION[idx]})


@app.route("/api/tasks/<int:tid>/today", methods=["POST"])
@login_required
def api_toggle_today(tid):
    data = request.get_json(silent=True) or {}
    is_today = 1 if data.get("is_today") else 0
    db = get_db()
    db.execute("UPDATE tasks SET is_today=? WHERE id=?", (is_today, tid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:tid>", methods=["DELETE"])
@login_required
def api_delete(tid):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- push / reminders
@app.route("/api/push/config")
@login_required
def api_push_config():
    """Liefert den VAPID-Public-Key (Application-Server-Key) fuer den Browser."""
    from push import VAPID_PUBLIC_KEY, push_configured
    return jsonify({"enabled": push_configured(), "key": VAPID_PUBLIC_KEY or ""})


@app.route("/api/push/subscribe", methods=["POST"])
@login_required
def api_push_subscribe():
    """Speichert eine Browser-Push-Subscription (idempotent per endpoint)."""
    data = request.get_json(force=True, silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()
    if not (endpoint and p256dh and auth):
        return jsonify({"error": "unvollstaendige Subscription"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO push_subs (endpoint, p256dh, auth, created_at) VALUES (?,?,?,?) "
        "ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh, auth=excluded.auth",
        (endpoint, p256dh, auth, datetime.now().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/push/test", methods=["POST"])
@login_required
def api_push_test():
    """Schickt sofort einen Test-Push an alle registrierten Geraete."""
    from push import push_configured, send_push
    if not push_configured():
        return jsonify({"error": "Push nicht konfiguriert (VAPID fehlt)"}), 503
    db = get_db()
    subs = db.execute("SELECT * FROM push_subs").fetchall()
    payload = json.dumps({
        "title": "Planungshelfer",
        "body": "Benachrichtigungen sind aktiv. 🔔",
        "tag": "test",
    })
    sent = 0
    for s in subs:
        result = send_push({"endpoint": s["endpoint"], "p256dh": s["p256dh"],
                            "auth": s["auth"]}, payload)
        if result == "ok":
            sent += 1
        elif result == "gone":
            db.execute("DELETE FROM push_subs WHERE id=?", (s["id"],))
    db.commit()
    return jsonify({"ok": True, "sent": sent, "devices": len(subs)})


@app.route("/api/reminders", methods=["GET"])
@login_required
def api_reminders_list():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM reminders WHERE active=1 ORDER BY remind_at ASC"
    ).fetchall()
    return jsonify({"reminders": [reminder_to_dict(r) for r in rows]})


@app.route("/api/reminders", methods=["POST"])
@login_required
def api_reminders_add():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    remind_at = (data.get("remind_at") or "").strip()  # 'YYYY-MM-DDTHH:MM'
    if not message or not remind_at:
        return jsonify({"error": "Nachricht und Zeitpunkt noetig"}), 400
    recur = data.get("recur") if data.get("recur") in ("none", "weekly") else "none"
    kind = data.get("kind") if data.get("kind") in ("info", "confirm") else "info"
    followup = data.get("followup")
    followup_json = json.dumps(followup) if isinstance(followup, dict) else None
    task_id = data.get("task_id")
    db = get_db()
    db.execute(
        "INSERT INTO reminders (task_id, message, remind_at, recur, kind, "
        "followup, active, created_at) VALUES (?,?,?,?,?,?,1,?)",
        (int(task_id) if task_id else None, message, remind_at, recur, kind,
         followup_json, datetime.now().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/reminders/<int:rid>", methods=["DELETE"])
@login_required
def api_reminders_delete(rid):
    db = get_db()
    db.execute("DELETE FROM reminders WHERE id=?", (rid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/reminders/<int:rid>/confirm", methods=["POST"])
@login_required
def api_reminder_confirm(rid):
    """Wird vom Service-Worker aufgerufen, wenn der 'Ja'-Button einer
    Bestaetigungs-Erinnerung getippt wird -> legt die Folge-Erinnerung an."""
    db = get_db()
    row = db.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()
    if row is None:
        return jsonify({"error": "nicht gefunden"}), 404
    if not row["followup"]:
        return jsonify({"ok": True, "created": False})
    spec = json.loads(row["followup"])
    at = next_weekday_time(spec["weekday"], spec["hour"], spec.get("minute", 0))
    db.execute(
        "INSERT INTO reminders (task_id, message, remind_at, recur, kind, "
        "active, created_at) VALUES (?,?,?,?,?,1,?)",
        (row["task_id"], spec["message"], at.isoformat(timespec="minutes"),
         "none", "info", datetime.now().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True, "created": True, "at": at.isoformat(timespec="minutes")})


@app.route("/api/one-thing")
@login_required
def api_one_thing():
    """Pickt EINE kleine offene Aufgabe zum Sofort-Starten (niedrigste est_min)."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM tasks WHERE status='open' "
        "ORDER BY CASE WHEN est_min=0 THEN 999 ELSE est_min END ASC, "
        "priority DESC, id ASC LIMIT 1"
    ).fetchone()
    return jsonify({"task": task_to_dict(row) if row else None})


# Schema beim Import sicherstellen (idempotent) — greift auch unter gunicorn.
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5005"))
    print(f"Planungshelfer laeuft:  http://127.0.0.1:{port}")
    print("Login:", "AN" if auth_enabled() else "aus (lokal)",
          "| API-Ingest:", "AN" if API_TOKEN else "aus")
    app.run(host="127.0.0.1", port=port, debug=False)
