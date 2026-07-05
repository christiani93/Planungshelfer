# Planungshelfer — Kleiner Helfer Planung

Lokaler ToDo-Planer, der **motiviert** statt nur verwaltet.

## Starten

Doppelklick auf **`start.bat`** — legt beim ersten Mal automatisch eine
virtuelle Umgebung an, installiert Flask und oeffnet den Browser auf
<http://127.0.0.1:5005>.

## Die Motivations-Idee

| Mechanik | Wirkung |
|---|---|
| **Heute im Fokus** | Nur wenige Aufgaben sichtbar → keine Ueberforderung |
| **Nur eine Sache** | Pickt eine kleine Aufgabe zum Sofort-Starten → Aktivierungs-Energie runter |
| **Streak 🔥** | Tage in Folge mit ≥1 erledigten Aufgabe → Gewohnheit (Duolingo-Prinzip) |
| **Level + XP** | Punkte pro Prioritaet (klein 10 / normal 20 / wichtig 30) |
| **Konfetti + Spruch** | Sofort-Belohnung beim Abhaken → gutes Gefuehl |

## Daten

Alles liegt lokal in `planung.db` (SQLite). Kein Server, keine Cloud.
Loeschen der Datei = kompletter Reset.

## Struktur

```
Planungshelfer/
├─ app.py              Flask-Backend + SQLite + JSON-API
├─ templates/index.html
├─ static/style.css
├─ static/app.js
├─ requirements.txt
├─ start.bat
└─ planung.db          (wird beim ersten Start erzeugt)
```

## Ideen fuer spaeter

- Wochen-Rueckblick ("diese Woche X Aufgaben, Y XP")
- Wiederkehrende Aufgaben (taeglich/woechentlich)
- Sub-Aufgaben zum Herunterbrechen grosser ToDos
- Optionaler `.exe`-Build via PyInstaller (Projekt-Konvention: .bat + .exe)
