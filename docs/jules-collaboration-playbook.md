# Playbook: Zusammenarbeit mit Jules (Google Labs) via GitHub

Stand: 2026-09-09. Dieses Dokument fasst zusammen, wie das Projekt "HA Library Tracker" mit dem autonomen Coding-Agenten **Jules** (Google Labs) über GitHub organisiert wird, welche Rollen Claude (ich) und Jules dabei haben, und welche Regeln gelten, um Überschneidungen und Datenverlust zu vermeiden.

Übernommen und angepasst aus dem entsprechenden Playbook im "Build Guide Merc"-Repo (Stand 2026-09-08), wo mehrere der unten genannten Regeln aus real aufgetretenen Vorfällen entstanden sind (siehe Abschnitt 5). Zweck: Dieses Dokument als Kontext in eine andere Chat-Session mitnehmen, damit dort nicht bei null angefangen werden muss.

---

## 1. Rollenverteilung

- **Jules** (`google-labs-jules[bot]`, GitHub App): autonomer Coding-Agent. Bekommt Aufgaben ausschließlich über GitHub-Issues zugewiesen, schreibt Code, öffnet PRs. Hat **keinen** Zugriff auf externen Chat-Kontext — alles, was Jules wissen muss, muss im Issue-Text stehen. Jules nimmt den Repo-Stand nur **einmal, zu Sessionbeginn** auf; spätere Änderungen (auch von Claude direkt gepusht) sieht Jules **nicht mehr**.
- **Claude (ich)**: Projektleitung/Reviewer. Verantwortlich für:
  - `docs/` im Repo als verbindliche Quelle der Wahrheit pflegen (Projekt-Blueprint, Entscheidungen, dieses Playbook) — **bevor** ein Jules-Issue geschrieben wird.
  - Jules-Issues so präzise formulieren, dass keine impliziten Annahmen nötig sind ("nicht raten, sondern unverifiziert markieren").
  - Vor jedem neuen Jules-Issue prüfen, ob eine offene Jules-PR dieselben Dateien anfasst oder der Repo-Stand sich gerade ändert — im Zweifel warten und das Label später setzen (explizite Vorgabe des Nutzers für dieses Projekt).
  - PRs von Jules reviewen: Diff lesen, `py_compile`/verfügbare Checks laufen lassen, CI-Status prüfen, mergen.
  - **Kleinere Korrekturen** (Merge-Konflikte, Lint, CI/Workflow-Config, Ein-Datei-Bugfixes, Doku) direkt selbst erledigen, **ohne** über Jules zu gehen — laut Nutzer explizit erlaubt ("kleinere Probleme löst du direkt selbst").
  - Neue Features/mehrschichtige Architektur-Änderungen bleiben bei Jules.
- **Nutzer (Mads/PergonGER)**: Repo-Owner, gibt Feature-Wünsche vor (siehe Projekt-Blueprint), trifft Entscheidungen bei Ambiguität.

---

## 2. Wie Jules getriggert wird

- Jules reagiert primär auf das GitHub-**Label `Jules`** auf einem Issue.
- **Wichtige Erfahrung aus dem Schwesterprojekt:** Ein Issue **ohne** `Jules`-Label, das aber `@jules` im Text enthält, wurde dort trotzdem von Jules aufgegriffen und bearbeitet. Weder Label-Vergabe noch `@jules`-Mention allein zurückzuhalten reicht also zuverlässig, um Jules von einem Issue fernzuhalten.
- **Konsequenz für dieses Projekt:** Ein Issue, das noch nicht bearbeitet werden soll, bekommt **weder** das Label **noch** einen vollständigen, mit `@jules` versehenen Aufgabentext. Erst wenn wirklich gestartet werden soll, wird der volle Text geschrieben und das Label gesetzt (nicht vorher als Entwurf mit Label liegen lassen).

---

## 3. Datei-Scope-Disziplin

**Regel:** Parallele Jules-Tasks dürfen sich nicht in denselben Dateien überschneiden — eigentlich soll es **keine** parallelen Jules-Sessions auf diesem Repo geben (explizite Vorgabe: "eigentlich keine Überschneidung"). Lieber warten und das nächste Issue später labeln, als zwei Jules-Sessions gleichzeitig laufen zu lassen.

**Vorgehen vor jedem neuen Jules-Issue:**
1. Prüfen: Gibt es eine offene, noch nicht gemergte Jules-PR? Falls ja → warten, bis sie gemerged (oder geschlossen) ist, bevor das nächste Issue gelabelt wird.
2. Prüfen: Ist `main` in einem klaren, vollständigen Zustand (keine offenen Feature-Branches mit unklarem Status)? Nur dann labeln.
3. Datei-Scope im Issue-Text explizit benennen (betroffene Dateien + ggf. "nicht anfassen"-Hinweise), auch wenn nur eine Session aktiv ist — erleichtert Review und macht Annahmen sichtbar.

