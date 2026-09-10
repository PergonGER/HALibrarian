# Backlog

Ideen und Anforderungen, die bewusst noch nicht umgesetzt wurden — zur
Berücksichtigung bei der nächsten passenden Erweiterung (Jules-Issue
oder direkter Fix). Kein Roadmap-Dokument mit Reihenfolge/Priorität,
nur eine Merkliste, damit nichts verloren geht.

## Erledigt

- ~~Autorenliste: Autoren ohne Bücher ausblenden~~ — umgesetzt
  2026-09-10 (`db.get_authors()`, Favoriten bleiben sichtbar wegen der
  geplanten Autoren-Tracking-Funktion aus Session 4).
- ~~Einstellungen: Bücherliste-Layout (Spaltenanzahl) pro Gerät~~ —
  umgesetzt 2026-09-10 (Einstellungsdialog, `--lt-books-columns`).

## Offen

- **Serien-Verknüpfung bereits erfasster Bücher** (umgesetzt als
  Jules-Issue, siehe dort für Details/Stand — Ursprungs-Recherche zur
  Google-Books-`seriesId`-Einschränkung vom 2026-09-10 bleibt relevant:
  kein API-Endpunkt, um nach allen Büchern einer `seriesId` zu suchen,
  nur Verlinkung bereits selbst erfasster Bücher möglich, keine
  automatische Lückenerkennung fehlender Bände).
