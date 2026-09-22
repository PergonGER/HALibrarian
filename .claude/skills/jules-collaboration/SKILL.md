---
name: jules-collaboration
description: How this repo (PergonGER/HALibrarian, "HA Library Tracker") works with the autonomous coding agent Jules (Google Labs, google-labs-jules[bot]) via GitHub issues, and how Claude's own role as project lead/reviewer is scoped against it. Use this whenever you're about to write or label a GitHub issue in this repo, decide whether a change should go to Jules or be fixed directly, review or respond to a PR opened by google-labs-jules[bot], or a Jules PR isn't responding correctly to review feedback. Also consult it before any GitHub-issue-driven feature work on this repo, even if Jules isn't mentioned by name in the request.
---

# Zusammenarbeit mit Jules (HA Library Tracker)

Dieses Projekt arbeitet mit dem autonomen Coding-Agenten **Jules** (Google
Labs, `google-labs-jules[bot]`) zusammen. Dieser Skill fasst die
etablierten Betriebsregeln zusammen, damit eine neue Session sofort
mitarbeiten kann, ohne die Vorgeschichte neu herzuleiten.

**Ausführliches Vorfall-/Entscheidungslog:** `docs/jules-collaboration-playbook.md`
— bei jedem konkreten Zwischenfall (Jules reagiert nicht wie erwartet,
Unsicherheit über die genaue Chronologie) dort nachlesen, dieser Skill
dupliziert die Historie nicht. Feature-Entscheidungen/Status:
`docs/backlog.md`.

## Rollenverteilung

- **Jules**: bekommt Aufgaben ausschließlich über GitHub-Issues mit dem
  Label `Jules`. Kein Zugriff auf diesen Chat oder sonstigen externen
  Kontext — alles Nötige muss im Issue-Text stehen. Liest den Repo-Stand
  nur **einmal, zu Sessionbeginn**; spätere Pushes (auch eigene direkte
  Fixes von Claude) sieht Jules danach nicht mehr automatisch mit.
- **Claude (diese Session)**: Projektleitung/Reviewer.
  - `docs/` vor jedem neuen Jules-Issue aktuell halten — das ist die
    Quelle der Wahrheit, aus der Jules arbeitet.
  - Issues präzise formulieren: keine impliziten Annahmen; unverifizierte
    Annahmen (z. B. ungetestete API-Antwortformate) explizit als
    unverifiziert kennzeichnen statt zu raten.
  - Vor dem Label-Setzen prüfen, ob bereits eine offene Jules-PR existiert
    — siehe „Keine parallelen Jules-Sessions" unten.
  - Jules-PRs reviewen (Diff lesen, verfügbare Checks laufen lassen,
    CI-Status prüfen) und mergen.
  - **Kleinere Sachen direkt selbst erledigen**, ohne über Jules zu gehen:
    Merge-Konflikte, Lint, CI/Workflow-Config, Ein-Datei-Bugfixes, Doku.
  - **Echte Features / mehrschichtige Architektur-Änderungen** gehen an
    Jules per Issue.
- **Nutzer (Mads/PergonGER)**: Repo-Owner, gibt Feature-Wünsche vor,
  entscheidet bei Ambiguität.

Die Abgrenzung "selbst fixen vs. Jules-Issue" ist meist eindeutig aus der
Größe der Änderung ablesbar; im Zweifel lieber kurz beim Nutzer
nachfragen als in eine der beiden Richtungen zu raten.

## Keine parallelen Jules-Sessions

Vor jedem neuen `Jules`-Label-Setzen prüfen: Gibt es noch eine offene,
ungemergte Jules-PR? Falls ja → warten, bis sie gemerged oder geschlossen
ist. Es soll grundsätzlich **keine zwei gleichzeitig laufenden
Jules-Sessions** auf diesem Repo geben (Überschneidungsgefahr bei
Datei-Scope). Lieber ein neues Issue später labeln als parallel
arbeiten lassen.

## Wie Jules ausgelöst wird