---

## 4. Bekanntes Jules-Fehlverhalten (aus dem Schwesterprojekt, hier vorsorglich dokumentiert)

- **"Leere"/rückgängig machende Commits:** Nach Review-Feedback reagiert Jules sichtbar, pusht aber teils einen Commit ohne echte inhaltliche Änderung.
  - Eskalation: 1) präzises Review-Kommentar mit konkretem Diff-Beweis, 2) falls nach 1–2 weiteren Commits keine echte Änderung erfolgt → Nutzer informieren und den Fix selbst umsetzen.
- **Überschreiben eigener Zwischen-Fixes:** In einem anderen Projekt hat Jules einen bereits von Claude auf derselben Branch gepushten Merge-Konflikt-Fix kurz danach unbemerkt wieder revertiert (Details siehe Abschnitt 5 des Original-Playbooks im Merc-Repo). Für dieses Projekt gilt daher vorsorglich:
  1. Nach jedem eigenen Push auf eine **aktive** Jules-PR-Branch: vor dem Merge den tatsächlichen Head-SHA und Diff erneut gegenprüfen (`pull_request_read`/`get_diff` unmittelbar vor dem Merge-Klick), nicht auf den zuletzt bekannten Stand verlassen.
  2. Nach dem Mergen stichprobenartig verifizieren, dass zuvor bereits gemergte, in der PR nicht erwähnte Dateien nicht plötzlich fehlen.
  3. Bei einem Merge-Konflikt auf einer noch **aktiven** Jules-Branch: eigenen Fix nach Möglichkeit als separaten PR gegen `main` vorschlagen statt direkt auf die laufende Jules-Branch zu pushen, um genau diese Race Condition zu vermeiden.

---

## 5. Weitere etablierte Regeln

- **"Unverifiziert markieren statt raten"**: Jede technische Annahme, die nicht direkt am echten Datenformat/an der echten API verifiziert wurde (z. B. Google-Books-/Open-Library-Response-Format), muss explizit als unverifiziert gekennzeichnet werden — sowohl in Code-Kommentaren als auch im PR-Text. Erfundene Formeln/Skalierungen ohne Beleg werden im Review zurückgewiesen.
- **Breite `except Exception`-Blöcke** brauchen einen Begründungskommentar (z. B. warum ein Netzwerkfehler bei der Buch-API nicht die ganze Integration crashen darf).
- **CI mit Bot-Actor prüfen:** Falls ein automatisches Review-Gate (z. B. `claude-code-action`) eingerichtet wird, sicherstellen, dass es auch für PRs von `google-labs-jules[bot]` läuft (ggf. `allowed_bots`-Konfiguration) — sonst schlägt das Gate für jeden Jules-PR unbemerkt fehl.
- **Reviewablauf pro Jules-PR:** Diff vollständig lesen → lokale Checks laufen lassen (`py_compile`, ggf. `pytest`/Home-Assistant-Testframework, sobald eingerichtet) → CI-Status prüfen → offene Review-Threads prüfen → erst dann mergen. Kleinere Findings selbst nachbessern statt an Jules zurückzugeben.

---

## 6. Aktueller Stand zum Zeitpunkt dieses Dokuments (2026-09-09)

| PR/Issue | Feature | Zustand |
|---|---|---|
| PR #1 | Session 1: Grundgerüst & Custom Panel | Gemergt (von Claude direkt implementiert, nicht Jules) |
| Issue #2 | Session 2: Backend-Logik, SQLite-DB & WebSocket-API | Mit Label `Jules` versehen, wartet auf PR |

Es läuft aktuell genau ein Jules-Issue — kein Überschneidungsrisiko. Bevor ein Issue für Session 3 gelabelt wird: warten, bis Issue #2 als PR gemergt ist.

---

## 7. Empfehlung für die Fortsetzung in einer neuen Chat-Session

Wer dieses Projekt weiterführt, sollte:
1. Den Projekt-Blueprint (Session-Roadmap) und dieses Dokument zuerst lesen.
2. Vor jeder neuen Jules-Aufgabe prüfen, ob noch ein offenes Jules-Issue/eine offene Jules-PR existiert — falls ja, warten statt parallel zu labeln.
3. Nach jedem eigenen Push auf eine **aktive** Jules-Branch den Head-SHA unmittelbar vor dem Merge erneut verifizieren.
4. Bei Merge-Konflikten auf einer aktiven Jules-Branch erwägen, den eigenen Fix als separaten PR gegen `main` zu stellen statt direkt auf die Jules-Branch zu pushen.
