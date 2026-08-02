# Planungshelfer — Kleiner Helfer Planung

Motivierender ToDo-Planer, der **motiviert** statt nur verwaltet. Läuft lokal
als kleine Flask-App **oder** als installierbare PWA auf dem Server
(<https://todo.z-b.tech>) mit zeitbezogenen Push-Erinnerungen.

## Starten (lokal)

Doppelklick auf **`start.bat`** — legt beim ersten Mal automatisch eine
virtuelle Umgebung an, installiert die Abhängigkeiten und öffnet den Browser auf
<http://127.0.0.1:5005>. Ohne gesetzte Env-Variablen läuft alles offen ohne
Login.

## Die Motivations-Idee

| Mechanik | Wirkung |
|---|---|
| **Heute im Fokus** | Nur wenige Aufgaben sichtbar → keine Überforderung |
| **Nur eine Sache** | Pickt eine kleine Aufgabe zum Sofort-Starten → Aktivierungs-Energie runter |
| **Streak 🔥** | Tage in Folge mit ≥1 erledigten Aufgabe → Gewohnheit (Duolingo-Prinzip) |
| **Level + XP** | Punkte pro Priorität (klein 10 / normal 20 / wichtig 30) |
| **Konfetti + Spruch** | Sofort-Belohnung beim Abhaken → gutes Gefühl |

## 🔔 Erinnerungen (Web-Push)

Zeitbezogene Benachrichtigungen — auch wenn die App geschlossen ist (installierte
PWA auf dem Handy). Der Zeitbezug läuft **serverseitig**: ein Cron-Job
(`deploy/send_reminders.py`) prüft jede Minute fällige Erinnerungen und
verschickt sie per Web-Push (VAPID).

- **Aktivieren:** in der PWA unten in der Karte „🔔 Erinnerungen" auf
  **Aktivieren** tippen und die Browser-Nachfrage erlauben (einmalig pro Gerät).
- **Pro Aufgabe:** 🔔-Button an jeder Aufgabe, oder direkt im Erinnerungs-Formular.
- **Wiederholung:** einmalig oder **wöchentlich**.
- **Bestätigungs-Kette (Ja/Nein):** z. B. Mittwoch 20:30 „Müll vorbereiten?" →
  bei **Ja** legt der Server automatisch die Folge-Erinnerung Donnerstag 06:00
  „Müll mitnehmen" an. Bestätigen geht per **Ja-Button** in der Meldung **oder**
  über das grüne Banner beim Öffnen der App.

> Hinweis: Notification-Buttons sind auf manchen Androids unzuverlässig — deshalb
> gibt es bewusst nur **einen** „Ja"-Button; verneinen per Wegwischen oder im
> App-Banner.

## Daten

- Lokal: `planung.db` (SQLite) im Projektordner. Löschen = kompletter Reset.
- Server: Datenbank außerhalb des Repos unter `~/apps/todo_data/planung.db`
  (überschreibbar via `PLANUNG_DB`), tägliches Backup via Cron.

Tabellen: `tasks`, `reminders`, `push_subs`.

## Machine-to-Machine: Aufgaben einspeisen

Andere Projekte können per `POST /api/ingest` Aufgaben anlegen
(Header `Authorization: Bearer <PLANUNG_API_TOKEN>`; nur `title` ist Pflicht).
Vorgesehene Einspeiser: **AdminPortal** und **Claude-MultiPC** — die
Auftragsverwaltung speist bewusst **keine** ToDos ein. Beispiel:
`examples/add_task.py`.

## Server-Deployment (HostPoint)

Flask via gunicorn + Supervisor, hinter HostPoint-Reverse-Proxy auf Port **8030**.

```bash
git push                                    # lokal master -> GitHub main
ssh -F .claude/ssh_config todo-hostpoint 'cd ~/apps/todo && bash deploy/update.sh'
```

`deploy/update.sh` synchronisiert (`git reset --hard origin/main`), installiert
Requirements und startet den `todo`-Service neu. Konfiguration über `.env`
(Vorlage: `deploy/.env.example`) — u. a. Login-Passwort, API-Token, `PLANUNG_DB`
und die **VAPID-Schlüssel** für Web-Push.

VAPID-Schlüssel einmalig erzeugen:
```bash
.venv/bin/python3 deploy/gen_vapid.py ~/apps/todo_data/vapid_private.pem
# gibt VAPID_PUBLIC_KEY aus -> in .env; VAPID_PRIVATE_KEY = PEM-Pfad
```

Erinnerungs-Cron einmalig installieren: `bash deploy/install-reminders-cron.sh`.

> Nach Service-Worker-Änderungen (`CACHE_NAME`-Bump in `static/sw.js`) muss die
> App auf dem Gerät einmal geöffnet werden, damit die neue Version aktiv wird.

## Struktur

```
Planungshelfer/
├─ app.py                 Flask-Backend + SQLite + JSON-API + Reminder-Endpunkte
├─ push.py                Web-Push-Versand (VAPID), ohne Flask
├─ templates/             index.html, login.html
├─ static/                style.css, app.js, sw.js (Service-Worker), manifest.json, icon.svg
├─ deploy/                update.sh, run.sh, gunicorn.conf.py, supervisor.conf,
│                         send_reminders.py, install-reminders-cron.sh, gen_vapid.py,
│                         backup.sh / restore.sh / install-cron.sh, .env.example
├─ examples/add_task.py   Ingest-Beispiel
├─ requirements.txt       Flask, gunicorn, pywebpush
├─ start.bat
└─ planung.db             (lokal, wird beim ersten Start erzeugt)
```

## Ideen für später

- Erinnerungen editierbar machen + mehr Wiederholungsmuster (täglich, mehrere
  Wochentage, Enddatum/Pause)
- Wochen-Rückblick („diese Woche X Aufgaben, Y XP")
- Wiederkehrende **Aufgaben** (nicht nur Erinnerungen)
- Sub-Aufgaben zum Herunterbrechen großer ToDos
- Optionaler `.exe`-Build via PyInstaller (Projekt-Konvention: .bat + .exe)