Nur das GitHub-**Label `Jules`** zuverlässig von Jules fernhalten reicht
nicht ganz — auch ein Issue **ohne** Label, das aber `@jules` im Text
enthält, wurde in der Vergangenheit (in einem Schwesterprojekt)
trotzdem aufgegriffen. Konsequenz für dieses Repo: Ein Issue, das noch
nicht starten soll, bekommt **weder** das Label **noch** einen
vollständigen `@jules`-Aufgabentext. Voller Text + Label werden erst
gemeinsam gesetzt, wenn wirklich losgelegt werden soll — kein Entwurf
mit Label liegen lassen.

## Bekanntes Fehlverhalten: No-Op-/Revert-Commits

Mehrfach in diesem Repo beobachtet (PR #3, #6, #15, #21): Nach einem
`REQUEST_CHANGES`-Review pusht Jules einen neuen Commit, der entweder
- einen **identischen Git-Tree-Hash** wie der vorherige Commit hat (keine
  inhaltliche Änderung trotz neuer SHA), oder
- eigene Zwischen-Fixes von Claude auf derselben Branch unbemerkt
  zurücksetzt, ohne die eigentlich angeforderte Änderung umzusetzen.

**Erkennen:** Tree-Hash vor/nach Jules' Antwort-Commit vergleichen:
```
git show -s --format=%T <sha-vorher>
git show -s --format=%T <sha-nachher>
```
Gleicher Hash → Leer-Commit. Unterschiedlicher Hash ist aber **kein**
Beleg dafür, dass die richtige Änderung drin ist — zusätzlich den Diff
gegen die konkret angeforderten Punkte prüfen, nicht nur "es gab einen
neuen Commit".

**Zusätzlich:** Ein formales GitHub-Review (`REQUEST_CHANGES`) allein
löst bei Jules oft **gar keine** Reaktion aus. Nach jedem Review
zusätzlich einen normalen PR-Kommentar mit explizitem `@jules` posten,
der die geforderten Änderungen kurz zusammenfasst — nicht auf das
Review-Objekt allein verlassen.

## Eskalation: gehärteter Branch

Wenn Jules nach 1–2 weiteren Anstößen die Änderung immer noch nicht
korrekt umsetzt: **nicht** in eine Fix-Revert-Schleife auf derselben
Branch geraten. Stattdessen:

1. Vom letzten validierten/guten Commit einen neuen Branch abzweigen,
   benannt nach dem Muster `<feature>-hardened`.
2. Den Fix dort selbst umsetzen.
3. Einen neuen PR gegen `main` öffnen, der den ursprünglichen
   Jules-PR/-Issue referenziert.
4. Den ursprünglichen Jules-PR kommentieren (Hinweis, dass nichts mehr
   gepusht werden muss) und schließen, das Issue schließen.
5. Den Nutzer über den Vorfall informieren.

## Versionierung

`custom_components/library_tracker/manifest.json` → `version`:
- **PATCH** (z. B. 0.10.1 → 0.10.2): kleine/selbst gefixte Änderungen.
- **MINOR** (z. B. 0.10.x → 0.11.0): echte, von Jules gelieferte Features.
- Reine Doku-Änderungen (README, `docs/`) bekommen **keinen** Versions-Bump.

## Selbstfix bei "hängendem" Jules-PR — Autorisierung einzeln einholen

Es gab bereits Fälle, in denen der Nutzer explizit **einmalig** erlaubt
hat, einen Jules-PR selbst zu fixen, wenn er zu lange ohne echten
Fortschritt hängt (Größenordnung: ~2 Stunden). Das ist **kein**
Standing-Freibrief für künftige Sessions — jede Session fragt den
Nutzer **erneut** und **explizit**, bevor sie aus reiner Zeitüberschreitung
(ohne das oben beschriebene No-Op-/Revert-Muster) selbst eingreift. Das
dokumentierte No-Op-/Revert-Verhalten (siehe oben) ist davon unabhängig
und rechtfertigt die Eskalation für sich genommen, ohne gesonderte
Nachfrage — dort ist das erwartete, etablierte Vorgehen.
